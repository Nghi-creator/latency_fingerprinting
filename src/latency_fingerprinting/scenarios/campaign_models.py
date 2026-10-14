"""Pure additive campaign models; schema imports never load inspection or adapters."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from ..observability.contracts import Commit, Count, Hash, RunID
from .contracts import ExperimentModel, Version
from .pacing import PacingEffect
from .result import Effect

Alias = Annotated[str, Field(strict=True, pattern=r"^campaign-[1-9][0-9]{0,8}$")]


SourceID = Annotated[str, Field(strict=True, pattern=r"^[0-9a-f]{32}$")]


class TrialPlan(ExperimentModel):
    run_id: Annotated[str, Field(strict=True, pattern=r"^run-[1-9][0-9]{0,8}$")]
    source_id: SourceID
    scenario: Literal["healthy", "host_contention", "render_capture_slowdown"]
    assignment: Literal["engineering", "reference", "held_out_query"]
    repeat_index: Annotated[int, Field(strict=True, ge=1, le=100)]


class CampaignPlan(ExperimentModel):
    schema_version: Literal["n5-campaign-plan-v1"]
    campaign_id: Alias
    core_version: Commit
    producer_version: Commit
    node_id: Annotated[str, Field(strict=True, pattern=r"^node-[1-9][0-9]{0,8}$")]
    workload_id: Annotated[str, Field(strict=True, pattern=r"^workload-[1-9][0-9]{0,8}$")]
    host_workers: Annotated[int, Field(strict=True, ge=1, le=8)]
    node_version: Version
    seed: Annotated[int, Field(strict=True, ge=0, le=2**32 - 1)]
    trials: Annotated[tuple[TrialPlan, ...], Field(min_length=1, max_length=24)]

    @model_validator(mode="after")
    def consistency(self):
        for key in ("run_id", "source_id"):
            if len({getattr(t, key) for t in self.trials}) != len(self.trials):
                raise ValueError("source/run reuse forbidden")
        if len({(t.scenario, t.assignment, t.repeat_index) for t in self.trials}) != len(
            self.trials
        ):
            raise ValueError("duplicate repetition")
        return self


class TrialReference(ExperimentModel):
    run_id: RunID
    source_id: SourceID
    status: Literal["exported", "unavailable"]
    reason: (
        Literal[
            "runtime_unavailable",
            "clock_unavailable",
            "source_unavailable",
            "permission_denied",
            "adapter_not_implemented",
        ]
        | None
    )
    file_name: Annotated[str, Field(strict=True, pattern=r"^run-[1-9][0-9]{0,8}\.tar\.gz$")] | None
    bytes: Annotated[int, Field(strict=True, ge=0, le=64 * 1024 * 1024)]
    sha256: Hash | None
    acquisition_started_ns: Count | None
    acquisition_ended_ns: Count | None

    @model_validator(mode="after")
    def consistency(self):
        if self.status == "unavailable":
            if (
                self.reason is None
                or self.file_name is not None
                or self.bytes
                or self.sha256 is not None
                or self.acquisition_started_ns is not None
                or self.acquisition_ended_ns is not None
            ):
                raise ValueError("unavailable acquisition cannot fabricate artifacts/timing")
        elif (
            self.reason is not None
            or self.file_name != self.run_id + ".tar.gz"
            or self.bytes == 0
            or self.sha256 is None
            or self.acquisition_started_ns is None
            or self.acquisition_ended_ns is None
            or self.acquisition_ended_ns <= self.acquisition_started_ns
        ):
            raise ValueError("export requires an actual bounded acquisition and exact artifact")
        return self


class CampaignIndex(ExperimentModel):
    schema_version: Literal["n5-campaign-index-v1"]
    campaign_id: Alias
    plan_sha256: Hash
    state: Literal[
        "running", "finished", "cancelled", "source_unavailable", "trial_failed", "campaign_failed"
    ]
    trials: Annotated[tuple[TrialReference, ...], Field(max_length=24)]


class ClassEffects(ExperimentModel):
    healthy: bool
    host_contention: bool
    render_capture_slowdown: bool


class TrialSummary(ExperimentModel):
    run_id: RunID
    scenario: Literal["healthy", "host_contention", "render_capture_slowdown"]
    assignment: Literal["engineering", "reference", "held_out_query"]
    state: Literal["verified", "failed", "unavailable"]
    reason: (
        Literal[
            "baseline_inadequate",
            "pressure_not_observed",
            "pacing_not_observed",
            "degradation_not_observed",
            "recovery_not_observed",
            "adapter_unavailable",
            "incomplete_run",
            "cleanup_unverified",
            "insufficient_evidence",
            "runtime_unavailable",
            "clock_unavailable",
            "source_unavailable",
            "permission_denied",
            "adapter_not_implemented",
        ]
        | None
    )
    effect: Effect | PacingEffect | None = None


class CampaignReport(ExperimentModel):
    schema_version: Literal["n5-campaign-report-v1"]
    campaign_id: Alias
    state: Literal[
        "running", "finished", "cancelled", "source_unavailable", "trial_failed", "campaign_failed"
    ]
    planned_trials: Annotated[int, Field(strict=True, ge=1, le=24)]
    retained_trials: Annotated[int, Field(strict=True, ge=0, le=24)]
    trials: Annotated[tuple[TrialSummary, ...], Field(max_length=24)]
    repeated_held_out_effects: ClassEffects
    repeated_effect_criteria_passed: bool
    source_independence: Literal["declared_disjoint_acquisitions_requires_external_verification"]
    inherited_n4_acceptance: Literal["pending"]
    phase_1_acceptance: Literal["pending"]
