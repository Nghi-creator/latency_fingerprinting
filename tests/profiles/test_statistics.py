"""Production Fraction helpers checked against the previously frozen Decimal/literal oracles."""

import copy
from types import SimpleNamespace

import pytest

from latency_fingerprinting.profiles import ProfileSnapshot
from latency_fingerprinting.profiles.arithmetic import (
    absolute_deviation,
    candidate_support,
    feature_statistics,
    median,
)
from latency_fingerprinting.profiles.selection import selection_reasons

from .cases import NAMES, grouped
from .test_design import VECTORS


@pytest.mark.parametrize("case", VECTORS["numeric_cases"], ids=lambda case: case["case_id"])
def test_exact_binary64_rounding(case):
    def calculate():
        return (
            median(case["values"])
            if case["operation"] == "median"
            else absolute_deviation(*case["values"])
        )

    if case["error"]:
        with pytest.raises(ValueError, match="^invalid_profile_arithmetic$"):
            calculate()
    else:
        value = calculate()
        assert value.hex() == case["expected_hex"]
        assert value == case["expected_value"]


@pytest.mark.parametrize("case", VECTORS["feature_cases"], ids=lambda case: case["case_id"])
def test_feature_stats_against_frozen_independent_oracle(case):
    values = [median(group) for group in case["groups"] if group]
    expected = {k: v for k, v in case["expected"].items() if k != "group_medians"}
    assert feature_statistics(values, len(case["groups"])) == expected


@pytest.mark.parametrize("case", VECTORS["candidate_cases"], ids=lambda case: case["case_id"])
def test_candidate_gates(case):
    result = candidate_support(case["training_groups"], case["active_features"])
    assert result["state"] == case["expected_state"]
    assert result["reason_codes"] == case["expected_reasons"]


@pytest.mark.parametrize("case", VECTORS["selection_cases"], ids=lambda case: case["case_id"])
def test_selection_is_metadata_only(case):
    result, mixed = selection_reasons([SimpleNamespace(**e) for e in case["entries"]])
    assert result == case["expected_reasons"]
    assert bool(mixed) == (case["case_id"] == "mixed_labels")


@pytest.mark.parametrize(
    "values",
    [
        [],
        [True],
        [None],
        ["1"],
        [float("nan")],
        [float("inf")],
        [float("-inf")],
        [10**1000],
        range(3),
        set([1]),
        iter([1]),
        [0.0] * 257,
    ],
)
def test_invalid_or_unbounded_arithmetic(values):
    with pytest.raises(ValueError, match="^invalid_profile_arithmetic$"):
        median(values)


@pytest.mark.parametrize(
    "groups,constants,missing",
    [
        ([[0.0] * 5, [1.0], [2.0], [3.0], [4.0]], 0, ()),
        ([[0.0], [1.0], [2.0], [3.0], [4.0]], 5, ()),
        ([[0.0], [1.0], [2.0], [3.0], [4.0]], 6, ()),
        ([[0.0], [1.0], [2.0], [3.0]], 0, ()),
        ([[0.0], [1.0], [2.0], [3.0], [4.0]], 0, (0,)),
        ([[0.0], [1.0], [2.0], [3.0], [4.0]], 0, (0, 1, 2, 3, 4)),
    ],
)
def test_full_snapshot_reconstructs_independent_decimal_expectations(groups, constants, missing):
    p = grouped(groups, constants=constants, missing_feature_groups=missing)
    snapshot = ProfileSnapshot.model_validate(p)
    assert snapshot.model_dump(mode="json") == p
    if len(groups[0]) == 5:
        assert snapshot.counts.selected_entries == 9
        assert snapshot.counts.selected_groups == 5
        assert snapshot.profiles[0].features[NAMES[0]].center == 2.0
    if missing:
        feature = snapshot.profiles[0].features[NAMES[-1]]
        assert feature.weight == 0
        assert feature.availability.numerator == 5 - len(missing)
    old = copy.deepcopy(p)
    p["profiles"][0]["features"][NAMES[0]]["center"] = 999.0
    assert snapshot.model_dump(mode="json") == old


def test_outlier_overflow_fails_even_with_no_supported_features():
    case = VECTORS["feature_overflow_case"]
    with pytest.raises(ValueError, match="^invalid_profile_arithmetic$"):
        feature_statistics([row[0] for row in case["groups"]], 3)
