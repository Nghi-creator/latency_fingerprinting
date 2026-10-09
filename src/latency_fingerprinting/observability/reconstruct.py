"""Pure same-lifetime timing reconstruction from revalidated N4 evidence."""

import hashlib

from .contracts import METHODS, PAIRS, capability_boundary
from .summary import StageTraceSummary
from .trace import StageTraceRecord


def _timing(stream, index, engine, endpoints):
    supported = {cap.boundary for cap in stream.capabilities if cap.state == "supported"}
    own_method = (index < 3) == engine
    accessible = all(capability_boundary(endpoint) in supported for endpoint in PAIRS[index])
    unavailable = (
        "unsupported_source"
        if not own_method
        else ("capability_unavailable" if not accessible else None)
    )
    exclusions = dict.fromkeys(
        (
            "unsupported",
            "correlation_missing",
            "correlation_ambiguous",
            "missing_endpoint",
            "negative_duration",
        ),
        0,
    )
    samples = []
    start_boundary, end_boundary = PAIRS[index]
    for frame in stream.frames:
        if unavailable is not None:
            excluded = "unsupported"
        elif frame.correlation != "exact":
            excluded = f"correlation_{frame.correlation}"
        else:
            start = endpoints.get((frame.frame_id, start_boundary))
            end = endpoints.get((frame.frame_id, end_boundary))
            if start is None or end is None:
                excluded = "missing_endpoint"
            elif end < start:
                excluded = "negative_duration"
            else:
                delta = end - start
                samples.append(
                    {"frame_id": frame.frame_id, "delta_ns": delta, "value_ms": delta / 1000000}
                )
                continue
        exclusions[excluded] += 1
    values = [sample["value_ms"] for sample in samples]
    eligible, usable = len(stream.frames), len(samples)
    return {
        "method_id": METHODS[index],
        "method_version": 1,
        "state": "measured" if usable else "unavailable",
        "reason": None
        if usable
        else (unavailable or ("no_frames" if not eligible else "no_usable_pairs")),
        "eligible_frames": eligible,
        "usable_frames": usable,
        "excluded_frames": eligible - usable,
        "exclusions": exclusions,
        "samples": samples,
        "min_ms": min(values) if values else None,
        "mean_ms": sum(sample["delta_ns"] for sample in samples) / (usable * 1000000)
        if usable
        else None,
        "max_ms": max(values) if values else None,
    }


def _deadline(stream, age):
    budget = stream.deadline.budget_ns if stream.deadline is not None else None
    samples = (
        []
        if budget is None
        else [
            {
                "frame_id": sample["frame_id"],
                "slack_ms": (budget - sample["delta_ns"]) / 1000000,
                "hit": sample["delta_ns"] <= budget,
            }
            for sample in age["samples"]
        ]
    )
    usable = len(samples)
    hits = sum(sample["hit"] for sample in samples)
    return {
        "state": "measured" if usable else "unavailable",
        "reason": None
        if usable
        else ("budget_not_declared" if budget is None else "no_usable_pairs"),
        "method_id": "capture-output-budget",
        "method_version": 1,
        "budget_ns": budget,
        "samples": samples,
        "usable_frames": usable,
        "hit_frames": hits,
        "hit_fraction": hits / usable if usable else None,
    }


def reconstruct_trace(trace: StageTraceRecord) -> StageTraceSummary:
    """Revalidate copies; never bridge clocks, streams, frame aliases or missing endpoints."""
    from ..pipeline import canonical_json

    if not isinstance(trace, StageTraceRecord):
        raise ValueError("reconstruction requires a StageTraceRecord")
    trace = StageTraceRecord.model_validate(trace)
    streams = []
    scope_fields = {
        "stream_id",
        "epoch_id",
        "clock_id",
        "clock",
        "capabilities",
        "sampling",
        "loss",
    }
    for stream in trace.streams:
        endpoints = {
            (event.frame_id, event.boundary): event.timestamp_ns for event in stream.events
        }
        results = [
            _timing(stream, index, trace.producer == "pixelated_engine", endpoints)
            for index in range(4)
        ]
        streams.append(
            {
                **stream.model_dump(include=scope_fields),
                "results": results,
                "deadline_result": _deadline(stream, results[2]),
            }
        )
    # Summary validators independently recompute statistics, coverage and budget arithmetic.
    return StageTraceSummary.model_validate(
        {
            "schema_version": "stage-trace-summary-v1",
            "method_release": trace.method_release,
            "trace_sha256": hashlib.sha256(canonical_json(trace).encode("utf-8")).hexdigest(),
            "provenance": trace.provenance,
            "producer": trace.producer,
            "producer_version": trace.producer_version,
            "streams": streams,
        }
    )
