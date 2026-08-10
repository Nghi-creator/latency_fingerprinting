"""Reusable orchestration for the complete offline P0 analytical path."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from .fingerprints import FingerprintRepository, load_fingerprint_repository
from .matcher import match_observation
from .models import (
    MatchResult,
    MatchThresholds,
    ObservationRecord,
    ObservationWindow,
    Probe,
)
from .normalization import (
    P0_FEATURE_CONFIG,
    FeatureNormalizationConfig,
    normalize_response,
)
from .windows import build_response_delta


@dataclass(frozen=True, slots=True)
class PipelineResult:
    observation: ObservationRecord
    match_result: MatchResult


def canonical_json(model: BaseModel) -> str:
    """Serialize a contract record as deterministic, newline-terminated JSON."""

    payload = model.model_dump(mode="json", by_alias=True)
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def build_observation_record(
    degraded: ObservationWindow,
    relief: ObservationWindow,
    probe: Probe,
    *,
    feature_config: Mapping[str, FeatureNormalizationConfig] = P0_FEATURE_CONFIG,
) -> ObservationRecord:
    """Validate, calculate, and normalize one declared window pair."""

    response = build_response_delta(degraded, relief, probe)
    normalized = normalize_response(response, feature_config=feature_config)
    return ObservationRecord(
        context=degraded.context,
        degraded_window=degraded,
        relief_window=relief,
        probe=probe,
        response_delta=response,
        normalized_response=normalized,
        provenance=degraded.provenance,
    )


def run_pipeline(
    degraded: ObservationWindow,
    relief: ObservationWindow,
    probe: Probe,
    repository: FingerprintRepository,
    *,
    feature_config: Mapping[str, FeatureNormalizationConfig] = P0_FEATURE_CONFIG,
    thresholds: MatchThresholds | None = None,
) -> PipelineResult:
    """Run the complete in-memory P0 observation and matching path."""

    observation = build_observation_record(
        degraded,
        relief,
        probe,
        feature_config=feature_config,
    )
    return PipelineResult(
        observation=observation,
        match_result=match_observation(
            observation,
            repository,
            thresholds=thresholds,
        ),
    )


def run_pipeline_from_files(
    degraded_path: Path,
    relief_path: Path,
    probe_path: Path,
    fingerprint_directory: Path,
    *,
    strict_repository: bool = True,
    feature_config: Mapping[str, FeatureNormalizationConfig] = P0_FEATURE_CONFIG,
    thresholds: MatchThresholds | None = None,
) -> PipelineResult:
    """Load standalone JSON inputs and run the complete offline P0 path."""

    degraded = ObservationWindow.model_validate_json(degraded_path.read_text(encoding="utf-8"))
    relief = ObservationWindow.model_validate_json(relief_path.read_text(encoding="utf-8"))
    probe = Probe.model_validate_json(probe_path.read_text(encoding="utf-8"))
    repository = load_fingerprint_repository(
        fingerprint_directory,
        strict=strict_repository,
    )
    return run_pipeline(
        degraded,
        relief,
        probe,
        repository,
        feature_config=feature_config,
        thresholds=thresholds,
    )


__all__ = [
    "PipelineResult",
    "build_observation_record",
    "canonical_json",
    "run_pipeline",
    "run_pipeline_from_files",
]
