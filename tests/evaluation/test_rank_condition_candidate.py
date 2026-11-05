"""Invented inputs only; never empirical validation of rank recognition."""

from copy import deepcopy
from fractions import Fraction
from types import SimpleNamespace

import pytest

from latency_fingerprinting.evaluation import rank_condition_candidate as candidate
from latency_fingerprinting.evaluation.fixture_conditions import CONDITIONS
from tests.evaluation.test_fixture_conditions import blocks, query, slot


def test_six_complete_folds_transform_only_other_five_blocks():
    result = candidate.fit_rank_condition_candidate(blocks(), session_id="s")
    assert result["state"] == "candidate_calibration_available"
    assert len(result["folds"]) == 6 and result["calibration_query_count"] == 18
    for fold in result["folds"]:
        assert fold["held_out_block_id"] not in fold["training_block_ids"]
        assert len(fold["training_block_ids"]) == 5 and fold["support_pool_size"] == 15
        assert fold["complete_and_correct"]
    assert result["thresholds"] == dict(
        class_radius={c: 0.0 for c in CONDITIONS}, minimum_gap=1 / 3
    )
    assert result["input_provenance_kinds"] == ["synthetic"]
    assert result["session_components"] == 1 and result["independent_support_groups"] == 0
    assert not result["empirical_acceptance"] and not result["acquisition_authority"]
    assert result["diagnostic_label"] is None and result["accepted_diagnostic_groups"] == 0


def test_held_out_extreme_cannot_expand_fold_support(monkeypatch):
    data = blocks()
    data["block-0"][CONDITIONS[0]] = slot("extreme", CONDITIONS[0], relief=(0, 120, 240))
    pools = []
    original = candidate.fit_rank_geometry

    def capture(samples, *, feature_names):
        pools.append(deepcopy(samples))
        return original(samples, feature_names=feature_names)

    monkeypatch.setattr(candidate, "fit_rank_geometry", capture)
    result = candidate.fit_rank_condition_candidate(data, session_id="s")
    extreme = data["block-0"][CONDITIONS[0]]["response"].features
    first_name = result["fixed_feature_mask"][0]
    assert len(pools[0]) == 15
    assert all(row[first_name] != extreme[first_name].normalized_value for row in pools[0])
    held = result["folds"][0]["queries"][0]
    assert held["reason_codes"] == ["outside_training_support"]
    assert not held["uniquely_correct"] and held["distances"] == {}
    assert result["state"] == "unavailable" and result["thresholds"] is None
    assert len(result["folds"]) == 6  # No failed fold discarded.


def test_centers_are_medians_after_transform_not_transform_of_even_raw_median():
    def record(value):
        return SimpleNamespace(features={"x": SimpleNamespace(normalized_value=value)})

    prepared = {
        "a": {c: record(v) for c, v in zip(CONDITIONS, (0, 1, 3), strict=True)},
        "b": {c: record(v) for c, v in zip(CONDITIONS, (10, 2, 4), strict=True)},
    }
    geometry, centers = candidate._model(prepared, ["x"])
    assert centers[CONDITIONS[0]]["x"] == Fraction(1, 2)
    raw_median_rank, _ = candidate._transform({"x": 5}, geometry)
    assert raw_median_rank["x"] == Fraction(5, 6)


@pytest.mark.parametrize("kind", ["partial", "missing_slot", "missing_features", "tie"])
def test_unavailable_calibration_retains_failures_and_no_thresholds(kind):
    data = (
        blocks(5)
        if kind == "partial"
        else blocks(identical=kind == "tie", missing=kind == "missing_features")
    )
    if kind == "missing_slot":
        data["block-2"][CONDITIONS[0]] = None
    result = candidate.fit_rank_condition_candidate(data, session_id="s")
    assert result["state"] == "unavailable" and result["thresholds"] is None
    assert result["training_support"] == {} and result["rank_centers"] == {}
    if kind == "tie":
        assert len(result["folds"]) == 6
        assert all(not f["complete_and_correct"] for f in result["folds"])
    if kind == "missing_slot":
        assert result["missing_slots"] == [dict(block_id="block-2", condition=CONDITIONS[0])]


@pytest.mark.parametrize(
    "relief,condition",
    [((0, 60, 120), CONDITIONS[0]), ((0, 30, 60), CONDITIONS[1]), ((0, 0, 0), CONDITIONS[2])],
)
def test_fresh_same_session_query_without_truth(relief, condition):
    result = candidate.score_rank_condition_candidate(
        query(relief=relief), blocks(), session_id="s", query_session_id="s", query_block_id="new"
    )
    assert result["state"] == "candidate_condition_prediction"
    assert result["predicted_condition"] == condition
    assert not result["empirical_acceptance"] and result["diagnostic_label"] is None
    assert result["confidence"] is None and result["accepted_diagnostic_groups"] == 0


@pytest.mark.parametrize(
    "kind,reason",
    [
        ("session", "different_query_session"),
        ("block", "query_block_overlap"),
        ("source", "query_source_overlap"),
        ("partition", "incompatible_query_partition"),
        ("missing", "query_missing_fixed_features"),
        ("support", "outside_training_support"),
        ("radius", "outside_condition_radius"),
        ("gap", "insufficient_query_gap"),
        ("tie", "equal_query_distances"),
        ("calibration", "calibration_unavailable"),
    ],
)
def test_query_gates_abstain_without_learning_from_query(kind, reason):
    data = blocks(5) if kind == "calibration" else blocks()
    q = query()
    session, block = "s", "new"
    if kind == "session":
        session = "different"
    elif kind == "block":
        block = "block-0"
    elif kind == "source":
        q = data["block-0"][CONDITIONS[0]]["response"]
    elif kind == "partition":
        q = query(workload="foreign")
    elif kind == "missing":
        q = query(missing=True)
    elif kind == "support":
        q = query(relief=(0, 120, 240))
    elif kind in ("radius", "gap"):
        q = query(relief=(0, 45, 90))
    elif kind == "tie":
        q = query(relief=(0, 15, 30))
    before = candidate.fit_rank_condition_candidate(data, session_id="s")
    result = candidate.score_rank_condition_candidate(
        q, data, session_id="s", query_session_id=session, query_block_id=block
    )
    assert result["state"] == "abstain" and result["predicted_condition"] is None
    assert reason in result["reason_codes"]
    assert candidate.fit_rank_condition_candidate(data, session_id="s") == before


def test_binding_tamper_duplicate_source_and_seventh_block_rejected():
    data = blocks()
    data["block-0"][CONDITIONS[0]]["binding"]["condition"] = CONDITIONS[1]
    with pytest.raises(ValueError):
        candidate.fit_rank_condition_candidate(data, session_id="s")
    data = blocks()
    data["block-1"] = data["block-0"]
    with pytest.raises(ValueError):
        candidate.fit_rank_condition_candidate(data, session_id="s")
    with pytest.raises(ValueError):
        candidate.fit_rank_condition_candidate(blocks(7), session_id="s")


def test_no_truth_or_cached_fit_argument_and_distinct_method_identity():
    with pytest.raises(TypeError):
        candidate.score_rank_condition_candidate(
            query(),
            blocks(),
            session_id="s",
            query_session_id="s",
            query_block_id="new",
            truth=CONDITIONS[0],
        )
    spec = candidate.rank_condition_candidate_spec()
    assert spec["geometry_content_hash"] != spec["content_hash"]
    spec["training_blocks"] = 1
    assert candidate.rank_condition_candidate_spec()["training_blocks"] == 6
