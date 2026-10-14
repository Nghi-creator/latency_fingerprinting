"""Frozen requested experiment configuration; no measured data or execution."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from ..observability.contracts import ClockID, Commit, Positive, Provenance, RunID
from .contracts import (
    FPS,
    SECOND,
    ActionID,
    AdapterReason,
    Duration,
    ExperimentID,
    ExperimentModel,
    Height,
    NodeID,
    Phase,
    Release,
    Version,
    Width,
    WorkloadID,
    phase_prefix,
)


class Runtime(ExperimentModel):
    kind: Literal["synthetic", "linux_x11"]
    python_version: Version
    node_version: Version
    gst_version: Version
    cpu_allocation: Annotated[int, Field(strict=True, ge=1, le=64)]
    width: Width
    height: Height
    fps: FPS
    codec: Literal["vp8"]
    clock_source: Literal["python_monotonic_ns"]
    clock_resolution_ns: Positive


class Adapter(ExperimentModel):
    adapter_id: Literal["none", "bounded_cpu_pressure"] | None
    state: Literal["available", "unavailable"]
    reason: AdapterReason | None

    @model_validator(mode="after")
    def consistency(self):
        if (self.state == "available") != (self.reason is None):
            raise ValueError("adapter state/reason disagree")
        return self


class PlannedPhase(ExperimentModel):
    phase: Phase
    duration_ns: Duration


class RequestedAction(ExperimentModel):
    action_id: ActionID
    kind: Literal["cpu_pressure"]
    start_phase: Literal["degraded"]
    stop_phase: Literal["recovery"]
    workers: Annotated[int, Field(strict=True, ge=1, le=8)]
    max_duration_ns: Annotated[int, Field(strict=True, ge=40 * SECOND, le=300 * SECOND)]


class TracePolicy(ExperimentModel):
    scope: Literal["per_phase"]
    every_nth_frame: Annotated[int, Field(strict=True, ge=1, le=1000)]
    max_frames: Annotated[int, Field(strict=True, ge=1, le=2000)]
    max_events: Annotated[int, Field(strict=True, ge=1, le=10000)]


class ExperimentManifest(ExperimentModel):
    schema_version: Literal["experiment-manifest-v1"]
    method_release: Release
    experiment_id: ExperimentID
    run_id: RunID
    node_id: NodeID
    workload_id: WorkloadID
    clock_id: ClockID
    provenance: Provenance
    scenario: Literal[
        "healthy",
        "host_contention",
        "render_capture_slowdown",
        "encoder_overload",
        "network_delay",
        "network_jitter",
        "network_loss",
        "bandwidth_pressure",
        "client_decode_pressure",
        "mixed",
        "changing",
    ]
    seed: Annotated[int, Field(strict=True, ge=0, le=2**32 - 1)]
    repeat_index: Annotated[int, Field(strict=True, ge=1, le=100)]
    assignment: Literal["engineering", "reference", "held_out_query"]
    core_version: Commit
    producer_version: Commit
    runtime: Runtime
    adapter: Adapter
    phases: Annotated[tuple[PlannedPhase, ...], Field(min_length=6, max_length=6)]
    actions: Annotated[tuple[RequestedAction, ...], Field(max_length=6)]
    trace_policy: TracePolicy

    @model_validator(mode="after")
    def consistency(self):
        phase_prefix(self.phases)
        if sum(p.duration_ns for p in self.phases) > 1200 * SECOND:
            raise ValueError("planned duration exceeds watchdog")
        expected_runtime = "synthetic" if self.provenance == "synthetic" else "linux_x11"
        if self.runtime.kind != expected_runtime:
            raise ValueError("runtime does not match provenance")
        expected_adapter = {"healthy": "none", "host_contention": "bounded_cpu_pressure"}.get(
            self.scenario
        )
        if self.adapter.adapter_id != expected_adapter:
            raise ValueError("adapter does not match scenario")
        if expected_adapter is None and self.adapter.state != "unavailable":
            raise ValueError("unapproved scenarios must be unavailable")
        if self.scenario == "host_contention":
            pressure_duration = self.phases[2].duration_ns + self.phases[3].duration_ns
            if not 30 * SECOND <= pressure_duration <= 290 * SECOND:
                raise ValueError("pressure duration is outside helper bounds")
            if len(self.actions) != 1:
                raise ValueError("host contention requires one requested action")
            action = self.actions[0]
            if action.workers > self.runtime.cpu_allocation:
                raise ValueError("workers exceed CPU allocation")
            if action.max_duration_ns != pressure_duration + 10 * SECOND:
                raise ValueError("action allowance differs from phase plan")
        elif self.actions:
            raise ValueError("scenario cannot request actions")
        policy = self.trace_policy
        for phase in self.phases[1:5]:
            denominator = SECOND * policy.every_nth_frame
            frames = (phase.duration_ns * self.runtime.fps + denominator - 1) // denominator
            if frames > policy.max_frames or 5 * frames > policy.max_events:
                raise ValueError("planned phase exceeds recording capacity")
        return self
