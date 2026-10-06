"""Strict, immutable registry contracts for N1's offline measurement path."""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import datetime, timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Literal

from pydantic import (
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    field_serializer,
    field_validator,
    model_validator,
)

from .common import (
    ContractModel,
    FiniteFloat,
    NonEmptyStr,
    NonNegativeFiniteFloat,
    NonNegativeInt,
    PositiveFiniteFloat,
    PositiveInt,
    UnitInterval,
)

METRIC_REGISTRY_SCHEMA_VERSION = "metric-registry-v1"

SemanticVersion = Annotated[
    str, Field(strict=True, pattern=r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
]
MetricName = Annotated[str, Field(strict=True, pattern=r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")]
RegistryVersion = Annotated[
    str,
    Field(
        strict=True,
        pattern=r"^latency-metrics-v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$",
    ),
]


class MetricKind(StrEnum):
    GAUGE = "gauge"
    CUMULATIVE_COUNTER = "cumulative_counter"
    EVENT_COUNT = "event_count"
    DERIVED = "derived"


class AggregationKind(StrEnum):
    MEDIAN = "median"
    NEAREST_RANK_P95 = "nearest_rank_p95"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"
    WINDOW_TOTAL = "window_total"
    TIME_WEIGHTED_RATE = "time_weighted_rate"


class MissingDataPolicy(StrEnum):
    OMIT_MISSING_SAMPLES = "omit_missing_samples"
    BREAK_COUNTER_CONTINUITY = "break_counter_continuity"
    REJECT_SERIES_ON_ANY_INVALID_SAMPLE = "reject_series_on_any_invalid_sample"


class CounterResetPolicy(StrEnum):
    REJECT_SEGMENT = "reject_segment"
    REJECT_SERIES = "reject_series"
    ALLOW_DECLARED_WRAPAROUND = "allow_declared_wraparound"


class MetricSource(StrEnum):
    BROWSER_WEBRTC = "browser_webrtc"
    ENGINE_RUNTIME = "engine_runtime"
    ENCODER_PIPELINE = "encoder_pipeline"


class MetricUnit(StrEnum):
    FPS = "fps"
    FRAMES_PER_SECOND = "frames/s"
    FRAMES = "frames"
    FREEZES_PER_MINUTE = "freezes/min"
    FREEZES = "freezes"
    MILLISECONDS_PER_SECOND = "ms/s"
    MILLISECONDS = "ms"
    PACKETS_PER_SECOND = "packets/s"
    PACKETS = "packets"
    KILOBITS_PER_SECOND = "kbps"
    PERCENT = "percent"
    MEBIBYTES = "MiB"
    BUFFERS = "buffers"


class ClockBasis(StrEnum):
    """The exported elapsed field; monotonic provenance is not implied."""

    SOURCE_ELAPSED_MS = "source_elapsed_ms"


def _ordered_sequence(value: object) -> object:
    """Allow JSON arrays/Python tuples, without unordered set or string coercion."""

    if not isinstance(value, (list, tuple)):
        raise ValueError("expected an ordered list or tuple")
    return tuple(value)


def _timestamp(value: object) -> object:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.strip())
    raise ValueError("expected a datetime or ISO timestamp string")


RawFields = Annotated[
    tuple[NonEmptyStr, ...], Field(min_length=1), BeforeValidator(_ordered_sequence)
]
Aggregations = Annotated[
    tuple[AggregationKind, ...], Field(min_length=1), BeforeValidator(_ordered_sequence)
]

GAUGE_AGGREGATIONS = frozenset(
    {
        AggregationKind.MEDIAN,
        AggregationKind.NEAREST_RANK_P95,
        AggregationKind.MINIMUM,
        AggregationKind.MAXIMUM,
    }
)
COUNTER_AGGREGATIONS = frozenset({AggregationKind.TIME_WEIGHTED_RATE, AggregationKind.WINDOW_TOTAL})
GAUGE_UNITS = frozenset(
    {
        MetricUnit.FPS,
        MetricUnit.KILOBITS_PER_SECOND,
        MetricUnit.MILLISECONDS,
        MetricUnit.PERCENT,
        MetricUnit.MEBIBYTES,
        MetricUnit.BUFFERS,
    }
)
COUNTER_RATE_UNITS = frozenset(
    {
        MetricUnit.FRAMES_PER_SECOND,
        MetricUnit.FREEZES_PER_MINUTE,
        MetricUnit.MILLISECONDS_PER_SECOND,
        MetricUnit.PACKETS_PER_SECOND,
    }
)
COUNTER_TOTAL_UNITS = frozenset(
    {MetricUnit.FRAMES, MetricUnit.FREEZES, MetricUnit.MILLISECONDS, MetricUnit.PACKETS}
)


class MetricDefinition(ContractModel):
    """One versioned raw quantity and its permitted output derivations."""

    model_config = ConfigDict(frozen=True)

    name: MetricName
    semantic_version: SemanticVersion
    source: MetricSource
    raw_fields: RawFields
    kind: MetricKind
    canonical_unit: MetricUnit
    primary_aggregation: AggregationKind
    available_aggregations: Aggregations
    clock_basis: ClockBasis
    expected_cadence_ms: PositiveFiniteFloat | None
    cadence_tolerance_ratio: PositiveFiniteFloat | None
    missing_data_policy: MissingDataPolicy
    counter_reset_policy: CounterResetPolicy | None
    non_negative: StrictBool
    description: NonEmptyStr
    counter_width_bits: Annotated[int, Field(strict=True, ge=1, le=64)] | None = None

    @model_validator(mode="after")
    def validate_definition(self) -> MetricDefinition:
        if len(set(self.raw_fields)) != len(self.raw_fields):
            raise ValueError("raw_fields cannot contain duplicates")
        if len(set(self.available_aggregations)) != len(self.available_aggregations):
            raise ValueError("available_aggregations cannot contain duplicates")
        if self.primary_aggregation not in self.available_aggregations:
            raise ValueError("primary_aggregation must belong to available_aggregations")
        if self.cadence_tolerance_ratio is not None and self.expected_cadence_ms is None:
            raise ValueError("cadence_tolerance_ratio requires expected_cadence_ms")
        if self.kind is MetricKind.GAUGE:
            self._validate_gauge()
        elif self.kind is MetricKind.CUMULATIVE_COUNTER:
            self._validate_counter()
        else:
            raise ValueError("event_count and derived definitions are reserved beyond N1")
        object.__setattr__(self, "raw_fields", tuple(sorted(self.raw_fields)))
        object.__setattr__(
            self, "available_aggregations", tuple(sorted(self.available_aggregations))
        )
        return self

    def _validate_gauge(self) -> None:
        if self.counter_reset_policy is not None or self.counter_width_bits is not None:
            raise ValueError("gauges cannot declare counter reset policy or width")
        if self.missing_data_policy is MissingDataPolicy.BREAK_COUNTER_CONTINUITY:
            raise ValueError("gauges cannot use break_counter_continuity")
        if not set(self.available_aggregations) <= GAUGE_AGGREGATIONS:
            raise ValueError("gauges require gauge aggregations")
        if self.canonical_unit not in GAUGE_UNITS:
            raise ValueError("unsupported gauge unit")

    def _validate_counter(self) -> None:
        if self.counter_reset_policy is None:
            raise ValueError("cumulative counters require a counter_reset_policy")
        if self.missing_data_policy is MissingDataPolicy.OMIT_MISSING_SAMPLES:
            raise ValueError("counters cannot omit gaps without breaking continuity")
        if not self.non_negative:
            raise ValueError("cumulative counters must be non_negative")
        if not set(self.available_aggregations) <= COUNTER_AGGREGATIONS:
            raise ValueError("counters require counter aggregations")
        # Each definition has one output unit. A total and a rate need separate
        # names/definitions rather than sharing an ambiguously dimensioned record.
        if len(self.available_aggregations) != 1:
            raise ValueError("counter rate and total require separate definitions")
        units = (
            COUNTER_RATE_UNITS
            if self.primary_aggregation is AggregationKind.TIME_WEIGHTED_RATE
            else COUNTER_TOTAL_UNITS
        )
        if self.canonical_unit not in units:
            raise ValueError("counter unit must match its rate or total aggregation")
        if self.counter_reset_policy is CounterResetPolicy.ALLOW_DECLARED_WRAPAROUND:
            if self.counter_width_bits is None:
                raise ValueError("declared wraparound requires counter_width_bits")
        elif self.counter_width_bits is not None:
            raise ValueError("counter_width_bits requires declared wraparound policy")


Definitions = Annotated[
    tuple[MetricDefinition, ...], Field(min_length=1), BeforeValidator(_ordered_sequence)
]


class MetricRegistry(ContractModel):
    """An immutable registry with canonical ordering and explicit release metadata."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["metric-registry-v1"] = METRIC_REGISTRY_SCHEMA_VERSION
    registry_version: RegistryVersion
    created_at: Annotated[datetime, BeforeValidator(_timestamp)]
    definitions: Definitions

    @model_validator(mode="after")
    def validate_registry(self) -> MetricRegistry:
        if self.created_at.utcoffset() != timedelta(0):
            raise ValueError("created_at must be a timezone-aware UTC timestamp")
        names = [definition.name for definition in self.definitions]
        if len(set(names)) != len(names):
            raise ValueError("metric definition names must be unique")
        object.__setattr__(
            self, "definitions", tuple(sorted(self.definitions, key=lambda item: item.name))
        )
        return self


class MeasurementSample(ContractModel):
    """One immutable source row; unusable evidence never invents a numeric value."""

    model_config = ConfigDict(frozen=True)

    elapsed_ms: NonNegativeFiniteFloat
    captured_at: Annotated[datetime, BeforeValidator(_timestamp)]
    value: FiniteFloat | None
    available: StrictBool
    source_row: PositiveInt
    rejection_reason: NonEmptyStr | None = None
    missing_reason: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_sample_state(self) -> MeasurementSample:
        if self.captured_at.utcoffset() != timedelta(0):
            raise ValueError("captured_at must be a timezone-aware UTC timestamp")
        reasons = int(self.rejection_reason is not None) + int(self.missing_reason is not None)
        if self.value is not None:
            if not self.available or reasons:
                raise ValueError("usable numeric samples must be available and have no reasons")
        elif reasons != 1:
            raise ValueError(
                "samples without values require exactly one missing or rejection reason"
            )
        if not self.available and self.rejection_reason is not None:
            raise ValueError("unavailable source rows are missing, not rejected numeric evidence")
        return self


class MetricSeriesStatus(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    MISSING = "missing"
    REJECTED = "rejected"


class MetricSeriesSummary(ContractModel):
    """Immutable, finite aggregation result with reconstructable source evidence."""

    model_config = ConfigDict(frozen=True, validate_default=True)

    metric_name: MetricName
    semantic_version: SemanticVersion
    registry_version: RegistryVersion
    source: MetricSource
    raw_fields: RawFields
    kind: MetricKind
    canonical_unit: MetricUnit
    primary_aggregation: AggregationKind
    available_aggregations: Aggregations
    clock_basis: ClockBasis
    window_start_ms: NonNegativeFiniteFloat
    window_end_ms: NonNegativeFiniteFloat
    window_duration_ms: PositiveFiniteFloat
    source_sample_count: NonNegativeInt
    usable_sample_count: NonNegativeInt
    usable_source_rows: tuple[PositiveInt, ...]
    accepted_interval_count: NonNegativeInt
    observed_duration_ms: NonNegativeFiniteFloat
    coverage: UnitInterval
    cadence_minimum_ms: PositiveFiniteFloat | None
    cadence_median_ms: PositiveFiniteFloat | None
    cadence_maximum_ms: PositiveFiniteFloat | None
    status: MetricSeriesStatus
    aggregates: Mapping[AggregationKind, FiniteFloat] = Field(default_factory=dict)
    missing_reasons: tuple[NonEmptyStr, ...] = ()
    rejected_reasons: tuple[NonEmptyStr, ...] = ()
    warnings: tuple[NonEmptyStr, ...] = ()

    @field_validator("aggregates", mode="after")
    @classmethod
    def freeze_aggregates(cls, value: Mapping[AggregationKind, float]) -> Mapping:
        return MappingProxyType(dict(sorted(value.items())))

    @field_serializer("aggregates")
    def serialize_aggregates(self, value: Mapping[AggregationKind, float]) -> dict[str, float]:
        return {key.value: number for key, number in value.items()}

    @model_validator(mode="after")
    def validate_summary(self) -> MetricSeriesSummary:
        if self.window_end_ms <= self.window_start_ms or self.window_duration_ms != (
            self.window_end_ms - self.window_start_ms
        ):
            raise ValueError("window duration must match positive elapsed bounds")
        if self.usable_sample_count > self.source_sample_count:
            raise ValueError("usable samples cannot exceed source samples")
        if (
            len(self.usable_source_rows) != self.usable_sample_count
            or len(set(self.usable_source_rows)) != self.usable_sample_count
        ):
            raise ValueError("usable_source_rows must uniquely identify each usable sample")
        if self.accepted_interval_count > max(0, self.usable_sample_count - 1):
            raise ValueError("accepted intervals cannot exceed consecutive usable pairs")
        if self.observed_duration_ms > self.window_duration_ms or (
            (self.accepted_interval_count == 0) != (self.observed_duration_ms == 0)
        ):
            raise ValueError("observed duration must agree with accepted intervals and bounds")
        if not math.isclose(
            self.coverage,
            self.observed_duration_ms / self.window_duration_ms,
            rel_tol=1e-12,
            abs_tol=0,
        ):
            raise ValueError("coverage must equal observed duration divided by window duration")
        cadence = (self.cadence_minimum_ms, self.cadence_median_ms, self.cadence_maximum_ms)
        if any(value is not None for value in cadence) and (
            self.source_sample_count < 2
            or any(value is None for value in cadence)
            or not (cadence[0] <= cadence[1] <= cadence[2])
        ):
            raise ValueError("cadence bounds must form one ordered complete summary")
        if len(set(self.raw_fields)) != len(self.raw_fields) or len(
            set(self.available_aggregations)
        ) != len(self.available_aggregations):
            raise ValueError("summary definition metadata cannot contain duplicates")
        if self.primary_aggregation not in self.available_aggregations or not set(
            self.aggregates
        ) <= set(self.available_aggregations):
            raise ValueError("summary aggregates must be registered by the definition")
        if self.aggregates and (
            self.usable_sample_count == 0 or self.primary_aggregation not in self.aggregates
        ):
            raise ValueError("aggregate results require usable samples and the primary value")
        if (
            self.status in {MetricSeriesStatus.MISSING, MetricSeriesStatus.REJECTED}
            and self.aggregates
        ):
            raise ValueError("missing or rejected series cannot contain aggregates")
        if self.status is MetricSeriesStatus.REJECTED and not self.rejected_reasons:
            raise ValueError("rejected series requires a rejection reason")
        if self.status is MetricSeriesStatus.MISSING and (
            self.usable_sample_count or self.rejected_reasons
        ):
            raise ValueError("missing series cannot claim usable or rejected evidence")
        if self.status is MetricSeriesStatus.INCOMPLETE and not self.usable_sample_count:
            raise ValueError("incomplete series requires some usable evidence")
        if self.status is MetricSeriesStatus.COMPLETE and (
            not self.aggregates
            or self.coverage != 1
            or self.missing_reasons
            or self.rejected_reasons
        ):
            raise ValueError("complete series requires aggregates and full coverage without gaps")
        return self

    @property
    def value(self) -> float | None:
        return self.aggregates.get(self.primary_aggregation)


__all__ = [
    "METRIC_REGISTRY_SCHEMA_VERSION",
    "AggregationKind",
    "ClockBasis",
    "CounterResetPolicy",
    "MetricDefinition",
    "MetricKind",
    "MetricRegistry",
    "MetricSource",
    "MetricUnit",
    "MeasurementSample",
    "MetricSeriesStatus",
    "MetricSeriesSummary",
    "MissingDataPolicy",
]
