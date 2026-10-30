"""Recompute limited cadence screens without trusting producer pass declarations."""

from typing import Literal

from pydantic import StrictBool

from ..calibration.contracts import Hash
from .cadence import SECOND, CadenceChecks, CadenceModel, CadenceProbeEvidence


class CadenceInspection(CadenceModel):
    evidence_hash: Hash
    checks: CadenceChecks
    receiver_counts_consistent: StrictBool
    unrelated_settings_stable: StrictBool
    generation_declared: StrictBool
    producer_assessment_matches: StrictBool
    local_screen: Literal["met", "not_met", "incomplete"]
    declared_restoration_supported: StrictBool
    receiver_scope: Literal["gst_loopback_not_browser"]
    quality: Literal["not_evaluated"]
    resource_cost: Literal["not_evaluated"]
    diagnostic_value: Literal["unverified"]
    capability: Literal["unavailable_unqualified"]
    live_authority: Literal[False]


def inspect_cadence_probe_evidence(evidence):
    evidence = CadenceProbeEvidence.model_validate(evidence)
    report = evidence.report
    checks = {}
    for phase, target in (("baseline", 30), ("during", 24), ("restoration", 30)):
        window = getattr(report.windows, phase)
        for counter in ("capture_buffers", "receiver_frames"):
            ok = False
            if window is not None and report.protocol is not None:
                first, last = window.start, window.end
                duration = last.at_ns - first.at_ns
                delta = getattr(last, counter) - getattr(first, counter)
                between = [o for o in report.observations if first.at_ns <= o.at_ns <= last.at_ns]
                ok = (
                    9 * target * duration <= 10 * delta * SECOND <= 11 * target * duration
                    and all(
                        o.healthy and o.configured_fps == o.negotiated_fps == target
                        for o in between
                    )
                    and all(
                        getattr(b, counter) >= getattr(a, counter)
                        for a, b in zip(between, between[1:], strict=False)
                    )
                )
            checks[phase + "_" + counter] = ok
    frames = report.receiver_timeline
    observations = report.observations
    checks["receiver_continuity"] = (
        report.protocol is not None
        and len(frames) >= 2
        and bool(observations)
        and all(
            0 < b.pts_ns - a.pts_ns <= 250000000
            and 0 <= b.observed_at_ns - a.observed_at_ns <= 500000000
            for a, b in zip(frames, frames[1:], strict=False)
        )
        and all(o.healthy for o in observations)
        and 0 <= observations[-1].at_ns - frames[-1].observed_at_ns <= 500000000
    )
    counts_consistent = bool(observations) and all(
        o.receiver_frames == sum(f.observed_at_ns <= o.at_ns for f in frames) for o in observations
    )
    stable = bool(observations) and len({o.settings_hash for o in observations}) == 1
    declared = report.assessment
    matches = (
        declared is not None
        and declared.checks.model_dump() == checks
        and (declared.status == ("met" if all(checks.values()) else "not_met"))
    )
    complete = (
        all(getattr(report.windows, p) is not None for p in ("baseline", "during", "restoration"))
        and report.protocol is not None
    )
    met = all(checks.values()) and counts_consistent and stable and report.generation is not None
    restoration_supported = (
        checks["restoration_capture_buffers"]
        and checks["restoration_receiver_frames"]
        and counts_consistent
        and stable
        and checks["receiver_continuity"]
        and report.result is not None
        and report.result.restoration == "verified_by_port"
        and report.journal_state == "clean"
        and report.generation is not None
    )
    return CadenceInspection(
        evidence_hash=evidence.content_hash,
        checks=CadenceChecks(**checks),
        receiver_counts_consistent=counts_consistent,
        unrelated_settings_stable=stable,
        generation_declared=report.generation is not None,
        producer_assessment_matches=matches,
        local_screen="incomplete" if not complete else "met" if met else "not_met",
        declared_restoration_supported=restoration_supported,
        receiver_scope="gst_loopback_not_browser",
        quality="not_evaluated",
        resource_cost="not_evaluated",
        diagnostic_value="unverified",
        capability="unavailable_unqualified",
        live_authority=False,
    )
