"""Precision budgeting and frozen-input custody regressions."""

import hashlib
import json
from fractions import Fraction as F

import pytest

from tests.evaluation.test_counter_specific_candidate import training
from tests.test_n11_experiment_tools import tool

planner = tool("plan_shared_window_precision")


def test_rate_box_encloses_both_rounding_and_elapsed_extremes():
    rate, duration, tick, error = F(91, 3), F(5), F(1), F(1, 1000)
    lo, hi = planner.planned_rate_bounds(rate, duration, tick, error, F(1, 2))
    for rounding in (-F(1, 2), F(1, 2)):
        for guard in (-tick, tick):
            for elapsed in (duration - error, duration + error):
                assert lo <= (rate * duration + rounding + guard) / elapsed <= hi
    assert planner.planned_rate_bounds(F(0), duration, tick, error, F(1, 2))[0] == 0


def test_planning_reports_both_uncertainty_costs_and_keeps_input_bytes(tmp_path):
    path = tmp_path / "fit.json"
    raw = json.dumps({"training": training()}).encode()
    path.write_bytes(raw)
    digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError, match="hash differs"):
        planner.plan(path, "sha256:" + "0" * 64)
    result = planner.plan(path, digest)
    assert path.read_bytes() == raw
    assert result["query_cases_used"] == 0
    assert result["empirical_acceptance"] is False
    assert len(result["scenarios"]) == 7
    for scenario in result["scenarios"]:
        assert scenario["pair_count"] == 36
        for pair in scenario["comparisons"]:
            assert F(**pair["center_penalty"]) >= 0
            assert F(**pair["query_penalty"]) >= 0
            assert F(**pair["sufficient_lower"]) == (
                F(**pair["nominal_margin"]) - F(**pair["combined_penalty"])
            )
