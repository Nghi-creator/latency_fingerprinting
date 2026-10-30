"""N10 immutable forensic evidence; this release cannot authorize live mutation."""

from typing import Annotated, Literal

from pydantic import Field, StrictBool, field_validator, model_validator

from ..analytical.policy_release import payload_hash
from ..calibration.contracts import Alias, Hash, check_identity, check_json_size, exact_string
from ..observability.contracts import TraceModel

RELEASE = "n10-live-evidence-v1"
Time = Annotated[int, Field(strict=True, ge=0, le=2**53 - 1)]
Bitrate = Annotated[int, Field(strict=True, ge=1, le=2**31 - 1)]
Phase = Literal["baseline", "during", "restoration"]
EvidenceID = exact_string(r"live-evidence-[a-f0-9]{64}")
MissingReason = Literal[
    "not_attempted",
    "capability_unqualified",
    "cancelled",
    "setter_failed",
    "clock_failed",
    "generation_changed",
    "counter_unavailable",
    "receiver_unavailable",
    "restore_failed",
    "deadline_exceeded",
    "foreign_control",
    "process_interrupted",
]


class EvidenceModel(TraceModel):
    collection_limits = {"windows": 3, "receipts": 3, "samples": 64, "reason_codes": 12}


class ProbeScope(EvidenceModel):
    acquisition_id: Alias
    owner_generation: Alias
    pipeline_generation: Alias
    peer_generation: Alias | None
    clock_domain: Alias
    clock_generation: Alias
    clock_basis: Literal["process_monotonic_relative_ns"]
    provenance: Literal["isolated_synthetic", "declared_producer_capture"]
    producer_revision: exact_string(r"[a-f0-9]{40}")
    image_hash: Hash

    @model_validator(mode="after")
    def peer_binding(self):
        if (self.provenance == "isolated_synthetic") != (self.peer_generation is None):
            raise ValueError("live evidence peer/provenance mismatch")
        return self


class ProbeIntent(EvidenceModel):
    request_id: Alias
    capability_revision: Alias
    policy_hash: Hash
    family: Literal["vp8_target_bitrate"]
    control: Literal["vp8enc.target-bitrate"]
    unit: Literal["bit_per_second"]
    prior_value: Bitrate
    requested_value: Bitrate
    intent_at_ns: Time
    application_deadline_ns: Time
    restoration_deadline_ns: Time
    application_settling_ns: Time
    restoration_settling_ns: Time

    @model_validator(mode="after")
    def ordered_intent(self):
        if not self.requested_value < self.prior_value:
            raise ValueError("live evidence intent must declare bitrate reduction")
        if not self.intent_at_ns < self.application_deadline_ns < self.restoration_deadline_ns:
            raise ValueError("live evidence deadlines must be ordered")
        return self


class SetterReceipt(EvidenceModel):
    phase: Literal["application", "restoration", "cleanup"]
    requested_value: Bitrate
    call_start_ns: Time
    call_end_ns: Time | None
    outcome: Literal["returned", "raised", "interrupted", "unknown"]

    @model_validator(mode="after")
    def bracket(self):
        if self.call_end_ns is not None and self.call_end_ns < self.call_start_ns:
            raise ValueError("live evidence setter clock reversed")
        if self.outcome == "returned" and self.call_end_ns is None:
            raise ValueError("returned setter needs an end time")
        return self


class EncoderSettings(EvidenceModel):
    cpu_used: Annotated[int, Field(strict=True, ge=-16, le=16)]
    min_quantizer: Annotated[int, Field(strict=True, ge=0, le=63)]
    max_quantizer: Annotated[int, Field(strict=True, ge=0, le=63)]
    width: Annotated[int, Field(strict=True, ge=1, le=16383)]
    height: Annotated[int, Field(strict=True, ge=1, le=16383)]
    fps_numerator: Annotated[int, Field(strict=True, ge=1, le=2**31 - 1)]
    fps_denominator: Annotated[int, Field(strict=True, ge=1, le=2**31 - 1)]
    end_usage: Literal["cbr"]
    threads: Annotated[int, Field(strict=True, ge=0, le=64)]
    deadline_us: Time
    keyframe_max_dist: Time
    buffer_initial_ms: Time
    buffer_optimal_ms: Time
    buffer_size_ms: Time
    lag_in_frames: Time
    dropframe_threshold: Annotated[int, Field(strict=True, ge=0, le=100)]
    resize_allowed: StrictBool

    @model_validator(mode="after")
    def quantizer_order(self):
        if self.min_quantizer > self.max_quantizer:
            raise ValueError("live evidence quantizer range reversed")
        return self


class CounterRead(EvidenceModel):
    read_start_ns: Time
    read_end_ns: Time
    counter_generation: Alias | None
    bitrate: Bitrate | None
    encoded_bytes: Time | None
    encoded_frames: Time | None
    decoded_frames: Time | None
    decoded_dropped: Time | None
    settings: EncoderSettings | None

    @model_validator(mode="after")
    def bracket(self):
        if self.read_end_ns < self.read_start_ns:
            raise ValueError("live evidence observation clock reversed")
        return self


