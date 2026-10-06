"""Pure, definition-driven finite aggregation for N1's shadow measurement path."""

from __future__ import annotations

import math
from collections.abc import Sequence

from ..models import (
    AggregationKind,
    CounterInterval,
    CounterResetPolicy,
    MeasurementSample,
    MetricDefinition,
    MetricKind,
    MetricSeriesStatus,
    MetricSeriesSummary,
    MetricUnit,
    MissingDataPolicy,
)
from ..models.measurement import _counter_rate
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


__all__ = ["aggregate_gauge", "aggregate_counter"]


# Every total definition still records interval rates in its quantity's rate unit.
_COUNTER_RATE_UNITS = {
    MetricUnit.FRAMES: MetricUnit.FRAMES_PER_SECOND,
    MetricUnit.FREEZES: MetricUnit.FREEZES_PER_MINUTE,
    MetricUnit.MILLISECONDS: MetricUnit.MILLISECONDS_PER_SECOND,
    MetricUnit.PACKETS: MetricUnit.PACKETS_PER_SECOND,
}


def aggregate_counter(
    definition: MetricDefinition,
    samples: tuple[MeasurementSample, ...],
    *,
    window_start_ms: float,
    window_end_ms: float,
    registry_version: str,
    warnings: tuple[str, ...] = (),
    source_missing_reason: str | None = None,
) -> MetricSeriesSummary:
    """Derive auditable deltas/rates across adjacent usable counter samples.

    Gaps never create a pair. Reset policy either starts a new baseline, rejects
    all results, or applies explicitly declared finite-width modular arithmetic.
    Arithmetic failures reject the series without publishing partial results.
    """
    if definition.kind is not MetricKind.CUMULATIVE_COUNTER:
        raise ValueError("aggregate_counter requires a cumulative-counter definition")
    if not isinstance(samples, tuple) or not all(
        isinstance(item, MeasurementSample) for item in samples
    ):
        raise ValueError("samples must be an immutable tuple of MeasurementSample records")
    start = _finite_number(window_start_ms, name="window_start_ms")
    end = _finite_number(window_end_ms, name="window_end_ms")
    if start < 0 or end <= start:
        raise ValueError("window bounds must be non-negative with positive duration")
    duration = end - start
    rate_unit = _COUNTER_RATE_UNITS.get(definition.canonical_unit, definition.canonical_unit)
    scale = 60000.0 if rate_unit is MetricUnit.FREEZES_PER_MINUTE else 1000.0
    missing: list[str] = []
    rejected: list[str] = []
    notes = list(warnings)
    rows: list[int] = []
    gaps: list[int] = []
    resets: list[int] = []
    intervals: list[CounterInterval] = []
    cadence: list[float] = []
    seen_rows: set[int] = set()
    previous: MeasurementSample | None = None
    previous_usable = False
    fatal = False
    chronology_valid = True
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
        if usable and sample.value < 0:
            rejected.append(f"{label}: definition forbids negative values")
            usable = False
        if (
            usable
            and definition.counter_width_bits is not None
            and (
                not sample.value.is_integer()
                or int(sample.value) >= 2**definition.counter_width_bits
            )
        ):
            rejected.append(f"{label}: counter value is outside the declared integer width")
            usable = False
        if not usable:
            gaps.append(sample.source_row)
        else:
            rows.append(sample.source_row)
            if previous_usable and chronology_valid:
                delta = sample.value - previous.value
                wrapped = False
                if delta < 0:
                    resets.append(sample.source_row)
                    if (
                        definition.counter_reset_policy
                        is CounterResetPolicy.ALLOW_DECLARED_WRAPAROUND
                    ):
                        delta = float(
                            2**definition.counter_width_bits
                            + int(sample.value)
                            - int(previous.value)
                        )
                        wrapped = True
                        notes.append(f"{label}: applied explicitly declared counter wraparound.")
                    else:
                        rejected.append(f"{label}: counter decreased; reset transition rejected")
                        if definition.counter_reset_policy is CounterResetPolicy.REJECT_SERIES:
                            fatal = True
                if delta >= 0 and not fatal:
                    try:
                        if not math.isfinite(delta):
                            raise ValueError("counter subtraction exceeds the finite numeric range")
                        elapsed = sample.elapsed_ms - previous.elapsed_ms
                        rate = _counter_rate(delta, elapsed, scale)
                        intervals.append(
                            CounterInterval(
                                start_source_row=previous.source_row,
                                end_source_row=sample.source_row,
                                start_elapsed_ms=previous.elapsed_ms,
                                end_elapsed_ms=sample.elapsed_ms,
                                duration_ms=elapsed,
                                delta=delta,
                                rate=rate,
                                wrapped=wrapped,
                            )
                        )
                    except (OverflowError, ValueError) as error:
                        rejected.append(f"{label}: counter arithmetic rejected: {error}")
                        fatal = True
        previous = sample
        previous_usable = usable
    if not samples:
        missing.append(source_missing_reason or "no source samples supplied")
    if (
        definition.missing_data_policy is MissingDataPolicy.REJECT_SERIES_ON_ANY_INVALID_SAMPLE
        and gaps
    ):
        rejected.append("Registered missing-data policy rejects a series with unusable samples.")
        fatal = True
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
        expected, tolerance = definition.expected_cadence_ms, definition.cadence_tolerance_ratio
        if any(
            abs(interval - expected) / max(1.0, tolerance) > expected * min(1.0, tolerance)
            for interval in cadence
        ):
            notes.append("Observed cadence differs from the advisory registered cadence tolerance.")
    aggregates = {}
    observed = 0.0
    if intervals and chronology_valid and not fatal:
        try:
            total = math.fsum(item.delta for item in intervals)
            observed = math.fsum(item.duration_ms for item in intervals)
            if not math.isfinite(total) or not math.isfinite(observed):
                raise ValueError("counter sum exceeds the finite numeric range")
            observed = min(duration, observed)
            rate = _counter_rate(total, observed, scale)
            value = (
                total if definition.primary_aggregation is AggregationKind.WINDOW_TOTAL else rate
            )
            aggregates = {definition.primary_aggregation: value}
        except (OverflowError, ValueError) as error:
            rejected.append(f"counter aggregate arithmetic rejected: {error}")
            fatal = True
    if fatal or not chronology_valid:
        intervals = []
        observed = 0.0
        aggregates = {}
    if len(seen_rows) != len(samples):
        rows = []
        resets = []
        gaps = []
        notes.append("Duplicate source row identities prevent counter row-level audit metadata.")
    coverage = observed / duration
    if aggregates:
        status = (
            MetricSeriesStatus.COMPLETE
            if coverage == 1 and not missing and not rejected
            else MetricSeriesStatus.INCOMPLETE
        )
    elif rejected:
        status = MetricSeriesStatus.REJECTED
    else:
        status = MetricSeriesStatus.INCOMPLETE if rows else MetricSeriesStatus.MISSING
    if rows and not intervals and not rejected:
        notes.append("No adjacent usable counter pair; interval aggregates are unavailable.")
    if aggregates and coverage < 1:
        notes.append(
            "Counter interval coverage is incomplete; totals and rates are not extrapolated."
        )
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
        usable_sample_count=len(rows),
        usable_source_rows=tuple(rows),
        accepted_interval_count=len(intervals),
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
        counter_intervals=tuple(intervals),
        interval_rate_unit=rate_unit,
        reset_source_rows=tuple(dict.fromkeys(resets)),
        gap_source_rows=tuple(dict.fromkeys(gaps)),
    )
