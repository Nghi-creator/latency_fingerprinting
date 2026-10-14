"""Independent reconstruction arithmetic, exclusion, identity and offline I/O cases."""

import hashlib
import json
import os
import subprocess
import sys
from fractions import Fraction

import pytest

from latency_fingerprinting.cli import main
from latency_fingerprinting.observability import StageTraceRecord, reconstruct_trace
from latency_fingerprinting.observability import input as trace_input
from latency_fingerprinting.observability.input import read_trace_record
from latency_fingerprinting.pipeline import canonical_json
from tests.observability.test_contracts import record, summary

SAFE_MAX = 9007199254740991


def trace(rows, *, browser=False, n=1, budget=12000000):
    data = record(browser)
    scope = data["streams"][0]
    scope["sampling"]["every_nth_frame"] = n
    scope["frames"], scope["events"] = [], []
    for index, (correlation, endpoints) in enumerate(rows):
        number = index * n + 1
        frame_id = f"frame-{number}"
        scope["frames"].append(
            {"frame_id": frame_id, "source_sequence": number, "correlation": correlation}
        )
        for boundary, timestamp in endpoints:
            scope["events"].append(
                {
                    "sequence": len(scope["events"]) + 1,
                    "frame_id": frame_id,
                    "boundary": boundary,
                    "timestamp_ns": timestamp,
                }
            )
    scope["loss"] = dict.fromkeys(scope["loss"], 0)
    offered = (len(rows) - 1) * n + 1 if rows else 0
    scope["loss"].update(
        offered_frames=offered,
        sampled_frames=len(rows),
        unsampled_frames=offered - len(rows),
        attempted_events=len(scope["events"]),
        retained_events=len(scope["events"]),
    )
    scope["deadline"] = (
        None
        if browser or budget is None
        else {"method_id": "capture-output-budget", "method_version": 1, "budget_ns": budget}
    )
    return StageTraceRecord.model_validate(data)


def test_full_summary_equals_independent_step_one_example():
    value = StageTraceRecord.model_validate(record())
    expected = summary()
    expected["trace_sha256"] = hashlib.sha256(canonical_json(value).encode()).hexdigest()
    assert reconstruct_trace(value).model_dump(mode="json") == expected


def test_priority_exclusions_and_budget_use_only_usable_age_pairs():
    value = trace(
        [
            (
                "exact",
                [
                    ("capture_output", 0),
                    ("pre_encode_queue_enter", 1000000),
                    ("pre_encode_queue_exit", 4000000),
                    ("encode_input", 5000000),
                    ("encode_output", 9000000),
                ],
            ),
            ("missing", [("capture_output", 20000000)]),
            ("ambiguous", [("capture_output", 40000000)]),
            ("exact", [("capture_output", 60000000), ("pre_encode_queue_enter", 61000000)]),
            (
                "exact",
                [
                    ("capture_output", 100000000),
                    ("pre_encode_queue_enter", 110000000),
                    ("pre_encode_queue_exit", 109000000),
                    ("encode_input", 120000000),
                    ("encode_output", 119000000),
                ],
            ),
            (
                "exact",
                [
                    ("capture_output", 200000000),
                    ("pre_encode_queue_enter", 201000000),
                    ("pre_encode_queue_exit", 201000000),
                    ("encode_input", 202000000),
                    ("encode_output", 200000000),
                ],
            ),
        ]
    )
    scope = reconstruct_trace(value).streams[0]
    queue, encode, age, presentation = scope.results
    assert [sample.delta_ns for sample in queue.samples] == [3000000, 0]
    assert [sample.delta_ns for sample in encode.samples] == [4000000]
    assert [sample.delta_ns for sample in age.samples] == [9000000, 19000000, 0]
    for result, negative in [(queue, 1), (encode, 2), (age, 0)]:
        assert result.eligible_frames == 6
        assert result.exclusions.model_dump() == {
            "unsupported": 0,
            "correlation_missing": 1,
            "correlation_ambiguous": 1,
            "missing_endpoint": 1,
            "negative_duration": negative,
        }
        assert result.excluded_frames + result.usable_frames == 6
    assert presentation.exclusions.unsupported == 6
    assert presentation.reason == "unsupported_source"
    assert [
        (sample.frame_id, sample.slack_ms, sample.hit) for sample in scope.deadline_result.samples
    ] == [("frame-1", 3.0, True), ("frame-5", -7.0, False), ("frame-6", 12.0, True)]
    assert scope.deadline_result.hit_fraction == 2 / 3


