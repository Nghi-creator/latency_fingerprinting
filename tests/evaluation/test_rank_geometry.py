"""Synthetic properties only; no empirical condition-recognition evidence."""

from copy import deepcopy
from dataclasses import FrozenInstanceError
from fractions import Fraction

import pytest

from latency_fingerprinting.evaluation.rank_geometry import (
    RankGeometry,
    fit_rank_geometry,
    rank_distance,
    rank_geometry_spec,
)


def fit(values):
    return fit_rank_geometry([dict(x=v) for v in values], feature_names=["x"])


def test_ties_frequency_and_unseen_interior_midrank():
    geometry = fit([0, 0, 2, 4])
    # midranks: 0 => 1/4, unseen 1 => 1/2, 2 => 5/8, 4 => 7/8.
    assert rank_distance(dict(x=0), dict(x=4), geometry)["distance"] == 0.625
    assert rank_distance(dict(x=1), dict(x=2), geometry)["distance"] == 0.125
    assert rank_distance(dict(x=0), dict(x=0), geometry)["distance"] == 0


def test_strict_monotone_change_of_units_preserves_distance():
    values = [-8, -2, -2, 1, 7]
    original = rank_distance(dict(x=-2), dict(x=7), fit(values))
    transformed = rank_distance(dict(x=(-2) ** 3), dict(x=7**3), fit([v**3 for v in values]))
    assert original == transformed
    assert rank_distance(dict(x=7), dict(x=-2), fit(list(reversed(values)))) == original


def test_constant_features_zero_without_epsilon_and_change_unavailable():
    geometry = fit([0, 0, 0])
    assert rank_distance(dict(x=0), dict(x=-0.0), geometry)["distance"] == 0
    changed = rank_distance(dict(x=1), dict(x=0), geometry)
    assert changed["reason_codes"] == ["outside_training_support"]
    assert changed["distance"] is None and changed["feature_distances"] == {}


def test_equal_bounded_contributions_prevent_large_units_dominating():
    geometry = fit_rank_geometry(
        [dict(x=0, y=-1e308), dict(x=1, y=1e308)], feature_names=["x", "y"]
    )
    result = rank_distance(dict(x=0, y=-1e308), dict(x=1, y=1e308), geometry)
    assert result["distance"] == 0.5
    assert result["feature_distances"] == dict(x=0.5, y=0.5)
    assert not result["empirical_acceptance"] and not result["acquisition_authority"]


def test_missing_and_outside_report_all_failures_without_partial_distance():
    geometry = fit_rank_geometry([dict(x=0, y=0), dict(x=1, y=1)], feature_names=["x", "y"])
    result = rank_distance(dict(x=2), dict(x=0, y=0), geometry)
    assert result["reason_codes"] == ["missing_frozen_features", "outside_training_support"]
    assert result["missing_features"] == ["y"] and result["outside_support_features"] == ["x"]
    assert result["distance"] is None and result["feature_distances"] == {}


def test_geometry_detaches_inputs_and_spec_is_detached():
    rows = [dict(x=0), dict(x=1)]
    names = ["x"]
    geometry = fit_rank_geometry(rows, feature_names=names)
    before = deepcopy(geometry)
    rows[0]["x"] = 500
    names[0] = "other"
    assert geometry == before
    with pytest.raises(FrozenInstanceError):
        geometry.support = ()
    spec = rank_geometry_spec()
    spec["distance"] = "changed"
    assert rank_geometry_spec()["distance"] != "changed"


@pytest.mark.parametrize("value", [True, "1", None, float("nan"), float("inf"), 10**400])
def test_non_finite_or_non_numeric_inputs_rejected_at_fit_and_distance(value):
    with pytest.raises(ValueError, match="invalid_rank_geometry_input"):
        fit([0, value])
    with pytest.raises(ValueError, match="invalid_rank_geometry_input"):
        rank_distance(dict(x=value), dict(x=0), fit([0, 1]))


@pytest.mark.parametrize(
    "samples,names",
    [
        ([], ["x"]),
        ([dict(x=1)], ["x"]),
        ([{}, {}], ["x"]),
        ([dict(x=0), dict(x=1)], []),
        ([dict(x=0), dict(x=1)], ["x", "x"]),
    ],
)
def test_invalid_training_pool_or_frozen_mask_rejected(samples, names):
    with pytest.raises(ValueError):
        fit_rank_geometry(samples, feature_names=names)


def test_manual_geometry_must_be_immutable_sorted_and_rectangular():
    for support in [
        (),
        (("x", (Fraction(1), Fraction(0))),),
        (("x", (0, 1)),),
        (("x", (Fraction(0), Fraction(1))), ("y", (Fraction(0), Fraction(1), Fraction(2)))),
    ]:
        with pytest.raises(ValueError):
            RankGeometry(support)


def test_query_cannot_update_training_support_and_labels_are_not_accepted():
    geometry = fit([0, 1])
    assert rank_distance(dict(x=100), dict(x=0), geometry)["state"] == "unavailable"
    assert geometry == fit([0, 1])
    with pytest.raises(TypeError):
        fit_rank_geometry([dict(x=0), dict(x=1)], feature_names=["x"], truth="condition")
