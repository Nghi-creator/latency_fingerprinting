"""Source and provenance checks for the event-span recognition input."""

import hashlib
import json
from itertools import pairwise

import pytest

from latency_fingerprinting.evaluation.shared_window_projection import project_shared_window_source
from tests.evaluation.test_combined_interval_candidate import source
from tests.evaluation.test_counter_specific_candidate import point_source
from tests.evaluation.test_counter_specific_projection import rows, seal

OFFSET = 1_000_000_000


def event_source(identifier="event-fixture", arm=0):
    origin = str(OFFSET + 12345)
    value = source(identifier, arm, step_ns=565_000_000, controller_origin_ns=origin)
    raw = json.loads(value["acquisition_json"])
    anchors = [(0, 0)]
    for row in rows(raw):
        read = row["native_read"]
        read["read_start_ns"] += OFFSET
        read["read_end_ns"] += OFFSET
        row["encoded_buffers"] += 1
        count = row["encoded_buffers"]
        anchors.append((read["read_start_ns"] - 100, count))
        row["encoded_counter_read"] = dict(
            **read,
            scope="reported_encoded_counter_only_not_other_snapshot_fields",
            underlying_counter_freshness="not_authenticated_by_read_brackets",
            live_authority=False,
            value=count,
        )
        row["encoded_counter_read"]["method"] = "native-encoded-counter-read-brackets-v1"
    stop, count = anchors[-1]
    anchors.append((stop + 30_000_000, count + 1))
    trace_rows = []
    for (start, first), (end, last) in pairwise(anchors):
        for ordinal in range(first + 1, last + 1):
            at = start + (ordinal - first) * (end - start) // (last - first)
            trace_rows.append([ordinal, at - 10, at])
    boundaries = []
    for event in raw["events"]:
        kind = event["kind"]
        if kind == "n11_pacing_reference":
            phase = event["phase"]
            boundaries.extend(
                dict(phase=phase, edge=edge, at_ns=event["samples"][i]["at_ns"])
                for edge, i in (("start", 0), ("end", -1))
            )
        elif kind in ("n11_pair_phase_started", "n11_pair_phase_completed"):
            edge = "start" if kind.endswith("started") else "end"
            boundaries.append(dict(phase=event["phase"], edge=edge, at_ns=event["at_ns"]))
    windows = {}
    for boundary in boundaries:
        windows.setdefault(boundary["phase"], {})["phase_" + boundary["edge"] + "_ns"] = (
            boundary["at_ns"] + OFFSET
        )
    n = len(trace_rows)
    raw["events"].append(
        dict(
            kind="n11_encoded_event_trace",
            method="n11-contained-encoded-event-trace-v1",
            state="count_reconciled",
            reason_codes=[],
            worker_clock_id=next(rows(raw))["native_read"]["clock_id"],
            controller_origin_ns=origin,
            controller_time_namespace="time:[123]",
            controller_boundaries=boundaries,
            windows=windows,
            trace=dict(
                origin_ns="12345",
                time_namespace="time:[123]",
                buffer_list=False,
                observed=n,
                rows=trace_rows,
                identity_read=dict(
                    start_ns=stop + 40_000_000,
                    end_ns=stop + 40_000_100,
                    count=n,
                    observed_before=n,
                    observed_after=n,
                ),
            ),
            live_authority=False,
        )
    )
    return seal(value, raw)


def test_event_span_yields_complete_distinct_projection_with_original_cpu_windows():
    value = event_source()
    legacy = project_shared_window_source(value)
    result = project_shared_window_source(value, event_span=True)
    assert result["state"] == "shared_window_rates_available"
    assert result["projection_id"] != legacy["projection_id"]
    assert len(result["marginal_bounds"]) == 9
    for group in ("cpu_quota_fraction", "throttled_seconds_per_wall_second"):
        assert result["phase_rates"][group] == legacy["phase_rates"][group]
    assert result["phase_rates"]["encoded"] != legacy["phase_rates"]["encoded"]
    assert set(result["encoded_event_spans"]) == {
        "healthy",
        "degraded",
        "relief",
        "recovery",
        "post",
    }


def test_missing_trace_is_unavailable_even_with_complete_polled_rates():
    projected = project_shared_window_source(point_source("polled-only"), event_span=True)
    assert projected["state"] == "unavailable"
    assert projected["unavailable_components"] == ["encoded"]
    assert projected["phase_rates"] == projected["marginal_bounds"] == {}


