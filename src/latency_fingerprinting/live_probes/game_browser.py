"""Additive engineering evidence for the contained real-game/browser acquisition."""

from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from ..analytical.policy_release import payload_hash
from ..calibration.contracts import Alias, Hash, check_identity, check_json_size, exact_string
from .cadence import (
    CadenceGeneration,
    CadenceModel,
    CadenceObservation,
    CadenceOutcome,
    CadenceReceipt,
    CadenceWindows,
    Count,
)
from .models import Time

Number = Annotated[float, Field(strict=True, allow_inf_nan=False, ge=0, le=2**53 - 1)]
RawHash = exact_string(r"[a-f0-9]{64}")
Mode = Literal["changed", "sham", "cancel", "disconnect"]
Width = Annotated[int, Field(strict=True, ge=640, le=640)]
Height = Annotated[int, Field(strict=True, ge=480, le=480)]
SourceName = exact_string(
    r"(?:private_journal\.py|live_probe_control/[a-z_]{1,64}\.py|"
    r"scripts/n10/[A-Za-z0-9_]{1,64}(?:\.test)?\.mjs)"
)


class GameBrowserModel(CadenceModel):
    collection_limits = {
        **CadenceModel.collection_limits,
        "browser_stats": 128,
        "visual_samples": 128,
        "resource_samples": 512,
        "browser_resources": 128,
        "source_hashes": 32,
    }


class SourceBinding(GameBrowserModel):
    name: SourceName
    sha256: RawHash


class GameBrowserProtocol(GameBrowserModel):
    prior_fps: Time
    target_fps: Time
    duration_ns: Time
    settling_ns: Time
    maximum_pts_gap_ns: Time
    maximum_worker_pull_gap_ns: Time
    rate_tolerance_percent: Time
    maximum_game_inputs: Time
    maximum_browser_frames_dropped: Time
    maximum_browser_freeze_count: Time
    minimum_visual_color_bins: Time
    warmup_ns: Time
    baseline_measure_ns: Time
    restoration_measure_ns: Time
    restoration_settling_ns: Time
    visual_sample_period_ns: Time
    browser_stats_period_ns: Time

    @model_validator(mode="after")
    def fixed_context(self):
        expected = (
            30,
            24,
            3000000000,
            500000000,
            250000000,
            500000000,
            10,
            64,
            0,
            0,
            4,
            3000000000,
            1000000000,
            750000000,
            200000000,
            500000000,
            200000000,
        )
        if tuple(self.model_dump().values()) != expected:
            raise ValueError("unsupported game/browser engineering protocol")
        return self


class BrowserFrame(GameBrowserModel):
    type: Literal["frame"]
    pts_ns: Time
    browser_at_ns: Time
    presented_frames: Annotated[int, Field(strict=True, ge=1, le=10000)]
    width: Width
    height: Height
    worker_at_ns: Time


class BrowserCounters(GameBrowserModel):
    framesReceived: Count | None
    framesDecoded: Count | None
    framesDropped: Count | None
    freezeCount: Count | None
    totalFreezesDuration: Number | None
    totalDecodeTime: Number | None
    jitterBufferDelay: Number | None
    jitterBufferEmittedCount: Count | None
    frameWidth: Count | None
    frameHeight: Count | None
    keyFramesDecoded: Count | None
    packetsLost: Count | None
    bytesReceived: Count | None


class BrowserStats(GameBrowserModel):
    type: Literal["stats"]
    browser_at_ns: Time
    values: BrowserCounters
    worker_at_ns: Time


class BrowserVisual(GameBrowserModel):
    type: Literal["visual"]
    browser_at_ns: Time
    hash: Annotated[int, Field(strict=True, ge=0, le=2**32 - 1)]
    color_bins: Annotated[int, Field(strict=True, ge=0, le=512)]
    worker_at_ns: Time


class GameResources(GameBrowserModel):
    cpu_ticks: Count
    rss_bytes: Count


class WorkerResources(GameBrowserModel):
    at_ns: Time
    read_start_ns: Time
    read_end_ns: Time
    worker_cpu_ns: Time
    game: GameResources

    @model_validator(mode="after")
    def bracket(self):
        if not self.at_ns <= self.read_start_ns <= self.read_end_ns:
            raise ValueError("game/browser resource read bracket reversed")
        return self


class HostBrowserResources(GameBrowserModel):
    host_at_ns: Time
    cpu_seconds: Number
    process_count: Annotated[int, Field(strict=True, ge=1, le=128)]
    inventory_hash: RawHash


class GameBrowserChecks(GameBrowserModel):
    baseline_capture_buffers: bool = Field(strict=True)
    baseline_receiver_frames: bool = Field(strict=True)
    during_capture_buffers: bool = Field(strict=True)
    during_receiver_frames: bool = Field(strict=True)
    restoration_capture_buffers: bool = Field(strict=True)
    restoration_receiver_frames: bool = Field(strict=True)
    presentation_continuity: bool = Field(strict=True)
    nonblank_moving_scene: bool = Field(strict=True)


