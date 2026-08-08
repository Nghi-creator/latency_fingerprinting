"""Deterministic generation of the P0 synthetic regression corpus."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from .models import (
    CompatibilityKey,
    CompatibilityResult,
    ContextKey,
    Fingerprint,
    MatchDecision,
    MatchResult,
    MatchThresholds,
    MetricAggregate,
    ObservationRecord,
    ObservationWindow,
    Probe,
    ProbeApplicationMethod,
    ProbeExecutionStatus,
    ProvenanceKind,
    RankedCandidate,
    RestorationStatus,
    SourceArtifact,
    TimeBounds,
    UnknownReason,
    ValidationStatus,
    ValidityState,
    WindowPhase,
)
from .normalization import normalize_response
from .windows import build_response_delta

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE_DIRECTORY = PROJECT_ROOT / "fixtures"
SYNTHETIC_COMPATIBILITY_GROUP = "p0-synthetic-v1"
SYNTHETIC_CREATED_AT = datetime(2026, 8, 8, tzinfo=UTC)

FEATURE_BASELINES: Mapping[str, tuple[float, str]] = {
    "client.received_bitrate_kbps": (3000.0, "kbps"),
    "client.received_fps": (40.0, "fps"),
    "transport.jitter_ms": (20.0, "ms"),
    "transport.packets_lost_delta": (10.0, "packets"),
}

REFERENCE_VECTORS: Mapping[str, Mapping[str, float]] = {
    "healthy": {
        "client.received_bitrate_kbps": 0.0,
        "client.received_fps": 0.0,
        "transport.jitter_ms": 0.0,
        "transport.packets_lost_delta": 0.0,
    },
    "network_pressure": {
        "client.received_bitrate_kbps": 0.10,
        "client.received_fps": 0.20,
        "transport.jitter_ms": -0.60,
        "transport.packets_lost_delta": -0.80,
    },
    "host_encoder_pressure": {
        "client.received_bitrate_kbps": 0.20,
        "client.received_fps": 0.60,
        "transport.jitter_ms": -0.10,
        "transport.packets_lost_delta": 0.0,
    },
}

QUERY_VECTORS: Mapping[str, Mapping[str, float]] = {
    "similar_network": {
        "client.received_bitrate_kbps": 0.12,
        "client.received_fps": 0.22,
        "transport.jitter_ms": -0.57,
        "transport.packets_lost_delta": -0.75,
    },
    "similar_encoder": {
        "client.received_bitrate_kbps": 0.18,
        "client.received_fps": 0.55,
        "transport.jitter_ms": -0.12,
        "transport.packets_lost_delta": -0.02,
    },
    "weak": {
        "client.received_bitrate_kbps": -0.90,
        "client.received_fps": 1.50,
        "transport.jitter_ms": 0.80,
        "transport.packets_lost_delta": -0.90,
    },
    "ambiguous": {
        "client.received_bitrate_kbps": 0.15,
        "client.received_fps": 0.40,
        "transport.jitter_ms": -0.35,
        "transport.packets_lost_delta": -0.40,
    },
    "conflicting": {
        "client.received_bitrate_kbps": 0.15,
        "client.received_fps": 0.65,
        "transport.jitter_ms": -0.65,
        "transport.packets_lost_delta": -0.75,
    },
    "incompatible_context": {
        "client.received_bitrate_kbps": 0.12,
        "client.received_fps": 0.22,
        "transport.jitter_ms": -0.57,
        "transport.packets_lost_delta": -0.75,
    },
}


@dataclass(frozen=True, slots=True)
class ExpectedDecision:
    decision: MatchDecision
    label: str | None = None
    unknown_reason: UnknownReason | None = None


QUERY_EXPECTATIONS: Mapping[str, ExpectedDecision] = {
    "similar_network": ExpectedDecision(MatchDecision.MATCHED, label="network_pressure"),
    "similar_encoder": ExpectedDecision(MatchDecision.MATCHED, label="host_encoder_pressure"),
    "weak": ExpectedDecision(MatchDecision.UNKNOWN, unknown_reason=UnknownReason.WEAK_MATCH),
    "ambiguous": ExpectedDecision(
        MatchDecision.UNKNOWN, unknown_reason=UnknownReason.AMBIGUOUS_MARGIN
    ),
    "conflicting": ExpectedDecision(
        MatchDecision.UNKNOWN, unknown_reason=UnknownReason.CONFLICTING_EVIDENCE
    ),
    "incompatible_context": ExpectedDecision(
        MatchDecision.UNKNOWN, unknown_reason=UnknownReason.INCOMPATIBLE_CONTEXT
    ),
}


def _json(model: BaseModel) -> str:
    payload = model.model_dump(mode="json", by_alias=True)
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _context(*, compatibility_group: str = SYNTHETIC_COMPATIBILITY_GROUP) -> ContextKey:
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


def _observation(
    case_id: str,
    vector: Mapping[str, float],
    *,
    compatibility_group: str = SYNTHETIC_COMPATIBILITY_GROUP,
) -> ObservationRecord:
    context = _context(compatibility_group=compatibility_group)
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


def _fingerprint(label: str, observation: ObservationRecord) -> Fingerprint:
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


def _candidate_scores(query_vector: Mapping[str, float]) -> list[RankedCandidate]:
    candidates: list[RankedCandidate] = []
    for label, candidate_vector in REFERENCE_VECTORS.items():
        squared_residuals = [
            (query_vector[feature] - candidate_vector[feature]) ** 2
            for feature in sorted(query_vector)
        ]
        distance = math.sqrt(sum(squared_residuals) / len(squared_residuals))
        candidates.append(
            RankedCandidate(
                fingerprint_id=f"fingerprint-{label}-v1",
                bottleneck_label=label,
                distance=distance,
                match_strength=1 / (1 + distance),
            )
        )
    return sorted(
        candidates, key=lambda candidate: (-candidate.match_strength, candidate.fingerprint_id)
    )


def _expected_match_result(case_name: str, observation: ObservationRecord) -> MatchResult:
    expectation = QUERY_EXPECTATIONS[case_name]
    compatibility_group = observation.context.compatibility_group
    if expectation.unknown_reason is UnknownReason.INCOMPATIBLE_CONTEXT:
        return MatchResult(
            decision=MatchDecision.UNKNOWN,
            shared_feature_count=0,
            feature_coverage=0,
            compatibility=CompatibilityResult(
                is_compatible=False,
                compatibility_group=compatibility_group,
                rejected_fingerprints={
                    f"fingerprint-{label}-v1": "compatibility group mismatch"
                    for label in REFERENCE_VECTORS
                },
            ),
            decision_reason="No fingerprint belongs to the query compatibility group.",
            unknown_reason=UnknownReason.INCOMPATIBLE_CONTEXT,
        )

    candidates = _candidate_scores(QUERY_VECTORS[case_name])
    score_margin = candidates[0].match_strength - candidates[1].match_strength
    return MatchResult(
        decision=expectation.decision,
        accepted_label=expectation.label,
        match_strength=candidates[0].match_strength,
        score_margin=score_margin,
        ranked_candidates=candidates,
        shared_feature_count=len(FEATURE_BASELINES),
        feature_coverage=1.0,
        compatibility=CompatibilityResult(
            is_compatible=True,
            compatibility_group=compatibility_group,
            compatible_fingerprint_ids=[candidate.fingerprint_id for candidate in candidates],
        ),
        thresholds=MatchThresholds(),
        decision_reason=(
            "Synthetic expected match for matcher regression."
            if expectation.decision is MatchDecision.MATCHED
            else "Synthetic expected unknown decision for matcher regression."
        ),
        unknown_reason=expectation.unknown_reason,
        warnings=["Expected software-test result; not measured diagnostic evidence."],
    )


def _readme(case_name: str, *, reference: bool, expectation: ExpectedDecision | None) -> str:
    role = "reference fingerprint" if reference else "query case"
    expected = (
        f"Expected label: `{expectation.label}`."
        if expectation is not None and expectation.label is not None
        else f"Expected decision: `unknown` ({expectation.unknown_reason.value})."
        if expectation is not None and expectation.unknown_reason is not None
        else "Expected artifact: a synthetic reference fingerprint."
    )
    return f"""# {case_name.replace("_", " ").title()}

