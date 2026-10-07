"""Gauge arithmetic, source evidence, coverage and registered missing policies."""

from __future__ import annotations

import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from latency_fingerprinting.adapters import load_pixelated_measurement_samples
from latency_fingerprinting.measurement import aggregation
from latency_fingerprinting.measurement.aggregation import aggregate_gauge
from latency_fingerprinting.measurement.metric_registry import (
    METRIC_REGISTRY_VERSION,
    get_metric_definition,
)
from latency_fingerprinting.models import (
    AggregationKind,
    MeasurementSample,
    MetricDefinition,
    MetricSeriesStatus,
    MetricSeriesSummary,
    WindowPhase,
)

DEFINITION = get_metric_definition("transport.jitter_ms")


def definition(**changes: object) -> MetricDefinition:
    return MetricDefinition.model_validate({**DEFINITION.model_dump(), **changes})


def samples(values, *, times=None, rejected=False, unavailable=False):
    times = times if times is not None else [index * 1000 for index in range(len(values))]
    return tuple(
        MeasurementSample(
            elapsed_ms=time,
            captured_at=datetime(2026, 10, 6, tzinfo=UTC) + timedelta(seconds=index),
            value=value,
            available=not (value is None and unavailable),
            source_row=index + 2,
            missing_reason="missing row value" if value is None and not rejected else None,
            rejection_reason="malformed row value" if value is None and rejected else None,
        )
        for index, (time, value) in enumerate(zip(times, values, strict=True))
    )


def summarize(values, *, metric=DEFINITION, end=None, **sample_options):
    rows = samples(values, **sample_options)
    end = end if end is not None else max(1000, rows[-1].elapsed_ms if rows else 1000)
    return aggregate_gauge(
        metric, rows, window_start_ms=0, window_end_ms=end, registry_version=METRIC_REGISTRY_VERSION
    )


@pytest.mark.parametrize(
    ("values", "median"),
    [
        ([3, 1, 2], 2),
        ([5, 1, 3, 7], 4),
        ([0], 0),
        ([7], 7),
        ([sys.float_info.max, sys.float_info.max], sys.float_info.max),
        ([-sys.float_info.max, -sys.float_info.max], -sys.float_info.max),
        ([-sys.float_info.max, sys.float_info.max], 0),
        ([sys.float_info.max / 2, sys.float_info.max], sys.float_info.max * 0.75),
        ([-sys.float_info.max, -sys.float_info.max / 2], -sys.float_info.max * 0.75),
    ],
)
def test_median_is_finite_for_odd_even_single_zero_and_extreme_values(values, median) -> None:
    result = summarize(values, metric=definition(non_negative=False))
    assert result.value == median
    assert all(math.isfinite(value) for value in result.aggregates.values())
    assert result.aggregates[AggregationKind.MINIMUM] == min(values)
    assert result.aggregates[AggregationKind.MAXIMUM] == max(values)


@pytest.mark.parametrize(
    ("count", "expected"), [(1, 1), (2, 2), (19, 19), (20, 19), (21, 20), (100, 95), (101, 96)]
)
def test_nearest_rank_p95(count: int, expected: int) -> None:
    assert (
        summarize(list(range(1, count + 1))).aggregates[AggregationKind.NEAREST_RANK_P95]
        == expected
    )


def test_only_registered_aggregates_and_primary_value_are_produced() -> None:
    metric = definition(
        primary_aggregation="maximum", available_aggregations=["minimum", "maximum"]
    )
    result = summarize([1, 2, 3], metric=metric)
    assert dict(result.aggregates) == {AggregationKind.MAXIMUM: 3, AggregationKind.MINIMUM: 1}
    assert result.value == 3


def test_complete_summary_reconstructs_from_usable_rows_and_capture_bounds() -> None:
    result = summarize([3, 1, 2])
    assert result.status is MetricSeriesStatus.COMPLETE
    assert result.source_sample_count == result.usable_sample_count == 3
    assert result.usable_source_rows == (2, 3, 4)
    assert result.accepted_interval_count == 2
    assert result.observed_duration_ms == result.window_duration_ms == 2000
    assert result.coverage == 1
    assert (
        result.cadence_minimum_ms == result.cadence_median_ms == result.cadence_maximum_ms == 1000
    )


