"""Fingerprint compatibility, source, and availability invariants."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from latency_fingerprinting.models import Fingerprint, ValidationStatus

from .factories import make_fingerprint


def test_fingerprint_requires_compatible_context_weights_sources_and_utc() -> None:
    fingerprint = make_fingerprint()
    invalid_changes = [
        {
            "compatibility": {
                **fingerprint.compatibility.model_dump(),
                "compatibility_group": "other",
            }
        },
        {"feature_weights": {}},
        {"source_case_ids": []},
        {"source_window_ids": []},
        {"created_at": datetime(2026, 8, 8)},
        {"created_at": datetime(2026, 8, 8, tzinfo=timezone(timedelta(hours=7)))},
        {"validation_status": ValidationStatus.VALIDATED},
    ]
    for changes in invalid_changes:
        payload = fingerprint.model_dump()
        payload.update(changes)
        with pytest.raises(ValidationError):
            Fingerprint.model_validate(payload)


def test_fingerprint_raw_and_normalized_availability_must_agree() -> None:
    fingerprint = make_fingerprint()
    payload = fingerprint.model_dump()
    payload["normalized_response"]["missing_features"] = ["client.received_bitrate_kbps"]
    with pytest.raises(ValidationError, match="missing-feature sets must agree"):
        Fingerprint.model_validate(payload)

    payload = fingerprint.model_dump()
    payload["raw_response_delta"]["rejected_features"] = {"unavailable.feature": "raw reason"}
    payload["normalized_response"]["rejected_features"] = {
        "unavailable.feature": "different reason"
    }
    with pytest.raises(ValidationError, match="rejected-feature metadata must agree"):
        Fingerprint.model_validate(payload)


def test_fingerprint_rejects_extra_weights_and_inconsistent_normalization() -> None:
    fingerprint = make_fingerprint()
    payload = fingerprint.model_dump()
    payload["feature_weights"]["undeclared.feature"] = 1.0
    with pytest.raises(ValidationError, match="without response features"):
        Fingerprint.model_validate(payload)

    payload = fingerprint.model_dump()
    payload["normalized_response"]["features"]["transport.jitter_ms"]["value"] = -0.2
    with pytest.raises(ValidationError, match="disagrees with its raw delta"):
        Fingerprint.model_validate(payload)


def test_fingerprint_rejects_non_canonical_clipped_values() -> None:
    fingerprint = make_fingerprint()
    payload = fingerprint.model_dump()
    normalized = payload["normalized_response"]["features"]["transport.jitter_ms"]
    normalized["was_clipped"] = True
    normalized["unclipped_value"] = normalized["value"]
    normalized["value"] = -999_999.0

    with pytest.raises(ValidationError, match="incorrect clipping metadata"):
        Fingerprint.model_validate(payload)
