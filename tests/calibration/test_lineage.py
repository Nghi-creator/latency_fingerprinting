"""Independent transitive grouping and split-leakage expectations."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from pydantic import ValidationError

from latency_fingerprinting.calibration import CalibrationDataset, validate_calibration_lineage

from .cases import HASH, dataset, group_id, seal_dataset
from .lineage_cases import add_review, payload, source


def components(result):
    return {frozenset(group.source_ids) for group in result.groups}


def test_disjoint_pairs_and_healthy_windows_have_declared_roles_and_pinned_group_id(monkeypatch):
    p = payload(
        [["source-a", "source-b"], ["source-c", "source-d"], ["source-e"]],
        [["source-a", "source-b"], ["source-c", "source-d"], ["source-e"]],
        roles=["training", "final_test", "validation"],
    )

    def forbid(*args, **kwargs):
        raise AssertionError("lineage validation must not open files")

    monkeypatch.setattr(Path, "open", forbid)
    result = validate_calibration_lineage(p)
    assert components(result) == {
        frozenset(["source-a", "source-b"]),
        frozenset(["source-c", "source-d"]),
        frozenset(["source-e"]),
    }
    assert (
        result.entries[0].group_id
        == "group-c20aec20097c7f36fc39d247bac3ce3bd0d5a644cac9669eb3fa9389b9da977e"
    )
    assert [e.role for e in result.entries] == ["training", "final_test", "validation"]
    assert result.split_review_state == "missing"
    assert all(g.independence_review_state == "missing" for g in result.groups)
    assert result.assurance == "external_review_declarations_not_authenticated"


@pytest.mark.parametrize("reason", ["run", "content", "session", "operator_group", "edge", "pair"])
def test_each_join_rule_rejects_leakage_and_accepts_one_complete_component(reason):
    bindings = [["source-a"], ["source-b"]]
    p = payload(bindings, [["source-a"], ["source-b"]], roles=["training", "final_test"])
    a, b = p["sources"]
    if reason == "run":
        b["run_id"] = a["run_id"]  # Distinct source hashes still join.
    elif reason == "content":
        b["source_content_hash"] = a["source_content_hash"]
        b["acquisition_namespace"] = "another-system"
    elif reason == "session":
        b["session_id"] = a["session_id"]
    elif reason == "operator_group":
        b["independence_group"] = a["independence_group"]
    elif reason == "edge":
        p["derivations"] = [dict(parent_source_id="source-a", child_source_id="source-b")]
    else:
        p = payload(
            [["source-a", "source-b"]],
            [["source-a"], ["source-b"]],
            roles=["training", "final_test"],
        )
    with pytest.raises(ValueError, match="^invalid_calibration_lineage$"):
        validate_calibration_lineage(seal_dataset(p))
    p["split"]["assignments"] = [dict(group_id=group_id(["source-a", "source-b"]), role="training")]
    assert components(validate_calibration_lineage(seal_dataset(p))) == {
        frozenset(["source-a", "source-b"])
    }


def test_transitive_pair_derivation_and_session_join_include_ancestor():
    names = ["source-a", "source-b", "source-c", "source-d", "source-e", "source-parent"]
    sources = [source(name) for name in names]
    sources[4]["session_id"] = sources[3]["session_id"]
    p = payload(
        [["source-a", "source-b"], ["source-c", "source-d"], ["source-e"]],
        [names],
        sources=sources,
        edges=[("source-b", "source-c"), ("source-parent", "source-a")],
    )
    result = validate_calibration_lineage(p)
    assert components(result) == {frozenset(names)}
    assert len({e.group_id for e in result.entries}) == 1
    assert all(e.representative_entry_id == e.entry_id for e in result.entries)


@pytest.mark.parametrize("field", ["session_id", "independence_group", "run_id"])
def test_local_identifiers_are_namespaced_not_global_acquisition_proof(field):
    p = payload([["source-a"], ["source-b"]], [["source-a"], ["source-b"]])
    p["sources"][1][field] = p["sources"][0][field]
    p["sources"][1]["acquisition_namespace"] = "another-system"
    result = validate_calibration_lineage(seal_dataset(p))
    assert len(result.groups) == 2
    assert all(g.independence_review_state == "missing" for g in result.groups)


def test_distinct_source_types_do_not_join_only_because_digest_matches():
    p = payload([["source-a"], ["source-b"]], [["source-a"], ["source-b"]])
    p["sources"][1].update(
        source_type="pixelated_bundle",
        bundle_schema_version="2",
        source_content_hash=p["sources"][0]["source_content_hash"],
    )
    assert len(validate_calibration_lineage(seal_dataset(p)).groups) == 2


@pytest.mark.parametrize("change", ["missing", "extra", "duplicate", "stale", "frame_split"])
def test_frozen_split_inventory_cannot_be_changed_or_divide_sources(change):
    p = payload([["source-a", "source-b"]], [["source-a", "source-b"]])
    if change == "missing":
        p["split"]["assignments"] = []
    elif change == "extra":
        p["split"]["assignments"].append(dict(group_id=group_id(["absent"]), role="engineering"))
    elif change == "duplicate":
        p["split"]["assignments"] *= 2
    elif change == "stale":
        p["split"]["assignments"] = [dict(group_id=group_id(["source-a"]), role="final_test")]
    else:
        p["split"]["assignments"] = [
            dict(group_id=group_id(["source-a"]), role="training"),
            dict(group_id=group_id(["source-b"]), role="final_test"),
        ]
    p["split"]["assignments"].sort(key=lambda a: a["group_id"])
    with pytest.raises(ValueError, match="^invalid_calibration_lineage$"):
        validate_calibration_lineage(seal_dataset(p))


def test_multiple_windows_same_source_are_one_group_without_false_duplicate_claim():
    p = payload([["source-a"], ["source-a"]], [["source-a"]])
    result = validate_calibration_lineage(p)
    assert len(result.groups) == 1 and len(result.entries) == 2
    assert [e.representative_entry_id for e in result.entries] == ["entry-000", "entry-001"]


@pytest.mark.parametrize("state", ["confirmed", "rejected", "uncertain"])
def test_complete_exact_group_review_retains_its_external_state(state):
    p = payload([["source-a", "source-b"]], [["source-a", "source-b"]])
    add_review(p, "review-a", ["source-a", "source-b"], state)
    result = validate_calibration_lineage(p)
    assert result.groups[0].independence_review_state == state
    assert result.assurance == "external_review_declarations_not_authenticated"


@pytest.mark.parametrize(
    "outcomes,expected",
    [
        (("confirmed",), "missing"),
        (("confirmed", "confirmed"), "missing"),
        (("confirmed", "uncertain"), "uncertain"),
        (("uncertain", "rejected"), "rejected"),
    ],
)
def test_partial_or_fragmented_reviews_cannot_upgrade_a_whole_group(outcomes, expected):
    p = payload([["source-a", "source-b"]], [["source-a", "source-b"]])
    for name, src, outcome in zip(
        ["review-a", "review-b"], ["source-a", "source-b"], outcomes, strict=False
    ):
        add_review(p, name, [src], outcome)
    assert (
        validate_calibration_lineage(seal_dataset(p)).groups[0].independence_review_state
        == expected
    )


def test_shared_review_covering_distinct_groups_is_not_exact_group_confirmation():
    p = payload([["source-a"], ["source-b"]], [["source-a"], ["source-b"]])
    add_review(p, "review-a", ["source-a", "source-b"])
    assert all(
        g.independence_review_state == "missing" for g in validate_calibration_lineage(p).groups
    )


def test_stale_freeze_review_cannot_follow_changed_assignments():
    p = dataset()
    p["split"]["mode"] = "prospective"
    seal_dataset(p)
    p["reviews"] = [
        dict(
            review_id="review-a",
            reviewer_id="reviewer",
            kind="split_freeze",
            subject_ids=[p["split"]["split_id"]],
            outcome="confirmed",
            evidence_sha256=HASH,
        )
    ]
    p["split"]["freeze_review_id"] = "review-a"
    seal_dataset(p)
    assert validate_calibration_lineage(p).split_review_state == "confirmed"
    p["split"]["assignments"][0]["role"] = "final_test"
    with pytest.raises(ValueError, match="^invalid_calibration_lineage$"):
        validate_calibration_lineage(seal_dataset(p))


def test_missing_entries_have_no_invented_group_or_split_assignment():
    result = validate_calibration_lineage(dataset(missing=True))
    assert result.groups == ()
    assert result.entries[0].group_id is None and result.entries[0].role is None
    assert result.entries[0].representative_entry_id == "entry-a"


def test_result_is_immutable_detached_and_deterministic_for_mapping_order():
    p = dataset()
    model = CalibrationDataset.model_validate(p)
    result = validate_calibration_lineage(model)
    assert result == validate_calibration_lineage(dict(reversed(list(p.items()))))
    p["sources"][0]["session_id"] = "changed"
    assert result == validate_calibration_lineage(model)
    with pytest.raises(FrozenInstanceError):
        result.entries = ()
    with pytest.raises(FrozenInstanceError):
        result.entries[0].role = "final_test"
    with pytest.raises(ValidationError):
        result.groups[0].role = "final_test"


def test_forged_reused_instances_are_revalidated_and_failure_does_not_echo_input(capsys):
    model = CalibrationDataset.model_validate(dataset())
    forged = model.model_copy(
        update={"sources": (model.sources[0].model_copy(update={"source_id": "/private/secret"}),)}
    )
    with pytest.raises(ValueError, match="^invalid_calibration_lineage$") as failure:
        validate_calibration_lineage(forged)
    assert failure.value.__suppress_context__
    assert capsys.readouterr().out == ""


def test_deep_bounded_graph_uses_iterative_components_and_keeps_one_repetition():
    names = [f"source-{i:03d}" for i in range(256)]
    edges = [(names[i], names[i + 1]) for i in range(255)]
    edges += [(names[i], names[i + 2]) for i in range(254)]
    edges += [(names[i], names[i + 3]) for i in range(3)]
    result = validate_calibration_lineage(payload([[name] for name in names], [names], edges=edges))
    assert len(result.groups) == 1 and len(result.groups[0].source_ids) == 256
    assert len(result.entries) == 256
