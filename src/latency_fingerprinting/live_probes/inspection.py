"""Pure reconstruction of declared counters; no capability or lifecycle promotion."""

from typing import Annotated, Literal

from pydantic import Field

from .models import EvidenceModel, LiveProbeEvidence, Phase, Time

REASONS = (
    "insufficient_samples",
    "missing_counter_generation",
    "counter_generation_changed",
    "missing_counter",
    "counter_reset",
    "missing_setting",
    "setting_mismatch",
    "missing_unrelated_settings",
    "unrelated_settings_changed",
    "no_encoded_progress",
    "no_decoded_progress",
)


class WindowInspection(EvidenceModel):
    phase: Phase
    reason_codes: Annotated[tuple[Literal[*REASONS], ...], Field(max_length=len(REASONS))]
    duration_ns: Time | None
    encoded_bytes_delta: Time | None
    encoded_frames_delta: Time | None
    decoded_frames_delta: Time | None
    decoded_dropped_delta: Time | None


class LiveProbeInspection(EvidenceModel):
    evidence_id: str
    live_authority: Literal[False]
    capability: Literal["unavailable_unqualified"]
    receiver_continuity: Literal["unverified"]
    application_attempted: bool
    budget_consumption: Literal["not_attempted", "reservation_required_not_verified"]
    restoration: Literal["not_needed", "unknown", "setting_and_local_progress_only"]
    late_receipt_phases: Annotated[
        tuple[Literal["application", "restoration", "cleanup"], ...], Field(max_length=3)
    ]
    unknown_completion_phases: Annotated[
        tuple[Literal["application", "restoration", "cleanup"], ...], Field(max_length=3)
    ]
    missing_phases: Annotated[tuple[Phase, ...], Field(max_length=3)]
    windows: Annotated[tuple[WindowInspection, ...], Field(max_length=3)]


def inspect_live_probe_evidence(evidence):
    """Revalidate even typed instances; setting reads cannot establish live safety."""
    evidence = LiveProbeEvidence.model_validate(evidence)
    prior_settings = None
    baseline = next((row for row in evidence.windows if row.phase == "baseline"), None)
    if baseline is not None and baseline.samples:
        prior_settings = baseline.samples[0].settings
    results = []
    counters = ("encoded_bytes", "encoded_frames", "decoded_frames", "decoded_dropped")
    for window in evidence.windows:
        samples = window.samples
        reasons = set()
        deltas = {key + "_delta": None for key in counters}
        duration = None
        if len(samples) < 2:
            reasons.add("insufficient_samples")
        else:
            duration = samples[-1].read_start_ns - samples[0].read_start_ns
        if any(row.counter_generation is None for row in samples):
            reasons.add("missing_counter_generation")
        if (
            len({row.counter_generation for row in samples if row.counter_generation is not None})
            > 1
        ):
            reasons.add("counter_generation_changed")
        if any(getattr(row, key) is None for row in samples for key in counters):
            reasons.add("missing_counter")
        else:
            for key in counters:
                if any(
                    getattr(b, key) < getattr(a, key)
                    for a, b in zip(samples, samples[1:], strict=False)
                ):
                    reasons.add("counter_reset")
        expected = (
            evidence.intent.requested_value
            if window.phase == "during"
            else evidence.intent.prior_value
        )
        if any(row.bitrate is None for row in samples):
            reasons.add("missing_setting")
        if any(row.bitrate is not None and row.bitrate != expected for row in samples):
            reasons.add("setting_mismatch")
        if prior_settings is None or any(row.settings is None for row in samples):
            reasons.add("missing_unrelated_settings")
        if prior_settings is not None and any(
            row.settings is not None and row.settings != prior_settings for row in samples
        ):
            reasons.add("unrelated_settings_changed")
        counter_reasons = {
            "insufficient_samples",
            "missing_counter_generation",
            "counter_generation_changed",
            "missing_counter",
            "counter_reset",
        }
        if not reasons.intersection(counter_reasons):
            deltas = {
                key + "_delta": getattr(samples[-1], key) - getattr(samples[0], key)
                for key in counters
            }
            if deltas["encoded_bytes_delta"] == 0 or deltas["encoded_frames_delta"] == 0:
                reasons.add("no_encoded_progress")
            if deltas["decoded_frames_delta"] == 0:
                reasons.add("no_decoded_progress")
        results.append(
            WindowInspection(
                phase=window.phase,
                reason_codes=tuple(key for key in REASONS if key in reasons),
                duration_ns=duration,
                **deltas,
            )
        )
    attempted = bool(evidence.receipts)
    restoration = "unknown" if attempted else "not_needed"
    restored = next((row for row in results if row.phase == "restoration"), None)
    # This is a local observation only. No receiver/quality/journal/watchdog proof
    # exists in v1, so it cannot clear a production dirty state or verify rollback.
    if restored is not None and not restored.reason_codes:
        restoration = "setting_and_local_progress_only"
    deadlines = {
        "application": evidence.intent.application_deadline_ns,
        "restoration": evidence.intent.restoration_deadline_ns,
        "cleanup": evidence.intent.restoration_deadline_ns,
    }
    late = tuple(
        row.phase
        for row in evidence.receipts
        if (
            row.call_start_ns > deadlines[row.phase]
            or row.call_end_ns is not None
            and row.call_end_ns > deadlines[row.phase]
        )
    )
    return LiveProbeInspection(
        evidence_id=evidence.evidence_id,
        live_authority=False,
        capability="unavailable_unqualified",
        receiver_continuity="unverified",
        application_attempted=attempted,
        budget_consumption="reservation_required_not_verified" if attempted else "not_attempted",
        restoration=restoration,
        late_receipt_phases=late,
        unknown_completion_phases=tuple(
            row.phase for row in evidence.receipts if row.call_end_ns is None
        ),
        missing_phases=tuple(
            phase
            for phase in ("baseline", "during", "restoration")
            if phase not in {row.phase for row in results}
        ),
        windows=tuple(results),
    )
