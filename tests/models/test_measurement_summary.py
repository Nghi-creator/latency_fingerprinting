"""Summary metadata and row identities cannot contradict their own evidence."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from latency_fingerprinting.measurement.aggregation import aggregate_counter, aggregate_gauge
from latency_fingerprinting.measurement.metric_registry import (
    METRIC_REGISTRY_VERSION,
    get_metric_definition,
)
from latency_fingerprinting.models import MeasurementSample, MetricSeriesSummary


def summary_payload(*, counter=False):
    samples = tuple(
        MeasurementSample(
            elapsed_ms=index * 1000,
            captured_at=datetime(2026, 10, 6, tzinfo=UTC) + timedelta(seconds=index),
            value=index * 60,
            available=True,
            source_row=index + 2,
        )
        for index in range(3)
    )
    metric = "client.frames_decoded_rate_fps" if counter else "transport.jitter_ms"
    aggregate = aggregate_counter if counter else aggregate_gauge
    return aggregate(
        get_metric_definition(metric),
        samples,
        window_start_ms=0,
        window_end_ms=2000,
        registry_version=METRIC_REGISTRY_VERSION,
    ).model_dump()


@pytest.mark.parametrize(
    "changes",
    [
        {"kind": "event_count"},
        {"kind": "derived"},
        {"canonical_unit": "frames/s"},
        {"canonical_unit": "packets"},
        {
            "primary_aggregation": "window_total",
            "available_aggregations": ("window_total",),
            "aggregates": {"window_total": 60},
        },
    ],
)
def test_summary_rejects_unimplemented_kinds_and_incompatible_gauge_semantics(changes):
    with pytest.raises(ValidationError):
        MetricSeriesSummary.model_validate({**summary_payload(), **changes})


def test_counter_summary_rejects_reversed_source_evidence():
    data = summary_payload(counter=True)
    data["usable_source_rows"] = (4, 3, 2)
    with pytest.raises(ValidationError):
        MetricSeriesSummary.model_validate(data)


def test_counter_summary_rejects_two_timestamps_for_one_source_row():
    data = summary_payload(counter=True)
    # Both rates and the aggregate still reconstruct, but row 3 cannot be
    # captured at both 1000 ms and 1500 ms.
    data["counter_intervals"][1].update(start_elapsed_ms=1500, duration_ms=500, rate=120)
    data.update(observed_duration_ms=1500, coverage=0.75, status="incomplete")
    data["aggregates"] = {"time_weighted_rate": 80}
    with pytest.raises(ValidationError):
        MetricSeriesSummary.model_validate(data)


def test_counter_summary_requires_wrapped_transition_in_reset_audit():
    data = summary_payload(counter=True)
    data["counter_intervals"][0]["wrapped"] = True
    with pytest.raises(ValidationError):
        MetricSeriesSummary.model_validate(data)
