"""Pure, definition-driven finite aggregation for N1's shadow measurement path."""

from __future__ import annotations

import math
from collections.abc import Sequence

from ..models import (
    AggregationKind,
    MeasurementSample,
    MetricDefinition,
    MetricKind,
    MetricSeriesStatus,
    MetricSeriesSummary,
    MissingDataPolicy,
)
from .feature_config import _finite_number


def _median(ordered: Sequence[float]) -> float:
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    lower, upper = ordered[midpoint - 1], ordered[midpoint]
    # Avoid overflow for both same-sign and opposite-sign finite extremes.
    return lower + (upper - lower) / 2 if lower >= 0 or upper <= 0 else lower / 2 + upper / 2


def _statistics(
    values: Sequence[float], aggregations: Sequence[AggregationKind]
) -> dict[AggregationKind, float]:
    ordered = sorted(values)
    result = {}
    for aggregation in aggregations:
        if aggregation is AggregationKind.MINIMUM:
            result[aggregation] = ordered[0]
        elif aggregation is AggregationKind.MAXIMUM:
            result[aggregation] = ordered[-1]
        elif aggregation is AggregationKind.MEDIAN:
            result[aggregation] = _median(ordered)
        else:
            # Integer nearest rank avoids floating rounding of 0.95 * n.
            result[aggregation] = ordered[(95 * len(ordered) + 99) // 100 - 1]
    if not all(math.isfinite(number) for number in result.values()):
        raise ValueError("aggregate arithmetic exceeds the finite numeric range")
    return result


def aggregate_gauge(
    definition: MetricDefinition,
    samples: tuple[MeasurementSample, ...],
    *,
    window_start_ms: float,
    window_end_ms: float,
    registry_version: str,
    warnings: tuple[str, ...] = (),
    source_missing_reason: str | None = None,
) -> MetricSeriesSummary:
    """Summarize registered gauges without file I/O, interpolation or imputation.

    Adjacent usable source rows support diagnostic duration coverage. This does
    not time-weight gauge statistics or imply values persisted between samples.
    Invalid source chronology rejects the whole series rather than sorting it.
    """

    if definition.kind is not MetricKind.GAUGE:
        raise ValueError("aggregate_gauge requires a gauge definition")
    if not isinstance(samples, tuple) or not all(
        isinstance(item, MeasurementSample) for item in samples
    ):
        raise ValueError("samples must be an immutable tuple of MeasurementSample records")
    start = _finite_number(window_start_ms, name="window_start_ms")
    end = _finite_number(window_end_ms, name="window_end_ms")
    if start < 0 or end <= start:
        raise ValueError("window bounds must be non-negative with positive duration")
    duration = end - start
    missing: list[str] = []
    rejected: list[str] = []
    notes = list(warnings)
    values: list[float] = []
    rows: list[int] = []
    cadence: list[float] = []
    observed_intervals: list[float] = []
    chronology_valid = True
    previous: MeasurementSample | None = None
    previous_usable = False
    seen_rows = set()
    for sample in samples:
        label = f"{definition.source} row {sample.source_row}"
        if sample.source_row in seen_rows:
            rejected.append(f"{label}: source row identity is duplicated")
            chronology_valid = False
        seen_rows.add(sample.source_row)
        if not start <= sample.elapsed_ms <= end:
            rejected.append(f"{label}: elapsed timestamp is outside the declared window")
            chronology_valid = False
        if previous is not None:
            if (
                sample.elapsed_ms <= previous.elapsed_ms
                or sample.captured_at <= previous.captured_at
            ):
                rejected.append(f"{label}: timestamps must be strictly increasing")
                chronology_valid = False
            else:
                cadence.append(sample.elapsed_ms - previous.elapsed_ms)
        usable = sample.available and sample.value is not None
        if sample.missing_reason is not None:
            missing.append(sample.missing_reason)
        if sample.rejection_reason is not None:
            rejected.append(sample.rejection_reason)
        if usable and definition.non_negative and sample.value < 0:
            rejected.append(f"{label}: definition forbids negative values")
            usable = False
        if usable:
            values.append(sample.value)
            rows.append(sample.source_row)
            if previous_usable and previous is not None and sample.elapsed_ms > previous.elapsed_ms:
                observed_intervals.append(sample.elapsed_ms - previous.elapsed_ms)
        previous = sample
        previous_usable = usable
    if not samples:
        missing.append(source_missing_reason or "no source samples supplied")
    cadence_stats = (
        _statistics(
            cadence, (AggregationKind.MINIMUM, AggregationKind.MEDIAN, AggregationKind.MAXIMUM)
        )
        if cadence and chronology_valid
        else {}
    )
    if (
        definition.expected_cadence_ms is not None
        and definition.cadence_tolerance_ratio is not None
    ):
        expected = definition.expected_cadence_ms
        tolerance = definition.cadence_tolerance_ratio
        if any(
            abs(interval - expected) / max(1.0, tolerance) > expected * min(1.0, tolerance)
            for interval in cadence
        ):
            notes.append("Observed cadence differs from the advisory registered cadence tolerance.")
    aggregates = {}
    observed = 0.0
    interval_count = 0
    if values and chronology_valid:
        strict_rejection = (
            definition.missing_data_policy is MissingDataPolicy.REJECT_SERIES_ON_ANY_INVALID_SAMPLE
            and (missing or rejected)
        )
        if strict_rejection:
            rejected.append(
                "Registered missing-data policy rejects a series with unusable samples."
            )
        else:
            try:
                observed = math.fsum(observed_intervals)
                if not math.isfinite(observed):
                    raise ValueError("observed duration exceeds the finite numeric range")
                # Non-overlapping pairs cannot exceed the window mathematically;
                # clip only accumulated floating-point rounding at the boundary.
                observed = min(duration, observed)
                aggregates = _statistics(values, definition.available_aggregations)
                interval_count = len(observed_intervals)
            except (OverflowError, ValueError) as error:
                rejected.append(str(error))
                observed = 0.0
    # Duplicate row identities make the entire clock/audit sequence unusable.
    if len(set(rows)) != len(rows):
        rows = []
        values = []
    coverage = observed / duration
    if aggregates:
        status = (
            MetricSeriesStatus.COMPLETE
            if coverage == 1 and not missing and not rejected
            else MetricSeriesStatus.INCOMPLETE
        )
    else:
        status = MetricSeriesStatus.REJECTED if rejected else MetricSeriesStatus.MISSING
    if aggregates and coverage < 1:
        notes.append("Gauge interval coverage is incomplete; values are not extrapolated.")
    return MetricSeriesSummary(
        metric_name=definition.name,
        semantic_version=definition.semantic_version,
        registry_version=registry_version,
        source=definition.source,
        raw_fields=definition.raw_fields,
        kind=definition.kind,
        canonical_unit=definition.canonical_unit,
        primary_aggregation=definition.primary_aggregation,
        available_aggregations=definition.available_aggregations,
        clock_basis=definition.clock_basis,
        window_start_ms=start,
        window_end_ms=end,
        window_duration_ms=duration,
        source_sample_count=len(samples),
        usable_sample_count=len(values),
        usable_source_rows=tuple(rows),
        accepted_interval_count=interval_count,
        observed_duration_ms=observed,
        coverage=coverage,
        cadence_minimum_ms=cadence_stats.get(AggregationKind.MINIMUM),
        cadence_median_ms=cadence_stats.get(AggregationKind.MEDIAN),
        cadence_maximum_ms=cadence_stats.get(AggregationKind.MAXIMUM),
        status=status,
        aggregates=aggregates,
        missing_reasons=tuple(missing),
        rejected_reasons=tuple(rejected),
        warnings=tuple(notes),
    )


__all__ = ["aggregate_gauge"]
