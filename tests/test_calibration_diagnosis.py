"""Synthetic forensic diagnostics; never empirical method selection or query validation."""

import hashlib
import json
from copy import deepcopy
from fractions import Fraction as F
from itertools import combinations_with_replacement, product

import pytest

from latency_fingerprinting.evaluation.counter_specific_candidate import (
    counter_specific_candidate_spec,
    fit_counter_specific_candidate,
)
from tests.evaluation.test_counter_specific_candidate import training
from tests.test_n11_experiment_tools import tool

diagnostic = tool("diagnose_counter_specific_fit")


def fitted(identical=False):
    blocks = training(identical)
    return {
        "method_content_hash": counter_specific_candidate_spec()["content_hash"],
        "training": blocks,
        "session_id": "diagnostic-session",
        "calibration": fit_counter_specific_candidate(blocks, session_id="diagnostic-session"),
    }


def test_stable_synthetic_fit_reconstructs_all_distances_without_changing_anything():
    value = fitted()
    before = deepcopy(value)
    report = diagnostic.diagnose_fit(value)
    assert report["all_recorded_distances_reconstructed_exactly"] is True
    assert report["query_cases_opened"] == 0
    assert report["empirical_acceptance"] is False
    assert len(report["cases"]) == 18
    assert all(s["robust_correct"] == 6 for s in report["condition_summary"].values())
    assert report["exploratory_only"]["midpoint_truth_strictly_closest_count"] == 18
    assert value == before
    for case in report["cases"]:
        for comparison in case["pairwise_truth_margins"].values():
            terms = comparison["coordinate_terms_unscaled"]
            assert len(terms) == 9
            total = sum(diagnostic.fraction(v["independent_margin"]) for v in terms.values()) / 9
            assert total == diagnostic.fraction(comparison["independent_margin"])


def test_identical_classes_remain_ambiguous_in_all_diagnostic_views():
    report = diagnostic.diagnose_fit(fitted(identical=True))
    assert all(s["ambiguous"] == 6 for s in report["condition_summary"].values())
    assert report["exploratory_only"]["midpoint_truth_strictly_closest_count"] == 0
    assert report["exploratory_only"]["shared_query_truth_strictly_separated_count"] == 0
    assert report["thresholds_unchanged"] is None


def test_shared_query_example_proves_independent_extrema_can_be_loose():
    query, own, rival = (F(0), F(10)), (F(-10), F(-10)), (F(-20), F(-20))
    independent = (
        diagnostic.distance_terms(query, rival)[0] - diagnostic.distance_terms(query, own)[1]
    )
    assert independent == 0
    assert diagnostic.shared_query_gap_lower(query, own, rival) == 10


def test_shared_query_piecewise_bound_matches_exhaustive_rational_grid():
    intervals = [tuple(map(F, pair)) for pair in combinations_with_replacement(range(-1, 2), 2)]
    for query, own, rival in product(intervals, repeat=3):
        grid = [F(i, 8) for i in range(int(query[0] * 8), int(query[1] * 8) + 1)]
        exhaustive = min(
            max(F(0), rival[0] - x, x - rival[1]) - max(abs(x - own[0]), abs(x - own[1]))
            for x in grid
        )
        shared = diagnostic.shared_query_gap_lower(query, own, rival)
        independent = (
            diagnostic.distance_terms(query, rival)[0] - diagnostic.distance_terms(query, own)[1]
        )
        assert shared == exhaustive
        assert shared >= independent


@pytest.mark.parametrize("kind", ["method", "distance", "threshold", "source"])
def test_wrong_method_or_changed_frozen_fit_cannot_be_explained_as_original(kind):
    value = fitted()
    if kind == "method":
        value["method_content_hash"] = "sha256:" + "0" * 64
    elif kind == "distance":
        value["calibration"]["folds"][0]["queries"][0]["distances"] = {}
    elif kind == "threshold":
        value["calibration"]["thresholds"] = None
    else:
        next(iter(value["training"].values()))["no_injected_fault"]["source"][
            "acquisition_json"
        ] += " "
    with pytest.raises(ValueError):
        diagnostic.diagnose_fit(value)


def test_hash_binding_exclusive_outputs_and_frozen_input_preservation(tmp_path):
    input_dir = tmp_path / "frozen"
    input_dir.mkdir()
    path = input_dir / "fit.json"
    raw = (json.dumps(fitted(), indent=2) + "\n").encode()
    path.write_bytes(raw)
    digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    output = tmp_path / "diagnosis"
    with pytest.raises(ValueError, match="byte hash differs"):
        diagnostic.diagnose_file(path, "wrong", output)
    assert not output.exists()
    with pytest.raises(ValueError, match="separate from frozen inputs"):
        diagnostic.diagnose_file(path, digest, input_dir / "diagnosis")
    report = diagnostic.diagnose_file(path, digest, output)
    assert report["input_fit_sha256"] == digest
    assert path.read_bytes() == raw
    with pytest.raises(FileExistsError):
        diagnostic.diagnose_file(path, digest, output)
