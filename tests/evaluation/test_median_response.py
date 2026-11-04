"""Independent synthetic checks for an opt-in experiment, never real label evidence."""

import hashlib
from types import SimpleNamespace

import pytest

from latency_fingerprinting.analytical.responses import derive_analytical_response
from latency_fingerprinting.evaluation.median_response import (
    ERROR,
    METHOD_CONTENT_HASH,
    _rms,
    compare_engineering_responses,
    median_response_method_spec,
    pacing_contrast_preflight,
    summarize_engineering_responses,
)
from latency_fingerprinting.models import FeaturePolicyV1, ObservationRecordV2
from latency_fingerprinting.profiles.arithmetic import feature_statistics
from tests.analytical.cases import policy_payload
from tests.models.v2_cases import pair_payload, window_payload


def response(identifier, *, relief=(0, 60, 120), missing=False, workload=None):
    pair = pair_payload()
    pair["comparison_case_id"] = identifier
    pair["observation_id"] = identifier + "-observation"
    pair["relief_window"] = window_payload(phase="relief", values=relief)
    for phase in ("degraded", "relief"):
        w = pair[phase + "_window"]
        w["comparison_case_id"] = identifier
        w["run_id"] = identifier + "-" + phase
        w["source_artifact"]["content_hash"] = (
            "sha256:"
            + hashlib.sha256(
                ("synthetic independent acquisition " + identifier + phase).encode()
            ).hexdigest()
        )
        if workload:
            w["context"]["workloadId"] = workload
        if missing:
            unavailable = window_payload(phase=phase, values=(None, None, None))
            for name in w["measurements"]:
                if name.startswith("client."):
                    w["measurements"][name] = unavailable["measurements"][name]
    return derive_analytical_response(
        ObservationRecordV2.model_validate(pair), FeaturePolicyV1.model_validate(policy_payload())
    )


def groups(prefix, **kwargs):
    return {f"{prefix}-{i}": [response(f"{prefix}-{i}", **kwargs)] for i in range(5)}


def test_constant_features_are_numeric_without_a_dispersion_floor():
    original = feature_statistics([0.0] * 5, 5)
    assert original["reason_codes"] == ["zero_dispersion"]
    result = summarize_engineering_responses(groups("zero"))
    assert result["state"] == "computable" and result["numeric_feature_count"] == 22
    assert all(f["center"] == f["raw_mad"] == 0 for f in result["features"].values())
    assert all(f["unique_group_values"] == 1 for f in result["features"].values())
    assert result["dispersion_used_as_divisor"] is False
    assert result["diagnostic_label"] is None and result["accepted_diagnostic_groups"] == 0


def test_majority_ties_with_nonzero_outliers_are_not_misreported_as_constant():
    rows = groups("majority")
    rows["majority-3"] = [response("majority-3", relief=(0, 30, 60))]
    rows["majority-4"] = [response("majority-4", relief=(0, 15, 30))]
    result = summarize_engineering_responses(rows)
    assert all(f["state"] == "numeric" and f["raw_mad"] == 0 for f in result["features"].values())
    assert all(f["unique_group_values"] == 3 for f in result["features"].values())


def test_constant_different_centers_have_finite_unscaled_distances_but_no_label():
    query = response("query")
    result = compare_engineering_responses(
        query, {"zero": groups("a"), "half": groups("b", relief=(0, 30, 60))}
    )
    assert result["state"] == "distances_available"
    assert result["comparisons"]["zero"]["distance"] == 0
    assert result["comparisons"]["half"]["distance"] == 0.5
    assert result["distance_gap"] == 0.5
    assert result["diagnostic_label"] is None
    assert result["classification_authority"] == "unavailable_experimental_method"


def test_identical_centers_and_equal_distances_cannot_create_informative_contrast():
    query = response("query", relief=(0, 30, 60))
    same = compare_engineering_responses(query, {"a": groups("a"), "b": groups("b")})
    assert same["state"] == "unavailable" and same["reason_codes"] == ["identical_centers"]
    tied = compare_engineering_responses(
        query, {"a": groups("a"), "b": groups("b", relief=(0, 0, 0))}
    )
    assert tied["reason_codes"] == ["equal_distances"]
    one = compare_engineering_responses(query, {"a": groups("a")})
    assert one["state"] == "unavailable" and one["comparisons"] == {}


def test_duplicate_responses_within_a_group_do_not_add_votes():
    rows = groups("a")
    original = summarize_engineering_responses(rows)
    rows["a-0"] *= 3
    repeated = summarize_engineering_responses(rows)
    assert repeated["features"] == original["features"]
    assert repeated["response_ids"] == original["response_ids"]
    assert len(repeated["group_ids"]) == 5 and repeated["input_rows"] == 7


