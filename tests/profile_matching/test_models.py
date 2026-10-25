"""Independent positive roots, exact reconstruction attacks and public dispatch boundaries."""

import hashlib
import json

import pytest

from latency_fingerprinting.cli import main
from latency_fingerprinting.profile_matching import (
    ProfileEvaluationResult,
    ProfileMatchPolicy,
    ProfileMatchResult,
    arithmetic,
)
from latency_fingerprinting.profile_matching.policy_release import approved_policy_payload
from tests.profiles.cases import reviewed

from .cases import canonical, evaluation, match, policy, root_seal
from .test_design import VECTORS


@pytest.mark.parametrize("case", VECTORS["numeric_cases"], ids=lambda c: c["case_id"])
def test_fraction_arithmetic_matches_preimplementation_literals(case):
    operation = getattr(
        arithmetic,
        dict(deviation="deviation", standardize="standardize", mean="mean", margin="margin")[
            case["operation"]
        ],
    )
    args = [case["values"]] if case["operation"] == "mean" else case["values"]
    if case["error"]:
        with pytest.raises(ValueError, match="^invalid_profile_match_arithmetic$"):
            operation(*args)
    else:
        assert operation(*args).hex() == case["expected_hex"]


@pytest.mark.parametrize("value", [True, "1", None, float("inf"), float("nan"), 10**1000])
def test_invalid_arithmetic_is_fixed(value):
    with pytest.raises(ValueError, match="^invalid_profile_match_arithmetic$"):
        arithmetic.deviation(value, 0.0)


@pytest.mark.parametrize("value", [[], [0.0] * 23, iter([0.0]), [-1.0]])
def test_mean_is_bounded_and_nonnegative(value):
    with pytest.raises(ValueError, match="^invalid_profile_match_arithmetic$"):
        arithmetic.mean(value)


def test_policy_approval_is_exact_and_detached():
    p = policy()
    model = ProfileMatchPolicy.model_validate(p)
    assert model.model_dump(mode="json") == p == approved_policy_payload()
    p["gates"]["minimum_common_features"] = 1
    with pytest.raises(ValueError):
        ProfileMatchPolicy.model_validate(p)
    changed = model.model_copy(
        update={"gates": model.gates.model_copy(update={"minimum_common_features": 1})}
    )
    with pytest.raises(ValueError):
        ProfileMatchPolicy.model_validate(changed)
    with pytest.raises(ValueError):
        model.gates.minimum_common_features = 1


@pytest.mark.parametrize(
    "factory,cls",
    [
        (match, ProfileMatchResult),
        (lambda: evaluation("validation"), ProfileEvaluationResult),
        (lambda: evaluation("final_test"), ProfileEvaluationResult),
        (lambda: evaluation("leave_training_group_out"), ProfileEvaluationResult),
        (lambda: evaluation("leave_training_group_out", 6), ProfileEvaluationResult),
    ],
)
def test_independent_complete_model_only_examples(factory, cls):
    expected = factory()
    actual = cls.model_validate(expected)
    assert actual.model_dump(mode="json") == expected
    assert cls.model_validate_json(canonical(expected)) == actual
    assert cls.model_validate(actual) == actual
    expected["evidence"]["snapshot"]["inputs"].clear()
    assert actual.evidence.snapshot.inputs
    if isinstance(actual, ProfileEvaluationResult):
        with pytest.raises(TypeError):
            actual.confusion_matrix["healthy"]["unknown"] = 99
    else:
        with pytest.raises(TypeError):
            actual.decision.query_feature_values[
                next(iter(actual.decision.query_feature_values))
            ] = 99
        with pytest.raises(ValueError):
            actual.decision.state = "trusted"


@pytest.mark.parametrize(
    "change",
    [
        "distance",
        "center",
        "deviation",
        "weight",
        "missing_feature",
        "mask",
        "rank",
        "chosen",
        "reason_order",
        "count",
        "row_id",
        "query_id",
        "artifact_id",
        "record_id",
        "heldout_role",
        "trusted",
        "extra",
        "hash",
        "snapshot_report",
        "dataset",
        "withdrawn",
        "copied",
    ],
)
def test_rehashed_false_match_fields_never_validate(change):
    p = match()
    d = p["decision"]
    first = next(iter(d["candidates"][0]["features"]))
    if change == "distance":
        d["candidates"][0]["distance"] = 1.0
    elif change == "center":
        d["candidates"][0]["features"][first]["center"] = 99.0
    elif change == "deviation":
        d["candidates"][0]["features"][first]["standardized_deviation"] = 99.0
    elif change == "weight":
        d["candidates"][0]["features"][first]["applied_weight"] = 0.0
    elif change == "missing_feature":
        del d["candidates"][0]["features"][first]
    elif change == "mask":
        d["common_feature_names"].pop()
    elif change == "rank":
        d["ranked_profile_ids"].reverse()
    elif change == "chosen":
        d["chosen_label"] = "host_contention"
    elif change == "reason_order":
        d["reason_codes"] = ["ambiguous_labels", "no_competing_label"]
    elif change == "count":
        d["common_coverage"]["numerator"] = 21
    elif change == "row_id":
        d["candidates"][0]["profile_id"] = "profile-" + "0" * 64
    elif change == "query_id":
        d["query_entry_id"] = "nonexistent"
    elif change == "artifact_id":
        d["query_artifact_id"] = "wrong"
    elif change == "record_id":
        d["query_record_id"] = "response-v2-" + "e" * 64 + "\n"
    elif change == "heldout_role":
        d["query_mode"] = "leave_training_group_out"
    elif change == "trusted":
        d["state"] = "trusted"
    elif change == "extra":
        d["probability"] = 0.99
    elif change == "hash":
        p["content_hash"] = "sha256:" + "0" * 64
    elif change == "snapshot_report":
        p["evidence"]["snapshot"]["source_report"]["dataset_id"] = "dataset-" + "0" * 64
    elif change == "dataset":
        p["evidence"]["dataset"]["sources"][0]["run_id"] = "different"
    elif change == "withdrawn":
        p["evidence"]["snapshot"] = reviewed(p["evidence"]["snapshot"])
    else:
        model = ProfileMatchResult.model_validate(p)
        d = model.decision.model_copy(update={"best_distance": 99.0})
        with pytest.raises(ValueError):
            ProfileMatchResult.model_validate(model.model_copy(update={"decision": d}))
        return
    if change != "hash":
        root_seal(p)
    with pytest.raises(ValueError):
        ProfileMatchResult.model_validate(p)