class DeclaredGameAssessment(GameBrowserModel):
    status: Literal["met", "not_met"]
    checks: GameBrowserChecks


class GameBrowserReport(GameBrowserModel):
    trial_version: Literal["n10-isolated-game-browser-v1"]
    mode: Mode
    live_authority: Literal[False]
    workload: Literal["frozen_bubble_level_1_scripted_arrows"]
    dimensions: tuple[Width, Height]
    receiver_scope: Literal["dedicated_headless_chromium_video"]
    perceptual_quality: Literal["not_evaluated"]
    diagnostic_value: Literal["unverified"]
    status: Literal["observed", "unavailable"]
    teardown: Literal["unknown", "null_observed"]
    protocol: GameBrowserProtocol
    result: CadenceOutcome | None = None
    journal_state: Literal["clean", "active", "dirty", "restored_pending_watchdog"] | None = None
    generation: CadenceGeneration | None = None
    receipts: tuple[CadenceReceipt, ...] = Field(default=(), max_length=2)
    observations: tuple[CadenceObservation, ...] = Field(default=(), max_length=512)
    assessment: DeclaredGameAssessment | None = None
    windows: CadenceWindows = Field(default_factory=CadenceWindows)
    receiver_timeline: tuple[BrowserFrame, ...] = Field(default=(), max_length=1200)
    browser_stats: tuple[BrowserStats, ...] = Field(default=(), max_length=128)
    visual_samples: tuple[BrowserVisual, ...] = Field(default=(), max_length=128)
    resource_samples: tuple[WorkerResources, ...] = Field(default=(), max_length=512)
    resource_clock_ticks_per_second: Annotated[int, Field(strict=True, ge=1, le=1000000)] | None = (
        None
    )
    game_inputs: Annotated[int, Field(strict=True, ge=0, le=64)] | None = None
    scene_cleanup: Literal["reaped", "unknown"]

    @model_validator(mode="after")
    def chronology(self):
        if self.mode == "sham" and (
            self.receipts or self.result is not None or self.journal_state is not None
        ):
            raise ValueError("unchanged control cannot declare a control request")
        if any(r.requested_fps != fps for r, fps in zip(self.receipts, (24, 30), strict=False)):
            raise ValueError("game/browser setter sequence mismatch")
        if any(
            b.before_ns < (a.after_ns if a.after_ns is not None else a.before_ns)
            for a, b in zip(self.receipts, self.receipts[1:], strict=False)
        ):
            raise ValueError("game/browser setter brackets overlap")
        if any(
            b.at_ns <= a.at_ns
            for a, b in zip(self.observations, self.observations[1:], strict=False)
        ):
            raise ValueError("game/browser observation clock reversed")
        previous = -1
        for phase in ("baseline", "during", "restoration"):
            window = getattr(self.windows, phase)
            if window is None:
                continue
            if window.start not in self.observations or window.end not in self.observations:
                raise ValueError("game/browser window endpoint not retained")
            if window.start.at_ns < previous:
                raise ValueError("game/browser windows overlap")
            previous = window.end.at_ns
            if phase == "baseline" and window.start.at_ns < self.protocol.warmup_ns:
                raise ValueError("game/browser baseline includes warmup")
            for receipt in self.receipts:
                end = receipt.after_ns if receipt.after_ns is not None else receipt.before_ns
                if window.start.at_ns <= end and receipt.before_ns <= window.end.at_ns:
                    raise ValueError("game/browser window crosses setter bracket")
            if (
                phase == "baseline"
                and self.receipts
                and window.end.at_ns >= self.receipts[0].before_ns
            ):
                raise ValueError("game/browser baseline follows application")
            if (
                phase == "during"
                and len(self.receipts) > 1
                and window.end.at_ns >= self.receipts[1].before_ns
            ):
                raise ValueError("game/browser during follows restoration")
            index = {"during": 0, "restoration": 1}.get(phase)
            if index is not None and self.mode != "sham":
                if len(self.receipts) <= index or self.receipts[index].after_ns is None:
                    raise ValueError("game/browser window without completed setter bracket")
                settling = (
                    self.protocol.settling_ns
                    if index == 0
                    else self.protocol.restoration_settling_ns
                )
                if window.start.at_ns < self.receipts[index].after_ns + settling:
                    raise ValueError("game/browser window includes settling")
        previous = -1
        previous_at = -1
        for sample in self.resource_samples:
            if (
                sample.at_ns not in {o.at_ns for o in self.observations}
                or sample.read_start_ns <= previous
                or sample.at_ns <= previous_at
            ):
                raise ValueError("game/browser resource sample not bound or ordered")
            previous = sample.read_end_ns
            previous_at = sample.at_ns
        return self


