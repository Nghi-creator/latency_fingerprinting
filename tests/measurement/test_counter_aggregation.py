"""Counter units, continuity, finite arithmetic and deterministic invariants."""

import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from latency_fingerprinting.adapters import load_pixelated_measurement_samples
from latency_fingerprinting.measurement import aggregation
from latency_fingerprinting.measurement.aggregation import aggregate_counter
from latency_fingerprinting.measurement.metric_registry import (
    METRIC_REGISTRY_VERSION,
    get_metric_definition,
)
from latency_fingerprinting.models import (
    CounterInterval,
    MeasurementSample,
    MetricDefinition,
    MetricSeriesStatus,
    MetricSeriesSummary,
    WindowPhase,
)

RATE = get_metric_definition("client.frames_decoded_rate_fps")
TOTAL = get_metric_definition("client.frames_decoded_window_total")


def definition(base=RATE, **changes):
    return MetricDefinition.model_validate({**base.model_dump(), **changes})


def samples(values, times=None, *, rejected=False, unavailable=False):
    times = times if times is not None else [1000 * index for index in range(len(values))]
    return tuple(
        MeasurementSample(
            elapsed_ms=time,
            captured_at=datetime(2026, 10, 6, tzinfo=UTC) + timedelta(seconds=index),
            value=value,
            available=not (value is None and unavailable),
            source_row=index + 2,
            missing_reason="missing source value" if value is None and not rejected else None,
            rejection_reason="malformed source value" if value is None and rejected else None,
        )
        for index, (value, time) in enumerate(zip(values, times, strict=True))
    )


def summarize(values, times=None, *, metric=RATE, end=None, **options):
    source = samples(values, times, **options)
    return aggregate_counter(
        metric,
        source,
        window_start_ms=0,
        window_end_ms=end
        if end is not None
        else max(1000, source[-1].elapsed_ms if source else 1000),
        registry_version=METRIC_REGISTRY_VERSION,
    )


@pytest.mark.parametrize("metric", [RATE, TOTAL])
def test_constant_counter_produces_legitimate_zero(metric):
    result = summarize([17, 17, 17], metric=metric)
    assert result.value == 0
    assert result.status is MetricSeriesStatus.COMPLETE
    assert [pair.delta for pair in result.counter_intervals] == [0, 0]
    assert [pair.rate for pair in result.counter_intervals] == [0, 0]
    assert result.coverage == 1


@pytest.mark.parametrize("spacing", [1, 5, 17])
def test_equivalent_regular_cadence_produces_same_rate(spacing):
    result = summarize(
        [100, 100 + 60 * spacing, 100 + 120 * spacing], [0, 1000 * spacing, 2000 * spacing]
    )
    assert result.value == 60
    assert result.accepted_interval_count == 2
    assert result.observed_duration_ms == 2000 * spacing


def test_irregular_cadence_weights_time_and_reconstructs_totals():
    values, times = [10, 70, 370], [0, 1000, 6000]
    rate = summarize(values, times)
    total = summarize(values, times, metric=TOTAL)
    assert rate.value == 60
    assert total.value == 360
    assert rate.counter_intervals == total.counter_intervals
    assert math.fsum(pair.delta for pair in rate.counter_intervals) == total.value
    assert (
        math.fsum(pair.duration_ms for pair in rate.counter_intervals) == rate.observed_duration_ms
    )
    assert rate.value == total.value / (rate.observed_duration_ms / 1000)
    varying = summarize([0, 100, 200], [0, 1000, 5000])
    assert varying.value == 40  # Unweighted interval-rate average would be 62.5.
    assert [pair.rate for pair in varying.counter_intervals] == [100, 25]


@pytest.mark.parametrize("options", [{}, {"unavailable": True}, {"rejected": True}])
def test_gaps_break_continuity_without_imputing_deltas(options):
    result = summarize([0, 60, None, 1000, 1060], **options)
    assert result.value == 60
    assert result.coverage == 0.5
    assert result.accepted_interval_count == 2
    assert result.gap_source_rows == (4,)
    assert result.usable_source_rows == (2, 3, 5, 6)
    assert result.status is MetricSeriesStatus.INCOMPLETE
    assert sum(pair.delta for pair in result.counter_intervals) == 120
    assert bool(result.rejected_reasons) == options.get("rejected", False)


