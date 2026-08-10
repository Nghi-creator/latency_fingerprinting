"""Shared contract-version, serialization, and strictness invariants."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from latency_fingerprinting.models import ContextKey

from .factories import make_context, make_fingerprint, make_match_result, make_observation


@pytest.mark.parametrize("record", [make_observation(), make_fingerprint(), make_match_result()])
def test_root_records_round_trip_through_camel_case_json(record: object) -> None:
    model_type = type(record)
    serialized = record.model_dump_json(by_alias=True)  # type: ignore[attr-defined]
    restored = model_type.model_validate_json(serialized)
    assert restored == record
    assert '"schemaVersion"' in serialized
    assert '"contractVersion"' in serialized


@pytest.mark.parametrize(
    ("record", "field", "invalid_version"),
    [
        (make_observation(), "schemaVersion", "observation-v2"),
        (make_observation(), "contractVersion", "2.0.0"),
        (make_fingerprint(), "schemaVersion", "fingerprint-v2"),
        (make_fingerprint(), "contractVersion", "2.0.0"),
        (make_match_result(), "schemaVersion", "match-result-v2"),
        (make_match_result(), "contractVersion", "2.0.0"),
    ],
)
def test_root_records_reject_invalid_versions(
    record: object, field: str, invalid_version: str
) -> None:
    payload = record.model_dump(mode="json", by_alias=True)  # type: ignore[attr-defined]
    payload[field] = invalid_version
    with pytest.raises(ValidationError):
        type(record).model_validate(payload)


@pytest.mark.parametrize("non_finite", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_nested_json_settings_are_rejected(non_finite: float) -> None:
    with pytest.raises(ValidationError, match="NaN or infinity"):
        make_context(nominal_stream_profile={"layers": [{"bitrateKbps": non_finite}]})


def test_contract_models_reject_unknown_fields() -> None:
    payload = make_context().model_dump()
    payload["undeclared_field"] = "not allowed"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ContextKey.model_validate(payload)