class ProbeWindow(EvidenceModel):
    phase: Phase
    start_ns: Time
    end_ns: Time
    samples: Annotated[tuple[CounterRead, ...], Field(max_length=64)]

    @model_validator(mode="after")
    def ordered_samples(self):
        if self.end_ns <= self.start_ns:
            raise ValueError("live evidence needs a positive window")
        previous = None
        for sample in self.samples:
            if not self.start_ns <= sample.read_start_ns <= sample.read_end_ns < self.end_ns:
                raise ValueError("live evidence observation outside half-open window")
            if previous is not None and sample.read_start_ns <= previous.read_end_ns:
                raise ValueError("live evidence observations overlap or repeat")
            previous = sample
        return self


class EvidenceBody(EvidenceModel):
    schema_version: Literal["live-probe-evidence-v1"]
    method_release: Literal[RELEASE]
    assurance: Literal["offline_declared_evidence_not_live_authority"]
    live_authority: Literal[False]
    capability: Literal["unavailable_unqualified"]
    receiver_continuity: Literal["unverified"]
    quality: Literal["not_evaluated"]
    scope: ProbeScope
    intent: ProbeIntent
    receipts: Annotated[tuple[SetterReceipt, ...], Field(max_length=3)]
    windows: Annotated[tuple[ProbeWindow, ...], Field(max_length=3)]
    reason_codes: Annotated[tuple[MissingReason, ...], Field(min_length=1, max_length=12)]

    @field_validator("live_authority", mode="before")
    @classmethod
    def no_authority(cls, value):
        if type(value) is not bool or value is not False:
            raise ValueError("live evidence cannot confer authority")
        return value

    @model_validator(mode="after")
    def bind_evidence(self):
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("live evidence duplicate reasons")
        if "capability_unqualified" not in self.reason_codes:
            raise ValueError("live evidence must retain unqualified capability")
        phases = [receipt.phase for receipt in self.receipts]
        if phases != sorted(set(phases), key=("application", "restoration", "cleanup").index):
            raise ValueError("live evidence setter order or duplicate")
        if phases and phases[0] != "application":
            raise ValueError("live evidence restoration without application attempt")
        previous = self.intent.intent_at_ns
        for receipt in self.receipts:
            if receipt.call_start_ns < previous:
                raise ValueError("live evidence setter chronology")
            previous = (
                receipt.call_end_ns if receipt.call_end_ns is not None else receipt.call_start_ns
            )
            expected = (
                self.intent.requested_value
                if receipt.phase == "application"
                else self.intent.prior_value
            )
            if receipt.requested_value != expected:
                raise ValueError("live evidence setter/intent mismatch")
        window_phases = [window.phase for window in self.windows]
        if window_phases != sorted(
            set(window_phases), key=("baseline", "during", "restoration").index
        ):
            raise ValueError("live evidence window order or duplicate")
        previous = None
        by_receipt = {row.phase: row for row in self.receipts}
        for window in self.windows:
            if previous is not None and window.start_ns < previous.end_ns:
                raise ValueError("live evidence windows overlap")
            previous = window
            for receipt in self.receipts:
                end = (
                    receipt.call_end_ns
                    if receipt.call_end_ns is not None
                    else receipt.call_start_ns
                )
                if window.start_ns <= end and receipt.call_start_ns < window.end_ns:
                    raise ValueError("live evidence window crosses setter bracket")
            required = {"during": "application", "restoration": "restoration"}.get(window.phase)
            if required is not None:
                if required not in by_receipt:
                    raise ValueError("live evidence phase without setter attempt")
                receipt = by_receipt[required]
                settling = (
                    self.intent.application_settling_ns
                    if required == "application"
                    else self.intent.restoration_settling_ns
                )
                if window.start_ns < (receipt.call_end_ns or receipt.call_start_ns) + settling:
                    raise ValueError("live evidence window precedes setter")
            if (
                window.phase == "baseline"
                and "application" in by_receipt
                and window.end_ns > by_receipt["application"].call_start_ns
            ):
                raise ValueError("live evidence baseline after application")
            if (
                window.phase == "during"
                and "restoration" in by_receipt
                and window.end_ns > by_receipt["restoration"].call_start_ns
            ):
                raise ValueError("live evidence during phase after restoration")
        return self


class LiveProbeEvidence(EvidenceBody):
    evidence_id: EvidenceID
    content_hash: Hash

    @model_validator(mode="after")
    def content_identity(self):
        digest = check_identity(
            self, "evidence_id", "live-evidence-", ("evidence_id", "content_hash")
        )
        if self.content_hash != digest:
            raise ValueError("live evidence content hash mismatch")
        check_json_size(self)
        return self


def create_live_probe_evidence(**fields):
    """Seal supplied declarations; validates evidence without executing any control."""
    reserved = {"schema_version", "method_release", "evidence_id", "content_hash", "assurance"}
    if reserved.intersection(fields):
        raise ValueError("live evidence factory received reserved fields")
    payload = dict(
        schema_version="live-probe-evidence-v1",
        method_release=RELEASE,
        assurance="offline_declared_evidence_not_live_authority",
        **fields,
    )
    body = EvidenceBody.model_validate(payload)
    payload = body.model_dump(mode="json")
    digest = payload_hash(payload)
    return LiveProbeEvidence.model_validate(
        dict(payload, evidence_id="live-evidence-" + digest[7:], content_hash=digest)
    )
