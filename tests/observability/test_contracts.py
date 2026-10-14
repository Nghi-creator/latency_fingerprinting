"""Hand-authored contract cases, without using a producer or trace derivation."""

import copy
import json
import math

import pytest
from pydantic import ValidationError

from latency_fingerprinting.cli import main
from latency_fingerprinting.observability import StageTraceRecord, StageTraceSummary
from latency_fingerprinting.observability.json import decode_trace_json
from latency_fingerprinting.pipeline import canonical_json

BOUNDARIES = [
    "render_ready",
    "capture_begin",
    "capture_output",
    "pre_encode_queue_enter",
    "pre_encode_queue_exit",
    "encode_input",
    "encode_output",
    "wire_send",
    "receive",
    "decode_ready",
    "presentation_proxy",
]
METHODS = [
    "pre-encode-queue-sojourn",
    "encode-boundary-elapsed",
    "capture-output-age-at-encode-output",
    "presentation-callback-lag",
]


def scope(browser=False):
    supported = ["presentation_proxy"] if browser else BOUNDARIES[2:7]
    return {
        "stream_id": "stream-1",
        "epoch_id": "epoch-1",
        "clock_id": "clock-1",
        "clock": {
            "source": "browser_performance" if browser else "python_monotonic_ns",
            "unit": "ns",
            "origin": "stream_start",
            "resolution_ns": None,
            "synchronization": "none",
        },
        "capabilities": [
            {
                "boundary": b,
                "state": "supported" if b in supported else "unavailable",
                "reason": None if b in supported else "unsupported_source",
            }
            for b in BOUNDARIES
        ],
        "sampling": {"every_nth_frame": 1},
        "loss": {
            "offered_frames": 4,
            "sampled_frames": 4,
            "unsampled_frames": 0,
            "frame_capacity_dropped": 0,
            "attempted_events": 17,
            "retained_events": 17,
            "event_capacity_dropped": 0,
            "event_invalid_timestamp_dropped": 0,
            "event_contention_dropped": 0,
            "event_shutdown_dropped": 0,
            "event_correlation_dropped": 0,
            "browser_missed_presentations": 0,
        },
    }


def record(browser=False):
    stream = scope(browser)
    stream.update(
        limits={"max_frames": 2000, "max_events": 10000},
        stop_reason="completed",
        deadline=None
        if browser
        else {"method_id": "capture-output-budget", "method_version": 1, "budget_ns": 12000000},
    )
    rows = [
        (0, 1000000, 4000000, 5000000, 9000000),
        (20000000, 21000000, 21000000, 22000000, 32000000),
        (40000000, 41000000, 46000000, 47000000, 57000000),
        (60000000, 61000000),
    ]
    stream["frames"] = [
        {"frame_id": f"frame-{i}", "source_sequence": i, "correlation": "exact"}
        for i in range(1, 5)
    ]
    stream["events"] = []
    for index, row in enumerate(rows, 1):
        for boundary, timestamp in zip(BOUNDARIES[2:7], row, strict=False):
            stream["events"].append(
                {
                    "sequence": len(stream["events"]) + 1,
                    "frame_id": f"frame-{index}",
                    "boundary": boundary,
                    "timestamp_ns": timestamp,
                }
            )
    if browser:
        stream["frames"] = stream["frames"][:1]
        stream["loss"].update(
            offered_frames=1, sampled_frames=1, attempted_events=2, retained_events=2
        )
        stream["events"] = [
            {
                "sequence": 1,
                "frame_id": "frame-1",
                "boundary": "presentation_proxy",
                "timestamp_ns": 10000000,
            },
            {
                "sequence": 2,
                "frame_id": "frame-1",
                "boundary": "presentation_callback",
                "timestamp_ns": 14000000,
            },
        ]
    return {
        "schema_version": "stage-trace-record-v1",
        "method_release": "n4-stage-local-v1",
        "trace_id": "trace-1",
        "session_id": "session-1",
        "run_id": "run-1",
        "provenance": "synthetic",
        "producer": "pixelated_browser" if browser else "pixelated_engine",
        "producer_version": "a" * 40,
        "streams": [stream],
    }


