"""Additive capture-pacing roots; frozen v1 roots and meanings remain unchanged."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from ..observability.contracts import Count
from .evidence import ExperimentPhaseEvidence
from .manifest import Adapter, ExperimentManifest, RequestedAction
from .result import Artifact, Effect, ExperimentResult

RELEASE = "n5-capture-pacing-v1"


class PacingAdapter(Adapter):
    adapter_id: Literal["bounded_capture_pacing"]


class PacingAction(RequestedAction):
    kind: Literal["capture_pacing"]
    workers: Annotated[int, Field(strict=True, ge=0, le=0)]
    delay_us: Literal[50000]


class ExperimentManifestV2(ExperimentManifest):
    schema_version: Literal["experiment-manifest-v2"]
    method_release: Literal["n5-capture-pacing-v1"]
    scenario: Literal["render_capture_slowdown"]
    adapter: PacingAdapter
    actions: Annotated[tuple[PacingAction, ...], Field(min_length=1, max_length=1)]

    @model_validator(mode="after")
    def consistency(self):
        common = self.model_dump(mode="json")
        common.update(
            schema_version="experiment-manifest-v1",
            method_release="n5-single-cause-v1",
            scenario="healthy",
            adapter=dict(adapter_id="none", state=self.adapter.state, reason=self.adapter.reason),
            actions=[],
        )
        ExperimentManifest.model_validate(common)
        duration = self.phases[2].duration_ns + self.phases[3].duration_ns
        if (
            not 30_000_000_000 <= duration <= 290_000_000_000
            or self.actions[0].max_duration_ns != duration + 10_000_000_000
        ):
            raise ValueError("bounded pacing action must match phase plan")
        return self


class ExperimentPhaseEvidenceV2(ExperimentPhaseEvidence):
    schema_version: Literal["experiment-phase-evidence-v2"]
    method_release: Literal["n5-capture-pacing-v1"]


class PacingArtifact(Artifact):
    schema_version: Literal[
        "experiment-phase-evidence-v2", "stage-trace-record-v1", "observation-window-v2"
    ]

    @model_validator(mode="after")
    def consistency(self):
        common = self.model_dump(mode="json")
        if self.role == "phase_evidence":
            common["schema_version"] = "experiment-phase-evidence-v1"
        Artifact.model_validate(common)
        return self


class PacingEffect(Effect):
    reason: (
        Literal[
            "baseline_inadequate",
            "pacing_not_observed",
            "degradation_not_observed",
            "recovery_not_observed",
            "adapter_unavailable",
            "incomplete_run",
            "cleanup_unverified",
            "insufficient_evidence",
        ]
        | None
    )
    pressure_cpu_percent: None
    capture_delay_ns: Count | None

    @model_validator(mode="after")
    def consistency(self):
        common = self.model_dump(mode="json")
        common.pop("capture_delay_ns")
        if self.reason == "pacing_not_observed":
            common["reason"] = "pressure_not_observed"
        Effect.model_validate(common)
        if (self.state == "unavailable") != (self.capture_delay_ns is None):
            raise ValueError("pacing effect requires measured delay only when available")
        return self


class ExperimentResultV2(ExperimentResult):
    schema_version: Literal["experiment-result-v2"]
    method_release: Literal["n5-capture-pacing-v1"]
    artifacts: Annotated[tuple[PacingArtifact, ...], Field(max_length=18)]
    effect: PacingEffect
