"""Strict JSON, public dispatch, bounded nesting/collections and approved-release ownership."""

import copy
import json

import pytest

from latency_fingerprinting.cli import main
from latency_fingerprinting.profiles import ProfilePolicy, ProfileSnapshot
from latency_fingerprinting.profiles.arithmetic import candidate_support, feature_statistics, ratio
from latency_fingerprinting.profiles.evidence import FeatureStatistics, InputSelection

from .cases import NAMES, canonical, digest, draft, excluded, policy, seal, supported


@pytest.mark.parametrize(
    "factory,cls", [(policy, ProfilePolicy), (draft, ProfileSnapshot), (supported, ProfileSnapshot)]
)
def test_public_validate_and_json_error_boundaries(tmp_path, capsys, factory, cls):
    value = factory()
    path = tmp_path / "input.json"
    path.write_bytes(canonical(value))
    assert main(["validate", str(path)]) == 0
    assert capsys.readouterr() == (canonical(value).decode(), "")
    for raw in [
        b"\xff",
        b'{"a":1,"a":2}',
        b'{"a":NaN}',
        b"[" * 33 + b"0" + b"]" * 33,
        b" " * (10 * 1024 * 1024 + 1),
    ]:
        with pytest.raises(ValueError):
            cls.model_validate_json(raw)
    with pytest.raises(ValueError):
        cls.model_validate_json({})


@pytest.mark.parametrize(
    "field,value", [("require_n6_eligible", False), ("exclude_duplicates", False)]
)
def test_rehashed_altered_policy_does_not_become_approved(field, value):
    p = policy()
    p["selection"][field] = value
    content = digest({k: v for k, v in p.items() if k not in ("content_hash", "policy_id")})
    p.update(content_hash="sha256:" + content, policy_id="profile-policy-" + content)
    with pytest.raises(ValueError, match="approved release"):
        ProfilePolicy.model_validate(p)


@pytest.mark.parametrize(
    "where,value",
    [
        ("weight", True),
        ("weight", "1"),
        ("center", float("inf")),
        ("dispersion", float("nan")),
        ("count", True),
        ("selected", 1),
        ("hash", "sha256:" + "a" * 64 + "\n"),
    ],
)
def test_scalar_types_and_identifiers_are_strict(where, value):
    p = supported()
    f = p["profiles"][0]["features"][NAMES[0]]
    if where == "weight":
        f["weight"] = value
    elif where in ("center", "dispersion"):
        f[where] = value
    elif where == "count":
        p["counts"]["selected_groups"] = value
    elif where == "selected":
        p["inputs"][0]["selected"] = value
    else:
        p["content_hash"] = value
    with pytest.raises(ValueError):
        ProfileSnapshot.model_validate(p)


@pytest.mark.parametrize("collection", [set(), iter([]), {"entry": 1}, [None] * 257])
def test_snapshot_collections_reject_before_nested_validation(collection):
    p = draft()
    p["inputs"] = collection
    with pytest.raises(ValueError, match="top-level collection"):
        ProfileSnapshot.model_validate(p)


@pytest.mark.parametrize("field", ["inputs", "profiles"])
def test_unbuilt_draft_cannot_smuggle_evidence(field):
    p = draft()
    p[field] = supported()[field]
    with pytest.raises(ValueError):
        ProfileSnapshot.model_validate(seal(p))


def test_nested_global_budget_is_rejected_before_invalid_child_models():
    p = draft()
    p["profiles"] = [{"features": {NAMES[0]: {"group_values": [{"entry_ids": ["entry-a"]}]}}}]
    with pytest.raises(ValueError, match="global profile group/reference budget"):
        ProfileSnapshot.model_validate(p)
    p["inputs"] = [{"selected": True}]
    p["profiles"][0]["features"][NAMES[0]]["group_values"] = [{"entry_ids": ["entry-a"] * 23}]
    with pytest.raises(ValueError, match="global profile group/reference budget"):
        ProfileSnapshot.model_validate(p)


@pytest.mark.parametrize("field", ["features", "feature_values"])
def test_exact_feature_maps_cannot_expand_or_drop_keys(field):
    if field == "features":
        p = supported()
        p["profiles"][0][field]["unknown"] = p["profiles"][0][field][NAMES[0]]
        with pytest.raises(ValueError):
            ProfileSnapshot.model_validate(p)
    else:
        item = supported()["inputs"][0]
        for values in ({}, {**item[field], "unknown": 1.0}, [1.0] * 22):
            item[field] = values
            with pytest.raises(ValueError):
                InputSelection.model_validate(item)


@pytest.mark.parametrize(
    "source",
    [
        "baseline",
        "confounded",
        "controlled-healthy",
        "controlled-host",
        "controlled-pacing",
        "declared",
        "duplicate",
        "failed-effect",
        "missing",
        "mixed-settings",
        "reviewed-response",
        "reviewed-roles",
    ],
)
def test_every_valid_synthetic_n6_case_stays_excluded(source):
    p = excluded(source)
    model = ProfileSnapshot.model_validate(p)
    assert model.model_dump(mode="json") == p
    assert model.counts.selected_entries == model.counts.selected_groups == 0
    assert model.lifecycle.state == "rejected"
    assert all(item.feature_values is None for item in model.inputs)