def summary():
    stream = scope()
    stream["results"] = []
    for method, values, mean in zip(
        METHODS, [[3, 0, 5], [4, 10, 10], [9, 12, 17], []], [8 / 3, 8.0, 38 / 3, None], strict=True
    ):
        has_values = bool(values)
        stream["results"].append(
            {
                "method_id": method,
                "method_version": 1,
                "state": "measured" if has_values else "unavailable",
                "reason": None if has_values else "unsupported_source",
                "eligible_frames": 4,
                "usable_frames": len(values),
                "excluded_frames": 4 - len(values),
                "exclusions": {
                    "unsupported": 0 if has_values else 4,
                    "correlation_missing": 0,
                    "correlation_ambiguous": 0,
                    "missing_endpoint": 1 if has_values else 0,
                    "negative_duration": 0,
                },
                "samples": [
                    {"frame_id": f"frame-{i}", "delta_ns": v * 1000000, "value_ms": float(v)}
                    for i, v in enumerate(values, 1)
                ],
                "min_ms": float(min(values)) if has_values else None,
                "mean_ms": mean,
                "max_ms": float(max(values)) if has_values else None,
            }
        )
    stream["deadline_result"] = {
        "state": "measured",
        "reason": None,
        "method_id": "capture-output-budget",
        "method_version": 1,
        "budget_ns": 12000000,
        "samples": [
            {"frame_id": "frame-1", "slack_ms": 3.0, "hit": True},
            {"frame_id": "frame-2", "slack_ms": 0.0, "hit": True},
            {"frame_id": "frame-3", "slack_ms": -5.0, "hit": False},
        ],
        "usable_frames": 3,
        "hit_frames": 2,
        "hit_fraction": 2 / 3,
    }
    return {
        "schema_version": "stage-trace-summary-v1",
        "method_release": "n4-stage-local-v1",
        "trace_sha256": "b" * 64,
        "provenance": "synthetic",
        "producer": "pixelated_engine",
        "producer_version": "a" * 40,
        "streams": [stream],
    }


def set_at(payload, path, value):
    for key in path[:-1]:
        payload = payload[key]
    payload[path[-1]] = value


@pytest.mark.parametrize("browser", [False, True])
def test_valid_record_roundtrip(browser):
    data = record(browser)
    model = StageTraceRecord.model_validate(data)
    assert model.model_dump(mode="json") == data
    assert StageTraceRecord.model_validate_json(canonical_json(model)) == model


def test_independent_summary_and_zero_are_measured():
    model = StageTraceSummary.model_validate(summary())
    assert model.streams[0].results[0].samples[1].value_ms == 0.0
    assert model.streams[0].deadline_result.samples[1].hit is True
    assert model.streams[0].deadline_result.samples[2].slack_ms == -5
    assert StageTraceSummary.model_validate_json(canonical_json(model)) == model


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema_version",), "stage-trace-record-v2"),
        (("method_release",), "remote-method"),
        (("trace_id",), "trace-01"),
        (("trace_id",), "trace-2147483648"),
        (("session_id",), "private-user"),
        (("producer_version",), "https://private"),
        (("streams", 0, "clock", "source"), "browser_performance"),
        (("streams", 0, "clock", "synchronization"), "utc"),
        (("streams", 0, "clock", "resolution_ns"), 0),
        (("streams", 0, "deadline", "method_version"), True),
        (("streams", 0, "deadline", "method_version"), 2),
        (("streams", 0, "deadline", "budget_ns"), "12000000"),
        (("streams", 0, "frames", 0, "frame_id"), "frame-2"),
        (("streams", 0, "frames", 0, "correlation"), "missing"),
        (("streams", 0, "events", 0, "timestamp_ns"), -1),
        (("streams", 0, "events", 0, "timestamp_ns"), 1.0),
        (("streams", 0, "events", 0, "timestamp_ns"), True),
        (("streams", 0, "events", 0, "timestamp_ns"), 2**53),
        (("streams", 0, "events", 0, "timestamp_ns"), math.inf),
        (("streams", 0, "events", 0, "frame_id"), "frame-99"),
        (("streams", 0, "events", 1, "sequence"), 1),
        (("streams", 0, "capabilities", 2, "reason"), "not_instrumented"),
        (("streams", 0, "capabilities", 0, "reason"), "not_instrumented"),
        (("streams", 0, "loss", "retained_events"), 16),
        (("streams", 0, "loss", "sampled_frames"), 5),
        (("streams", 0, "loss", "browser_missed_presentations"), 1),
        (("streams", 0, "sampling", "every_nth_frame"), 2),
        (("streams", 0, "limits", "max_events"), 16),
        (("streams", 0, "stop_reason"), "disabled"),
    ],
)
def test_record_rejects_false_meaning(path, value):
    data = record()
    set_at(data, path, value)
    with pytest.raises(ValidationError):
        StageTraceRecord.model_validate(data)


