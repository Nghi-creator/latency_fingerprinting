"""Validate the producer's compact trace and reconstruct its phase event spans."""

import re
from bisect import bisect_left

from ..analytical.policy_release import payload_hash
from .combined_resource_projection import _exact
from .contrast_bounds import _integer
from .cpu_resource_response import PHASES
from .encoded_event_rate import MAX_EVENTS, MAX_SPAN_NS, encoded_event_rate

TRACE_METHOD = "n11-contained-encoded-event-trace-v1"
TRACE_CAPACITY = 1024
MAX_TRACE_VALUE = 2**53 - 1
ERROR = "invalid_encoded_event_source"


def _origin(value):
    if type(value) is not str or re.fullmatch(r"[0-9]{1,19}", value) is None:
        raise ValueError(ERROR)
    return _integer(int(value))


def _bounds(events, samples):
    bounds, records = {}, []
    previous_end = 0
    for phase in PHASES:
        if phase in ("healthy", "post"):
            start, end = (samples[phase][i]["at_ns"] for i in (0, -1))
        else:
            (start,) = (
                e["at_ns"]
                for e in events
                if e.get("phase") == phase and e["kind"] == "n11_pair_phase_started"
            )
            (end,) = (
                e["at_ns"]
                for e in events
                if e.get("phase") == phase and e["kind"] == "n11_pair_phase_completed"
            )
        _integer(start, previous_end)
        _integer(end, start + 1)
        bounds[phase] = dict(phase_start_ns=start, phase_end_ns=end)
        previous_end = end
        records.extend(
            (dict(phase=phase, edge="start", at_ns=start), dict(phase=phase, edge="end", at_ns=end))
        )
    return bounds, records


def _prefix(trace):
    observed = _integer(trace["observed"], high=MAX_TRACE_VALUE)
    read = trace["identity_read"]
    _exact(read, ("start_ns", "end_ns", "count", "observed_before", "observed_after"))
    start = _integer(read["start_ns"], high=MAX_TRACE_VALUE)
    _integer(read["end_ns"], start, MAX_TRACE_VALUE)
    before = _integer(read["observed_before"], high=observed)
    after = _integer(read["observed_after"], before, observed)
    count = read["count"]
    if count is not None:
        _integer(count, high=MAX_TRACE_VALUE)
    rows = trace["rows"]
    if type(rows) is not list or len(rows) != min(observed, TRACE_CAPACITY):
        raise ValueError(ERROR)
    previous = -1
    for ordinal, row in enumerate(rows, 1):
        if type(row) is not list or len(row) != 3:
            raise ValueError(ERROR)
        _integer(row[0], ordinal, ordinal)
        at = _integer(row[1], previous + 1, MAX_TRACE_VALUE)
        previous = _integer(row[2], at, MAX_TRACE_VALUE)
    if not count or count != before or count != after or count > len(rows):
        return None
    if rows[count - 1][2] > start:
        return None
    return rows[:count]


def _check_polled_counts(samples, rows, read_start):
    # Identity increments before pushing from its source pad. In the serialized
    # buffer stream, at most the last counted buffer can still be waiting for its
    # callback. The prior callback must have completed before identity counts it.
    for phase_rows in samples.values():
        for sample in phase_rows:
            read = sample["encoded_counter_read"]
            count = read["value"]
            if (
                read["read_end_ns"] > read_start
                or count > len(rows)
                or count >= 2
                and rows[count - 2][2] > read["read_end_ns"]
                or count < len(rows)
                and rows[count][2] <= read["read_start_ns"]
            ):
                raise ValueError(ERROR)


def inspect_encoded_event_source(events, *, worker_clock, controller_origin):
    """Return per-phase event-span reports and eligibility reasons for a verified source."""
    traces = [e for e in events if e["kind"] == "n11_encoded_event_trace"]
    if not traces:
        return {}, ["encoded_event_trace_missing"]
    (report,) = traces
    _exact(
        report,
        (
            "kind",
            "method",
            "state",
            "reason_codes",
            "worker_clock_id",
            "controller_origin_ns",
            "controller_time_namespace",
            "controller_boundaries",
            "windows",
            "trace",
            "live_authority",
        ),
    )
    if (
        report["method"] != TRACE_METHOD
        or report["live_authority"] is not False
        or report["worker_clock_id"] != worker_clock
        or report["controller_origin_ns"] != controller_origin
    ):
        raise ValueError(ERROR)
    trace = report["trace"]
    _exact(
        trace, ("origin_ns", "time_namespace", "identity_read", "observed", "buffer_list", "rows")
    )
    offset = _origin(controller_origin) - _origin(trace["origin_ns"])
    for namespace in (trace["time_namespace"], report["controller_time_namespace"]):
        if type(namespace) is not str or re.fullmatch(r"time:\[[0-9]{1,20}\]", namespace) is None:
            raise ValueError(ERROR)
    if type(trace["buffer_list"]) is not bool:
        raise ValueError(ERROR)

    prefix = _prefix(trace)
    reasons = []
    if trace["time_namespace"] != report["controller_time_namespace"]:
        reasons.append("time_namespace_mismatch")
    if trace["buffer_list"]:
        reasons.append("unsupported_buffer_list")
    if trace["observed"] > TRACE_CAPACITY:
        reasons.append("event_capacity_exceeded")
    if prefix is None:
        reasons.append("identity_prefix_not_reconciled")
    if report["reason_codes"] != reasons or report["state"] != (
        "unavailable" if reasons else "count_reconciled"
    ):
        raise ValueError(ERROR)

    samples = {}
    for phase in PHASES:
        if phase in ("healthy", "post"):
            (samples[phase],) = (
                e["samples"]
                for e in events
                if e["kind"] == "n11_pacing_reference" and e.get("phase") == phase
            )
        else:
            samples[phase] = [
                e for e in events if e["kind"] == "n11_pair_native" and e["phase"] == phase
            ]
    bounds, records = _bounds(events, samples)
    if payload_hash(report["controller_boundaries"]) != payload_hash(records):
        raise ValueError(ERROR)
    if reasons:
        if report["windows"] != {}:
            raise ValueError(ERROR)
        return {}, reasons

    read_start = trace["identity_read"]["start_ns"]
    windows = {
        p: {k: _integer(v + offset, high=read_start) for k, v in b.items()}
        for p, b in bounds.items()
    }
    if payload_hash(report["windows"]) != payload_hash(windows):
        raise ValueError(ERROR)
    _check_polled_counts(samples, prefix, read_start)
    starts, ends = [r[1] for r in prefix], [r[2] for r in prefix]
    spans = {}
    for phase, window in windows.items():
        start, end = window["phase_start_ns"], window["phase_end_ns"]
        first = max(0, bisect_left(ends, start) - 1)
        stop = bisect_left(starts, end) + 1
        selected = prefix[first:stop]
        if not 4 <= len(selected) <= MAX_EVENTS or end - start > MAX_SPAN_NS:
            spans[phase] = dict(state="unavailable", reason="event_window_outside_limits")
            continue
        spans[phase] = encoded_event_rate(
            [
                dict(clock_id=worker_clock, event_ordinal=n, read_start_ns=a, read_end_ns=b)
                for n, a, b in selected
            ],
            **window,
        )
    return spans, ["encoded_event_phase_unavailable"] if any(
        row["state"] == "unavailable" for row in spans.values()
    ) else []