@pytest.mark.parametrize("options", [{}, {"unavailable": True}, {"rejected": True}])
def test_missing_and_rejected_middle_rows_do_not_bridge_gauge_interval_coverage(options) -> None:
    result = summarize([10, 20, None, 40, 50], **options)
    assert result.value == 30
    assert result.source_sample_count == 5
    assert result.usable_source_rows == (2, 3, 5, 6)
    assert result.usable_sample_count == 4
    assert result.accepted_interval_count == 2
    assert result.observed_duration_ms == 2000
    assert result.coverage == 0.5
    assert result.status is MetricSeriesStatus.INCOMPLETE
    assert result.warnings
    assert bool(result.rejected_reasons) == bool(options.get("rejected"))
    assert bool(result.missing_reasons) != bool(options.get("rejected"))


@pytest.mark.parametrize("options", [{}, {"unavailable": True}, {"rejected": True}])
def test_strict_policy_suppresses_all_aggregates_on_any_unusable_sample(options) -> None:
    metric = definition(missing_data_policy="reject_series_on_any_invalid_sample")
    result = summarize([1, None, 3], metric=metric, **options)
    assert result.status is MetricSeriesStatus.REJECTED
    assert result.usable_sample_count == 2
    assert result.rejected_reasons
    assert result.value is None
    assert not result.aggregates
    assert result.accepted_interval_count == result.observed_duration_ms == result.coverage == 0


@pytest.mark.parametrize("strict", [False, True])
def test_entirely_missing_series_stays_missing_under_either_policy(strict: bool) -> None:
    metric = (
        definition(missing_data_policy="reject_series_on_any_invalid_sample")
        if strict
        else DEFINITION
    )
    result = summarize([None, None], metric=metric)
    assert result.status is MetricSeriesStatus.MISSING
    assert result.usable_sample_count == 0
    assert result.value is None
    assert not result.aggregates


def test_empty_rejected_and_single_sample_series_have_explicit_different_states() -> None:
    empty = summarize([])
    assert empty.status is MetricSeriesStatus.MISSING
    assert empty.missing_reasons == ("no source samples supplied",)
    rejected = summarize([None], rejected=True)
    assert rejected.status is MetricSeriesStatus.REJECTED
    single = summarize([5], times=[500], end=1000)
    assert single.status is MetricSeriesStatus.INCOMPLETE
    assert single.value == 5
    assert single.coverage == 0
    assert single.cadence_median_ms is None


@pytest.mark.parametrize("strict", [False, True])
def test_negative_values_follow_definition_and_missing_policy(strict: bool) -> None:
    metric = (
        definition(missing_data_policy="reject_series_on_any_invalid_sample")
        if strict
        else DEFINITION
    )
    result = summarize([1, -100, 3], metric=metric)
    assert result.usable_sample_count == 2
    assert result.rejected_reasons
    assert result.value == (None if strict else 2)
    assert summarize([1, -100, 3], metric=definition(non_negative=False)).value == 1


@pytest.mark.parametrize(
    "case", ["decreasing", "duplicate_elapsed", "duplicate_utc", "duplicate_row", "outside"]
)
def test_bad_chronology_rejects_whole_series_without_sorting(case: str) -> None:
    rows = samples([1, 2, 3])
    if case == "decreasing":
        rows = (rows[0], rows[2], rows[1])
    else:
        update = {
            "duplicate_elapsed": {"elapsed_ms": 0},
            "duplicate_utc": {"captured_at": rows[0].captured_at},
            "duplicate_row": {"source_row": 2},
            "outside": {"elapsed_ms": 5000},
        }[case]
        rows = (
            rows[0],
            MeasurementSample.model_validate({**rows[1].model_dump(), **update}),
            rows[2],
        )
    result = aggregate_gauge(
        DEFINITION,
        rows,
        window_start_ms=0,
        window_end_ms=2000,
        registry_version=METRIC_REGISTRY_VERSION,
    )
    assert result.status is MetricSeriesStatus.REJECTED
    assert not result.aggregates
    assert result.rejected_reasons
    assert result.accepted_interval_count == result.observed_duration_ms == 0


