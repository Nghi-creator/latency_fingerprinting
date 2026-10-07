"""Missing, rejected and usable raw measurement sample states stay distinct."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from latency_fingerprinting.models import MeasurementSample


def sample(**changes: object) -> MeasurementSample:
    return MeasurementSample.model_validate(
        {
            "elapsedMs": 0,
            "capturedAt": "2026-10-06T00:00:00Z",
            "value": 0,
            "available": True,
            "sourceRow": 2,
            **changes,
        }
    )


def test_zero_sample_is_usable_immutable_and_round_trips() -> None:
    value = sample()
    assert value.value == 0
    assert value.captured_at == datetime(2026, 10, 6, tzinfo=UTC)
    assert MeasurementSample.model_validate_json(value.model_dump_json(by_alias=True)) == value
    with pytest.raises(ValidationError, match="frozen"):
        value.value = 1


@pytest.mark.parametrize(
    "changes",
    [
        {"value": None, "missingReason": "missing cell"},
        {"value": None, "rejectionReason": "malformed numeric cell"},
        {"value": None, "available": False, "missingReason": "unavailable source"},
    ],
)
def test_unusable_evidence_never_invents_a_value(changes: dict[str, object]) -> None:
    value = sample(**changes)
    assert value.value is None
    assert bool(value.missing_reason) != bool(value.rejection_reason)


@pytest.mark.parametrize(
    "changes",
    [
        {"value": None},
        {"value": None, "missingReason": "missing", "rejectionReason": "rejected"},
        {"value": 1, "missingReason": "missing"},
        {"value": 1, "rejectionReason": "rejected"},
        {"available": False},
        {"available": False, "value": None, "rejectionReason": "rejected"},
        {"available": "true"},
        {"sourceRow": 0},
        {"sourceRow": True},
        {"sourceRow": "2"},
        {"elapsedMs": -1},
        {"elapsedMs": True},
        {"elapsedMs": float("inf")},
        {"elapsedMs": 10**1000},
        {"value": float("nan")},
        {"value": float("inf")},
        {"value": True},
        {"value": "1"},
        {"value": 10**1000},
        {"capturedAt": "2026-10-06T00:00:00"},
        {"capturedAt": "2026-10-06T00:00:00+07:00"},
        {"extra": "field"},
    ],
)
def test_sample_rejects_ambiguous_or_invalid_states(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        sample(**changes)
