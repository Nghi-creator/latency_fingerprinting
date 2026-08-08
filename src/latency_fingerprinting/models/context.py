"""Context, timing, metric, and observation-window contract models."""

from __future__ import annotations

import math
from datetime import datetime

from pydantic import Field, JsonValue, model_validator

from .common import (
    ContractModel,
    FiniteFloat,
    NonEmptyStr,
    NonNegativeFiniteFloat,
    NonNegativeInt,
    PositiveFiniteFloat,
    PositiveInt,
    ProvenanceKind,
    WindowPhase,
)


class ContextKey(ContractModel):
    """The explicit boundary within which P0 records may be compared."""

    context_id: NonEmptyStr
    compatibility_group: NonEmptyStr
    edge_node_class: NonEmptyStr
    node_id: NonEmptyStr
    operating_system: NonEmptyStr
    runtime_class: NonEmptyStr
    workload_id: NonEmptyStr
    capture_implementation: NonEmptyStr
    encoder_family: NonEmptyStr
    encoder_profile: NonEmptyStr
    transport_implementation: NonEmptyStr
    connection_mode: NonEmptyStr
    client_class: NonEmptyStr
    nominal_stream_profile: dict[str, JsonValue]
    network_scenario: str | None = None
    versions: dict[str, str] = Field(default_factory=dict)


class TimeBounds(ContractModel):
    """Either UTC wall-clock bounds or elapsed synthetic bounds, never both."""

    started_at: datetime | None = None
    ended_at: datetime | None = None
    elapsed_start_s: NonNegativeFiniteFloat | None = None
    elapsed_end_s: NonNegativeFiniteFloat | None = None

    @model_validator(mode="after")
    def validate_bound_pair(self) -> TimeBounds:
        wall_clock = self.started_at is not None or self.ended_at is not None
        elapsed = self.elapsed_start_s is not None or self.elapsed_end_s is not None
        if wall_clock == elapsed:
            raise ValueError("provide exactly one complete wall-clock or elapsed-time bound pair")
        if wall_clock:
            if self.started_at is None or self.ended_at is None:
                raise ValueError("started_at and ended_at must be provided together")
            if self.started_at.tzinfo is None or self.ended_at.tzinfo is None:
                raise ValueError("wall-clock bounds must be timezone-aware UTC timestamps")
            if (
                self.started_at.utcoffset() != self.ended_at.utcoffset()
                or self.started_at.utcoffset().total_seconds() != 0
            ):
                raise ValueError("wall-clock bounds must use UTC offsets")
            if self.ended_at < self.started_at:
                raise ValueError("ended_at must not precede started_at")
        else:
            if self.elapsed_start_s is None or self.elapsed_end_s is None:
                raise ValueError("elapsed_start_s and elapsed_end_s must be provided together")
            if self.elapsed_end_s < self.elapsed_start_s:
                raise ValueError("elapsed_end_s must not precede elapsed_start_s")
        return self


class MetricAggregate(ContractModel):
    """A finite numeric aggregate with enough detail to audit its derivation."""

    unit: NonEmptyStr
    aggregation: NonEmptyStr
    value: FiniteFloat
    count: PositiveInt
    median: FiniteFloat | None = None
    p95: FiniteFloat | None = None
    minimum: FiniteFloat | None = None
    maximum: FiniteFloat | None = None

    @model_validator(mode="after")
    def validate_summary_range(self) -> MetricAggregate:
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum must not exceed maximum")
        for name in ("median", "p95", "value"):
            candidate = getattr(self, name)
            if candidate is not None and self.minimum is not None and candidate < self.minimum:
                raise ValueError(f"{name} must not be below minimum")
            if candidate is not None and self.maximum is not None and candidate > self.maximum:
                raise ValueError(f"{name} must not exceed maximum")
        return self


class ValidityState(ContractModel):
    is_valid: bool
    reasons: list[NonEmptyStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_reason_consistency(self) -> ValidityState:
        if not self.is_valid and not self.reasons:
            raise ValueError("an invalid window requires at least one reason")
        if self.is_valid and self.reasons:
            raise ValueError("a valid window cannot have invalidity reasons")
        return self


class SourceArtifact(ContractModel):
    artifact_id: NonEmptyStr
    source_type: NonEmptyStr
    checksum: str | None = None
    producer: str | None = None


class ObservationWindow(ContractModel):
    """One bounded, aggregated measurement window under a stable context."""

    run_id: NonEmptyStr
    window_id: NonEmptyStr
    comparison_case_id: NonEmptyStr | None = None
    context: ContextKey
    phase: WindowPhase
    bounds: TimeBounds
    duration_s: PositiveFiniteFloat
    sample_count: NonNegativeInt
    effective_settings: dict[str, JsonValue]
    metrics: dict[NonEmptyStr, MetricAggregate]
    missing_metrics: list[NonEmptyStr] = Field(default_factory=list)
    rejected_metrics: dict[NonEmptyStr, NonEmptyStr] = Field(default_factory=dict)
    validity: ValidityState
    source_artifact: SourceArtifact
    provenance: ProvenanceKind
    confounders: list[NonEmptyStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_window_metrics(self) -> ObservationWindow:
        unavailable_metrics = set(self.missing_metrics) | set(self.rejected_metrics)
        overlap = set(self.metrics).intersection(unavailable_metrics)
        if overlap:
            raise ValueError(f"metrics cannot be measured and missing/rejected: {sorted(overlap)}")
        if self.sample_count == 0 and self.metrics:
            raise ValueError("a window with metrics must have a positive sample_count")
        if self.bounds.started_at is not None and self.bounds.ended_at is not None:
            bounded_duration = (self.bounds.ended_at - self.bounds.started_at).total_seconds()
        else:
            assert self.bounds.elapsed_start_s is not None
            assert self.bounds.elapsed_end_s is not None
            bounded_duration = self.bounds.elapsed_end_s - self.bounds.elapsed_start_s
        if not math.isclose(self.duration_s, bounded_duration, rel_tol=1e-9, abs_tol=1e-6):
            raise ValueError("duration_s must equal the duration represented by bounds")
        return self