@pytest.mark.parametrize(
    ("start", "end"),
    [(0, 0), (-1, 1), (1, 0), (True, 1), (0, "1000"), (0, float("inf")), (0, 10**1000)],
)
def test_invalid_bounds_are_configuration_errors_without_arithmetic_exceptions(start, end) -> None:
    with pytest.raises(ValueError):
        aggregate_gauge(
            DEFINITION,
            (),
            window_start_ms=start,
            window_end_ms=end,
            registry_version=METRIC_REGISTRY_VERSION,
        )


def test_invalid_definition_and_mutable_input_are_rejected() -> None:
    with pytest.raises(ValueError, match="gauge definition"):
        aggregate_gauge(
            get_metric_definition("client.frames_decoded_rate_fps"),
            (),
            window_start_ms=0,
            window_end_ms=1000,
            registry_version=METRIC_REGISTRY_VERSION,
        )
    for rows in ([samples([1])[0]], (1,)):
        with pytest.raises(ValueError, match="immutable tuple"):
            aggregate_gauge(
                DEFINITION,
                rows,
                window_start_ms=0,
                window_end_ms=1000,
                registry_version=METRIC_REGISTRY_VERSION,
            )


@pytest.mark.parametrize(
    ("cadence", "tolerance", "warning"),
    [(1000, 0.1, False), (100, 0.1, True), (1e-300, 0.1, True), (1e300, 1e300, False)],
)
def test_cadence_is_advisory_with_safe_extreme_tolerance(cadence, tolerance, warning) -> None:
    metric = definition(expected_cadence_ms=cadence, cadence_tolerance_ratio=tolerance)
    result = summarize([1, 2, 3], metric=metric)
    assert bool(result.warnings) == warning
    assert result.value == 2
    assert result.status is MetricSeriesStatus.COMPLETE


@pytest.mark.parametrize("failure", [OverflowError("overflow"), float("inf")])
def test_duration_arithmetic_failure_becomes_rejected_evidence(
    monkeypatch: pytest.MonkeyPatch, failure
) -> None:
    def failing_sum(values):
        if isinstance(failure, Exception):
            raise failure
        return failure

    monkeypatch.setattr(aggregation.math, "fsum", failing_sum)
    result = summarize([1, 2, 3])
    assert result.status is MetricSeriesStatus.REJECTED
    assert result.rejected_reasons
    assert result.value is None
    assert not result.aggregates


def test_no_io_and_input_preservation_and_deterministic_definition_field_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_io(*args, **kwargs):
        pytest.fail("aggregation must not read files")

    rows = samples([3, 1, 2])
    before = tuple(row.model_dump_json() for row in rows)
    metric = MetricDefinition.model_validate(dict(reversed(list(DEFINITION.model_dump().items()))))
    monkeypatch.setattr(Path, "open", no_io)
    first = aggregate_gauge(
        metric,
        rows,
        window_start_ms=0,
        window_end_ms=2000,
        registry_version=METRIC_REGISTRY_VERSION,
    )
    second = aggregate_gauge(
        DEFINITION,
        rows,
        window_start_ms=0,
        window_end_ms=2000,
        registry_version=METRIC_REGISTRY_VERSION,
    )
    assert first.model_dump_json(by_alias=True) == second.model_dump_json(by_alias=True)
    assert tuple(row.model_dump_json() for row in rows) == before
    assert MetricSeriesSummary.model_validate_json(first.model_dump_json(by_alias=True)) == first


