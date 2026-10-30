"""Additive, offline cadence evidence from the isolated Gst WebRTC worker."""

from typing import Annotated, Literal

from pydantic import Field, StrictBool, field_validator, model_validator

from ..analytical.policy_release import payload_hash
from ..calibration.contracts import Alias, Hash, check_identity, check_json_size, exact_string
from ..observability.contracts import TraceModel
from .models import Time

FPS = Annotated[int, Field(strict=True, ge=24, le=60)]
Count = Annotated[int, Field(strict=True, ge=0, le=2**53 - 1)]
Phase = Literal["baseline", "during", "restoration"]
SECOND = 1000000000


class CadenceModel(TraceModel):
    collection_limits = {"receipts": 2, "observations": 512, "receiver_timeline": 1200}

    @field_validator("live_authority", mode="before", check_fields=False)
    @classmethod
    def no_authority(cls, value):
        if value is not False:
            raise ValueError("cadence evidence cannot grant live authority")
        return value


class CadenceGeneration(CadenceModel):
    owner: Alias
    pipeline: Alias
    peer: Alias


class CadenceObservation(CadenceModel):
    at_ns: Time
    configured_fps: FPS
    negotiated_fps: FPS
    capture_buffers: Count
    receiver_frames: Count
    healthy: StrictBool
    settings_hash: exact_string(r"[a-f0-9]{64}")


class CadenceWindow(CadenceModel):
    start: CadenceObservation
    end: CadenceObservation

    @model_validator(mode="after")
    def chronology(self):
        if self.end.at_ns <= self.start.at_ns:
            raise ValueError("cadence window must advance")
        return self


class CadenceWindows(CadenceModel):
    baseline: CadenceWindow | None = None
    during: CadenceWindow | None = None
    restoration: CadenceWindow | None = None


class CadenceReceipt(CadenceModel):
    requested_fps: FPS
    before_ns: Time
    after_ns: Time | None

    @model_validator(mode="after")
    def chronology(self):
        if self.after_ns is not None and self.after_ns < self.before_ns:
            raise ValueError("cadence setter clock reversed")
        return self


class ReceivedFrame(CadenceModel):
    pts_ns: Time
    observed_at_ns: Time


class CadenceProtocol(CadenceModel):
    baseline_fps: FPS
    target_fps: FPS
    requested_duration_ns: Time
    settling_ns: Time
    maximum_pts_gap_ns: Time
    maximum_pull_gap_ns: Time
    rate_tolerance_percent: Annotated[int, Field(strict=True, ge=0, le=100)]

    @model_validator(mode="after")
    def fixed_experiment(self):
        if tuple(self.model_dump().values()) != (
            30,
            24,
            3 * SECOND,
            500000000,
            250000000,
            500000000,
            10,
        ):
            raise ValueError("unsupported isolated cadence protocol")
        return self


class CadenceOutcome(CadenceModel):
    request_id: Alias
    outcome: Literal["completed", "aborted", "unknown", "interrupted_teardown"]
    restoration: Literal["verified_by_port", "unknown", "not_verified_teardown"]
    reason: Literal[
        "duration_elapsed",
        "cancelled",
        "health_abort",
        "apply_failed",
        "restore_failed",
        "generation_changed",
        "journal_failed",
        "worker_terminated",
    ]
    live_authority: Literal[False]

    @model_validator(mode="after")
    def consistency(self):
        if self.outcome == "completed" and (
            self.restoration != "verified_by_port" or self.reason != "duration_elapsed"
        ):
            raise ValueError("contradictory declared completion")
        if (self.outcome == "interrupted_teardown") != (
            self.restoration == "not_verified_teardown" and self.reason == "worker_terminated"
        ):
            raise ValueError("contradictory declared teardown")
        return self


class CadenceChecks(CadenceModel):
    baseline_capture_buffers: StrictBool
    baseline_receiver_frames: StrictBool
    during_capture_buffers: StrictBool
    during_receiver_frames: StrictBool
    restoration_capture_buffers: StrictBool
    restoration_receiver_frames: StrictBool
    receiver_continuity: StrictBool


class DeclaredCadenceAssessment(CadenceModel):
    checks: CadenceChecks
    status: Literal["met", "not_met"]