class GameBrowserAcquisition(GameBrowserModel):
    version: Literal["n10-game-browser-acquisition-v1"]
    mode: Mode
    image_hash: Hash
    live_authority: Literal[False]
    browser_clock_basis: Literal["browser_performance_relative_ns"]
    worker_clock_basis: Literal["worker_monotonic_relative_ns"]
    host_clock_basis: Literal["harness_monotonic_relative_ns"]
    clock_alignment: Literal["none"]
    report: GameBrowserReport | None
    browser_resources: tuple[HostBrowserResources, ...] = Field(max_length=128)
    source_hashes: tuple[SourceBinding, ...] = Field(default=(), max_length=32)
    browser_version: exact_string(r"[0-9]{1,4}(?:\.[0-9]{1,6}){2,3}") | None = None
    browser_resource_error: Literal["counter_unavailable"] | None = None
    receiver_screenshot_hash: Hash | None = None
    container_cleanup: Literal["removed_or_already_removed", "unknown"]
    worker_exit_code: Annotated[int, Field(strict=True, ge=-255, le=255)] | None
    failure: (
        Literal[
            "setup_failed", "worker_failed", "browser_cleanup_failed", "container_cleanup_failed"
        ]
        | None
    )
    stderr_bytes: Count
    bounded_stderr_hash: Hash

    @model_validator(mode="after")
    def binding(self):
        if self.report is not None and self.mode != self.report.mode:
            raise ValueError("game/browser acquisition mode mismatch")
        if type(self) is GameBrowserAcquisition:
            names = [b.name for b in self.source_hashes]
            if names != sorted(set(names)):
                raise ValueError("source manifest must be unique and sorted")
        return self


class _RawGameBrowserAcquisition(GameBrowserAcquisition):
    """Temporary operator input only; mutable source map never enters the sealed root."""

    collection_limits = {
        k: v for k, v in GameBrowserModel.collection_limits.items() if k != "source_hashes"
    }
    source_hashes: dict[SourceName, RawHash] = Field(default_factory=dict, max_length=32)

    @field_validator("source_hashes", mode="before")
    @classmethod
    def manifest_bound(cls, value):
        if not isinstance(value, dict) or len(value) > 32:
            raise ValueError("bounded source manifest object required")
        return value


class GameBrowserEvidenceBody(GameBrowserModel):
    schema_version: Literal["game-browser-probe-evidence-v1"]
    method_release: Literal["n10-game-browser-evidence-v1"]
    assurance: Literal["offline_declared_engineering_evidence_not_live_authority"]
    acquisition_id: Alias
    producer_revision: exact_string(r"[a-f0-9]{40}")
    acquisition_hash: Hash
    source_manifest_hash: Hash
    acquisition: GameBrowserAcquisition
    evidence_role: Literal["engineering"]
    capability: Literal["unavailable_unqualified"]
    live_authority: Literal[False]

    @model_validator(mode="after")
    def bindings(self):
        if self.acquisition_hash != payload_hash(self.acquisition.model_dump(mode="json")):
            raise ValueError("game/browser acquisition hash mismatch")
        manifest = {b.name: b.sha256 for b in self.acquisition.source_hashes}
        if self.source_manifest_hash != payload_hash(manifest):
            raise ValueError("game/browser source manifest hash mismatch")
        return self


class GameBrowserProbeEvidence(GameBrowserEvidenceBody):
    evidence_id: exact_string(r"game-browser-evidence-[a-f0-9]{64}")
    content_hash: Hash

    @model_validator(mode="after")
    def identity(self):
        digest = check_identity(
            self, "evidence_id", "game-browser-evidence-", ("evidence_id", "content_hash")
        )
        if self.content_hash != digest:
            raise ValueError("game/browser evidence hash mismatch")
        check_json_size(self)
        return self


def import_game_browser_acquisition(acquisition, *, acquisition_id, producer_revision):
    """Seal the supplied operator record without executing media or granting authority."""
    if type(acquisition) is GameBrowserAcquisition:
        normalized = GameBrowserAcquisition.model_validate(acquisition)
    else:
        raw = _RawGameBrowserAcquisition.model_validate(acquisition).model_dump(mode="json")
        raw["source_hashes"] = [
            dict(name=name, sha256=digest) for name, digest in sorted(raw["source_hashes"].items())
        ]
        normalized = GameBrowserAcquisition.model_validate(raw)
    body = GameBrowserEvidenceBody.model_validate(
        dict(
            schema_version="game-browser-probe-evidence-v1",
            method_release="n10-game-browser-evidence-v1",
            assurance="offline_declared_engineering_evidence_not_live_authority",
            acquisition_id=acquisition_id,
            producer_revision=producer_revision,
            acquisition_hash=payload_hash(normalized.model_dump(mode="json")),
            source_manifest_hash=payload_hash({b.name: b.sha256 for b in normalized.source_hashes}),
            acquisition=normalized,
            evidence_role="engineering",
            capability="unavailable_unqualified",
            live_authority=False,
        )
    ).model_dump(mode="json")
    hashed = payload_hash(body)
    return GameBrowserProbeEvidence.model_validate(
        dict(body, evidence_id="game-browser-evidence-" + hashed[7:], content_hash=hashed)
    )
