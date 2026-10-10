"""Execution declarations and intrinsic consistency; bundle proof is separate."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from ..observability.contracts import Count, Hash, NonnegativeFloat, RunID, alias_number, ordered
from .contracts import (
    MEASURED,
    SECOND,
    ActionID,
    AdapterReason,
    ArtifactID,
    ExperimentModel,
    Phase,
    Release,
    Workers,
    ordered_times,
    phase_prefix,
)


class ActualPhase(ExperimentModel):
    phase: Phase
    start_ns: Count
    end_ns: Count
    state: Literal["complete", "partial"]

    @model_validator(mode="after")
    def consistency(self):
        ordered_times(self.start_ns, self.end_ns)
        if self.state == "complete" and not SECOND <= self.end_ns - self.start_ns <= 302 * SECOND:
            raise ValueError("complete phase duration is outside plan tolerance bounds")
        if self.end_ns > 1200 * SECOND:
            raise ValueError("phase exceeds run watchdog")
        return self


class ActionResult(ExperimentModel):
    action_id: ActionID
    state: Literal["not_started", "started", "stopped", "failed"]
    started_ns: Count | None
    stopped_ns: Count | None
    reason: Literal["start_failed", "exit_failed", "stop_failed", "cancelled", "timeout"] | None

    @model_validator(mode="after")
    def consistency(self):
        ordered_times(self.started_ns, self.stopped_ns)
        if (self.state == "failed") != (self.reason is not None):
            raise ValueError("action state/reason disagree")
        if self.state == "not_started" and (
            self.started_ns is not None or self.stopped_ns is not None
        ):
            raise ValueError("not-started action cannot retain execution times")
        if self.state == "started" and (self.started_ns is None or self.stopped_ns is not None):
            raise ValueError("started action requires only start")
        if self.state == "stopped" and (self.started_ns is None or self.stopped_ns is None):
            raise ValueError("stopped action requires both times")
        return self


class Effect(ExperimentModel):
    state: Literal["verified", "failed", "unavailable"]
    reason: (
        Literal[
            "baseline_inadequate",
            "pressure_not_observed",
            "degradation_not_observed",
            "recovery_not_observed",
            "adapter_unavailable",
            "incomplete_run",
            "cleanup_unverified",
            "insufficient_evidence",
        ]
        | None
    )
    healthy_fps: NonnegativeFloat | None
    degraded_fps: NonnegativeFloat | None
    recovery_fps: NonnegativeFloat | None
    pressure_cpu_percent: NonnegativeFloat | None

    @model_validator(mode="after")
    def consistency(self):
        reasons = {
            "verified": (None,),
            "failed": (
                "baseline_inadequate",
                "pressure_not_observed",
                "degradation_not_observed",
                "recovery_not_observed",
            ),
            "unavailable": (
                "adapter_unavailable",
                "incomplete_run",
                "cleanup_unverified",
                "insufficient_evidence",
            ),
        }
        if self.reason not in reasons[self.state]:
            raise ValueError("effect state/reason disagree")
        if self.state != "unavailable" and any(
            v is None for v in (self.healthy_fps, self.degraded_fps, self.recovery_fps)
        ):
            raise ValueError("available effect requires throughput values")
        return self


class Cleanup(ExperimentModel):
    state: Literal["not_required", "restored", "failed", "unverified"]
    reason: Literal["stop_failed", "restore_failed", "ownership_lost", "missing_evidence"] | None
    started_ns: Count | None
    ended_ns: Count | None
    owned_workers_remaining: Workers | None

    @model_validator(mode="after")
    def consistency(self):
        ordered_times(self.started_ns, self.ended_ns)
        if (self.state in ("not_required", "restored")) != (self.reason is None):
            raise ValueError("cleanup state/reason disagree")
        if self.state == "not_required" and (
            self.started_ns is not None or self.ended_ns is not None
        ):
            raise ValueError("unneeded cleanup cannot have timestamps")
        if self.state in ("not_required", "restored") and self.owned_workers_remaining != 0:
            raise ValueError("successful cleanup requires zero remaining workers")
        if self.state == "restored" and (self.started_ns is None or self.ended_ns is None):
            raise ValueError("restoration requires timing evidence")
        if (
            self.started_ns is not None
            and self.ended_ns is not None
            and self.ended_ns - self.started_ns > 10 * SECOND
        ):
            raise ValueError("cleanup exceeds its bounded allowance")
        return self


class Artifact(ExperimentModel):
    artifact_id: ArtifactID
    file_name: Annotated[str, Field(strict=True, pattern=r"^artifact-[1-9][0-9]{0,9}\.json$")]
    phase: Phase
    role: Literal["phase_evidence", "stage_trace", "observation_window"]
    schema_version: Literal[
        "experiment-phase-evidence-v1", "stage-trace-record-v1", "observation-window-v2"
    ]
    bytes: Annotated[int, Field(strict=True, ge=1, le=10 * 1024 * 1024)]
    sha256: Hash

    @model_validator(mode="after")
    def consistency(self):
        schemas = {
            "phase_evidence": "experiment-phase-evidence-v1",
            "stage_trace": "stage-trace-record-v1",
            "observation_window": "observation-window-v2",
        }
        if (
            self.file_name != f"{self.artifact_id}.json"
            or self.schema_version != schemas[self.role]
        ):
            raise ValueError("artifact identity or schema disagrees with role")
        if self.role == "stage_trace" and self.phase not in MEASURED:
            raise ValueError("stage traces require a measured phase")
        return self


class ExperimentResult(ExperimentModel):
    schema_version: Literal["experiment-result-v1"]
    method_release: Release
    manifest_sha256: Hash
    run_id: RunID
    status: Literal["completed", "aborted", "unsupported"]
    reason: (
        Literal[
            "cancelled", "timeout", "clock_error", "source_error", "action_failed", "cleanup_failed"
        ]
        | AdapterReason
        | None
    )
    phases: Annotated[tuple[ActualPhase, ...], Field(max_length=6)]
    actions: Annotated[tuple[ActionResult, ...], Field(max_length=6)]
    artifacts: Annotated[tuple[Artifact, ...], Field(max_length=18)]
    effect: Effect
    cleanup: Cleanup

    @model_validator(mode="after")
    def consistency(self):
        reasons = {
            "completed": (None,),
            "aborted": (
                "cancelled",
                "timeout",
                "clock_error",
                "source_error",
                "action_failed",
                "cleanup_failed",
            ),
            "unsupported": (
                "adapter_not_implemented",
                "runtime_unavailable",
                "permission_denied",
                "clock_unavailable",
                "source_unavailable",
            ),
        }
        if self.reason not in reasons[self.status]:
            raise ValueError("execution status/reason disagree")
        phase_prefix(self.phases)
        if self.phases and self.phases[0].start_ns != 0:
            raise ValueError("warmup must define runner origin")
        for index, phase in enumerate(self.phases):
            if phase.state == "partial" and index != len(self.phases) - 1:
                raise ValueError("only final phase may be partial")
            if index:
                previous = self.phases[index - 1]
                gap = phase.start_ns - previous.end_ns
                if not 0 <= gap <= 5 * SECOND or (phase.phase == "probe" and gap):
                    raise ValueError("invalid phase transition gap")
        ordered(self.actions, lambda a: alias_number(a.action_id))
        ordered(self.artifacts, lambda a: alias_number(a.artifact_id))
        pairs = {(a.role, a.phase) for a in self.artifacts}
        if len(pairs) != len(self.artifacts):
            raise ValueError("duplicate role/phase artifact")
        if any(a.phase not in {p.phase for p in self.phases} for a in self.artifacts):
            raise ValueError("artifact belongs to an unexecuted phase")
        started = [a for a in self.actions if a.started_ns is not None]
        if self.cleanup.state == "not_required" and started:
            raise ValueError("started actions require cleanup")
        if self.cleanup.state == "restored" and any(a.stopped_ns is None for a in started):
            raise ValueError("restoration cannot leave started actions unstopped")
        if self.cleanup.state == "restored" and any(
            a.stopped_ns > self.cleanup.ended_ns for a in started
        ):
            raise ValueError("action stop must precede restored cleanup")
        if self.status == "unsupported":
            if (
                self.phases
                or self.actions
                or self.artifacts
                or self.cleanup.state != "not_required"
            ):
                raise ValueError("unsupported execution must be empty")
            if (
                self.effect.state != "unavailable"
                or self.effect.reason != "adapter_unavailable"
                or any(
                    getattr(self.effect, field) is not None
                    for field in (
                        "healthy_fps",
                        "degraded_fps",
                        "recovery_fps",
                        "pressure_cpu_percent",
                    )
                )
            ):
                raise ValueError("unsupported effect must be unavailable without numbers")
        elif self.status == "aborted":
            if self.effect.state != "unavailable" or self.effect.reason != "incomplete_run":
                raise ValueError("aborted effect must retain incomplete-run precedence")
        else:
            if len(self.phases) != 6 or any(p.state != "complete" for p in self.phases):
                raise ValueError("completion requires six complete phases")
            required = {("phase_evidence", p.phase) for p in self.phases} | {
                ("stage_trace", p) for p in MEASURED
            }
            if not required <= pairs:
                raise ValueError("completion requires phase evidence and measured traces")
            if any(a.state != "stopped" for a in self.actions):
                raise ValueError("completed actions must be stopped")
            if self.actions:
                if (
                    self.cleanup.state != "restored"
                    or self.cleanup.ended_ns > self.phases[4].start_ns
                ):
                    raise ValueError("action cleanup must be restored before recovery")
                for action in self.actions:
                    if not self.phases[1].end_ns <= action.started_ns <= self.phases[2].start_ns:
                        raise ValueError("action must start before degradation")
                    if not self.phases[3].end_ns <= action.stopped_ns <= self.phases[4].start_ns:
                        raise ValueError("action must stop before recovery")
        if (
            self.cleanup.state in ("failed", "unverified")
            and self.status == "completed"
            and (self.effect.state != "unavailable" or self.effect.reason != "cleanup_unverified")
        ):
            raise ValueError("unverified restoration cannot supply available effects")
        if self.effect.state == "verified" and self.cleanup.state not in (
            "restored",
            "not_required",
        ):
            raise ValueError("verified effect requires successful cleanup")
        return self