@pytest.mark.parametrize(
    "pair,index,browser",
    [
        (("pre_encode_queue_enter", "pre_encode_queue_exit"), 0, False),
        (("encode_input", "encode_output"), 1, False),
        (("capture_output", "encode_output"), 2, False),
        (("presentation_proxy", "presentation_callback"), 3, True),
    ],
)
@pytest.mark.parametrize("end,state", [(0, "measured"), (1, "measured"), (-1, "unavailable")])
def test_positive_zero_negative_pairs(pair, index, browser, end, state):
    value = trace([("exact", [(pair[0], 10), (pair[1], 10 + end)])], browser=browser)
    result = reconstruct_trace(value).streams[0].results[index]
    assert result.state == state
    if end < 0:
        assert result.reason == "no_usable_pairs"
        assert result.exclusions.negative_duration == 1
        assert result.min_ms is result.mean_ms is result.max_ms is None
    else:
        assert result.samples[0].delta_ns == end
        assert result.samples[0].value_ms == end / 1000000
        assert result.min_ms == result.mean_ms == result.max_ms == end / 1000000


@pytest.mark.parametrize("browser", [False, True])
def test_empty_active_source_has_no_frames_with_foreign_method_precedence(browser):
    scope = reconstruct_trace(trace([], browser=browser)).streams[0]
    for index, result in enumerate(scope.results):
        own = (index == 3) == browser
        assert result.reason == ("no_frames" if own else "unsupported_source")
        assert result.usable_frames == result.eligible_frames == result.excluded_frames == 0
    assert scope.deadline_result.reason == ("budget_not_declared" if browser else "no_usable_pairs")


@pytest.mark.parametrize("with_frames", [False, True])
def test_unavailable_capability_precedes_empty_and_correlation(with_frames):
    value = trace([("missing", [("capture_output", 1)])] if with_frames else [])
    data = value.model_dump(mode="json")
    cap = data["streams"][0]["capabilities"][3]
    cap.update(state="unavailable", reason="not_instrumented")
    scope = reconstruct_trace(StageTraceRecord.model_validate(data)).streams[0]
    result = scope.results[0]
    assert result.reason == "capability_unavailable"
    assert result.exclusions.unsupported == int(with_frames)
    assert result.exclusions.correlation_missing == 0
    assert scope.results[1].exclusions.correlation_missing == int(with_frames)


def test_browser_missing_api_is_capability_unavailable_not_zero_duration():
    data = trace([], browser=True).model_dump(mode="json")
    data["streams"][0]["capabilities"][-1].update(state="unavailable", reason="api_unavailable")
    result = reconstruct_trace(StageTraceRecord.model_validate(data)).streams[0].results[-1]
    assert result.reason == "capability_unavailable"
    assert result.mean_ms is None


def test_sampling_prefix_and_loss_are_preserved_without_extrapolation():
    value = trace(
        [
            ("exact", [("presentation_proxy", 10), ("presentation_callback", 14)]),
            ("exact", [("presentation_proxy", 20)]),
            ("exact", [("presentation_proxy", 30), ("presentation_callback", 32)]),
        ],
        browser=True,
        n=3,
    )
    data = value.model_dump(mode="json")
    stream = data["streams"][0]
    stream["loss"].update(
        offered_frames=10,
        unsampled_frames=6,
        frame_capacity_dropped=1,
        attempted_events=6,
        event_capacity_dropped=1,
        browser_missed_presentations=17,
    )
    stream["events"][-1]["sequence"] = 6
    value = StageTraceRecord.model_validate(data)
    result = reconstruct_trace(value).streams[0]
    assert result.loss == value.streams[0].loss
    assert result.sampling.every_nth_frame == 3
    timing = result.results[-1]
    assert timing.eligible_frames == 3
    assert timing.usable_frames == 2
    assert [sample.frame_id for sample in timing.samples] == ["frame-1", "frame-7"]
    assert timing.exclusions.missing_endpoint == 1
    assert timing.mean_ms == 0.000003