@pytest.mark.parametrize(
    "damage",
    ["namespace", "clock", "origin", "window", "ordinal", "count", "duplicate", "getter_count"],
)
def test_inconsistent_reconciled_trace_is_rejected(damage):
    value = event_source()
    raw = json.loads(value["acquisition_json"])
    report = raw["events"][-1]
    if damage == "namespace":
        report["trace"]["time_namespace"] = "time:[321]"
    elif damage == "clock":
        report["worker_clock_id"] = "different-worker"
    elif damage == "origin":
        report["controller_origin_ns"] = "1"
    elif damage == "window":
        report["windows"]["recovery"]["phase_end_ns"] -= 1
    elif damage == "ordinal":
        report["trace"]["rows"][3][0] = 3
    elif damage == "count":
        report["trace"]["identity_read"]["count"] -= 1
    elif damage == "getter_count":
        row = list(rows(raw))[2]
        row["encoded_buffers"] += 2
        row["encoded_counter_read"]["value"] += 2
    else:
        raw["events"].append(report)
    with pytest.raises(ValueError, match="invalid_shared_window_source"):
        project_shared_window_source(seal(value, raw), event_span=True)


@pytest.mark.parametrize("options", [{"event_span": True}, {"condition_specific": True}])
def test_event_span_fitting_and_query_share_a_separate_binding_release(options):
    from latency_fingerprinting.evaluation import shared_window_candidate as candidate
    from latency_fingerprinting.evaluation.fixture_conditions import CONDITIONS

    context = "sha256:" + "a" * 64
    blocks = {}
    for i in range(6):
        block = {}
        for arm, condition in enumerate(CONDITIONS):
            identifier = f"event-fit-{i}-{arm}"
            value = event_source(identifier, arm)
            binding = candidate.declare_shared_window_binding(
                value,
                condition=condition,
                context_hash=context,
                inspection_sha256="sha256:" + hashlib.sha256(identifier.encode()).hexdigest(),
                **options,
            )
            block[condition] = dict(source=value, binding=binding)
        blocks[f"block-{i}"] = block

    fit = candidate.fit_shared_window_candidate(blocks, session_id="fixture", **options)
    assert fit["state"] == "candidate_calibration_available"
    assert fit["method_spec"] == candidate.shared_window_candidate_spec(**options)
    assert fit["calibration_query_count"] == 18
    for arm, condition in enumerate(CONDITIONS):
        report = candidate.score_shared_window_candidate(
            event_source(f"event-query-{arm}", arm),
            blocks,
            session_id="fixture",
            query_session_id="fixture",
            query_block_id="query",
            context_hash=context,
            **options,
        )
        assert report["predicted_condition"] == condition
        assert report["experiment_id"] == fit["experiment_id"]
    with pytest.raises(ValueError, match=candidate.ERROR):
        candidate.fit_shared_window_candidate(blocks, session_id="fixture")


def test_explicit_unreconciled_trace_is_unavailable_without_polled_fallback():
    value = event_source()
    raw = json.loads(value["acquisition_json"])
    report = raw["events"][-1]
    report["trace"]["identity_read"]["count"] -= 1
    report["state"] = "unavailable"
    report["reason_codes"] = ["identity_prefix_not_reconciled"]
    report["windows"] = {}
    result = project_shared_window_source(seal(value, raw), event_span=True)
    assert result["state"] == "unavailable"
    assert result["encoded_event_reason_codes"] == ["identity_prefix_not_reconciled"]
    assert result["phase_rates"] == result["marginal_bounds"] == {}


def test_identity_getter_can_count_one_buffer_before_its_source_pad_callback():
    value = event_source()
    raw = json.loads(value["acquisition_json"])
    sample = list(rows(raw))[2]
    point = sample["encoded_counter_read"]
    callback_start = raw["events"][-1]["trace"]["rows"][point["value"] - 1][1]
    bracket = dict(read_start_ns=callback_start - 100_000, read_end_ns=callback_start - 50_000)
    point.update(bracket)
    sample["native_read"].update(bracket)
    result = project_shared_window_source(seal(value, raw), event_span=True)
    assert result["state"] == "shared_window_rates_available"
    assert len(result["encoded_event_spans"]) == 5
