"""Detached integer predicates over validated, hash-bound phase evidence."""

from .contracts import PHASES, SECOND
from .result import Effect


def recompute_effect(manifest, result, evidence):
    reason = (
        "adapter_unavailable"
        if manifest.adapter.state == "unavailable"
        else "incomplete_run"
        if result.status != "completed"
        else "cleanup_unverified"
        if result.cleanup.state not in ("restored", "not_required")
        else None
    )
    empty = dict(healthy_fps=None, degraded_fps=None, recovery_fps=None, pressure_cpu_percent=None)
    if reason:
        return Effect(state="unavailable", reason=reason, **empty)
    if any(evidence.get(phase) is None or evidence[phase].state != "complete" for phase in PHASES):
        return Effect(state="unavailable", reason="insufficient_evidence", **empty)
    selected = [evidence.get(phase) for phase in ("healthy", "degraded", "recovery")]
    if any(
        p is None
        or p.state != "complete"
        or len(p.intervals) < 30
        or p.end_ns - p.start_ns < 30 * SECOND
        for p in selected
    ):
        return Effect(state="unavailable", reason="insufficient_evidence", **empty)
    totals = [
        (
            sum(i.frames_end - i.frames_start for i in p.intervals),
            p.end_ns - p.start_ns,
            sum(i.worker_cpu_ns for i in p.intervals),
        )
        for p in selected
    ]
    (h, ht, _), (d, dt, cpu), (r, rt, _) = totals
    contention = manifest.scenario == "host_contention"
    if h * SECOND < 27 * ht:
        reason = "baseline_inadequate"
    elif contention and cpu * 100 < 50 * dt:
        reason = "pressure_not_observed"
    elif (d * ht * 100 > h * dt * 95) if contention else (d * SECOND < 27 * dt):
        reason = "degradation_not_observed"
    elif (r * ht * 100 < h * rt * 95) if contention else (r * SECOND < 27 * rt):
        reason = "recovery_not_observed"
    return Effect(
        state="failed" if reason else "verified",
        reason=reason,
        healthy_fps=h * SECOND / ht,
        degraded_fps=d * SECOND / dt,
        recovery_fps=r * SECOND / rt,
        pressure_cpu_percent=cpu * 100 / dt if contention else None,
    )