def test_stream_epoch_clock_resets_never_bridge_identical_frame_aliases():
    first = trace([("exact", [("capture_output", 0)])]).model_dump(mode="json")
    second = trace([("exact", [("encode_output", 10000000)])]).model_dump(mode="json")["streams"][0]
    second.update(stream_id="stream-2", epoch_id="epoch-2", clock_id="clock-2")
    first["streams"].append(second)
    result = reconstruct_trace(StageTraceRecord.model_validate(first))
    assert [scope.clock_id for scope in result.streams] == ["clock-1", "clock-2"]
    for scope in result.streams:
        assert scope.results[2].usable_frames == 0
        assert scope.results[2].exclusions.missing_endpoint == 1
        assert scope.deadline_result.reason == "no_usable_pairs"


def test_event_arrival_order_does_not_change_endpoint_arithmetic():
    value = trace([("exact", [("encode_output", 9000000), ("capture_output", 1000000)])])
    sample = reconstruct_trace(value).streams[0].results[2].samples[0]
    assert sample.delta_ns == 8000000
    assert [event.boundary for event in value.streams[0].events] == [
        "encode_output",
        "capture_output",
    ]


@pytest.mark.parametrize("budget,reason", [(None, "budget_not_declared"), (12000000, None)])
def test_optional_budget_and_equality(budget, reason):
    scope = reconstruct_trace(
        trace([("exact", [("capture_output", 0), ("encode_output", 12000000)])], budget=budget)
    ).streams[0]
    assert scope.results[2].mean_ms == 12.0
    assert scope.deadline_result.reason == reason
    if budget:
        assert scope.deadline_result.samples[0].slack_ms == 0.0
        assert scope.deadline_result.samples[0].hit is True
        assert scope.deadline_result.hit_fraction == 1.0
    else:
        assert scope.deadline_result.samples == ()


def test_safe_limit_deltas_large_integer_sum_and_negative_slack():
    rows = [
        ("exact", [("capture_output", 0), ("encode_output", SAFE_MAX - index)])
        for index in range(2000)
    ]
    value = trace(rows, budget=1)
    scope = reconstruct_trace(value).streams[0]
    age = scope.results[2]
    expected = float(Fraction(2000 * SAFE_MAX - 1999000, 2000 * 1000000))
    assert age.mean_ms == expected
    assert age.min_ms == (SAFE_MAX - 1999) / 1000000
    assert age.max_ms == SAFE_MAX / 1000000
    assert scope.deadline_result.samples[0].slack_ms == (1 - SAFE_MAX) / 1000000
    assert scope.deadline_result.hit_fraction == 0.0


def test_purity_detachment_hash_and_source_error_evidence():
    value = StageTraceRecord.model_validate(record())
    data = value.model_dump(mode="json")
    data["streams"][0]["stop_reason"] = "source_error"
    value = StageTraceRecord.model_validate(data)
    before = canonical_json(value)
    first, second = reconstruct_trace(value), reconstruct_trace(value)
    assert first == second
    assert canonical_json(value) == before
    assert first.trace_sha256 == hashlib.sha256(before.encode()).hexdigest()
    assert first.streams[0].clock == value.streams[0].clock
    assert first.streams[0].capabilities == value.streams[0].capabilities
    assert first.streams[0].results[0].usable_frames == 3
    with pytest.raises(ValueError):
        first.streams[0].results[0].samples[0].value_ms = 7.0


@pytest.mark.parametrize("case", ["timestamp", "loss", "clock", "duplicate"])
def test_revalidate_forged_copied_instances_before_derivation(case):
    value = StageTraceRecord.model_validate(record())
    scope = value.streams[0]
    if case == "timestamp":
        event = scope.events[0].model_copy(update={"timestamp_ns": True})
        scope = scope.model_copy(update={"events": (event, *scope.events[1:])})
    elif case == "loss":
        scope = scope.model_copy(
            update={"loss": scope.loss.model_copy(update={"sampled_frames": 99})}
        )
    elif case == "clock":
        scope = scope.model_copy(
            update={"clock": scope.clock.model_copy(update={"source": "wall_clock"})}
        )
    else:
        events = (*scope.events, scope.events[0].model_copy(update={"sequence": 18}))
        loss = scope.loss.model_copy(update={"retained_events": 18, "attempted_events": 18})
        scope = scope.model_copy(update={"events": events, "loss": loss})
    with pytest.raises(ValueError):
        reconstruct_trace(value.model_copy(update={"streams": (scope,)}))