def test_sanitized_bundle_gauges_use_the_same_sample_median_in_shadow() -> None:
    from latency_fingerprinting.json_io import load_model_file
    from latency_fingerprinting.models import ContextKey

    fixture = Path(__file__).resolve().parents[1] / "data/pixelated_bundle"
    bundle = load_pixelated_measurement_samples(
        fixture / "valid-v2",
        context=load_model_file(fixture / "context-v2.json", ContextKey),
        phase=WindowPhase.DEGRADED,
        comparison_case_id="controlled-case-001",
    )
    for name, expected in (
        ("client.received_fps", 54),
        ("host.node_cpu_percent", 6),
        ("encoder.queue_level_buffers", 2),
    ):
        result = aggregate_gauge(
            get_metric_definition(name),
            bundle.series[name].samples,
            window_start_ms=bundle.elapsed_start_ms,
            window_end_ms=bundle.elapsed_end_ms,
            registry_version=bundle.registry_version,
            warnings=bundle.warnings,
        )
        assert result.value == expected
        assert result.coverage == 1
        assert result.warnings == bundle.warnings


@pytest.mark.parametrize(
    "changes",
    [
        {"window_end_ms": 0},
        {"window_duration_ms": 1000},
        {"source_sample_count": 2},
        {"usable_source_rows": (2, 2, 4)},
        {"usable_source_rows": (2, 3)},
        {"accepted_interval_count": 3},
        {"observed_duration_ms": 3000},
        {"accepted_interval_count": 0},
        {"coverage": 0.5},
        {"cadence_minimum_ms": None},
        {"cadence_median_ms": 2000},
        {"raw_fields": ("jitter_ms", "jitter_ms")},
        {"available_aggregations": ("median", "median")},
        {"primary_aggregation": "window_total"},
        {"aggregates": {"window_total": 1, "median": 2}},
        {"aggregates": {"minimum": 1}},
        {"status": "missing"},
        {"status": "rejected"},
        {"missing_reasons": ("gap",)},
        {"rejected_reasons": ("invalid",)},
        {"aggregates": {}},
        {"aggregates": {"median": float("inf")}},
    ],
)
def test_summary_rejects_inconsistent_or_nonfinite_evidence(changes) -> None:
    from pydantic import ValidationError

    data = summarize([1, 2, 3]).model_dump()
    with pytest.raises(ValidationError):
        MetricSeriesSummary.model_validate({**data, **changes})


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "incomplete"},
        {"status": "rejected"},
        {"rejected_reasons": ("invalid",)},
        {"cadence_minimum_ms": 1, "cadence_median_ms": 1, "cadence_maximum_ms": 1},
        {"aggregates": {"median": 0}},
    ],
)
def test_empty_summary_rejects_unsupported_evidence(changes) -> None:
    from pydantic import ValidationError

    data = summarize([]).model_dump()
    with pytest.raises(ValidationError):
        MetricSeriesSummary.model_validate({**data, **changes})


def test_summary_detaches_and_freezes_caller_owned_aggregates() -> None:
    from pydantic import ValidationError

    data = summarize([1, 2, 3]).model_dump()
    aggregates = data["aggregates"]
    result = MetricSeriesSummary.model_validate(data)
    aggregates["median"] = 999
    assert result.value == 2
    with pytest.raises(TypeError):
        result.aggregates[AggregationKind.MEDIAN] = 999
    with pytest.raises(ValidationError):
        result.coverage = 0


def test_empty_series_preserves_source_missing_provenance() -> None:
    result = aggregate_gauge(
        DEFINITION,
        (),
        window_start_ms=0,
        window_end_ms=1000,
        registry_version=METRIC_REGISTRY_VERSION,
        source_missing_reason="optional CSV absent",
    )
    assert result.missing_reasons == ("optional CSV absent",)
    assert result.value is None


def test_all_negative_values_are_rejected_without_imputation() -> None:
    result = summarize([-1, -2])
    assert result.status is MetricSeriesStatus.REJECTED
    assert result.usable_sample_count == 0
    assert result.value is None
    assert result.coverage == 0