@pytest.mark.parametrize("options", [{}, {"rejected": True}, {"unavailable": True}])
def test_strict_missing_policy_rejects_partial_results(options):
    result = summarize(
        [0, 60, None, 1000, 1060],
        metric=definition(missing_data_policy="reject_series_on_any_invalid_sample"),
        **options,
    )
    assert result.status is MetricSeriesStatus.REJECTED
    assert not result.counter_intervals
    assert result.value is None
    assert result.observed_duration_ms == 0
    assert result.rejected_reasons


@pytest.mark.parametrize("values", [[], [None], [None, None]])
def test_empty_or_missing_series_has_no_numeric_result(values):
    result = summarize(values)
    assert result.status is MetricSeriesStatus.MISSING
    assert result.value is None
    assert not result.counter_intervals


@pytest.mark.parametrize("values", [[7], [7, None, 9]])
def test_usable_samples_without_adjacent_pair_are_incomplete(values):
    result = summarize(values)
    assert result.status is MetricSeriesStatus.INCOMPLETE
    assert result.value is None
    assert result.accepted_interval_count == 0
    assert result.coverage == 0


@pytest.mark.parametrize("policy", ["reject_segment", "reject_series"])
def test_resets_obey_registered_policy(policy):
    result = summarize([100, 160, 5, 65], metric=definition(counter_reset_policy=policy))
    assert result.reset_source_rows == (4,)
    assert result.rejected_reasons
    if policy == "reject_series":
        assert result.status is MetricSeriesStatus.REJECTED
        assert result.value is None
        assert not result.counter_intervals
    else:
        assert result.value == 60
        assert result.status is MetricSeriesStatus.INCOMPLETE
        assert result.accepted_interval_count == 2
        assert result.coverage == pytest.approx(2 / 3)
        assert [
            (pair.start_source_row, pair.end_source_row) for pair in result.counter_intervals
        ] == [(2, 3), (4, 5)]


def test_multiple_segments_preserve_only_supported_activity():
    result = summarize([0, 60, None, 1000, 1060, 1, 61, None, 2000, 2060], metric=TOTAL)
    assert result.value == 240
    assert result.accepted_interval_count == 4
    assert result.reset_source_rows == (7,)
    assert result.gap_source_rows == (4, 9)


@pytest.mark.parametrize("times", [[0, 0, 2000], [0, 1000, 500]])
def test_nonincreasing_elapsed_clock_rejects_whole_series(times):
    result = summarize([0, 60, 120], times)
    assert result.value is None
    assert result.status is MetricSeriesStatus.REJECTED
    assert result.accepted_interval_count == 0


@pytest.mark.parametrize(
    "changes", [{"source_row": 2}, {"captured_at": datetime(2026, 10, 6, tzinfo=UTC)}]
)
def test_duplicate_row_or_utc_clock_rejects_whole_series(changes):
    source = samples([0, 60])
    modified = MeasurementSample.model_validate({**source[1].model_dump(), **changes})
    result = aggregate_counter(
        RATE,
        (source[0], modified),
        window_start_ms=0,
        window_end_ms=1000,
        registry_version=METRIC_REGISTRY_VERSION,
    )
    assert result.status is MetricSeriesStatus.REJECTED
    assert not result.counter_intervals


def test_out_of_window_sample_rejects_whole_series():
    assert summarize([0, 60, 120], end=1000).status is MetricSeriesStatus.REJECTED


@pytest.mark.parametrize("width", [8, 32, 64])
def test_only_declared_integer_width_permits_wraparound(width):
    maximum_exact = 2**width - 1 if width < 64 else 2**64 - 4096
    result = summarize(
        [maximum_exact, 5, 65],
        metric=definition(
            counter_reset_policy="allow_declared_wraparound", counter_width_bits=width
        ),
    )
    assert result.counter_intervals[0].wrapped
    assert result.counter_intervals[0].delta == 2**width + 5 - maximum_exact
    assert result.reset_source_rows == (3,)
    assert result.coverage == 1
    assert result.warnings


