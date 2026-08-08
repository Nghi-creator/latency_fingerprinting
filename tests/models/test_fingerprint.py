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
