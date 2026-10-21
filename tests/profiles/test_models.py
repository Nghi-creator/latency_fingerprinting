"""Independent positive snapshots and rehashed structural/statistical contradictions."""

import copy

import pytest
from pydantic import ValidationError

from latency_fingerprinting.profiles import ProfilePolicy, ProfileSnapshot
from latency_fingerprinting.profiles.policy_release import approved_policy_payload

from .cases import NAMES, candidate_id, canonical, draft, policy, reviewed, seal, supported


def test_policy_matches_frozen_spec_and_detaches_inputs():
    p = policy()
    model = ProfilePolicy.model_validate(p)
    assert model.model_dump(mode="json") == approved_policy_payload() == p
    p["feature_names"].clear()
    assert len(model.feature_names) == 22
    with pytest.raises(ValidationError):
        model.gates.minimum_training_groups = 1
    with pytest.raises(ValidationError):
        ProfilePolicy.model_validate(
            model.model_copy(
                update={
                    "selection": model.selection.model_copy(update={"require_n6_eligible": False})
                }
            )
        )


@pytest.mark.parametrize("factory", [draft, supported])
def test_snapshot_independently_reconstructs_and_is_deeply_immutable(factory):
    p = factory()
    model = ProfileSnapshot.model_validate(p)
    assert model.model_dump(mode="json") == p
    assert ProfileSnapshot.model_validate_json(canonical(p)) == model
    assert ProfileSnapshot.model_validate(model) == model
    p["inputs"].clear()
    if model.inputs:
        assert len(model.inputs) == 7
        with pytest.raises(TypeError):
            model.inputs[0].feature_values[NAMES[0]] = 99
        with pytest.raises(TypeError):
            model.profiles[0].features[NAMES[0]] = None
        with pytest.raises(ValidationError):
            model.profiles[0].features[NAMES[0]].group_values[0].median = 99


@pytest.mark.parametrize(
    "change",
    [
        "count",
        "center",
        "dispersion",
        "group_median",
        "feature_count",
        "coverage",
        "weight",
        "missing_feature",
        "candidate_id",
        "selected_group",
        "group_entries",
        "values",
        "selected",
        "heldout_values",
        "reason_order",
        "source_id",
        "snapshot_id",
        "hash",
        "source_count",
    ],
)
def test_rehashed_wrong_statistics_and_ownership_rejected(change):
    p = supported()
    profile = p["profiles"][0]
    feature = profile["features"][NAMES[0]]
    if change == "count":
        p["counts"]["selected_groups"] = 4
    elif change == "center":
        feature["center"] = 3.0
    elif change == "dispersion":
        feature["dispersion"] = 2.0
    elif change == "group_median":
        feature["group_values"][0]["median"] += 0.5
    elif change == "feature_count":
        profile["active_feature_count"] = 21
    elif change == "coverage":
        profile["active_feature_coverage"]["value"] = 0.5
    elif change == "weight":
        feature["weight"] = 0.0
    elif change == "missing_feature":
        del profile["features"][NAMES[0]]
    elif change == "candidate_id":
        profile["profile_id"] = "profile-" + "0" * 64
    elif change == "selected_group":
        profile["training_group_ids"].pop()
    elif change == "group_entries":
        feature["group_values"][0]["entry_ids"] = ["unknown"]
    elif change == "values":
        p["inputs"][0]["feature_values"][NAMES[0]] = 1.5
    elif change == "selected":
        p["inputs"][0]["selected"] = False
    elif change == "heldout_values":
        p["inputs"][-1]["feature_values"] = dict(p["inputs"][0]["feature_values"])
    elif change == "reason_order":
        p["inputs"][-1]["reason_codes"] = ["not_training", "not_training"]
    elif change == "source_id":
        p["inputs"][0]["entry_id"] = "another"
    elif change == "source_count":
        p["inputs"][0]["feature_values"][NAMES[0]] = None
    elif change == "snapshot_id":
        p["snapshot_id"] = "profile-snapshot-" + "0" * 64
    else:
        p["content_hash"] = "sha256:" + "0" * 64
    if change not in ("snapshot_id", "hash"):
        if change != "candidate_id":
            candidate_id(profile, p["policy"], p["source_report"])
        seal(p)
    with pytest.raises(ValueError):
        ProfileSnapshot.model_validate(p)