def test_aliases_cannot_inflate_groups_or_competing_profiles():
    rows = groups("a")
    rows["alias"] = rows["a-0"]
    with pytest.raises(ValueError, match=ERROR):
        summarize_engineering_responses(rows)
    with pytest.raises(ValueError, match=ERROR):
        compare_engineering_responses(response("q"), {"a": groups("a"), "alias": groups("a")})


def test_query_source_overlap_blocks_distances_even_with_changed_group_name():
    rows = groups("a")
    result = compare_engineering_responses(rows["a-0"][0], {"a": rows, "b": groups("b")})
    assert result["reason_codes"] == ["query_source_overlap"]
    assert result["comparisons"] == {} and result["diagnostic_label"] is None


def test_incompatible_partitions_do_not_pool_or_compete():
    rows = groups("a")
    rows["b"] = [response("b", workload="different-workload")]
    with pytest.raises(ValueError, match=ERROR):
        summarize_engineering_responses(rows)
    result = compare_engineering_responses(
        response("q"), {"a": groups("a"), "b": groups("b", workload="other")}
    )
    assert result["state"] == "unavailable"
    assert result["reason_codes"] == ["insufficient_compatible_profiles"]


def test_small_group_count_stays_unavailable_and_order_is_deterministic():
    rows = groups("a")
    summary = summarize_engineering_responses(rows)
    assert summarize_engineering_responses(dict(reversed(list(rows.items())))) == summary
    del rows["a-4"]
    result = summarize_engineering_responses(rows)
    assert result["state"] == "unavailable" and result["numeric_feature_count"] == 0
    assert "insufficient_training_groups" in result["reason_codes"]


def test_missing_values_remain_missing_and_cannot_pass_numeric_coverage():
    result = summarize_engineering_responses(groups("a", missing=True))
    assert result["state"] == "unavailable"
    for name, feature in result["features"].items():
        if name.startswith("client."):
            assert feature["center"] is None and feature["raw_mad"] is None
            assert feature["contributing_groups"] == 0 and feature["group_values"] == []


@pytest.mark.parametrize("value", [1e-200, 1e308])
def test_unrepresentable_squared_residual_is_rejected(value):
    query = SimpleNamespace(features={"f": SimpleNamespace(normalized_value=value)})
    with pytest.raises(ValueError):
        _rms(query, {"f": {"center": 0.0}}, ["f"])


@pytest.mark.parametrize("bad", [{}, {"g": []}, {True: [response("a")]}, {"g": (None,)}])
def test_invalid_bounded_inputs_fail_closed(bad):
    with pytest.raises(ValueError, match=ERROR):
        summarize_engineering_responses(bad)


def test_modeled_contrast_preserves_safety_and_does_not_authorize_acquisition():
    old = pacing_contrast_preflight(prior_fps=30, target_fps=24, delay_us=50_000)
    assert old["modeled_ceiling"] == {"numerator": 20, "denominator": 1}
    assert old["modeled_crossing"] is False
    new = pacing_contrast_preflight(prior_fps=30, target_fps=24, delay_us=37_500)
    assert new["modeled_ceiling"] == {"numerator": 80, "denominator": 3}
    assert new["modeled_crossing"] is True
    assert new["measured_contrast"] == new["diagnostic_utility"] == "unavailable"
    assert new["acquisition_authority"] is False
    for args in [
        dict(prior_fps=30, target_fps=18, delay_us=37_500),
        dict(prior_fps=30, target_fps=24, delay_us=True),
        dict(prior_fps=30, target_fps=30, delay_us=37_500),
    ]:
        with pytest.raises(ValueError, match=ERROR):
            pacing_contrast_preflight(**args)


def test_method_identity_is_explicit_and_returned_spec_cannot_change_it():
    spec = median_response_method_spec()
    assert spec["content_hash"] == METHOD_CONTENT_HASH
    assert spec["minimum_numeric_features"] == 17
    assert spec["classification_thresholds"] is None
    spec["feature_names"].clear()
    spec["minimum_feature_availability"]["numerator"] = 0
    assert len(median_response_method_spec()["feature_names"]) == 22
    assert median_response_method_spec()["minimum_feature_availability"]["numerator"] == 4


def test_raw_source_aliases_and_response_budget_fail_before_fitting():
    a = response("a")
    b = response("b")
    pair = b.observation.model_dump(mode="json", by_alias=False)
    pair["degraded_window"]["source_artifact"]["content_hash"] = (
        a.observation.degraded_window.source_artifact.content_hash
    )
    alias = derive_analytical_response(ObservationRecordV2.model_validate(pair), b.policy)
    with pytest.raises(ValueError, match=ERROR):
        summarize_engineering_responses({"a": [a], "b": [alias]})
    with pytest.raises(ValueError, match=ERROR):
        summarize_engineering_responses({"a": [a] * 257})