This directory is a deterministic synthetic {role} for P0 software testing.
Its values are constructed regression evidence, not engine measurements,
experimental findings or a scientifically validated latency profile.

{expected}

The simulated pair records a declared `stream_profile_relief` change. No live
runtime action or restoration occurred.
"""


def rendered_fixture_files() -> dict[Path, str]:
    """Return all expected fixture files keyed by paths relative to ``fixtures``."""

    files: dict[Path, str] = {}
    for label, vector in REFERENCE_VECTORS.items():
        case_id = f"reference-{label}"
        observation = _observation(case_id, vector)
        directory = Path("reference_cases") / label
        files[directory / "degraded.json"] = _json(observation.degraded_window)
        files[directory / "relief.json"] = _json(observation.relief_window)
        files[directory / "probe.json"] = _json(observation.probe)
        files[directory / "observation.json"] = _json(observation)
        files[directory / "fingerprint.json"] = _json(_fingerprint(label, observation))
        files[directory / "README.md"] = _readme(label, reference=True, expectation=None)

    for case_name, vector in QUERY_VECTORS.items():
        compatibility_group = (
            "p0-incompatible-synthetic-v1"
            if case_name == "incompatible_context"
            else SYNTHETIC_COMPATIBILITY_GROUP
        )
        observation = _observation(
            f"query-{case_name}", vector, compatibility_group=compatibility_group
        )
        directory = Path("query_cases") / case_name
        files[directory / "degraded.json"] = _json(observation.degraded_window)
        files[directory / "relief.json"] = _json(observation.relief_window)
        files[directory / "probe.json"] = _json(observation.probe)
        files[directory / "observation.json"] = _json(observation)
        files[directory / "expected-match-result.json"] = _json(
            _expected_match_result(case_name, observation)
        )
        files[directory / "README.md"] = _readme(
            case_name,
            reference=False,
            expectation=QUERY_EXPECTATIONS[case_name],
        )
    return files


def export_fixture_files(
    output_directory: Path = DEFAULT_FIXTURE_DIRECTORY,
) -> tuple[Path, ...]:
    """Write the deterministic fixture corpus and return paths in stable order."""

    rendered = rendered_fixture_files()
    paths = tuple(output_directory / relative_path for relative_path in sorted(rendered))
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered[path.relative_to(output_directory)], encoding="utf-8")
    return paths


def fixture_drift(
    output_directory: Path = DEFAULT_FIXTURE_DIRECTORY,
) -> dict[Path, str]:
    """Return generated fixture files that are missing or out of date."""

    drift: dict[Path, str] = {}
    for relative_path, expected in rendered_fixture_files().items():
        path = output_directory / relative_path
        if not path.is_file() or path.read_text(encoding="utf-8") != expected:
            drift[path] = expected
    return drift


__all__ = [
    "DEFAULT_FIXTURE_DIRECTORY",
    "FEATURE_BASELINES",
    "QUERY_EXPECTATIONS",
    "QUERY_VECTORS",
    "REFERENCE_VECTORS",
    "SYNTHETIC_COMPATIBILITY_GROUP",
    "export_fixture_files",
    "fixture_drift",
    "rendered_fixture_files",
]
