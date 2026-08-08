"""Contract-model builders for deterministic synthetic fixture cases."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

from ..models import (
    CompatibilityKey,
    ContextKey,
    Fingerprint,
    MetricAggregate,
    ObservationRecord,
    ObservationWindow,
    Probe,
    ProbeApplicationMethod,
    ProbeExecutionStatus,
    ProvenanceKind,
    RestorationStatus,
    SourceArtifact,
    TimeBounds,
    ValidationStatus,
    ValidityState,
    WindowPhase,
)
from ..normalization import normalize_response
from ..windows import build_response_delta
from .definitions import FEATURE_BASELINES, SYNTHETIC_COMPATIBILITY_GROUP

SYNTHETIC_CREATED_AT = datetime(2026, 8, 8, tzinfo=UTC)


def build_context(*, compatibility_group: str = SYNTHETIC_COMPATIBILITY_GROUP) -> ContextKey:
    return ContextKey(
        context_id=f"context-{compatibility_group}",
        compatibility_group=compatibility_group,
        edge_node_class="synthetic-edge",
        node_id="anonymous-node-001",
        operating_system="linux",
        runtime_class="container",
        workload_id="synthetic-game",
        capture_implementation="synthetic-fixture-generator",
        encoder_family="vp8",
        encoder_profile="realtime",
        transport_implementation="webrtc",
        connection_mode="direct",
        client_class="chromium",
        nominal_stream_profile={"fps": 60, "bitrateKbps": 6000},
        network_scenario="controlled-synthetic",
        versions={"fixtureGenerator": "0.1.0"},
    )


def _metric(value: float, unit: str) -> MetricAggregate:
    return MetricAggregate(
        unit=unit,
        aggregation="median",
        value=value,
        count=20,
        median=value,
        p95=value,
        minimum=value,
        maximum=value,
    )


def _window(
    *,
    case_id: str,
    phase: WindowPhase,
    context: ContextKey,
    vector: Mapping[str, float],
) -> ObservationWindow:
    is_degraded = phase is WindowPhase.DEGRADED
    metrics = {
        feature: _metric(
            baseline if is_degraded else round(baseline * (1 + vector[feature]), 12),
            unit,
        )
        for feature, (baseline, unit) in FEATURE_BASELINES.items()
    }
    start = 0.0 if is_degraded else 10.0
    phase_name = phase.value
    return ObservationWindow(
        run_id=f"run-{case_id}",
        window_id=f"{case_id}-{phase_name}",
        comparison_case_id=case_id,
        context=context,
        phase=phase,
        bounds=TimeBounds(elapsed_start_s=start, elapsed_end_s=start + 10),
        duration_s=10,
        sample_count=20,
        effective_settings={
            "fps": 60,
            "bitrateKbps": 6000,
            "encoderComplexity": "normal" if is_degraded else "reduced",
        },
        metrics=metrics,
        validity=ValidityState(is_valid=True),
        source_artifact=SourceArtifact(
            artifact_id=f"fixture-{case_id}-{phase_name}",
            source_type="synthetic_fixture",
            producer="latency_fingerprinting.synthetic_fixtures",
        ),
        provenance=ProvenanceKind.SYNTHETIC,
    )


def build_observation(
    case_id: str,
    vector: Mapping[str, float],
    *,
    compatibility_group: str = SYNTHETIC_COMPATIBILITY_GROUP,
) -> ObservationRecord:
    context = build_context(compatibility_group=compatibility_group)
    degraded = _window(
        case_id=case_id,
        phase=WindowPhase.DEGRADED,
        context=context,
        vector=vector,
    )
    relief = _window(
        case_id=case_id,
        phase=WindowPhase.RELIEF,
        context=context,
        vector=vector,
    )
    probe = Probe(
        probe_id=f"probe-{case_id}",
        probe_type="stream_profile_relief",
        probe_version="1",
        requested_settings={"encoderComplexity": "reduced"},
        intensity=0.5,
        application_method=ProbeApplicationMethod.SIMULATED_PAIR,
        degraded_window_id=degraded.window_id,
        relief_window_id=relief.window_id,
        execution_status=ProbeExecutionStatus.NOT_EXECUTED,
        restoration_status=RestorationStatus.NOT_EXECUTED,
        safety_notes=["No runtime action occurred; this pair is synthetic."],
    )
    response = build_response_delta(degraded, relief, probe)
    normalized = normalize_response(response)
    return ObservationRecord(
        context=context,
        degraded_window=degraded,
        relief_window=relief,
        probe=probe,
        response_delta=response,
        normalized_response=normalized,
        provenance=ProvenanceKind.SYNTHETIC,
    )


def build_fingerprint(label: str, observation: ObservationRecord) -> Fingerprint:
    return Fingerprint(
        fingerprint_id=f"fingerprint-{label}-v1",
        bottleneck_label=label,
        context=observation.context,
        compatibility=CompatibilityKey(
            compatibility_group=observation.context.compatibility_group,
            probe_type=observation.probe.probe_type,
        ),
        raw_response_delta=observation.response_delta,
        normalized_response=observation.normalized_response,
        feature_weights={feature: 1.0 for feature in observation.normalized_response.features},
        provenance=ProvenanceKind.SYNTHETIC,
        source_case_ids=[observation.degraded_window.comparison_case_id or "unreachable"],
        source_window_ids=[
            observation.degraded_window.window_id,
            observation.relief_window.window_id,
        ],
        source_run_ids=[observation.degraded_window.run_id],
        created_at=SYNTHETIC_CREATED_AT,
        software_version="0.1.0",
        validation_status=ValidationStatus.SOFTWARE_TEST_REFERENCE,
        notes=["Synthetic software-test reference; not a scientific finding."],
    )


__all__ = ["SYNTHETIC_CREATED_AT", "build_context", "build_fingerprint", "build_observation"]
