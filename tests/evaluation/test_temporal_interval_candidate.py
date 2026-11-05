"""Invented native-shaped inputs; no real condition-recognition evidence."""

from copy import deepcopy
from fractions import Fraction
from hashlib import sha256
from itertools import product

import pytest

from latency_fingerprinting.evaluation import temporal_interval_candidate as candidate
from latency_fingerprinting.evaluation.contrast_bounds import native_worker_clock_id
from latency_fingerprinting.evaluation.fixture_conditions import CONDITIONS
from tests.evaluation.test_temporal_rate_response import acquisition

CONTEXT = "sha256:" + "b" * 64
RATES = ((30, 30, 24, 30), (30, 20, 16, 30), (30, 10, 8, 30))


def source(identifier, rates=RATES[0]):
    raw = acquisition()
    request = raw["events"][0]["request"]
    request["generation"]["owner"] = identifier
    clock = native_worker_clock_id(request["generation"])
    base = 0
    for phase in ("healthy", "degraded", "relief", "recovery", "post"):
        events = [e for e in raw["events"] if e.get("phase") == phase]
        rows = events[0]["samples"] if phase in ("healthy", "post") else events
        rate = (
            rates[("healthy", "degraded", "relief", "post").index(phase)]
            if phase != "recovery"
            else 30
        )
        for i, row in enumerate(rows):
            row["encoded_buffers"] = base + i * rate // 2
            row["native_read"]["clock_id"] = clock
        base = rows[-1]["encoded_buffers"] + 10
    return raw


def slot(identifier, condition, rates):
    raw = source(identifier, rates)
    binding = candidate.declare_temporal_condition_binding(
        raw,
        condition=condition,
        context_hash=CONTEXT,
        inspection_sha256="sha256:" + sha256(identifier.encode()).hexdigest(),
    )
    return dict(acquisition=raw, binding=binding)


def blocks(count=6, identical=False):
    return {
        f"block-{i}": {
            c: slot(f"case-{i}-{j}", c, RATES[0] if identical else RATES[j])
            for j, c in enumerate(CONDITIONS)
        }
        for i in range(count)
    }


def vector(low, high):
    return {name: (Fraction(low), Fraction(high)) for name in candidate.FEATURES}


def test_interval_distance_encloses_all_box_corners_without_midpoints():
    left, right = vector(0, 2), vector(3, 4)
    lower, upper = candidate._distance(left, right)
    assert (lower, upper) == (1, 4)
    for a in product((0, 2), repeat=3):
        for b in product((3, 4), repeat=3):
            distance = sum(abs(x - y) for x, y in zip(a, b, strict=True)) / 3
            assert lower <= distance <= upper
    assert candidate._distance(vector(-1, 1), vector(0, 2)) == (0, 3)


def test_overlapping_distance_intervals_abstain_despite_midpoint_preference():
    centers = dict(zip(CONDITIONS, (vector(0, 1), vector(1, 2), vector(10, 11)), strict=True))
    distances, winner, gap = candidate._score(vector(0, 1), centers)
    assert distances[CONDITIONS[0]][0] == distances[CONDITIONS[1]][0] == 0
    assert winner is None and gap is None


def test_complete_source_linked_synthetic_folds_and_thresholds_are_conservative():
    result = candidate.fit_temporal_interval_candidate(blocks(), session_id="session")
    assert result["state"] == "candidate_calibration_available"
    assert len(result["folds"]) == 6 and result["calibration_query_count"] == 18
    assert len(result["source_clock_ids"]) == len(result["bindings"]) == 18
    for fold in result["folds"]:
        assert len(fold["training_block_ids"]) == 5
        assert fold["held_out_block_id"] not in fold["training_block_ids"]
        assert fold["complete_and_correct"]
        for row in fold["queries"]:
            assert row["robust_condition"] == row["condition"] and row["uniquely_correct"]
            assert row["robust_gap"]["numerator"] > 0
    assert result["thresholds"]["minimum_gap"]["numerator"] > 0
    assert result["session_components"] == 1 and result["independent_support_groups"] == 0
    assert result["accepted_diagnostic_groups"] == 0 and result["diagnostic_label"] is None
    assert not result["empirical_acceptance"] and not result["acquisition_authority"]


@pytest.mark.parametrize("kind", ["partial", "missing", "unavailable", "ambiguous"])
def test_missing_or_ambiguous_folds_never_create_thresholds(kind):
    data = blocks(5) if kind == "partial" else blocks(identical=kind == "ambiguous")
    if kind == "missing":
        data["block-1"][CONDITIONS[0]] = None
    elif kind == "unavailable":
        row = data["block-1"][CONDITIONS[0]]
        raw = row["acquisition"]
        event = next(e for e in raw["events"] if e.get("phase") == "healthy")
        event["samples"] = event["samples"][:4]
        row["binding"] = candidate.declare_temporal_condition_binding(
            raw,
            condition=CONDITIONS[0],
            context_hash=CONTEXT,
            inspection_sha256=row["binding"]["inspection_sha256"],
        )
    result = candidate.fit_temporal_interval_candidate(data, session_id="s")
    assert result["state"] == "unavailable" and result["thresholds"] is None
    assert result["centers"] == {}
    if kind == "ambiguous":
        assert len(result["folds"]) == 6
        assert all(not f["complete_and_correct"] for f in result["folds"])
        assert all(q["robust_condition"] is None for f in result["folds"] for q in f["queries"])
    if kind == "unavailable":
        assert len(result["unavailable_slots"]) == 1