@pytest.mark.parametrize(
    "path,value",
    [
        (("trace_sha256",), "not-a-hash"),
        (("streams", 0, "results", 0, "method_version"), 1.0),
        (("streams", 0, "results", 0, "method_id"), "decode-guess"),
        (("streams", 0, "results", 0, "mean_ms"), 3.0),
        (("streams", 0, "results", 0, "mean_ms"), math.nan),
        (("streams", 0, "results", 0, "state"), "estimated"),
        (("streams", 0, "results", 0, "reason"), "no_usable_pairs"),
        (("streams", 0, "results", 0, "samples", 0, "value_ms"), 4.0),
        (("streams", 0, "results", 0, "samples", 1, "frame_id"), "frame-1"),
        (("streams", 0, "results", 0, "samples", 0, "frame_id"), "frame-5"),
        (("streams", 0, "results", 0, "exclusions", "missing_endpoint"), 0),
        (("streams", 0, "results", 0, "eligible_frames"), 5),
        (("streams", 0, "results", 3, "reason"), "no_usable_pairs"),
        (("streams", 0, "deadline_result", "samples", 1, "hit"), False),
        (("streams", 0, "deadline_result", "samples", 1, "hit"), 1),
        (("streams", 0, "deadline_result", "samples", 0, "slack_ms"), 4.0),
        (("streams", 0, "deadline_result", "hit_fraction"), 1.0),
        (("streams", 0, "deadline_result", "budget_ns"), None),
        (("streams", 0, "deadline_result", "state"), "unavailable"),
    ],
)
def test_summary_rejects_false_arithmetic(path, value):
    data = summary()
    set_at(data, path, value)
    with pytest.raises(ValidationError):
        StageTraceSummary.model_validate(data)


@pytest.mark.parametrize("root,builder", [(StageTraceRecord, record), (StageTraceSummary, summary)])
def test_detaches_inputs_and_revalidates_copies(root, builder):
    data = builder()
    model = root.model_validate(data)
    data["streams"][0]["clock"]["unit"] = "seconds"
    assert model.streams[0].clock.unit == "ns"
    with pytest.raises(ValidationError):
        model.producer = "private"
    corrupted_clock = model.streams[0].clock.model_copy(update={"unit": "seconds"})
    stream = model.streams[0].model_copy(update={"clock": corrupted_clock})
    corrupted = model.model_copy(update={"streams": (stream,)})
    with pytest.raises(ValidationError):
        root.model_validate(corrupted)
    data = builder()
    data["metadata"] = {"credentials": "private"}
    with pytest.raises(ValidationError):
        root.model_validate(data)


def test_negative_pair_and_interleaved_timestamps_are_evidence_not_input_error():
    data = record()
    data["streams"][0]["events"][2]["timestamp_ns"] = 500000
    StageTraceRecord.model_validate(data)  # exclusion is Step 6's responsibility


