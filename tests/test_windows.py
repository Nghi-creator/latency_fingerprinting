"""Tests for raw response-delta construction."""

from __future__ import annotations

import sys
from typing import TypeVar

import pytest
from pydantic import BaseModel, ValidationError

from latency_fingerprinting.models import (
    ContextKey,
    FeatureDelta,
    MetricAggregate,
    ObservationWindow,
    Probe,
    ProbeApplicationMethod,
    ProbeExecutionStatus,
    ProvenanceKind,
    ResponseDelta,
    RestorationStatus,
    SourceArtifact,
    TimeBounds,
    ValidityState,
    WindowPhase,
)
from latency_fingerprinting.windows import build_response_delta

ModelT = TypeVar("ModelT", bound=BaseModel)


def rebuild(model: ModelT, **changes: object) -> ModelT:
    payload = model.model_dump()
    payload.update(changes)
    return type(model).model_validate(payload)


def make_context(**changes: object) -> ContextKey:
    values: dict[str, object] = {
        "context_id": "context-p0-synthetic",
        "compatibility_group": "p0-synthetic-v1",
        "edge_node_class": "synthetic-edge",
        "node_id": "anonymous-node-001",
        "operating_system": "linux",
        "runtime_class": "container",
        "workload_id": "synthetic-game",
        "capture_implementation": "synthetic-fixture",
        "encoder_family": "vp8",
        "encoder_profile": "realtime",
        "transport_implementation": "webrtc",
        "connection_mode": "direct",
        "client_class": "chromium",
        "nominal_stream_profile": {"fps": 60, "bitrateKbps": 6000},
    }
    values.update(changes)
    return ContextKey.model_validate(values)


def metric(value: float, unit: str) -> MetricAggregate:
    return MetricAggregate(
        unit=unit,
        aggregation="median",
        value=value,
        count=20,
        median=value,
        minimum=value,
        maximum=value,
    )


def make_window(
    phase: WindowPhase,
    window_id: str,
    elapsed_start_s: float,
    metrics: dict[str, MetricAggregate],
    *,
    context: ContextKey,
    missing_metrics: list[str] | None = None,
    rejected_metrics: dict[str, str] | None = None,
    effective_settings: dict[str, object] | None = None,
    confounders: list[str] | None = None,
) -> ObservationWindow:
    return ObservationWindow(
        run_id="run-synthetic-001",
        window_id=window_id,
        comparison_case_id="case-response-001",
        context=context,
        phase=phase,
        bounds=TimeBounds(
            elapsed_start_s=elapsed_start_s,
            elapsed_end_s=elapsed_start_s + 10,
        ),
        duration_s=10,
        sample_count=20,
        effective_settings=effective_settings
        or {"fps": 60 if phase is WindowPhase.DEGRADED else 30, "bitrateKbps": 6000},
        metrics=metrics,
        missing_metrics=missing_metrics or [],
        rejected_metrics=rejected_metrics or {},
        validity=ValidityState(is_valid=True),
        source_artifact=SourceArtifact(
            artifact_id=f"fixture-{window_id}", source_type="synthetic_fixture"
        ),
        provenance=ProvenanceKind.SYNTHETIC,
        confounders=confounders or [],
    )


def make_pair() -> tuple[ObservationWindow, ObservationWindow, Probe]:
    context = make_context()
    degraded = make_window(
        WindowPhase.DEGRADED,
        "window-degraded",
        0,
        {
            "client.received_fps": metric(35, "fps"),
            "transport.jitter_ms": metric(20, "ms"),
        },
        context=context,
    )
    relief = make_window(
        WindowPhase.RELIEF,
        "window-relief",
        10,
        {
            "client.received_fps": metric(55, "fps"),
            "transport.jitter_ms": metric(8, "ms"),
        },
        context=context,
    )
    probe = Probe(
        probe_id="probe-stream-relief-001",
        probe_type="stream_profile_relief",
        probe_version="1",
        requested_settings={"fps": 30},
        intensity=0.5,
        application_method=ProbeApplicationMethod.SIMULATED_PAIR,
        degraded_window_id=degraded.window_id,
        relief_window_id=relief.window_id,
        execution_status=ProbeExecutionStatus.NOT_EXECUTED,
        restoration_status=RestorationStatus.NOT_EXECUTED,
    )
    return degraded, relief, probe


def test_build_response_uses_relief_minus_degraded_for_each_feature() -> None:
    degraded, relief, probe = make_pair()
    response = build_response_delta(degraded, relief, probe)

    assert response.is_valid
    assert list(response.features) == ["client.received_fps", "transport.jitter_ms"]
    assert response.features["transport.jitter_ms"].raw_delta == pytest.approx(-12)
    assert response.features["transport.jitter_ms"].unit == "ms"
    assert response.features["client.received_fps"].raw_delta == pytest.approx(20)
    assert response.features["client.received_fps"].unit == "fps"


def test_response_retains_raw_values_and_aggregation() -> None:
    degraded, relief, probe = make_pair()
    feature = build_response_delta(degraded, relief, probe).features["transport.jitter_ms"]

    assert feature.degraded_value == 20
    assert feature.relief_value == 8
    assert feature.aggregation == "median"


