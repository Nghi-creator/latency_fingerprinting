"""Shared valid-record factories for model invariant tests."""

from __future__ import annotations

from datetime import UTC, datetime

from latency_fingerprinting.models import (
    CompatibilityKey,
    CompatibilityResult,
    ContextKey,
    FeatureDelta,
    FeatureEvidence,
    Fingerprint,
    MatchDecision,
    MatchResult,
    MetricAggregate,
    NormalizedFeature,
    NormalizedResponse,
    ObservationRecord,
    ObservationWindow,
    Probe,
    ProbeApplicationMethod,
    ProbeExecutionStatus,
    ProvenanceKind,
    RankedCandidate,
    ResponseDelta,
    RestorationStatus,
    SourceArtifact,
    TimeBounds,
    ValidationStatus,
    ValidityState,
    WindowPhase,
)


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
        "network_scenario": "controlled-synthetic",
        "versions": {"fixtureGenerator": "0.1.0"},
    }
    values.update(changes)
    return ContextKey.model_validate(values)


def make_metric(value: float, *, unit: str = "ms") -> MetricAggregate:
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


def make_window(
    phase: WindowPhase,
    window_id: str,
    elapsed_start_s: float,
    value: float,
    *,
    context: ContextKey | None = None,
    provenance: ProvenanceKind = ProvenanceKind.SYNTHETIC,
) -> ObservationWindow:
    return ObservationWindow(
        run_id="run-synthetic-001",
        window_id=window_id,
        comparison_case_id="case-network-001",
        context=context or make_context(),
        phase=phase,
        bounds=TimeBounds(
            elapsed_start_s=elapsed_start_s,
            elapsed_end_s=elapsed_start_s + 10,
        ),
        duration_s=10,
        sample_count=20,
        effective_settings={"fps": 60 if phase is WindowPhase.DEGRADED else 30},
        metrics={"transport.jitter_ms": make_metric(value)},
        validity=ValidityState(is_valid=True),
        source_artifact=SourceArtifact(
            artifact_id=f"fixture-{window_id}", source_type="synthetic_fixture"
        ),
        provenance=provenance,
    )


def make_observation() -> ObservationRecord:
    context = make_context()
    degraded = make_window(WindowPhase.DEGRADED, "window-degraded", 0, 20, context=context)
    relief = make_window(WindowPhase.RELIEF, "window-relief", 10, 8, context=context)
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
        safety_notes=["No runtime action occurred."],
    )
    response_delta = ResponseDelta(
        degraded_window_id=degraded.window_id,
        relief_window_id=relief.window_id,
        features={
            "transport.jitter_ms": FeatureDelta(
                unit="ms",
                aggregation="median",
                degraded_value=20,
                relief_value=8,
                raw_delta=-12,
            )
        },
        is_valid=True,
    )
    normalized_response = NormalizedResponse(
        features={
            "transport.jitter_ms": NormalizedFeature(
                value=-0.6,
                epsilon=0.1,
                reference_value=20,
            )
        }
    )
    return ObservationRecord(
        context=context,
        degraded_window=degraded,
        relief_window=relief,
        probe=probe,
        response_delta=response_delta,
        normalized_response=normalized_response,
        provenance=ProvenanceKind.SYNTHETIC,
    )


def make_fingerprint() -> Fingerprint:
    observation = make_observation()
    return Fingerprint(
        fingerprint_id="fingerprint-network-001",
        bottleneck_label="network_pressure",
        context=observation.context,
        compatibility=CompatibilityKey(
            compatibility_group=observation.context.compatibility_group,
            probe_type=observation.probe.probe_type,
        ),
        raw_response_delta=observation.response_delta,
        normalized_response=observation.normalized_response,
        feature_weights={"transport.jitter_ms": 1.0},
        provenance=ProvenanceKind.SYNTHETIC,
        source_case_ids=["case-network-001"],
        source_window_ids=["window-degraded", "window-relief"],
        source_run_ids=["run-synthetic-001"],
        created_at=datetime(2026, 8, 8, tzinfo=UTC),
        software_version="0.1.0",
        validation_status=ValidationStatus.SOFTWARE_TEST_REFERENCE,
        notes=["Synthetic software-test reference."],
    )


def make_match_result() -> MatchResult:
    candidate = RankedCandidate(
        fingerprint_id="fingerprint-network-001",
        bottleneck_label="network_pressure",
        distance=0.1,
        match_strength=0.85,
    )
    evidence = FeatureEvidence(
        feature="transport.jitter_ms",
        observed_value=-0.6,
        candidate_value=-0.5,
        residual=-0.1,
        weight=1.0,
        weighted_squared_residual=0.01,
    )
    return MatchResult(
        decision=MatchDecision.MATCHED,
        accepted_label="network_pressure",
        match_strength=0.85,
        ranked_candidates=[candidate],
        shared_feature_count=3,
        feature_coverage=1.0,
        supporting_evidence=[evidence],
        compatibility=CompatibilityResult(
            is_compatible=True,
            compatibility_group="p0-synthetic-v1",
            compatible_fingerprint_ids=["fingerprint-network-001"],
        ),
        decision_reason="The best compatible response exceeded all provisional thresholds.",
    )


__all__ = [
    "make_context",
    "make_fingerprint",
    "make_match_result",
    "make_metric",
    "make_observation",
    "make_window",
]