def test_copied_nested_models_are_revalidated():
    model = ProfileSnapshot.model_validate(supported())
    feature = model.profiles[0].features[NAMES[0]].model_copy(update={"center": 99.0})
    candidate = model.profiles[0].model_copy(
        update={"features": {**model.profiles[0].features, NAMES[0]: feature}}
    )
    with pytest.raises(ValueError):
        ProfileSnapshot.model_validate(model.model_copy(update={"profiles": (candidate,)}))


@pytest.mark.parametrize("state", ["trusted", "active", "archived"])
def test_unknown_or_trusted_state_is_rejected(state):
    p = supported()
    p["lifecycle"]["state"] = state
    with pytest.raises(ValueError):
        ProfileSnapshot.model_validate(seal(p))


@pytest.mark.parametrize(
    "operation,reason,replacement",
    [
        ("mark_stale", "external_review", None),
        ("reject", "operator_rejected", None),
        ("supersede", "replacement_selected", "profile-snapshot-" + "b" * 64),
    ],
)
def test_administrative_shape_preserves_statistics(operation, reason, replacement):
    p = supported()
    changed = reviewed(p, operation, reason, replacement)
    model = ProfileSnapshot.model_validate(changed)
    assert model.profiles == ProfileSnapshot.model_validate(p).profiles
    assert model.snapshot_id != p["snapshot_id"]
    changed["lifecycle"]["review"]["subject_snapshot_id"] = "profile-snapshot-" + "0" * 64
    with pytest.raises(ValueError):
        ProfileSnapshot.model_validate(seal(changed))


def test_draft_rejection_remains_unbuilt_and_cannot_be_staled():
    p = reviewed(draft(), "reject", "operator_rejected")
    assert ProfileSnapshot.model_validate(p).source_report is None
    with pytest.raises(ValueError):
        ProfileSnapshot.model_validate(reviewed(p))


@pytest.mark.parametrize(
    "change",
    [
        "no_review",
        "wrong_reason",
        "replacement",
        "no_parent",
        "own_parent",
        "own_replacement",
        "no_source",
        "created_source",
        "build_state",
    ],
)
def test_lifecycle_shape_rejects_forged_revisions(change):
    p = reviewed(supported())
    if change == "no_review":
        p["lifecycle"]["review"] = None
    elif change == "wrong_reason":
        p["lifecycle"]["reason_code"] = "operator_rejected"
    elif change == "replacement":
        p["lifecycle"]["replacement_snapshot_id"] = "profile-snapshot-" + "b" * 64
    elif change == "no_parent":
        p["lifecycle"]["parent_snapshot_id"] = None
    elif change == "own_parent":
        p["lifecycle"]["parent_snapshot_id"] = p["snapshot_id"]
        p["lifecycle"]["review"]["subject_snapshot_id"] = p["snapshot_id"]
    elif change == "own_replacement":
        p = reviewed(
            supported(), "supersede", "replacement_selected", p["lifecycle"]["parent_snapshot_id"]
        )
    elif change == "no_source":
        p["source_report"] = None
    elif change == "created_source":
        p["lifecycle"] = draft()["lifecycle"]
    else:
        p["lifecycle"] = supported()["lifecycle"]
        p["lifecycle"].update(state="rejected", reason_code="no_supported_profiles")
    if change != "own_parent":
        seal(p)
    with pytest.raises(ValueError):
        ProfileSnapshot.model_validate(p)


def test_heldout_feature_count_cannot_change_fitted_statistics():
    from tests.calibration.cases import seal_report

    p = supported()
    before = ProfileSnapshot.model_validate(p)
    p["source_report"]["entries"][-1]["eligible_feature_count"] = 17
    seal_report(p["source_report"])
    candidate_id(p["profiles"][0], p["policy"], p["source_report"])
    after = ProfileSnapshot.model_validate(seal(p))
    assert after.profiles[0].features == before.profiles[0].features
    assert after.profiles[0].training_group_ids == before.profiles[0].training_group_ids
    assert after.profiles[0].profile_id != before.profiles[0].profile_id
    assert after.inputs[-1].feature_values is None