@pytest.mark.parametrize(
    "change",
    [
        "query_inventory",
        "group_vote",
        "matrix",
        "denominator",
        "conditional_accuracy",
        "refit_id",
        "fold_profile_id",
        "fold_input",
        "fold_scale",
        "fold_count",
        "missing_fold",
        "reuse_original",
        "copied",
    ],
)
def test_rehashed_false_evaluation_and_refit_fields_fail(change):
    p = evaluation("leave_training_group_out")
    r = p["refits"][0]
    if change == "query_inventory":
        p["decisions"].pop()
    elif change == "group_vote":
        p["group_outcomes"][0]["predicted_label"] = "healthy"
    elif change == "matrix":
        p["confusion_matrix"]["healthy"]["healthy"] += 1
    elif change == "denominator":
        p["metrics"]["accuracy"]["denominator"] = 0
    elif change == "conditional_accuracy":
        p["counts"]["known_truth_groups"] = 0
    elif change == "refit_id":
        r["refit_id"] = "profile-refit-" + "0" * 64
    elif change == "fold_profile_id":
        r["profiles"][0]["profile_id"] = "profile-fold-" + "0" * 64
    elif change == "fold_input":
        r["inputs"][0]["selected"] = not r["inputs"][0]["selected"]
    elif change == "fold_scale":
        next(iter(r["profiles"][0]["features"].values()))["dispersion"] = 99.0
    elif change == "fold_count":
        r["counts"]["removed_entries"] = 0
    elif change == "missing_fold":
        p["refits"].pop()
    elif change == "reuse_original":
        p["decisions"][0]["candidates"][0]["profile_id"] = p["evidence"]["snapshot"]["profiles"][0][
            "profile_id"
        ]
    else:
        m = ProfileEvaluationResult.model_validate(p)
        bad = m.refits[0].model_copy(
            update={"counts": m.refits[0].counts.model_copy(update={"removed_entries": 0})}
        )
        with pytest.raises(ValueError):
            ProfileEvaluationResult.model_validate(
                m.model_copy(update={"refits": (bad, *m.refits[1:])})
            )
        return
    with pytest.raises(ValueError):
        ProfileEvaluationResult.model_validate(root_seal(p))


@pytest.mark.parametrize(
    "factory,cls",
    [
        (policy, ProfileMatchPolicy),
        (match, ProfileMatchResult),
        (evaluation, ProfileEvaluationResult),
    ],
)
def test_cli_standalone_dispatch_and_hostile_json(factory, cls, tmp_path, capsys):
    p = factory()
    path = tmp_path / "input.json"
    path.write_bytes(canonical(p))
    assert main(["validate", str(path)]) == 0
    assert capsys.readouterr() == (canonical(p).decode(), "")
    for bad in [
        b'{"a":1,"a":2}',
        b'{"a":NaN}',
        b"\xff",
        b"[" * 33 + b"0" + b"]" * 33,
        b" " * (10485760 + 1),
    ]:
        with pytest.raises(ValueError):
            cls.model_validate_json(bad)


def test_all_old_schema_bytes_are_pinned_and_three_exports_are_additive():
    from latency_fingerprinting.schemas import (
        DEFAULT_SCHEMA_DIRECTORY,
        SCHEMA_MODELS,
        render_schema,
    )

    additions = {
        "profile-match-policy-v1.schema.json",
        "profile-match-result-v1.schema.json",
        "profile-evaluation-result-v1.schema.json",
    }
    assert len(SCHEMA_MODELS) == 38
    old = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in DEFAULT_SCHEMA_DIRECTORY.glob("*.schema.json")
        if p.name
        not in additions
        | {
            "cadence-probe-evidence-v1.schema.json",
            "live-probe-evidence-v1.schema.json",
            "passive-gate-policy-v1.schema.json",
            "passive-baseline-v1.schema.json",
            "passive-replay-v1.schema.json",
            "passive-gate-result-v1.schema.json",
        }
    }
    assert (
        hashlib.sha256(json.dumps(old, sort_keys=True).encode()).hexdigest()
        == "10d8f99def1f421460ce1b8cae47d56478e924d183ab33c8c624988b1ff12041"
    )
    for name, model in SCHEMA_MODELS.items():
        assert (DEFAULT_SCHEMA_DIRECTORY / name).read_text() == render_schema(model)
