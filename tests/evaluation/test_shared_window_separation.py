"""Synthetic certificates and witnesses; no calibration or study measurements."""

from copy import deepcopy
from fractions import Fraction as F
from itertools import product

import pytest

from latency_fingerprinting.evaluation import shared_window_separation as model

OWN, RIVAL, OTHER = model.CONDITIONS
CPU = "cpu_quota_fraction"


def ratio(value):
    v = F(value)
    return dict(numerator=v.numerator, denominator=v.denominator)


def interval(a, b=None):
    return dict(lower=ratio(a), upper=ratio(a if b is None else b))


def fixture():
    rates = {g: {p: interval(int(g == "encoded")) for p in model.PHASES} for g in model.GROUPS}
    centers = {
        c: {n: interval(10 if c == OTHER else 0) for n in model.FEATURES} for c in model.CONDITIONS
    }
    return rates, centers


def cpu_fixture(rival):
    rates, centers = fixture()
    rates[CPU].update(degraded=interval(0, 2), relief=interval(2))
    for feature in list(model.GROUPS[CPU])[:2]:
        centers[RIVAL][feature] = interval(rival)
    return rates, centers


def frac(value):
    return F(value["numerator"], value["denominator"])


def test_shared_difference_certifies_when_feature_boxes_do_not():
    # x=D and y=2-D. Each independent feature can reach 2, but not both.
    # With candidate (0,0) and rival (3,3), the exact margin is always 2/9.
    rates, centers = cpu_fixture(3)
    original = deepcopy((rates, centers))
    result = model.compare_shared_window_centers(rates, centers)
    pair = result["comparisons"][OWN][RIVAL]
    assert result["separated_condition"] == OWN
    assert frac(pair["root_lower"]) == F(-2, 9)
    assert 0 < frac(pair["lower"]) <= F(2, 9) == frac(pair["upper"])
    assert pair["splits"] > 0
    assert (rates, centers) == original


def test_encoded_shared_denominator_and_numerator_are_not_independent():
    rates, centers = fixture()
    rates["encoded"]["degraded"] = interval(1, 2)
    centers[OWN]["encoded.relief_vs_degraded"] = interval(-1)
    centers[RIVAL]["encoded.degraded_vs_healthy"] = interval(F(11, 5))
    # Margin is (6/5 - 2*(D + 1/D - 2))/9, minimized at D=2.
    result = model.compare_shared_window_centers(rates, centers)
    pair = result["comparisons"][OWN][RIVAL]
    assert result["separated_condition"] == OWN
    assert frac(pair["root_lower"]) < 0 < frac(pair["lower"]) <= F(1, 45)
    assert frac(pair["upper"]) >= F(1, 45)


def test_real_tie_and_unresolved_search_both_abstain_for_distinct_reasons():
    for rival, reason in [
        (2, "nonpositive_witness"),
        (F(20001, 10000), "unresolved_at_split_limit"),
    ]:
        result = model.compare_shared_window_centers(*cpu_fixture(rival))
        pair = result["comparisons"][OWN][RIVAL]
        assert result["state"] == "abstain" and result["separated_condition"] is None
        assert pair["state"] == reason
        if rival > 2:
            assert pair["splits"] == model.MAX_SPLITS
            assert frac(pair["lower"]) <= 0 < frac(pair["upper"])


def test_recovery_coordinate_and_center_uncertainty_are_retained():
    rates, centers = fixture()
    feature = "encoded.post_vs_healthy"
    centers[OWN][feature] = interval(-1, 1)
    centers[RIVAL][feature] = interval(1)
    result = model.compare_shared_window_centers(rates, centers)
    assert result["state"] == "abstain"
    assert frac(result["comparisons"][OWN][RIVAL]["upper"]) == 0
    centers[OWN][feature] = interval(0)
    assert model.compare_shared_window_centers(rates, centers)["separated_condition"] == OWN


def test_certificate_encloses_grid_and_reported_witness_is_feasible():
    rates, centers = cpu_fixture(3)
    rates[CPU]["healthy"] = interval(0, 1)
    centers[OWN][list(model.GROUPS[CPU])[0]] = interval(-1, 0)
    pair = model.compare_shared_window_centers(rates, centers)["comparisons"][OWN][RIVAL]

    def objective(h, d):
        # Direct enumeration of both uncertain own endpoints, rival is a point.
        return min(
            (abs(d - h - 3) + abs(2 - d - 3) - abs(d - h - own) - abs(2 - d)) / 9 for own in (-1, 0)
        )

    for h, d in product([F(i, 8) for i in range(9)], [F(i, 8) for i in range(17)]):
        assert frac(pair["lower"]) <= objective(h, d)
    witness = pair["witness_rates"][CPU]
    h, d = frac(witness["healthy"]), frac(witness["degraded"])
    assert 0 <= h <= 1 and 0 <= d <= 2
    assert frac(pair["upper"]) == objective(h, d)


@pytest.mark.parametrize(
    "invalid",
    [
        "missing_phase",
        "zero_denominator",
        "negative_cpu",
        "missing_coordinate",
        "float",
        "huge",
        "reversed",
    ],
)
def test_invalid_inputs_never_produce_a_certificate(invalid):
    rates, centers = fixture()
    if invalid == "missing_phase":
        del rates[CPU]["post"]
    elif invalid == "zero_denominator":
        rates["encoded"]["healthy"] = interval(0, 1)
    elif invalid == "negative_cpu":
        rates[CPU]["post"] = interval(-1)
    elif invalid == "missing_coordinate":
        del centers[OWN][model.FEATURES[0]]
    elif invalid == "float":
        rates[CPU]["post"]["lower"]["numerator"] = 0.0
    elif invalid == "huge":
        rates[CPU]["post"] = interval(1 << model.MAX_INPUT_BITS)
    else:
        rates[CPU]["post"] = interval(2, 1)
    with pytest.raises(ValueError, match=model.ERROR):
        model.compare_shared_window_centers(rates, centers)