def test_two_partitions_do_not_double_count_shared_source_groups():
    from tests.calibration.cases import counts, seal_report

    from .cases import grouped

    p = grouped([[0.0], [1.0], [2.0], [3.0], [4.0]])
    report = p["source_report"]
    second_partition = "partition-" + "2" * 64
    entries = []
    for i, entry in enumerate(report["entries"]):
        entries.append(
            {
                **entry,
                "entry_id": f"entry-{i + 5:03d}",
                "representative_entry_id": f"entry-{i + 5:03d}",
                "partition_id": second_partition,
            }
        )
    report["entries"].extend(entries)
    report["counts"] = {
        **counts(10, 10, 0, 5, 5),
        "by_role": dict(
            engineering=counts(0, 0, 0, 0, 0),
            training=counts(10, 10, 0, 5, 5),
            validation=counts(0, 0, 0, 0, 0),
            final_test=counts(0, 0, 0, 0, 0),
        ),
    }
    report["partitions"].append({**report["partitions"][0], "partition_id": second_partition})
    seal_report(report)
    for i, entry in enumerate(entries):
        p["inputs"].append(
            dict(
                entry_id=entry["entry_id"],
                selected=True,
                reason_codes=[],
                feature_values={name: float(i + 5) for name in NAMES},
            )
        )
    second = copy.deepcopy(p["profiles"][0])
    second["partition_id"] = second_partition
    second["selected_entry_ids"] = [e["entry_id"] for e in entries]
    for f in second["features"].values():
        f["center"] = 7.0
        for row in f["group_values"]:
            row["median"] += 5
            row["entry_ids"] = [f"entry-{int(row['entry_ids'][0][-3:]) + 5:03d}"]
    p["profiles"].append(second)
    for profile in p["profiles"]:
        candidate_id(profile, p["policy"], report)
    p["counts"].update(retained_entries=10, selected_entries=10)
    model = ProfileSnapshot.model_validate(seal(p))
    assert model.counts.selected_groups == 5
    assert [f.features[NAMES[0]].center for f in model.profiles] == [2.0, 7.0]


def test_conflicting_selectable_labels_are_retained_without_votes():
    from tests.calibration.cases import counts, seal_report

    from .cases import excluded, source_report

    p = draft()
    report = source_report(1, heldout=False)
    entry = {
        **report["entries"][0],
        "entry_id": "entry-001",
        "representative_entry_id": "entry-001",
        "label": "render_capture_slowdown",
    }
    report["entries"].append(entry)
    report["counts"] = {
        **counts(2, 2, 0, 1, 1),
        "by_role": dict(
            engineering=counts(0, 0, 0, 0, 0),
            training=counts(2, 2, 0, 1, 1),
            validation=counts(0, 0, 0, 0, 0),
            final_test=counts(0, 0, 0, 0, 0),
        ),
    }
    report["partitions"][0].update(retained_entries=2, eligible_entries=2)
    seal_report(report)
    empty = excluded("reviewed-response")["profiles"][0]
    p["source_report"] = report
    p["inputs"] = [
        dict(
            entry_id=e["entry_id"],
            selected=False,
            reason_codes=["mixed_group_labels"],
            feature_values=None,
        )
        for e in report["entries"]
    ]
    p["profiles"] = []
    for label in ("host_contention", "render_capture_slowdown"):
        candidate = copy.deepcopy(empty)
        candidate.update(partition_id=report["entries"][0]["partition_id"], label=label)
        candidate_id(candidate, p["policy"], report)
        p["profiles"].append(candidate)
    p["counts"].update(retained_entries=2, excluded_entries=2, mixed_label_groups=1)
    p["lifecycle"].update(state="rejected", operation="build", reason_code="no_supported_profiles")
    model = ProfileSnapshot.model_validate(seal(p))
    assert len(model.profiles) == 2
    assert model.counts.selected_groups == 0
    assert model.counts.mixed_label_groups == 1


@pytest.mark.parametrize("factory", [draft, supported])
def test_create_build_do_not_borrow_administrative_reviews(factory):
    p = factory()
    p["lifecycle"]["review"] = reviewed(supported())["lifecycle"]["review"]
    with pytest.raises(ValueError, match="cannot borrow administrative reviews"):
        ProfileSnapshot.model_validate(seal(p))


def test_non_supersession_cannot_record_a_replacement_even_with_matching_review():
    p = reviewed(supported())
    replacement = "profile-snapshot-" + "c" * 64
    p["lifecycle"]["replacement_snapshot_id"] = replacement
    p["lifecycle"]["review"]["replacement_snapshot_id"] = replacement
    with pytest.raises(ValueError, match="supersession requires exactly one replacement"):
        ProfileSnapshot.model_validate(seal(p))