class CadenceWorkerReport(CadenceModel):
    """Frozen normalized report; partial acquisition/failure remains representable."""

    trial_version: Literal["n10-isolated-webrtc-controller-v1"]
    live_authority: Literal[False]
    scope: Literal["disposable_synthetic_gst_webrtc_pair"]
    quality: Literal["not_evaluated"]
    resource_cost: Literal["not_evaluated"]
    diagnostic_value: Literal["unverified"]
    receiver_scope: Literal["gst_loopback_not_browser"]
    clock_basis: Literal["process_monotonic_relative_ns"]
    pts_basis: Literal["receiver_pipeline_pts_not_source_or_browser_aligned"]
    status: Literal["observed", "unavailable"]
    teardown: Literal["not_created", "null_observed", "unknown"]
    generation: CadenceGeneration | None = None
    receipts: tuple[CadenceReceipt, ...] = Field(default=(), max_length=2)
    observations: tuple[CadenceObservation, ...] = Field(default=(), max_length=512)
    windows: CadenceWindows = Field(default_factory=CadenceWindows)
    receiver_timeline: tuple[ReceivedFrame, ...] = Field(default=(), max_length=1200)
    result: CadenceOutcome | None = None
    journal_state: Literal["clean", "active", "dirty", "restored_pending_watchdog"] | None = None
    protocol: CadenceProtocol | None = None
    assessment: DeclaredCadenceAssessment | None = None

    @model_validator(mode="after")
    def chronology(self):
        if any(
            r.requested_fps != expected
            for r, expected in zip(self.receipts, (24, 30), strict=False)
        ):
            raise ValueError("cadence setter sequence differs from fixed protocol")
        if (
            self.receipts
            and self.windows.baseline is not None
            and (self.windows.baseline.end.at_ns >= self.receipts[0].before_ns)
        ):
            raise ValueError("cadence baseline follows application")
        if (
            len(self.receipts) > 1
            and self.windows.during is not None
            and (self.windows.during.end.at_ns >= self.receipts[1].before_ns)
        ):
            raise ValueError("cadence during follows restoration")
        if any(
            b.at_ns <= a.at_ns
            for a, b in zip(self.observations, self.observations[1:], strict=False)
        ):
            raise ValueError("cadence observation clock reversed")
        if any(
            b.before_ns < (a.after_ns or a.before_ns)
            for a, b in zip(self.receipts, self.receipts[1:], strict=False)
        ):
            raise ValueError("cadence setter brackets overlap")
        previous_end = -1
        for phase in ("baseline", "during", "restoration"):
            window = getattr(self.windows, phase)
            if window is None:
                continue
            if window.start not in self.observations or window.end not in self.observations:
                raise ValueError("cadence window endpoint not retained")
            if window.start.at_ns < previous_end:
                raise ValueError("cadence windows overlap")
            previous_end = window.end.at_ns
            for receipt in self.receipts:
                end = receipt.after_ns if receipt.after_ns is not None else receipt.before_ns
                if window.start.at_ns <= end and receipt.before_ns <= window.end.at_ns:
                    raise ValueError("cadence window crosses setter")
            index = {"during": 0, "restoration": 1}.get(phase)
            if index is not None:
                if len(self.receipts) <= index or self.receipts[index].after_ns is None:
                    raise ValueError("cadence window without completed setter bracket")
                settle = 500000000 if phase == "during" else 200000000
                if window.start.at_ns < self.receipts[index].after_ns + settle:
                    raise ValueError("cadence window includes settling")
        return self


class CadenceEvidenceBody(CadenceModel):
    schema_version: Literal["cadence-probe-evidence-v1"]
    method_release: Literal["n10-cadence-evidence-v1"]
    assurance: Literal["offline_declared_evidence_not_live_authority"]
    acquisition_id: Alias
    producer_revision: exact_string(r"[a-f0-9]{40}")
    image_hash: Hash
    source_manifest_hash: Hash
    source_report_hash: Hash
    report: CadenceWorkerReport
    live_authority: Literal[False]
    capability: Literal["unavailable_unqualified"]

    @model_validator(mode="after")
    def report_identity(self):
        if payload_hash(self.report.model_dump(mode="json")) != self.source_report_hash:
            raise ValueError("cadence normalized source report hash mismatch")
        return self


class CadenceProbeEvidence(CadenceEvidenceBody):
    evidence_id: exact_string(r"cadence-evidence-[a-f0-9]{64}")
    content_hash: Hash

    @model_validator(mode="after")
    def identity(self):
        hashed = check_identity(
            self, "evidence_id", "cadence-evidence-", ("evidence_id", "content_hash")
        )
        if self.content_hash != hashed:
            raise ValueError("cadence evidence hash mismatch")
        check_json_size(self)
        return self


def import_cadence_worker_report(
    report, *, acquisition_id, producer_revision, image_hash, source_manifest_hash
):
    """Normalize and seal supplied observations. Never execute or qualify a probe."""
    normalized = CadenceWorkerReport.model_validate(report).model_dump(mode="json")
    body = CadenceEvidenceBody.model_validate(
        dict(
            schema_version="cadence-probe-evidence-v1",
            method_release="n10-cadence-evidence-v1",
            assurance="offline_declared_evidence_not_live_authority",
            acquisition_id=acquisition_id,
            producer_revision=producer_revision,
            image_hash=image_hash,
            source_manifest_hash=source_manifest_hash,
            source_report_hash=payload_hash(normalized),
            report=normalized,
            live_authority=False,
            capability="unavailable_unqualified",
        )
    ).model_dump(mode="json")
    hashed = payload_hash(body)
    return CadenceProbeEvidence.model_validate(
        dict(body, evidence_id="cadence-evidence-" + hashed[7:], content_hash=hashed)
    )
