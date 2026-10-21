"""Literal N8 design pins and Decimal oracles, independent of future production code."""

import copy
import hashlib
import json
import math
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs/profile_matching"
POLICY_HASH = "sha256:b296df5c172d19e9470f64b3546fcb7af54c6623dd5951bc0c652a94e87b95db"
VECTOR_HASH = "42b2bb4d483f3605122a8aa2090153f200470f03466163f552e0ef8497e35c65"
POLICY = json.loads((DOCS / "N8_MATCH_POLICY_SPEC.json").read_bytes())
VECTORS = json.loads((DOCS / "N8_DESIGN_VECTORS.json").read_bytes())


def canonical(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode()


def number(value):
    if type(value) is not float or not math.isfinite(value):
        raise ValueError("invalid_profile_match_arithmetic")
    return Decimal.from_float(value)


def rounded(value):
    result = float(value)
    if not math.isfinite(result) or (value != 0 and result == 0):
        raise ValueError("invalid_profile_match_arithmetic")
    return 0.0 if result == 0 else result


def deviation(value, center):
    with localcontext() as context:
        context.prec = 2200
        return rounded(abs(number(value) - number(center)))


def standardize(value, scale):
    with localcontext() as context:
        context.prec = 2200
        if value < 0 or scale <= 0:
            raise ValueError("invalid_profile_match_arithmetic")
        return rounded(number(value) / number(scale))


def mean(values):
    if not isinstance(values, (list, tuple)) or not 1 <= len(values) <= 22:
        raise ValueError("invalid_profile_match_arithmetic")
    with localcontext() as context:
        context.prec = 2200
        operands = [number(value) for value in values]
        if any(value < 0 for value in operands):
            raise ValueError("invalid_profile_match_arithmetic")
        return rounded(sum(operands, Decimal(0)) / len(operands))


def margin(runner_up, best):
    with localcontext() as context:
        context.prec = 2200
        if runner_up < best:
            raise ValueError("invalid_profile_match_arithmetic")
        return rounded(number(runner_up) - number(best))


def decide(scores, common_count):
    """Independent literal decision gates; score inputs are already rounded binary64."""
    if len({label for label, _ in scores}) != len(scores):
        raise ValueError("duplicate label candidate")
    if not scores:
        reasons = ["no_compatible_profiles"]
    elif common_count < 17:
        reasons = ["insufficient_common_features"]
        if common_count * 4 < 22 * 3:
            reasons.append("insufficient_common_coverage")
    else:
        ranked = sorted(scores, key=lambda row: (row[1], row[0]))
        reasons = []
        if len(ranked) < 2:
            reasons.append("no_competing_label")
        if ranked[0][1] > 3.0:
            reasons.append("distance_exceeded")
        if len(ranked) >= 2 and margin(ranked[1][1], ranked[0][1]) < 0.25:
            reasons.append("ambiguous_labels")
        if not reasons:
            return "provisional_match", ranked[0][0], []
    return "unknown", None, reasons


def feature_scores(case):
    query, profiles = case["query"], case["profiles"]
    common = set(i for i, value in enumerate(query) if value is not None)
    for profile in profiles:
        common.intersection_update(profile["active"])
    indices = sorted(common)
    if len(indices) < 17:
        return indices, None
    return indices, [
        mean([standardize(deviation(query[i], p["centers"][i]), p["scales"][i]) for i in indices])
        for p in profiles
    ]


def test_policy_identity_and_unchanged_source_releases():
    raw = (DOCS / "N8_MATCH_POLICY_SPEC.json").read_bytes()
    assert raw == canonical(POLICY)
    content = {k: v for k, v in POLICY.items() if k not in {"policy_id", "content_hash"}}
    assert "sha256:" + hashlib.sha256(canonical(content)).hexdigest() == POLICY_HASH
    assert POLICY["content_hash"] == POLICY_HASH
    assert POLICY["policy_id"] == "profile-match-policy-" + POLICY_HASH[7:]
    n7 = json.loads((ROOT / "docs/profiles/N7_PROFILE_POLICY_SPEC.json").read_bytes())
    assert POLICY["profile_policy_hash"] == n7["content_hash"]
    for key in ("registry", "response_policy_hash", "feature_names"):
        assert POLICY[key] == n7[key]
    assert POLICY["evaluation"]["trust_promotion"] is False
    assert POLICY["evaluation"]["automatic_tuning"] is False
    assert POLICY["operating_mode"] == "offline_provisional"
    assert POLICY["scoring"]["scale_floor"] is None
    assert POLICY["scoring"]["imputation"] is None
    assert len(POLICY["feature_names"]) == 22


def test_literal_vector_release_pin():
    raw = (DOCS / "N8_DESIGN_VECTORS.json").read_bytes()
    assert raw == canonical(VECTORS)
    assert hashlib.sha256(raw).hexdigest() == VECTOR_HASH
    assert VECTORS["provenance"] == "synthetic_design_only"


@pytest.mark.parametrize("case", VECTORS["numeric_cases"], ids=lambda c: c["case_id"])
def test_binary64_literals_against_decimal_oracle(case):
    operation = dict(deviation=deviation, standardize=standardize, mean=mean, margin=margin)[
        case["operation"]
    ]
    arguments = [case["values"]] if case["operation"] == "mean" else case["values"]
    if case["error"]:
        with pytest.raises(ValueError, match="^invalid_profile_match_arithmetic$"):
            operation(*arguments)
    else:
        assert operation(*arguments).hex() == case["expected_hex"]


@pytest.mark.parametrize("case", VECTORS["decision_cases"], ids=lambda c: c["case_id"])
def test_decision_boundaries_and_reason_order(case):
    assert decide(case["scores"], case["common_count"]) == (
        case["state"],
        case["chosen"],
        case["reasons"],
    )
    assert decide(list(reversed(case["scores"])), case["common_count"]) == (
        case["state"],
        case["chosen"],
        case["reasons"],
    )


@pytest.mark.parametrize("case", VECTORS["feature_cases"], ids=lambda c: c["case_id"])
def test_common_feature_mask_and_literal_scores(case):
    assert feature_scores(case) == (case["expected_common"], case["expected_distances"])
    swapped = {**case, "profiles": list(reversed(case["profiles"]))}
    mask, scores = feature_scores(swapped)
    assert mask == case["expected_common"]
    assert scores == (
        list(reversed(case["expected_distances"])) if case["expected_distances"] else None
    )


@pytest.mark.parametrize("truth", ["healthy", "host_contention", "render_capture_slowdown", None])
def test_query_truth_cannot_choose_features_or_distances(truth):
    case = copy.deepcopy(VECTORS["feature_cases"][0])
    case["truth_label"] = truth
    assert feature_scores(case) == (list(range(17)), [0.0, 1.0])


def test_same_label_revisions_cannot_be_competitors():
    with pytest.raises(ValueError, match="duplicate label"):
        decide([["healthy", 0.0], ["healthy", 0.25]], 22)


@pytest.mark.parametrize("case", VECTORS["overlap_cases"], ids=lambda c: c["case_id"])
def test_scoped_component_source_and_receipt_overlap(case):
    excluded = (
        case["query_group"] in case["training_groups"]
        or bool(set(case["query_sources"]) & set(case["training_sources"]))
        or bool(set(case["query_receipts"]) & set(case["training_receipts"]))
    )
    assert excluded is case["excluded"]


@pytest.mark.parametrize("case", VECTORS["metadata_cases"], ids=lambda c: c["case_id"])
def test_metadata_gates_and_unavailable_revisions(case):
    if not case["scope_bound"] or case["revision_count"] != 1:
        assert case["expected_error"] == "invalid_profile_match"
        return
    assert case["expected_error"] is None
    reasons = []
    if case["snapshot_state"] != "provisional":
        reasons.append("snapshot_unavailable")
    if case["query_kind"] == "missing":
        reasons.append("missing_measurements")
    else:
        if case["query_kind"] == "healthy_window":
            reasons.append("baseline_only")
        if case["query_role"] not in ("validation", "final_test"):
            reasons.append("not_held_out")
        if not case["n6_eligible"]:
            reasons.append("n6_excluded")
        if not case["self_representative"]:
            reasons.append("duplicate_evidence")
    assert reasons == case["expected_reasons"]


@pytest.mark.parametrize("case", VECTORS["refit_cases"], ids=lambda c: c["case_id"])
def test_leave_whole_group_out_and_refit_from_remaining_votes(case):
    # Reuse the frozen independent N7 Decimal oracle, never production fitting.
    from tests.profiles.test_design import feature

    groups = [g for index, g in enumerate(case["groups"]) if index != case["removed_group"]]
    expected = feature(groups)
    assert expected["contributing_groups"] == case["expected_group_count"]
    assert expected["center"] == case["expected_center"]
    assert expected["dispersion"] == case["expected_mad"]
    assert (expected["state"] == "supported") is case["expected_supported"]


@pytest.mark.parametrize("case", VECTORS["evaluation_cases"], ids=lambda c: c["case_id"])
def test_group_vote_and_unknown_denominators(case):
    predictions = [
        p[0] if p and p[0] is not None and all(x == p[0] for x in p) else None
        for p in case["predictions"]
    ]
    known = sum(t is not None for t in case["truth"])
    correct = sum(t is not None and p == t for t, p in zip(case["truth"], predictions, strict=True))
    incorrect = sum(
        t is not None and p is not None and p != t
        for t, p in zip(case["truth"], predictions, strict=True)
    )
    unknown = predictions.count(None)
    groups = len(predictions)
    assert (
        dict(
            groups=groups,
            known_truth=known,
            correct=correct,
            incorrect=incorrect,
            unknown=unknown,
            accuracy=[correct, known],
            unknown_rate=[unknown, groups],
            truth_coverage=[known, groups],
        )
        == case["expected"]
    )


@pytest.mark.parametrize("case", VECTORS["evaluation_cases"], ids=lambda c: c["case_id"])
def test_metric_ratio_literals_and_null_empty_cohorts(case):
    for name in ("accuracy", "unknown_rate", "truth_coverage"):
        numerator, denominator = case["expected"][name]
        with localcontext() as context:
            context.prec = 2200
            value = rounded(Decimal(numerator) / denominator) if denominator else None
        assert value == case["expected_values"][name]


def test_equal_policy_parameters_are_explicit_software_gates():
    assert POLICY["gates"] == dict(
        minimum_common_features=17,
        minimum_common_coverage=dict(numerator=3, denominator=4),
        minimum_scored_labels=2,
        maximum_best_distance=3.0,
        minimum_absolute_margin=0.25,
    )
    assert POLICY["source"]["scope"] == "one_fresh_n6_dataset"
    assert POLICY["source"]["snapshot_selection"] == "one_explicit_revision"
    assert POLICY["source"]["label_use"] == "evaluation_truth_only"


@pytest.mark.parametrize("case", VECTORS["group_outcome_cases"], ids=lambda c: c["case_id"])
def test_truth_and_prediction_group_reasons(case):
    truth_reasons = []
    if None in case["labels"] or any(
        set(reasons) & set(POLICY["evaluation"]["truth_invalid_reasons"])
        for reasons in case["n6_reasons"]
    ):
        truth_reasons.append("label_unverified")
    if len({label for label in case["labels"] if label is not None}) > 1:
        truth_reasons.append("mixed_labels")
    prediction_reasons = []
    if None in case["predictions"]:
        prediction_reasons.append("entry_unknown")
    if len({label for label in case["predictions"] if label is not None}) > 1:
        prediction_reasons.append("entry_disagreement")
    truth = None if truth_reasons else case["labels"][0]
    prediction = None if prediction_reasons else case["predictions"][0]
    assert (truth, truth_reasons) == (case["truth"], case["truth_reasons"])
    assert (prediction, prediction_reasons) == (case["prediction"], case["prediction_reasons"])