@pytest.mark.parametrize("condition,rates", list(zip(CONDITIONS, RATES, strict=True)))
def test_truth_free_fresh_query_passes_robust_distance_radius_and_gap(condition, rates):
    result = candidate.score_temporal_interval_candidate(
        source("fresh-query", rates),
        blocks(),
        session_id="s",
        query_session_id="s",
        query_block_id="fresh",
        context_hash=CONTEXT,
    )
    assert result["state"] == "candidate_condition_prediction"
    assert result["predicted_condition"] == condition
    assert result["confidence"] is None and result["diagnostic_label"] is None
    assert not result["empirical_acceptance"]


@pytest.mark.parametrize(
    "kind,reason",
    [
        ("session", "different_query_session"),
        ("block", "query_block_overlap"),
        ("context", "incompatible_query_context"),
        ("source", "query_source_or_clock_overlap"),
        ("clock", "query_source_or_clock_overlap"),
        ("calibration", "calibration_unavailable"),
        ("unavailable", "query_response_unavailable"),
        ("ambiguous", "ambiguous_interval_distances"),
        ("radius", "outside_condition_radius"),
        ("gap", "insufficient_robust_gap"),
    ],
)
def test_query_abstention_preserves_original_model(kind, reason):
    data = blocks(5) if kind == "calibration" else blocks()
    raw, session, block, context = source("fresh"), "s", "new", CONTEXT
    if kind == "session":
        session = "other"
    elif kind == "block":
        block = "block-0"
    elif kind == "context":
        context = "sha256:" + "c" * 64
    elif kind in ("source", "clock"):
        raw = deepcopy(data["block-0"][CONDITIONS[0]]["acquisition"])
        if kind == "clock":
            raw["ignored_metadata"] = "different payload same generation"
    elif kind == "unavailable":
        ref = next(e for e in raw["events"] if e.get("phase") == "healthy")
        ref["samples"] = ref["samples"][:4]
    elif kind == "ambiguous":
        raw = source("fresh", (30, 26, 20, 30))
    elif kind in ("radius", "gap"):
        raw = source("fresh", (30, 28, 22, 30))
    before = candidate.fit_temporal_interval_candidate(data, session_id="s")
    result = candidate.score_temporal_interval_candidate(
        raw,
        data,
        session_id="s",
        query_session_id=session,
        query_block_id=block,
        context_hash=context,
    )
    assert result["state"] == "abstain" and result["predicted_condition"] is None
    assert reason in result["reason_codes"]
    assert candidate.fit_temporal_interval_candidate(data, session_id="s") == before


@pytest.mark.parametrize("kind", ["binding", "context", "inspection", "source", "seventh"])
def test_invalid_declarations_and_reused_source_evidence_rejected(kind):
    data = blocks(7) if kind == "seventh" else blocks()
    a, b = data["block-0"][CONDITIONS[0]], data["block-1"][CONDITIONS[0]]
    if kind == "binding":
        a["binding"]["response_id"] = "changed"
    elif kind == "context":
        b["binding"] = candidate.declare_temporal_condition_binding(
            b["acquisition"],
            condition=CONDITIONS[0],
            context_hash="sha256:" + "d" * 64,
            inspection_sha256=b["binding"]["inspection_sha256"],
        )
    elif kind == "inspection":
        b["binding"]["inspection_sha256"] = a["binding"]["inspection_sha256"]
    elif kind == "source":
        data["block-1"][CONDITIONS[0]] = deepcopy(a)
    with pytest.raises(ValueError, match=candidate.ERROR):
        candidate.fit_temporal_interval_candidate(data, session_id="s")


def test_method_spec_is_detached_and_query_truth_or_cached_fit_not_accepted():
    spec = candidate.temporal_interval_candidate_spec()
    spec["features"].clear()
    assert len(candidate.temporal_interval_candidate_spec()["features"]) == 3
    with pytest.raises(TypeError):
        candidate.score_temporal_interval_candidate(
            source("fresh"),
            blocks(),
            session_id="s",
            query_session_id="s",
            query_block_id="fresh",
            context_hash=CONTEXT,
            truth=CONDITIONS[0],
        )


def test_fold_centers_are_built_from_other_five_sources_only(monkeypatch):
    observed = []
    original = candidate._centers

    def capture(prepared):
        observed.append(set(prepared))
        return original(prepared)

    monkeypatch.setattr(candidate, "_centers", capture)
    result = candidate.fit_temporal_interval_candidate(blocks(), session_id="s")
    assert result["state"] == "candidate_calibration_available"
    for fold, used in zip(result["folds"], observed[:6], strict=True):
        assert used == set(fold["training_block_ids"])
        assert fold["held_out_block_id"] not in used
    assert len(observed[-1]) == 6


def test_query_witness_labels_and_properties_do_not_change_scores():
    data, raw = blocks(), source("fresh")
    arguments = dict(
        session_id="s", query_session_id="s", query_block_id="fresh", context_hash=CONTEXT
    )
    before = candidate.score_temporal_interval_candidate(raw, data, **arguments)
    for event in raw["events"]:
        for row in event.get("samples", [event]):
            row["condition_witness"] = dict(condition="arbitrary", sleep_time_us=99999)
            row["at_ns"] = -1
    after = candidate.score_temporal_interval_candidate(raw, data, **arguments)
    assert before == after
    with pytest.raises(TypeError):
        candidate.fit_temporal_interval_candidate(data, session_id="s", cached_fit={})
