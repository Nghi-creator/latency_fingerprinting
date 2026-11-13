"""Synthetic fitting and scoring regressions for the shared-window candidate."""

import hashlib
import json
from copy import deepcopy

import pytest

from latency_fingerprinting.evaluation import shared_window_candidate as method
from latency_fingerprinting.evaluation.counter_specific_candidate import (
    counter_specific_candidate_spec,
    declare_counter_specific_binding,
)
from latency_fingerprinting.evaluation.fixture_conditions import CONDITIONS
from tests.evaluation.test_combined_interval_candidate import CONTEXT
from tests.evaluation.test_counter_specific_candidate import point_source
from tests.evaluation.test_counter_specific_projection import seal

SESSION = "engineering-session"


def bind(source, condition, identifier):
    return method.declare_shared_window_binding(
        source,
        condition=condition,
        context_hash=CONTEXT,
        inspection_sha256="sha256:" + hashlib.sha256(identifier.encode()).hexdigest(),
    )


def training(identical=False):
    blocks = {}
    for i in range(6):
        block = {}
        for arm, condition in enumerate(CONDITIONS):
            identifier = f"shared-fit-{i}-{arm}"
            source = point_source(identifier, arm, identical)
            block[condition] = dict(source=source, binding=bind(source, condition, identifier))
        blocks[f"block-{i}"] = block
    return blocks


def score(source, blocks, **overrides):
    args = dict(
        session_id=SESSION,
        query_session_id=SESSION,
        query_block_id="later-block",
        context_hash=CONTEXT,
    )
    return method.score_shared_window_candidate(source, blocks, **(args | overrides))


def test_complete_fit_and_truth_free_scoring_for_every_class():
    blocks = training()
    before = deepcopy(blocks)
    fit = method.fit_shared_window_candidate(blocks, session_id=SESSION)
    assert fit["state"] == "candidate_calibration_available"
    assert fit["calibration_query_count"] == 18
    assert all(fold["complete_and_correct"] for fold in fit["folds"])
    for fold in fit["folds"]:
        assert len(fold["training_block_ids"]) == 5
        assert fold["held_out_block_id"] not in fold["training_block_ids"]
        for query in fold["queries"]:
            assert all(
                pair["state"] == "strictly_separated"
                for pair in query["separation_comparisons"][query["condition"]].values()
            )
    for arm, condition in enumerate(CONDITIONS):
        result = score(point_source(f"fresh-{arm}", arm), blocks)
        assert result["predicted_condition"] == condition
        assert result["experiment_id"] == fit["experiment_id"]
        assert result["empirical_acceptance"] is False
    assert blocks == before


def test_ambiguous_folds_disable_calibration_and_scoring():
    blocks = training(identical=True)
    fit = method.fit_shared_window_candidate(blocks, session_id=SESSION)
    assert fit["state"] == "unavailable"
    assert fit["reason_codes"] == ["calibration_folds_not_all_robustly_correct"]
    assert fit["thresholds"] is None and fit["centers"] == {}
    assert fit["calibration_query_count"] == 18
    result = score(point_source("later"), blocks)
    assert result["reason_codes"] == ["calibration_unavailable"]
    assert result["predicted_condition"] is None
    assert result["separation_comparisons"] == {}


def test_missing_slot_disables_all_folds():
    blocks = training()
    blocks["block-0"][CONDITIONS[0]] = None
    fit = method.fit_shared_window_candidate(blocks, session_id=SESSION)
    assert fit["reason_codes"] == ["incomplete_blocks"]
    assert fit["thresholds"] is None and fit["folds"] == []


def test_binding_requires_new_projection_identity():
    assert (
        method.shared_window_candidate_spec()["content_hash"]
        != (counter_specific_candidate_spec()["content_hash"])
    )
    blocks = training()
    condition = CONDITIONS[0]
    slot = blocks["block-0"][condition]
    slot["binding"] = declare_counter_specific_binding(
        slot["source"],
        condition=condition,
        context_hash=CONTEXT,
        inspection_sha256=slot["binding"]["inspection_sha256"],
    )
    with pytest.raises(ValueError, match=method.ERROR):
        method.fit_shared_window_candidate(blocks, session_id=SESSION)


@pytest.mark.parametrize(
    "case,reason",
    [
        ("session", "different_query_session"),
        ("context", "incompatible_query_context"),
        ("block", "query_block_overlap"),
        ("source", "query_source_or_clock_overlap"),
    ],
)
def test_query_guards_precede_comparison(case, reason):
    blocks = training()
    query = point_source("later")
    changes = {}
    if case == "session":
        changes["query_session_id"] = "other-session"
    elif case == "context":
        changes["context_hash"] = "sha256:" + "a" * 64
    elif case == "block":
        changes["query_block_id"] = "block-0"
    else:
        query = blocks["block-0"][CONDITIONS[0]]["source"]
    result = score(query, blocks, **changes)
    assert reason in result["reason_codes"]
    assert result["state"] == "abstain" and result["separation_comparisons"] == {}


def test_separation_alone_does_not_bypass_radius():
    value = point_source("shifted-post")
    raw = json.loads(value["acquisition_json"])
    post = next(
        e["samples"]
        for e in raw["events"]
        if e["kind"] == "n11_pacing_reference" and e["phase"] == "post"
    )
    for index, row in enumerate(post):
        row["encoded_buffers"] += index
        row["encoded_counter_read"]["value"] = row["encoded_buffers"]
    result = score(seal(value, raw), training())
    assert "outside_condition_radius" in result["reason_codes"]
    assert result["predicted_condition"] is None
    assert result["separation_comparisons"]


def test_positive_certificate_below_frozen_gap_still_abstains(monkeypatch):
    blocks = training()
    fit = method.fit_shared_window_candidate(blocks, session_id=SESSION)
    minimum_gap = fit["thresholds"]["minimum_gap"]
    compare = method.compare_shared_window_centers

    def weaker_query_certificate(phase_rates, centers):
        certificate = compare(phase_rates, centers)
        # Fold centers use five samples. The final full-training center is called last.
        if weaker_query_certificate.calls == 18:
            for pair in certificate["comparisons"][CONDITIONS[0]].values():
                pair["lower"] = {
                    "numerator": minimum_gap["numerator"],
                    "denominator": 2 * minimum_gap["denominator"],
                }
        weaker_query_certificate.calls += 1
        return certificate

    weaker_query_certificate.calls = 0
    monkeypatch.setattr(method, "compare_shared_window_centers", weaker_query_certificate)
    result = score(point_source("fresh-small-certified-gap"), blocks)
    assert weaker_query_certificate.calls == 19
    assert result["reason_codes"] == ["insufficient_robust_gap"]
    assert result["predicted_condition"] is None


def test_unavailable_query_abstains_before_comparison():
    value = point_source("wide-getter")
    raw = json.loads(value["acquisition_json"])
    row = next(e for e in raw["events"] if e.get("kind") == "n11_pair_native")
    end = row["native_read"]["read_start_ns"] + 101_000_000
    row["native_read"]["read_end_ns"] = end
    row["encoded_counter_read"]["read_end_ns"] = end
    result = score(seal(value, raw), training())
    assert result["reason_codes"] == ["query_response_unavailable"]
    assert result["separation_comparisons"] == {}
