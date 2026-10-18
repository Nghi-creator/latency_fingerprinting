"""Pure raw overhead and derived report shapes, independent of file inspection."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from ..observability.contracts import Commit, Count, Float, Hash, NonnegativeFloat
from .campaign_models import Alias
from .contracts import SECOND, ExperimentModel
from .manifest import Runtime

ORDER = (
    (1, "disabled"),
    (1, "enabled"),
    (2, "enabled"),
    (2, "disabled"),
    (3, "disabled"),
    (3, "enabled"),
    (4, "enabled"),
    (4, "disabled"),
    (5, "disabled"),
    (5, "enabled"),
)


class ProcessMeasure(ExperimentModel):
    warmup_ns: Annotated[int, Field(strict=True, ge=10 * SECOND, le=15 * SECOND)]
    wall_ns: Annotated[int, Field(strict=True, ge=30 * SECOND, le=35 * SECOND)]
    cpu_ns: Count
    frames_start: Count
    frames_end: Count

    @model_validator(mode="after")
    def consistency(self):
        if self.frames_end < self.frames_start or self.cpu_ns > self.wall_ns * 64:
            raise ValueError("counter reset or CPU exceeds bound")
        return self


class OverheadTrial(ProcessMeasure):
    pair: Annotated[int, Field(strict=True, ge=1, le=5)]
    mode: Literal["disabled", "enabled"]
    trace_file_name: (
        Annotated[str, Field(strict=True, pattern=r"^pair-[1-5]-enabled\.tar\.gz$")] | None
    )
    trace_bytes: Annotated[int, Field(strict=True, ge=0, le=32 * 1024 * 1024)]
    trace_sha256: Hash | None
    export_duration_ns: Count | None

    @model_validator(mode="after")
    def references(self):
        if self.trace_file_name is None:
            if (
                self.trace_bytes
                or self.trace_sha256 is not None
                or self.export_duration_ns is not None
            ):
                raise ValueError("missing trace cannot retain metadata")
        elif (
            self.mode != "enabled"
            or self.trace_file_name != f"pair-{self.pair}-enabled.tar.gz"
            or self.trace_bytes == 0
            or self.trace_sha256 is None
            or self.export_duration_ns is None
        ):
            raise ValueError("exact enabled trace reference required")
        return self


class ProbeDiagnostic(ExperimentModel):
    baseline: ProcessMeasure
    measured: ProcessMeasure
    probe_durations_ns: Annotated[tuple[Count, ...], Field(max_length=10000)]
    observed_probes: Count

    @model_validator(mode="after")
    def consistency(self):
        if self.observed_probes < len(self.probe_durations_ns):
            raise ValueError("sample count exceeds actual observations")
        return self


class OverheadEvidence(ExperimentModel):
    schema_version: Literal["n4-overhead-evidence-v1"]
    provenance: Literal["synthetic", "producer_capture"]
    campaign_id: Alias
    plan_sha256: Hash
    core_version: Commit
    producer_version: Commit
    runtime: Runtime | None
    state: Literal["unavailable", "failed", "completed"]
    reason: (
        Literal[
            "runtime_unavailable",
            "clock_unavailable",
            "source_unavailable",
            "permission_denied",
            "cancelled",
            "source_error",
            "cleanup_failed",
        ]
        | None
    )
    trials: Annotated[tuple[OverheadTrial, ...], Field(max_length=10)]
    diagnostic: ProbeDiagnostic | None
    cleanup_verified: bool

    @model_validator(mode="after")
    def consistency(self):
        expected_runtime = "synthetic" if self.provenance == "synthetic" else "linux_x11"
        if self.runtime is not None and self.runtime.kind != expected_runtime:
            raise ValueError("overhead runtime does not match provenance")
        if (self.state == "completed") != (self.reason is None):
            raise ValueError("overhead state/reason disagree")
        if any(
            (t.pair, t.mode) != expected for t, expected in zip(self.trials, ORDER, strict=False)
        ):
            raise ValueError("predeclared paired order changed")
        if self.state == "unavailable" and (
            self.runtime is not None or self.trials or self.diagnostic is not None
        ):
            raise ValueError("unavailable runtime cannot invent measurements")
        if self.state == "completed" and (
            self.runtime is None
            or len(self.trials) != 10
            or not self.cleanup_verified
            or self.diagnostic is None
            or len(self.diagnostic.probe_durations_ns) < 1000
            or any(t.mode == "enabled" and t.trace_file_name is None for t in self.trials)
        ):
            raise ValueError(
                "completion requires all real counters, traces, diagnostics and cleanup"
            )
        return self


class PairSummary(ExperimentModel):
    pair: Annotated[int, Field(strict=True, ge=1, le=5)]
    disabled_cpu_percent: NonnegativeFloat
    enabled_cpu_percent: NonnegativeFloat
    disabled_fps: NonnegativeFloat
    enabled_fps: NonnegativeFloat
    cpu_increase_percentage_points: Float
    fps_change_fraction: Float | None


class NominalSummary(ExperimentModel):
    pair: Annotated[int, Field(strict=True, ge=1, le=5)]
    queue_pairs: Count
    encode_pairs: Count
    joint_pairs: Count
    frame_count: Count
    drops: Count
    nominal_capture_passed: bool
    export_duration_ns: Count


class DiagnosticSummary(ExperimentModel):
    observed_probes: Count
    retained_samples: Count
    min_ns: Count | None
    mean_ns: NonnegativeFloat | None
    max_ns: Count | None
    cpu_increase_percentage_points: Float
    fps_change_fraction: Float | None


class OverheadReport(ExperimentModel):
    schema_version: Literal["n4-overhead-report-v1"]
    state: Literal["unavailable", "failed", "completed"]
    reason: (
        Literal[
            "runtime_unavailable",
            "clock_unavailable",
            "source_unavailable",
            "permission_denied",
            "cancelled",
            "source_error",
            "cleanup_failed",
        ]
        | None
    )
    provenance: Literal["synthetic", "producer_capture"]
    pairs: Annotated[tuple[PairSummary, ...], Field(max_length=5)]
    median_cpu_increase_percentage_points: Float | None
    median_fps_change_fraction: Float | None
    baseline_passed: bool
    nominal_traces: Annotated[tuple[NominalSummary, ...], Field(max_length=5)]
    diagnostic: DiagnosticSummary | None
    measured_thresholds_passed: bool
    real_overhead_acceptance: bool
    remaining_n4_cases: Literal[
        "interruption_tiny_capacity_reenable_two_peer_browser_require_separate_evidence"
    ]
    phase_1_acceptance: Literal["pending"]
