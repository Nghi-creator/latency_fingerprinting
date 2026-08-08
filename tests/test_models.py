"""Contract validation and JSON round-trip tests for P0 models."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

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
    UnknownReason,
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
def test_non_finite_metric_values_are_rejected(non_finite: float) -> None:
    with pytest.raises(ValidationError, match="finite"):
        make_metric(non_finite)


@pytest.mark.parametrize("non_finite", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_nested_json_settings_are_rejected(non_finite: float) -> None:
    with pytest.raises(ValidationError, match="NaN or infinity"):
        make_context(nominal_stream_profile={"layers": [{"bitrateKbps": non_finite}]})


def test_contract_models_reject_unknown_fields() -> None:
    payload = make_context().model_dump()
    payload["undeclared_field"] = "not allowed"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ContextKey.model_validate(payload)


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


def test_feature_evidence_arithmetic_is_auditable() -> None:
    with pytest.raises(ValidationError, match="residual must equal"):
        FeatureEvidence(
            feature="transport.jitter_ms",
            observed_value=-0.6,
            candidate_value=-0.5,
            residual=0.1,
            weight=1,
            weighted_squared_residual=0.01,
        )
    with pytest.raises(ValidationError, match="weighted_squared_residual"):
        FeatureEvidence(
            feature="transport.jitter_ms",
            observed_value=-0.6,
            candidate_value=-0.5,
            residual=-0.1,
            weight=2,
            weighted_squared_residual=0.01,
        )


def test_match_result_rejects_invalid_decision_combinations() -> None:
    matched = make_match_result()
    invalid_matched = matched.model_dump()
    invalid_matched["accepted_label"] = None
    with pytest.raises(ValidationError, match="requires accepted_label"):
        MatchResult.model_validate(invalid_matched)

    unknown = MatchResult(
        decision=MatchDecision.UNKNOWN,
        shared_feature_count=0,
        feature_coverage=0,
        compatibility=CompatibilityResult(
            is_compatible=False,
            compatibility_group="p0-synthetic-v1",
            rejected_fingerprints={"fingerprint-network-001": "context mismatch"},
        ),
        decision_reason="No compatible candidates were available.",
        unknown_reason=UnknownReason.INCOMPATIBLE_CONTEXT,
    )
    invalid_unknown = unknown.model_dump()
    invalid_unknown["accepted_label"] = "network_pressure"
    with pytest.raises(ValidationError, match="must not have an accepted_label"):
        MatchResult.model_validate(invalid_unknown)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("accepted_label", "host_encoder_pressure"),
        ("match_strength", 0.70),
        ("shared_feature_count", 2),
        ("feature_coverage", 0.50),
    ],
)
def test_matched_result_must_satisfy_candidate_and_threshold_invariants(
    field: str, value: object
) -> None:
    payload = make_match_result().model_dump()
    payload[field] = value
    with pytest.raises(ValidationError):
        MatchResult.model_validate(payload)


def test_top_two_candidates_require_an_exact_margin() -> None:
    payload = make_match_result().model_dump()
    payload["ranked_candidates"].append(
        RankedCandidate(
            fingerprint_id="fingerprint-encoder-001",
            bottleneck_label="host_encoder_pressure",
            distance=0.2,
            match_strength=0.70,
        ).model_dump()
    )
    with pytest.raises(ValidationError, match="require a score_margin"):
        MatchResult.model_validate(payload)

    payload["score_margin"] = 0.14
    with pytest.raises(ValidationError, match="top-two strength difference"):
        MatchResult.model_validate(payload)

    payload["score_margin"] = 0.15
    assert MatchResult.model_validate(payload).score_margin == pytest.approx(0.15)


@pytest.mark.parametrize("field", ["match_strength", "score_margin", "feature_coverage"])
def test_match_scores_are_unit_intervals(field: str) -> None:
    payload = make_match_result().model_dump()
    payload[field] = 1.01
    with pytest.raises(ValidationError):
        MatchResult.model_validate(payload)
