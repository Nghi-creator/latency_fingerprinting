"""Context, metric, time-bound, and observation-window model invariants."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from latency_fingerprinting.models import (
    MetricAggregate,
    ObservationWindow,
    TimeBounds,
    ValidityState,
    WindowPhase,
)

from .factories import make_metric, make_window


@pytest.mark.parametrize("non_finite", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_metric_values_are_rejected(non_finite: float) -> None:
    with pytest.raises(ValidationError, match="finite"):
        make_metric(non_finite)


@pytest.mark.parametrize(
    "bounds",
    [
        {},
        {"elapsed_start_s": 0},
        {"elapsed_start_s": 10, "elapsed_end_s": 5},
        {
            "started_at": datetime(2026, 8, 8),
            "ended_at": datetime(2026, 8, 8, 0, 0, 10),
        },
        {
            "started_at": datetime(2026, 8, 8, tzinfo=timezone(timedelta(hours=7))),
            "ended_at": datetime(2026, 8, 8, 0, 0, 10, tzinfo=timezone(timedelta(hours=7))),
        },
        {
            "started_at": datetime(2026, 8, 8, tzinfo=UTC),
            "ended_at": datetime(2026, 8, 8, 0, 0, 10, tzinfo=UTC),
            "elapsed_start_s": 0,
            "elapsed_end_s": 10,
        },
    ],
)
def test_invalid_time_bounds_are_rejected(bounds: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        TimeBounds.model_validate(bounds)


def test_window_duration_must_match_bounds() -> None:
    payload = make_window(WindowPhase.DEGRADED, "window-degraded", 0, 20).model_dump()
    payload["duration_s"] = 9
    with pytest.raises(ValidationError, match="duration_s"):
        ObservationWindow.model_validate(payload)


def test_metric_summary_must_have_samples_and_consistent_range() -> None:
    with pytest.raises(ValidationError):
        MetricAggregate(unit="ms", aggregation="median", value=1, count=0)
    with pytest.raises(ValidationError, match="minimum must not exceed maximum"):
        MetricAggregate(unit="ms", aggregation="median", value=5, count=1, minimum=10, maximum=1)
    with pytest.raises(ValidationError, match="must not exceed maximum"):
        MetricAggregate(unit="ms", aggregation="median", value=5, count=1, minimum=0, maximum=4)


def test_metric_cannot_be_measured_and_missing_or_rejected() -> None:
    window = make_window(WindowPhase.DEGRADED, "window-degraded", 0, 20)
    for field, value in (
        ("missing_metrics", ["transport.jitter_ms"]),
        ("rejected_metrics", {"transport.jitter_ms": "invalid samples"}),
    ):
        payload = window.model_dump()
        payload[field] = value
        with pytest.raises(ValidationError, match="measured and missing/rejected"):
            ObservationWindow.model_validate(payload)


@pytest.mark.parametrize(
    ("is_valid", "reasons"),
    [(False, []), (True, ["contradictory reason"])],
)
def test_window_validity_state_and_reasons_must_agree(is_valid: bool, reasons: list[str]) -> None:
    with pytest.raises(ValidationError):
        ValidityState(is_valid=is_valid, reasons=reasons)