@pytest.mark.parametrize("value", [256, 1.5, -1])
def test_wraparound_rejects_values_outside_declared_integer_domain(value):
    result = summarize(
        [0, value, 10],
        metric=definition(counter_reset_policy="allow_declared_wraparound", counter_width_bits=8),
    )
    assert result.value is None
    assert result.gap_source_rows == (3,)
    assert result.rejected_reasons


def test_undeclared_reset_never_infers_wraparound():
    assert summarize([255, 5]).value is None


@pytest.mark.parametrize(
    "name,expected,unit",
    [
        ("client.freeze_count_rate_per_min", 120, "freezes/min"),
        ("client.freeze_duration_rate_ms_per_s", 2, "ms/s"),
        ("transport.packets_lost_rate_per_s", 2, "packets/s"),
        ("client.frames_decoded_rate_fps", 2, "frames/s"),
        ("client.freeze_count_window_total", 4, "freezes/min"),
        ("client.freeze_duration_window_total_ms", 4, "ms/s"),
        ("transport.packets_lost_window_total", 4, "packets/s"),
    ],
)
def test_registered_units_are_respected(name, expected, unit):
    result = summarize([10, 12, 14], metric=get_metric_definition(name))
    assert result.value == expected
    assert result.interval_rate_unit == unit
    assert result.counter_intervals[0].rate == (120 if unit == "freezes/min" else 2)


def test_huge_nonnegative_subtraction_remains_representable():
    result = summarize([sys.float_info.max / 2, sys.float_info.max])
    assert result.value == pytest.approx(sys.float_info.max / 2)
    assert math.isfinite(result.counter_intervals[0].delta)


@pytest.mark.parametrize("metric", [RATE, TOTAL])
def test_rate_overflow_rejects_even_a_total_definition(metric):
    result = summarize([0, sys.float_info.max], [0, 0.5], metric=metric)
    assert result.value is None
    assert result.status is MetricSeriesStatus.REJECTED
    assert not result.counter_intervals
    assert "arithmetic" in result.rejected_reasons[-1]


def test_sum_overflow_rejects_all_partial_results():
    result = summarize([0, sys.float_info.max, 0, sys.float_info.max], metric=TOTAL)
    assert result.status is MetricSeriesStatus.REJECTED
    assert result.value is None
    assert result.accepted_interval_count == 0
    assert "aggregate arithmetic" in result.rejected_reasons[-1]


def test_tiny_interval_and_delta_do_not_lose_representable_rate():
    tiny = math.ulp(0.0)
    result = summarize([0, tiny], [0, tiny])
    assert result.value == 1000


def test_unrepresentable_positive_rate_is_rejected_instead_of_zero():
    result = summarize([0, math.ulp(0.0)], [0, sys.float_info.max])
    assert result.status is MetricSeriesStatus.REJECTED
    assert result.value is None


@pytest.mark.parametrize("offset", [0, 17, 1000000])
@pytest.mark.parametrize("scale", [1, 5, 37])
def test_offset_and_proportional_duration_delta_scaling_invariants(offset, scale):
    result = summarize(
        [offset, offset + 60 * scale, offset + 120 * scale], [0, 1000 * scale, 2000 * scale]
    )
    assert result.value == 60
    assert sum(pair.delta for pair in result.counter_intervals) == 120 * scale


@pytest.mark.parametrize("parts", [1, 2, 5, 10])
def test_proportional_interval_splitting_preserves_total_and_weighted_rate(parts):
    values = [600 * index / parts for index in range(parts + 1)]
    times = [10000 * index / parts for index in range(parts + 1)]
    assert summarize(values, times).value == 60
    assert summarize(values, times, metric=TOTAL).value == 600


@pytest.mark.parametrize("gap", list(range(7)))
def test_gap_never_increases_interval_count_or_window_duration(gap):
    values = [60 * index for index in range(7)]
    complete = summarize(values)
    values[gap] = None
    result = summarize(values)
    assert result.accepted_interval_count <= complete.accepted_interval_count
    assert result.observed_duration_ms <= result.window_duration_ms
    assert result.value == 60