@pytest.mark.parametrize(
    "numerator,denominator",
    [(True, 5), (1, False), (1, 0), (-1, 5), (6, 5), (1, 257), (1.0, 5), (1, "5")],
)
def test_ratios_do_not_coerce_or_invent_counts(numerator, denominator):
    with pytest.raises(ValueError, match="^invalid_profile_arithmetic$"):
        ratio(numerator, denominator)


@pytest.mark.parametrize(
    "values,denominator",
    [([True], 5), ([1.0] * 257, 256), (iter([1.0]), 5), ([1.0], 0), ([], True)],
)
def test_feature_helper_enforces_domain_and_collection_bounds(values, denominator):
    with pytest.raises(ValueError, match="^invalid_profile_arithmetic$"):
        feature_statistics(values, denominator)


@pytest.mark.parametrize("groups,active", [(True, 22), (-1, 22), (257, 22), (5, 23), (5, False)])
def test_candidate_helper_enforces_count_domain(groups, active):
    with pytest.raises(ValueError, match="^invalid_profile_arithmetic$"):
        candidate_support(groups, active)


def test_nullable_ratio_is_not_zero_filled():
    f = copy.deepcopy(excluded("reviewed-response")["profiles"][0]["features"][NAMES[0]])
    f["availability"]["value"] = 0.0
    with pytest.raises(ValueError, match="ratio does not reconstruct"):
        FeatureStatistics.model_validate(f)


def test_new_schemas_do_not_modify_any_existing_bytes():
    from latency_fingerprinting.schemas import (
        DEFAULT_SCHEMA_DIRECTORY,
        SCHEMA_MODELS,
        render_schema,
    )

    assert len(SCHEMA_MODELS) == 40
    for name, model in SCHEMA_MODELS.items():
        assert (DEFAULT_SCHEMA_DIRECTORY / name).read_text() == render_schema(model)
    assert set(
        json.loads((DEFAULT_SCHEMA_DIRECTORY / "profile-snapshot-v1.schema.json").read_text())[
            "properties"
        ]
    ) == set(draft())


@pytest.mark.parametrize("where", ["group_values", "entry_ids"])
@pytest.mark.parametrize("value", [iter([]), [None] * 257])
def test_nested_reference_shapes_fail_before_parsing_children(where, value):
    p = draft()
    p["inputs"] = [{"selected": True}]
    rows = value if where == "group_values" else [{"entry_ids": value}]
    p["profiles"] = [{"features": {NAMES[0]: {"group_values": rows}}}]
    with pytest.raises(ValueError, match="collection exceeds bound"):
        ProfileSnapshot.model_validate(p)


def test_missing_input_inventory_is_not_silently_omitted():
    p = supported()
    p["inputs"].pop()
    p["profiles"] = []
    with pytest.raises(ValueError, match="input inventory disagrees"):
        ProfileSnapshot.model_validate(p)


@pytest.mark.parametrize("field", ["content_hash", "policy_id", "weights"])
def test_trusted_policy_renderer_detects_unreviewed_internal_drift(monkeypatch, field):
    from latency_fingerprinting.profiles import policy_release

    changed = policy()
    if field == "weights":
        changed["weights"]["supported"] = 2.0
    elif field == "content_hash":
        changed[field] = "sha256:" + "0" * 64
    else:
        changed[field] = "profile-policy-" + "0" * 64
    monkeypatch.setattr(policy_release, "_APPROVED", changed)
    with pytest.raises(ValueError, match="unreviewed profile policy change"):
        policy_release.approved_policy_payload()


def test_negative_zero_is_retained_only_in_raw_selected_values():
    p = supported()
    p["inputs"][0]["feature_values"][NAMES[0]] = -0.0
    model = ProfileSnapshot.model_validate(seal(p))
    assert model.inputs[0].feature_values[NAMES[0]].hex().startswith("-0x0")
    rows = model.profiles[0].features[NAMES[0]].group_values
    row = next(row for row in rows if row.entry_ids == (p["inputs"][0]["entry_id"],))
    assert row.median.hex() == "0x0.0p+0"


@pytest.mark.parametrize("heldout", [False, True])
def test_declared_selection_cannot_hide_training_or_admit_heldout_values(heldout):
    p = supported()
    item = p["inputs"][-1] if heldout else p["inputs"][0]
    item.update(
        selected=heldout,
        reason_codes=[] if heldout else ["n6_excluded"],
        feature_values=dict(p["inputs"][0]["feature_values"]) if heldout else None,
    )
    p["profiles"] = []
    with pytest.raises(ValueError, match="profile selection does not reconstruct"):
        ProfileSnapshot.model_validate(p)