def test_sampling_and_event_gaps_are_conserved():
    data = record()
    stream = data["streams"][0]
    stream["sampling"]["every_nth_frame"] = 3
    stream["limits"]["max_frames"] = 3
    stream["frames"] = [
        {"frame_id": f"frame-{i}", "source_sequence": i, "correlation": "exact"} for i in [1, 4, 7]
    ]
    stream["events"] = [
        {"sequence": i, "frame_id": "frame-1", "boundary": b, "timestamp_ns": 0}
        for i, b in zip([1, 2, 4, 7, 8], BOUNDARIES[2:7], strict=True)
    ]
    stream["loss"].update(
        offered_frames=10,
        sampled_frames=3,
        unsampled_frames=6,
        frame_capacity_dropped=1,
        attempted_events=8,
        retained_events=5,
        event_capacity_dropped=2,
        event_shutdown_dropped=1,
    )
    StageTraceRecord.model_validate(data)


def test_missing_correlation_keeps_only_capture_and_counts_removed_events():
    data = record()
    stream = data["streams"][0]
    stream["frames"][0]["correlation"] = "ambiguous"
    stream["events"] = [
        e
        for e in stream["events"]
        if e["frame_id"] != "frame-1" or e["boundary"] == "capture_output"
    ]
    stream["loss"].update(retained_events=13, event_correlation_dropped=4)
    StageTraceRecord.model_validate(data)


@pytest.mark.parametrize("field", ["epoch_id", "clock_id", "stream_id"])
def test_no_reused_lifetime_identity(field):
    data = record()
    other = copy.deepcopy(data["streams"][0])
    other.update(stream_id="stream-2", epoch_id="epoch-2", clock_id="clock-2")
    other[field] = data["streams"][0][field]
    data["streams"].append(other)
    with pytest.raises(ValidationError):
        StageTraceRecord.model_validate(data)


def test_duplicate_endpoint_rejected_even_with_distinct_event_sequence():
    data = record()
    stream = data["streams"][0]
    duplicate = dict(stream["events"][0], sequence=18)
    stream["events"].append(duplicate)
    stream["loss"].update(attempted_events=18, retained_events=18)
    with pytest.raises(ValidationError):
        StageTraceRecord.model_validate(data)


@pytest.mark.parametrize(
    "data",
    [
        '{"x":1,"x":2}',
        "[" * 33 + "0" + "]" * 33,
        '{"x":NaN}',
        " " * (10 * 1024 * 1024 + 1),
        b"\xff",
        123,
    ],
)
def test_text_boundary_rejects_ambiguous_or_unbounded_json(data):
    with pytest.raises((ValueError, UnicodeDecodeError)):
        StageTraceRecord.model_validate_json(data)


def test_depth_scanner_understands_escaped_strings_and_bytes():
    data = json.dumps({"text": '\\"' + "[" * 40})
    assert decode_trace_json(bytearray(data.encode())) == json.loads(data)
    with pytest.raises(ValueError):
        decode_trace_json(b" " * (10 * 1024 * 1024 + 1))


@pytest.mark.parametrize("builder", [record, summary])
def test_generic_validate_cli_adds_n4_without_new_adoption_command(builder, tmp_path, capsys):
    data = builder()
    file = tmp_path / "record.json"
    file.write_text(json.dumps(data))
    assert main(["validate", str(file)]) == 0
    output = capsys.readouterr().out
    assert json.loads(output) == data
    assert output.endswith("\n")


def test_disabled_empty_stream_and_unavailable_summary():
    data = record()
    stream = data["streams"][0]
    stream.update(frames=[], events=[], stop_reason="disabled")
    stream["loss"] = dict.fromkeys(stream["loss"], 0)
    for cap in stream["capabilities"]:
        cap.update(state="unavailable", reason="disabled")
    StageTraceRecord.model_validate(data)
    data = summary()
    stream = data["streams"][0]
    stream["loss"] = dict.fromkeys(stream["loss"], 0)
    for index, result in enumerate(stream["results"]):
        result.update(
            state="unavailable",
            reason="no_frames" if index < 3 else "unsupported_source",
            eligible_frames=0,
            usable_frames=0,
            excluded_frames=0,
            samples=[],
            min_ms=None,
            mean_ms=None,
            max_ms=None,
        )
        result["exclusions"] = dict.fromkeys(result["exclusions"], 0)
    stream["deadline_result"].update(
        state="unavailable",
        reason="budget_not_declared",
        budget_ns=None,
        samples=[],
        usable_frames=0,
        hit_frames=0,
        hit_fraction=None,
    )
    StageTraceSummary.model_validate(data)
    stream["deadline_result"].update(budget_ns=12000000, reason="no_usable_pairs")
    StageTraceSummary.model_validate(data)


