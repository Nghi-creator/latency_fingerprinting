"""Frozen design pins and a Decimal arithmetic oracle, independent of future N7 code."""

import hashlib
import json
import math
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "docs/profiles"
POLICY_HASH = "sha256:8e805ffb205e7808559c0eac30d286f3395f006c358b100aef1e95fc705ec641"
# Set from the reviewed, literal vector file; no update mode.
VECTOR_SHA256 = "d5995432d645c4a18cd624ebb3183b22862cc0d380dff2fb003f3b1c927b5840"
POLICY = json.loads((ROOT / "N7_PROFILE_POLICY_SPEC.json").read_bytes())
VECTORS = json.loads((ROOT / "N7_DESIGN_VECTORS.json").read_bytes())


def canonical(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode()


def rounded(value):
    result = float(value)
    if not math.isfinite(result) or (value != 0 and result == 0):
        raise ValueError("invalid_profile_arithmetic")
    return 0.0 if result == 0 else result


def median(values):
    if not values:
        raise ValueError("invalid_profile_arithmetic")
    ordered = sorted(Decimal.from_float(value) for value in values)
    middle = len(ordered) // 2
    # 2200 decimal digits cover all exact binary64 midpoint/difference operands.
    with localcontext() as context:
        context.prec = 2200
        value = ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2
        return rounded(value)


def deviation(value, center):
    with localcontext() as context:
        context.prec = 2200
        return rounded(abs(Decimal.from_float(value) - Decimal.from_float(center)))


def feature(groups):
    medians = [median(values) if values else None for values in groups]
    observed = [value for value in medians if value is not None]
    count, denominator = len(observed), len(groups)
    center = median(observed) if observed else None
    mad = median([deviation(value, center) for value in observed]) if observed else None
    reasons = []
    if not observed:
        reasons.append("missing_measurements")
    if count < 5:
        reasons.append("insufficient_group_support")
    if denominator == 0 or count * 5 < denominator * 4:
        reasons.append("insufficient_availability")
    if mad == 0:
        reasons.append("zero_dispersion")
    return dict(
        group_medians=medians,
        center=center,
        dispersion=mad,
        contributing_groups=count,
        availability=dict(
            numerator=count,
            denominator=denominator,
            value=count / denominator if denominator else None,
        ),
        state="excluded" if reasons else "supported",
        reason_codes=reasons,
        weight=0.0 if reasons else 1.0,
    )


def test_policy_identity_release_and_existing_feature_inventory():
    payload = {k: v for k, v in POLICY.items() if k not in ("policy_id", "content_hash")}
    assert (
        POLICY["content_hash"]
        == POLICY_HASH
        == "sha256:" + hashlib.sha256(canonical(payload)).hexdigest()
    )
    assert POLICY["policy_id"] == "profile-policy-" + POLICY_HASH[7:]
    assert (ROOT / "N7_PROFILE_POLICY_SPEC.json").read_bytes() == canonical(POLICY)
    n3 = json.loads((ROOT.parent / "analysis/N3_FEATURE_POLICY_SPEC.json").read_bytes())
    assert POLICY["response_policy_hash"] == n3["contentHash"]
    assert POLICY["feature_names"] == sorted(n3["features"])
    assert len(POLICY["feature_names"]) == 22
    assert POLICY["registry"] == dict(
        registry_version=n3["registry"]["registryVersion"],
        content_hash=n3["registry"]["contentHash"],
    )
    assert POLICY["parameter_provenance"] == "software_provisional"
    assert POLICY["statistics"]["dispersion_floor"] is None


def test_vector_pin_and_canonical_serialization():
    raw = (ROOT / "N7_DESIGN_VECTORS.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == VECTOR_SHA256
    assert raw == canonical(VECTORS)
    assert VECTORS["policy_content_hash"] == POLICY_HASH
    assert VECTORS["provenance"] == "synthetic_design_only"


@pytest.mark.parametrize("case", VECTORS["numeric_cases"], ids=lambda case: case["case_id"])
def test_literal_binary64_results_against_decimal_oracle(case):
    operation = median if case["operation"] == "median" else lambda values: deviation(*values)
    if case["error"]:
        with pytest.raises(ValueError, match="^invalid_profile_arithmetic$"):
            operation(case["values"])
    else:
        value = operation(case["values"])
        assert value == case["expected_value"]
        assert value.hex() == case["expected_hex"]


@pytest.mark.parametrize("case", VECTORS["feature_cases"], ids=lambda case: case["case_id"])
def test_literal_two_level_statistics_and_all_exclusion_reasons(case):
    assert feature(case["groups"]) == case["expected"]


@pytest.mark.parametrize("case", VECTORS["candidate_cases"], ids=lambda case: case["case_id"])
def test_candidate_gate_boundaries(case):
    reasons = []
    if case["training_groups"] < 5:
        reasons.append("insufficient_training_groups")
    if case["active_features"] < 17:
        reasons.append("insufficient_active_features")
    if case["active_features"] * 4 < 22 * 3:
        reasons.append("insufficient_active_coverage")
    assert reasons == case["expected_reasons"]
    assert case["expected_state"] == ("rejected" if reasons else "provisional")
    # The example must also be possible under the per-feature minimum.
    assert case["training_groups"] >= 5 or case["active_features"] == 0


def test_extreme_deviation_fails_even_if_mad_rank_would_hide_it():
    with pytest.raises(ValueError, match="^invalid_profile_arithmetic$"):
        feature(VECTORS["feature_overflow_case"]["groups"])


def test_group_vote_and_heldout_independence_examples():
    case = VECTORS["heldout_case"]
    result = feature(case["training_groups"])
    assert result["center"] == case["expected_center"]
    assert result["dispersion"] == case["expected_dispersion"]
    grouped = VECTORS["feature_cases"][0]
    assert median([value for group in grouped["groups"] for value in group]) == 0.0
    assert grouped["expected"]["center"] == 2.0
    assert case["validation_values"] != case["mutated_validation_values"]
    assert case["final_test_values"] != case["mutated_final_test_values"]


def test_real_n6_synthetic_fixture_cannot_become_profile_training_data():
    from latency_fingerprinting.calibration import inspect_calibration_dataset
    from tests.calibration.check_reproduction import FIXTURES, load_release

    case = VECTORS["synthetic_dataset_expectation"]
    load_release()
    report = inspect_calibration_dataset(FIXTURES / "reviewed-roles").report
    assert report.counts.retained_entries == case["retained_entries"]
    assert report.counts.eligible_entries == case["selected_entries"] == 0
    assert report.counts.eligible_groups == case["selected_groups"] == 0
    assert (
        len(
            {
                (entry.partition_id, entry.label)
                for entry in report.entries
                if entry.role == "training" and entry.label is not None
            }
        )
        == case["profiles"]
        == 1
    )


@pytest.mark.parametrize("case", VECTORS["selection_cases"], ids=lambda case: case["case_id"])
def test_literal_selection_and_mixed_label_examples(case):
    # Minimal design metadata, not fabricated production N6 records.
    labels = {}
    for entry in case["entries"]:
        if (
            entry["input_kind"] == "response"
            and entry["role"] == "training"
            and entry["eligible"]
            and entry["label"] is not None
            and entry["representative_entry_id"] == entry["entry_id"]
        ):
            labels.setdefault((entry["partition_id"], entry["group_id"]), set()).add(entry["label"])
    reasons, selected, groups = {}, [], set()
    for entry in case["entries"]:
        codes = []
        if entry["input_kind"] == "missing":
            codes = ["missing_measurements"]
        else:
            if entry["input_kind"] == "healthy_window":
                codes.append("baseline_only")
            if entry["role"] != "training":
                codes.append("not_training")
            if not entry["eligible"]:
                codes.append("n6_excluded")
            if entry["representative_entry_id"] != entry["entry_id"]:
                codes.append("duplicate_evidence")
            if entry["input_kind"] == "response" and entry["label"] is None:
                codes.append("unknown_label")
            if not codes and len(labels[(entry["partition_id"], entry["group_id"])]) > 1:
                codes.append("mixed_group_labels")
        reasons[entry["entry_id"]] = codes
        if not codes:
            selected.append(entry["entry_id"])
            groups.add(entry["group_id"])
    assert reasons == case["expected_reasons"]
    assert selected == case["expected_selected_entries"]
    assert sorted(groups) == case["expected_selected_groups"]


def test_lifecycle_examples_cover_withdrawal_and_prohibit_trust():
    cases = VECTORS["lifecycle_cases"]
    successes = [case for case in cases if case["error"] is None]
    assert {case["expected_state"] for case in successes} == {
        "created",
        "provisional",
        "rejected",
        "stale",
        "superseded",
    }
    assert all(
        case["has_review"]
        for case in successes
        if case["operation"] in {"reject", "mark_stale", "supersede"}
    )
    assert all(
        case["replacement_state"] == "provisional"
        for case in successes
        if case["operation"] == "supersede"
    )
    assert all(
        case["error"] is not None
        for case in cases
        if case["parent"] in {"trusted", "superseded"} or case["operation"] == "promote"
    )
