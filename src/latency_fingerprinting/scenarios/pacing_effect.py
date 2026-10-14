"""Independent integer pacing predicates, requiring actual same-frame stage pairs."""

from .contracts import PHASES, SECOND
from .pacing import PacingEffect


def capture_delays(trace):
    values = []
    for stream in trace.streams:
        by_frame = {}
        for event in stream.events:
            by_frame.setdefault(event.frame_id, {})[event.boundary] = event.timestamp_ns
        for frame in stream.frames:
            if frame.correlation != "exact":
                continue
            events = by_frame.get(frame.frame_id, {})
            if "capture_output" in events and "pre_encode_queue_enter" in events:
                delay = events["pre_encode_queue_enter"] - events["capture_output"]
                if delay >= 0:
                    values.append(delay)
    return sorted(values)


def recompute_pacing(manifest, result, evidence, traces):
    empty = dict(
        healthy_fps=None,
        degraded_fps=None,
        recovery_fps=None,
        pressure_cpu_percent=None,
        capture_delay_ns=None,
    )
    reason = (
        "adapter_unavailable"
        if manifest.adapter.state == "unavailable"
        else "incomplete_run"
        if result.status != "completed"
        else "cleanup_unverified"
        if result.cleanup.state not in ("restored", "not_required")
        else None
    )
    if reason:
        return PacingEffect(state="unavailable", reason=reason, **empty)
    if any(p not in evidence or evidence[p].state != "complete" for p in PHASES):
        return PacingEffect(state="unavailable", reason="insufficient_evidence", **empty)
    totals, medians = [], []
    for phase in ("healthy", "degraded", "recovery"):
        item = evidence[phase]
        pairs = capture_delays(traces[phase]) if phase in traces else []
        duration = item.end_ns - item.start_ns
        if len(item.intervals) < 30 or duration < 30 * SECOND or len(pairs) < 30:
            return PacingEffect(state="unavailable", reason="insufficient_evidence", **empty)
        totals.append((sum(i.frames_end - i.frames_start for i in item.intervals), duration))
        medians.append(pairs[(len(pairs) - 1) // 2])
    (h, ht), (d, dt), (r, rt) = totals
    base, delayed, recovered = medians
    if h * SECOND < 27 * ht:
        reason = "baseline_inadequate"
    elif delayed < 40_000_000 or delayed - base < 40_000_000:
        reason = "pacing_not_observed"
    elif d * ht * 100 > h * dt * 95:
        reason = "degradation_not_observed"
    elif r * ht * 100 < h * rt * 95 or recovered > base + 10_000_000:
        reason = "recovery_not_observed"
    return PacingEffect(
        state="failed" if reason else "verified",
        reason=reason,
        healthy_fps=h * SECOND / ht,
        degraded_fps=d * SECOND / dt,
        recovery_fps=r * SECOND / rt,
        pressure_cpu_percent=None,
        capture_delay_ns=delayed,
    )
