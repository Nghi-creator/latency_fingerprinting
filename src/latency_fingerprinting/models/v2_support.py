"""Clock, capability and unavailable timing evidence for observation-v2."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Annotated, Literal

from pydantic import BeforeValidator, StrictBool, model_validator

from .common import NonEmptyStr, NonNegativeFiniteFloat, NonNegativeInt, PositiveFiniteFloat
from .measurement import ClockBasis, MetricSource, SemanticVersion, _timestamp
from .v2_common import V2Model

SupportState = Literal["supported", "unsupported", "unavailable"]
SourceSupportBasis = Literal["source_declaration", "source_rows", "source_absent"]
MetricSupportBasis = Literal["measurement_declaration", "source_support", "source_rows"]
ValidityReason = Literal[
    "producer_invalid", "required_source_unavailable", "source_samples_unavailable"
]


class WindowClock(V2Model):
    basis: ClockBasis
    provenance: Literal["wall_clock_derived_elapsed", "synthetic_elapsed"]
    domain_id: NonEmptyStr
    elapsed_start_ms: NonNegativeFiniteFloat
    elapsed_end_ms: NonNegativeFiniteFloat
    duration_ms: PositiveFiniteFloat
    started_at: Annotated[
        datetime | None, BeforeValidator(lambda v: None if v is None else _timestamp(v))
    ]
    ended_at: Annotated[
        datetime | None, BeforeValidator(lambda v: None if v is None else _timestamp(v))
    ]

    @model_validator(mode="after")
    def validate_clock(self):
        if self.elapsed_end_ms <= self.elapsed_start_ms or self.duration_ms != (
            self.elapsed_end_ms - self.elapsed_start_ms
        ):
            raise ValueError("clock duration must match positive elapsed bounds")
        if self.provenance == "synthetic_elapsed":
            if self.started_at is not None or self.ended_at is not None:
                raise ValueError("synthetic clocks cannot claim UTC capture bounds")
        else:
            if self.started_at is None or self.ended_at is None:
                raise ValueError("Pixelated clocks require both UTC bounds")
            if any(t.utcoffset() != timedelta(0) for t in (self.started_at, self.ended_at)):
                raise ValueError("capture bounds must use UTC")
            utc_duration = (self.ended_at - self.started_at).total_seconds()
            if utc_duration <= 0 or not math.isclose(
                self.duration_ms / 1000, utc_duration, rel_tol=1e-6, abs_tol=0.001
            ):
                raise ValueError("UTC and elapsed durations disagree")
        return self


class SourceSupport(V2Model):
    state: SupportState
    declared_state: SupportState | None
    basis: SourceSupportBasis
    source_file: Literal["stream-telemetry.csv", "engine-telemetry.csv"] | None
    row_count: NonNegativeInt
    available_row_count: NonNegativeInt

    @model_validator(mode="after")
    def validate_support(self):
        if self.available_row_count > self.row_count:
            raise ValueError("available rows cannot exceed source rows")
        if self.declared_state is not None:
            if self.basis != "source_declaration" or self.state != self.declared_state:
                raise ValueError("source state must follow its declaration")
        else:
            expected_basis = "source_rows" if self.row_count else "source_absent"
            expected_state = "supported" if self.available_row_count else "unavailable"
            if self.basis != expected_basis or self.state != expected_state:
                raise ValueError("inferred source state/basis must follow observed rows")
        if self.state != "supported" and self.available_row_count:
            raise ValueError("unsupported/unavailable sources cannot claim available rows")
        return self


class MetricSupport(V2Model):
    state: SupportState
    declared_state: SupportState | None
    basis: MetricSupportBasis


def resolve_metric_support(source: SourceSupport, declared_state: SupportState | None):
    """Select controlling typed evidence; metric declarations win ties."""
    for state in ("unsupported", "unavailable", "supported"):
        if declared_state == state:
            return state, "measurement_declaration"
        if source.state == state:
            basis = "source_support" if source.declared_state is not None else "source_rows"
            return state, basis
    raise ValueError("unrecognized support state")


class WindowValidityV2(V2Model):
    is_valid: StrictBool
    reason_codes: tuple[ValidityReason, ...]

    @model_validator(mode="after")
    def validate_reasons(self):
        if self.is_valid != (not self.reason_codes) or len(set(self.reason_codes)) != len(
            self.reason_codes
        ):
            raise ValueError("validity must agree with unique reason codes")
        return self


class StageTiming(V2Model):
    stage: Literal["capture", "encode", "decode", "render"]
    state: Literal["measured", "estimated", "unavailable"]
    source: MetricSource
    method_id: NonEmptyStr | None
    method_version: SemanticVersion | None
    clock_domain_id: NonEmptyStr | None
    unit: Literal["ms"]
    statistic: Literal["sample_mean"] | None
    value: NonNegativeFiniteFloat | None
    sample_count: NonNegativeInt
    reason_code: Literal["not_instrumented", "unsupported_source", "source_unavailable"] | None

    @model_validator(mode="after")
    def validate_timing(self):
        if self.state != "unavailable":
            raise ValueError("no measured/estimated stage methods are approved in N2")
        if (
            any(
                value is not None
                for value in (
                    self.method_id,
                    self.method_version,
                    self.clock_domain_id,
                    self.statistic,
                    self.value,
                )
            )
            or self.sample_count != 0
            or self.reason_code is None
        ):
            raise ValueError("unavailable timing requires null evidence, zero count and a reason")
        return self