def test_no_io_no_input_mutation_and_deterministic_round_trip(monkeypatch):
    source = samples([0, 60, None, 1000, 1060])
    before = tuple(item.model_dump_json() for item in source)

    def forbidden(*args, **kwargs):
        raise AssertionError("unexpected I/O")

    monkeypatch.setattr(Path, "open", forbidden)
    options = dict(window_start_ms=0, window_end_ms=4000, registry_version=METRIC_REGISTRY_VERSION)
    result = aggregate_counter(RATE, source, **options)
    reordered = MetricDefinition.model_validate(dict(reversed(list(RATE.model_dump().items()))))
    assert (
        result.model_dump_json()
        == aggregate_counter(reordered, source, **options).model_dump_json()
    )
    assert tuple(item.model_dump_json() for item in source) == before
    assert MetricSeriesSummary.model_validate_json(result.model_dump_json()) == result
    with pytest.raises(ValidationError):
        result.counter_intervals[0].delta = 999


@pytest.mark.parametrize(
    "bounds", [(True, 1000), (0, "1000"), (0, math.inf), (1000, 1000), (-1, 1000), (0, 10**1000)]
)
def test_invalid_bounds_raise_configuration_errors(bounds):
    with pytest.raises(ValueError):
        aggregate_counter(
            RATE,
            (),
            window_start_ms=bounds[0],
            window_end_ms=bounds[1],
            registry_version=METRIC_REGISTRY_VERSION,
        )


def test_wrong_kind_and_mutable_input_are_rejected():
    with pytest.raises(ValueError, match="counter definition"):
        aggregate_counter(
            get_metric_definition("transport.jitter_ms"),
            (),
            window_start_ms=0,
            window_end_ms=1000,
            registry_version=METRIC_REGISTRY_VERSION,
        )
    with pytest.raises(ValueError, match="immutable tuple"):
        aggregate_counter(
            RATE,
            [],
            window_start_ms=0,
            window_end_ms=1000,
            registry_version=METRIC_REGISTRY_VERSION,
        )


def test_missing_source_provenance_is_preserved():
    result = aggregate_counter(
        RATE,
        (),
        window_start_ms=0,
        window_end_ms=1000,
        registry_version=METRIC_REGISTRY_VERSION,
        source_missing_reason="optional CSV absent",
    )
    assert result.missing_reasons == ("optional CSV absent",)


def test_advisory_cadence_warns_without_rejecting():
    result = summarize(
        [0, 60, 120], metric=definition(expected_cadence_ms=5000, cadence_tolerance_ratio=0.1)
    )
    assert result.value == 60
    assert "cadence" in result.warnings[0]


def test_sanitized_bundle_counter_pairs_have_identical_interval_evidence():
    from latency_fingerprinting.json_io import load_model_file
    from latency_fingerprinting.models import ContextKey

    fixture = Path(__file__).resolve().parents[1] / "data/pixelated_bundle"
    bundle = load_pixelated_measurement_samples(
        fixture / "valid-v2",
        context=load_model_file(fixture / "context-v2.json", ContextKey),
        phase=WindowPhase.DEGRADED,
        comparison_case_id="controlled-case-001",
    )
    summaries = []
    for metric in (RATE, TOTAL):
        summaries.append(
            aggregate_counter(
                metric,
                bundle.series[metric.name].samples,
                window_start_ms=bundle.elapsed_start_ms,
                window_end_ms=bundle.elapsed_end_ms,
                registry_version=bundle.registry_version,
                warnings=bundle.warnings,
            )
        )
    rate, total = summaries
    assert rate.counter_intervals == total.counter_intervals
    assert rate.value == total.value / (rate.observed_duration_ms / 1000)
    assert rate.warnings == bundle.warnings


@pytest.mark.parametrize(
    "changes",
    [
        {"duration_ms": 2},
        {"end_elapsed_ms": 0},
        {"end_source_row": 2},
        {"delta": -1},
        {"rate": math.inf},
    ],
)
def test_interval_contract_rejects_inconsistent_or_nonfinite_evidence(changes):
    data = dict(
        start_source_row=2,
        end_source_row=3,
        start_elapsed_ms=0,
        end_elapsed_ms=1000,
        duration_ms=1000,
        delta=60,
        rate=60,
    )
    with pytest.raises(ValidationError):
        CounterInterval.model_validate({**data, **changes})


