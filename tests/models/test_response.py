"""Probe, response-delta, normalization, and observation-pair invariants."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from latency_fingerprinting.models import (
    FeatureDelta,
    ObservationRecord,
    Probe,
    ProbeExecutionStatus,
    ProvenanceKind,
    ResponseDelta,
    RestorationStatus,
)

from .factories import make_observation


@pytest.mark.parametrize(
    "changes",
    [
        {"execution_status": ProbeExecutionStatus.EXECUTED},
        {"restoration_status": RestorationStatus.RESTORED},
        {"observed_settings": {"fps": 30}},
        {"paired_window_order": ["degraded", "degraded"]},
        {"paired_window_order": ["degraded"]},
    ],
)
def test_simulated_probe_truthfulness_and_ordering(changes: dict[str, object]) -> None:
    observation = make_observation()
    payload = observation.probe.model_dump()
    payload.update(changes)
    with pytest.raises(ValidationError):
        Probe.model_validate(payload)


def test_executed_probe_requires_observed_settings() -> None:
    observation = make_observation()
    payload = observation.probe.model_dump()
    payload.update(
        {
            "application_method": "paired_run",
            "execution_status": "executed",
            "observed_settings": None,
            "restoration_status": "unknown",
        }
    )

    with pytest.raises(ValidationError, match="observed runtime settings"):
        Probe.model_validate(payload)


def test_probe_requires_a_change_and_consistent_execution_metadata() -> None:
    observation = make_observation()
    payload = observation.probe.model_dump()
    payload["requested_settings"] = {}
    with pytest.raises(ValidationError, match="at least one requested setting"):
        Probe.model_validate(payload)

    payload = observation.probe.model_dump()
    payload["observed_settings"] = {"fps": 30}
    with pytest.raises(ValidationError, match="observed runtime settings"):
        Probe.model_validate(payload)

    payload = observation.probe.model_dump()
    payload["intensity"] = 0
    with pytest.raises(ValidationError):
        Probe.model_validate(payload)


def test_observation_provenance_and_derived_values_must_be_truthful() -> None:
    observation = make_observation()
    payload = observation.model_dump()
    payload["provenance"] = ProvenanceKind.CONTROLLED_REAL
    payload["degraded_window"]["provenance"] = ProvenanceKind.CONTROLLED_REAL
    payload["relief_window"]["provenance"] = ProvenanceKind.CONTROLLED_REAL
    with pytest.raises(ValidationError, match="real observations cannot use"):
        ObservationRecord.model_validate(payload)

    payload = observation.model_dump()
    payload["normalized_response"]["features"]["transport.jitter_ms"]["value"] = -0.1
    with pytest.raises(ValidationError, match="disagrees with its raw delta"):
        ObservationRecord.model_validate(payload)


def test_feature_delta_enforces_relief_minus_degraded_sign() -> None:
    with pytest.raises(ValidationError, match="relief_value minus degraded_value"):
        FeatureDelta(
            unit="ms",
            aggregation="median",
            degraded_value=20,
            relief_value=8,
            raw_delta=12,
        )


@pytest.mark.parametrize(
    ("is_valid", "invalid_reasons"),
    [(False, []), (True, ["contradictory reason"])],
)
def test_response_validity_and_reasons_must_agree(
    is_valid: bool, invalid_reasons: list[str]
) -> None:
    with pytest.raises(ValidationError):
        ResponseDelta(
            degraded_window_id="degraded",
            relief_window_id="relief",
            features={},
            is_valid=is_valid,
            invalid_reasons=invalid_reasons,
        )


def test_observation_pair_references_must_be_consistent() -> None:
    observation = make_observation()
    payload = observation.model_dump()
    payload["probe"]["relief_window_id"] = "different-window"
    with pytest.raises(ValidationError, match="probe window identifiers"):
        ObservationRecord.model_validate(payload)


def test_observation_raw_and_normalized_feature_sets_must_agree() -> None:
    observation = make_observation()
    payload = observation.model_dump()
    payload["normalized_response"]["features"] = {}
    with pytest.raises(ValidationError, match="feature sets must agree"):
        ObservationRecord.model_validate(payload)