def test_unrepresentable_delta_is_rejected_instead_of_raising() -> None:
    degraded, relief, probe = make_pair()
    degraded = rebuild(
        degraded,
        metrics={"transport.jitter_ms": metric(-sys.float_info.max, "ms")},
    )
    relief = rebuild(
        relief,
        metrics={"transport.jitter_ms": metric(sys.float_info.max, "ms")},
    )

    response = build_response_delta(degraded, relief, probe)

    assert response.is_valid
    assert response.features == {}
    assert response.rejected_features == {
        "transport.jitter_ms": "derived response delta exceeds finite numeric range"
    }


def test_missing_feature_is_preserved_and_never_imputed_as_zero() -> None:
    degraded, relief, probe = make_pair()
    degraded_metrics = {
        **degraded.metrics,
        "client.received_bitrate_kbps": metric(4000, "kbps"),
    }
    degraded = rebuild(degraded, metrics=degraded_metrics)
    relief = rebuild(relief, missing_metrics=["client.received_bitrate_kbps"])

    response = build_response_delta(degraded, relief, probe)

    assert response.is_valid
    assert "client.received_bitrate_kbps" not in response.features
    assert response.missing_features == ["client.received_bitrate_kbps"]


def test_rejected_feature_preserves_phase_and_reason() -> None:
    degraded, relief, probe = make_pair()
    degraded_metrics = {
        **degraded.metrics,
        "transport.packets_lost_delta": metric(12, "packets"),
    }
    degraded = rebuild(degraded, metrics=degraded_metrics)
    relief = rebuild(
        relief,
        rejected_metrics={"transport.packets_lost_delta": "counter reset during window"},
    )

    response = build_response_delta(degraded, relief, probe)

    assert "transport.packets_lost_delta" not in response.features
    assert "transport.packets_lost_delta" not in response.missing_features
    assert response.rejected_features == {
        "transport.packets_lost_delta": "relief: counter reset during window"
    }


def test_incomparable_pair_returns_invalid_response_without_calculated_features() -> None:
    degraded, relief, probe = make_pair()
    relief = rebuild(
        relief,
        context=make_context(network_scenario="incompatible-scenario"),
    )

    response = build_response_delta(degraded, relief, probe)

    assert not response.is_valid
    assert response.features == {}
    assert any(reason.startswith("context_mismatch:") for reason in response.invalid_reasons)


def test_metric_unit_mismatch_cannot_produce_a_valid_delta() -> None:
    degraded, relief, probe = make_pair()
    relief_metrics = {**relief.metrics, "transport.jitter_ms": metric(0.008, "s")}
    relief = rebuild(relief, metrics=relief_metrics)

    response = build_response_delta(degraded, relief, probe)

    assert not response.is_valid
    assert response.features == {}
    assert any(reason.startswith("metric_unit_mismatch:") for reason in response.invalid_reasons)


def test_comparability_warnings_are_preserved() -> None:
    degraded, relief, probe = make_pair()
    relief = rebuild(
        relief,
        effective_settings={"fps": 30, "bitrateKbps": 3000},
        confounders=["Composite preset also changed bitrate."],
    )

    response = build_response_delta(degraded, relief, probe)

    assert response.is_valid
    assert response.warnings == [
        "unrelated effective settings changed but confounders were recorded: bitrateKbps"
    ]


def test_response_build_is_deterministic_and_does_not_mutate_windows() -> None:
    degraded, relief, probe = make_pair()
    degraded_before = degraded.model_dump()
    relief_before = relief.model_dump()

    first = build_response_delta(degraded, relief, probe)
    second = build_response_delta(degraded, relief, probe)

    assert first == second
    assert degraded.model_dump() == degraded_before
    assert relief.model_dump() == relief_before
    assert ResponseDelta.model_validate_json(first.model_dump_json(by_alias=True)) == first


def test_response_model_rejects_ambiguous_feature_availability() -> None:
    feature = FeatureDelta(
        unit="ms",
        aggregation="median",
        degraded_value=20,
        relief_value=8,
        raw_delta=-12,
    )
    with pytest.raises(ValidationError, match="exactly one measured, missing or rejected state"):
        ResponseDelta(
            degraded_window_id="window-degraded",
            relief_window_id="window-relief",
            features={"transport.jitter_ms": feature},
            missing_features=["transport.jitter_ms"],
            is_valid=True,
        )


def test_invalid_response_cannot_claim_calculated_features() -> None:
    feature = FeatureDelta(
        unit="ms",
        aggregation="median",
        degraded_value=20,
        relief_value=8,
        raw_delta=-12,
    )
    with pytest.raises(ValidationError, match="cannot contain calculated features"):
        ResponseDelta(
            degraded_window_id="window-degraded",
            relief_window_id="window-relief",
            features={"transport.jitter_ms": feature},
            is_valid=False,
            invalid_reasons=["context_mismatch: contexts differ"],
        )