@pytest.mark.parametrize(
    "changes",
    [
        {"interval_rate_unit": None},
        {"interval_rate_unit": "freezes/min"},
        {"counter_intervals": ()},
        {"aggregates": {"time_weighted_rate": 999}},
        {"reset_source_rows": (999,)},
        {"reset_source_rows": (3, 3)},
        {"gap_source_rows": (3,)},
        {"gap_source_rows": (999, 999)},
        {"canonical_unit": "frames"},
        {"available_aggregations": ("time_weighted_rate", "window_total")},
    ],
)
def test_summary_contract_rejects_inconsistent_counter_metadata(changes):
    data = summarize([0, 60, 120]).model_dump()
    with pytest.raises(ValidationError):
        MetricSeriesSummary.model_validate({**data, **changes})


@pytest.mark.parametrize(
    "changes",
    [
        {"rate": 999},
        {"start_source_row": 999},
        {"end_source_row": 999},
        {"start_elapsed_ms": 500, "duration_ms": 500, "rate": 120},
        {"end_elapsed_ms": 3000, "duration_ms": 3000, "rate": 20},
    ],
)
def test_summary_contract_rejects_inconsistent_counter_interval_evidence(changes):
    data = summarize([0, 60, 120]).model_dump()
    index = 1 if "start_elapsed_ms" in changes else 0
    data["counter_intervals"][index].update(changes)
    with pytest.raises(ValidationError):
        MetricSeriesSummary.model_validate(data)


def test_summary_duration_must_reconstruct_from_intervals():
    data = summarize([0, 60, 120], end=3000).model_dump()
    data.update(observed_duration_ms=1000, coverage=1 / 3)
    with pytest.raises(ValidationError, match="reconstruct observed duration"):
        MetricSeriesSummary.model_validate(data)


def test_gauge_summary_cannot_claim_counter_evidence():
    from latency_fingerprinting.measurement.aggregation import aggregate_gauge

    data = aggregate_gauge(
        get_metric_definition("transport.jitter_ms"),
        samples([1, 2]),
        window_start_ms=0,
        window_end_ms=1000,
        registry_version=METRIC_REGISTRY_VERSION,
    ).model_dump()
    data["interval_rate_unit"] = "frames/s"
    with pytest.raises(ValidationError, match="gauge summaries"):
        MetricSeriesSummary.model_validate(data)


def test_rejected_series_still_reports_later_resets_and_gaps():
    result = summarize(
        [100, 1, 50, 2, None], metric=definition(counter_reset_policy="reject_series")
    )
    assert result.reset_source_rows == (3, 5)
    assert result.gap_source_rows == (6,)
    assert result.value is None


@pytest.mark.parametrize("nonfinite", [math.inf, math.nan])
def test_nonfinite_accumulation_is_structured_rejection(monkeypatch, nonfinite):
    monkeypatch.setattr(aggregation.math, "fsum", lambda items: nonfinite)
    # fsum is shared with model validation, but a rejected summary's empty
    # evidence must still validate independently of an arithmetic failure.
    result = summarize([0, 60, 120])
    assert result.status is MetricSeriesStatus.REJECTED
    assert not result.counter_intervals


@pytest.mark.parametrize("values", [[100, 5, 65], [None, 5, 65]])
def test_ambiguous_duplicate_rows_reject_without_inconsistent_audit_metadata(values):
    source = samples(values)
    duplicate = MeasurementSample.model_validate({**source[1].model_dump(), "source_row": 2})
    result = aggregate_counter(
        RATE,
        (source[0], duplicate, source[2]),
        window_start_ms=0,
        window_end_ms=2000,
        registry_version=METRIC_REGISTRY_VERSION,
    )
    assert result.status is MetricSeriesStatus.REJECTED
    assert result.value is None
    assert result.usable_source_rows == ()
    assert result.reset_source_rows == result.gap_source_rows == ()