def test_api_requires_validated_trace_not_arbitrary_dict_or_summary():
    with pytest.raises(ValueError):
        reconstruct_trace(record())
    with pytest.raises(ValueError):
        reconstruct_trace(reconstruct_trace(StageTraceRecord.model_validate(record())))


@pytest.mark.parametrize("format", ["canonical", "minified"])
def test_inspect_cli_and_input_hash_identity(tmp_path, capsys, format):
    value = StageTraceRecord.model_validate(record())
    source, target = tmp_path / "trace.json", tmp_path / "summary.json"
    source.write_text(
        canonical_json(value)
        if format == "canonical"
        else json.dumps(value.model_dump(mode="json"))
    )
    expected = canonical_json(reconstruct_trace(value))
    assert read_trace_record(source) == value
    assert main(["inspect-trace", "--trace", str(source), "--output", str(target)]) == 0
    assert target.read_text() == expected
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "case",
    [
        "symlink",
        "ancestor",
        "fifo",
        "directory",
        "missing",
        "private",
        "duplicate",
        "depth",
        "oversize",
        "summary",
    ],
)
def test_inspect_invalid_input_is_bounded_and_private(tmp_path, capsys, monkeypatch, case):
    source = tmp_path / "secret-marker.json"
    source.write_text(canonical_json(StageTraceRecord.model_validate(record())))
    if case == "symlink":
        real = tmp_path / "real.json"
        source.rename(real)
        source.symlink_to(real)
    elif case == "ancestor":
        alias = tmp_path / "alias"
        alias.symlink_to(tmp_path, target_is_directory=True)
        source = alias / source.name
    elif case == "fifo":
        source.unlink()
        os.mkfifo(source)
    elif case == "directory":
        source.unlink()
        source.mkdir()
    elif case == "missing":
        source.unlink()
    elif case == "private":
        source.write_text('{"private": "secret-marker"}')
    elif case == "duplicate":
        source.write_text(
            '{"schema_version":"stage-trace-record-v1","schema_version":"stage-trace-record-v1"}'
        )
    elif case == "depth":
        source.write_text("[" * 33 + "0" + "]" * 33)
    elif case == "oversize":
        monkeypatch.setattr(trace_input, "MAX_CONTRACT_JSON_BYTES", 1)
    else:
        source.write_text(
            canonical_json(reconstruct_trace(StageTraceRecord.model_validate(record())))
        )
    target = tmp_path / "summary.json"
    target.write_bytes(b"original")
    assert main(["inspect-trace", "--trace", str(source), "--output", str(target)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error: inspect-trace: invalid_input_or_output\n"
    assert target.read_bytes() == b"original"
    assert not list(tmp_path.glob(".n4-*.tmp"))


def test_inspect_output_symlink_preserves_existing_and_privacy(tmp_path, capsys):
    source = tmp_path / "trace.json"
    source.write_text(canonical_json(StageTraceRecord.model_validate(record())))
    original = tmp_path / "original.json"
    original.write_bytes(b"original")
    target = tmp_path / "private-path"
    target.symlink_to(original)
    assert main(["inspect-trace", "--trace", str(source), "--output", str(target)]) == 1
    assert capsys.readouterr().err == "error: inspect-trace: invalid_input_or_output\n"
    assert original.read_bytes() == b"original"


@pytest.mark.parametrize(
    "module", ["latency_fingerprinting.models", "latency_fingerprinting.observability"]
)
def test_fresh_public_imports_avoid_serialization_dependency_cycle(module):
    result = subprocess.run(  # noqa: S603 — module names are the closed parametrized literals above
        [sys.executable, "-c", f"import {module}"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