@pytest.mark.parametrize("key,count", [("streams", 17), ("frames", 2001), ("events", 10001)])
def test_container_cap_precedes_element_validation(key, count):
    data = record()
    target = data if key == "streams" else data["streams"][0]
    target[key] = [None] * count
    with pytest.raises(ValidationError, match="limit"):
        StageTraceRecord.model_validate(data)


def test_total_limit_applies_before_validating_each_stream():
    data = record()
    data["streams"] = [{"frames": [None] * 1100, "events": []}] * 2
    with pytest.raises(ValidationError, match="total"):
        StageTraceRecord.model_validate(data)


@pytest.mark.parametrize("collection", [set(), frozenset(), iter([])])
def test_contract_collections_cannot_be_unordered_or_unbounded_iterators(collection):
    data = record()
    data["streams"][0]["events"] = collection
    with pytest.raises(ValidationError):
        StageTraceRecord.model_validate(data)


@pytest.mark.parametrize(
    "change", ["host_event", "host_budget", "correlation", "clock", "source_capability"]
)
def test_browser_rejects_host_evidence(change):
    data = record(True)
    stream = data["streams"][0]
    if change == "host_event":
        stream["events"][0]["boundary"] = "encode_output"
    elif change == "host_budget":
        stream["deadline"] = {
            "method_id": "capture-output-budget",
            "method_version": 1,
            "budget_ns": 1,
        }
    elif change == "correlation":
        stream["frames"][0]["correlation"] = "missing"
        stream["events"] = []
        stream["loss"].update(attempted_events=0, retained_events=0)
    elif change == "clock":
        stream["clock"]["source"] = "python_monotonic_ns"
    else:
        stream["events"] = []
        stream["loss"].update(attempted_events=0, retained_events=0)
        stream["capabilities"][-1].update(state="unavailable", reason="api_unavailable")
    with pytest.raises(ValidationError):
        StageTraceRecord.model_validate(data)


def test_missing_capability_summary_has_no_fabricated_samples():
    data = summary()
    stream = data["streams"][0]
    stream["capabilities"][3].update(state="unavailable", reason="not_instrumented")
    result = stream["results"][0]
    with pytest.raises(ValidationError):
        StageTraceSummary.model_validate(data)
    result.update(
        state="unavailable",
        reason="capability_unavailable",
        samples=[],
        usable_frames=0,
        excluded_frames=4,
        min_ms=None,
        mean_ms=None,
        max_ms=None,
    )
    result["exclusions"].update(unsupported=4, missing_endpoint=0)
    StageTraceSummary.model_validate(data)


def test_summary_host_correlation_is_consistent_across_supported_methods():
    data = summary()
    result = data["streams"][0]["results"][0]
    result["exclusions"].update(missing_endpoint=0, correlation_missing=1)
    with pytest.raises(ValidationError, match="correlation"):
        StageTraceSummary.model_validate(data)


def test_positive_zero_canonicalization():
    data = summary()
    data["streams"][0]["deadline_result"]["samples"][1]["slack_ms"] = -0.0
    output = canonical_json(StageTraceSummary.model_validate(data))
    assert '"slack_ms": -0.0' not in output


def test_generic_cli_rejects_n4_depth_without_output(tmp_path, capsys):
    text = json.dumps(record())[:-1] + ', "extra":' + "[" * 33 + "0" + "]" * 33 + "}"
    file = tmp_path / "deep.json"
    file.write_text(text)
    assert main(["validate", str(file)]) != 0
    captured = capsys.readouterr()
    assert captured.out == "" and "depth 32" in captured.err
