"""Validation and drift tests for the P0 synthetic fixture corpus."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TypeVar

import pytest
from pydantic import BaseModel

from latency_fingerprinting.models import (
    Fingerprint,
    MatchDecision,
    MatchResult,
    ObservationRecord,
    ObservationWindow,
    Probe,
    ProvenanceKind,
)
from latency_fingerprinting.normalization import normalize_response
from latency_fingerprinting.synthetic_fixtures import (
    DEFAULT_FIXTURE_DIRECTORY,
    QUERY_EXPECTATIONS,
    QUERY_VECTORS,
    REFERENCE_VECTORS,
    SYNTHETIC_COMPATIBILITY_GROUP,
    fixture_drift,
    rendered_fixture_files,
)
from latency_fingerprinting.windows import build_response_delta

REFERENCE_CASES = tuple(sorted(REFERENCE_VECTORS))
QUERY_CASES = tuple(sorted(QUERY_VECTORS))
ModelT = TypeVar("ModelT", bound=BaseModel)


def load_model(model_type: type[ModelT], path: Path) -> ModelT:
    return model_type.model_validate_json(path.read_text(encoding="utf-8"))


def test_fixture_generation_is_deterministic_and_checked_in() -> None:
    assert rendered_fixture_files() == rendered_fixture_files()
    assert len(rendered_fixture_files()) == 54
    assert fixture_drift() == {}


@pytest.mark.parametrize("case_name", REFERENCE_CASES)
def test_reference_case_contract_records_are_consistent(case_name: str) -> None:
    directory = DEFAULT_FIXTURE_DIRECTORY / "reference_cases" / case_name
    degraded = load_model(ObservationWindow, directory / "degraded.json")
    relief = load_model(ObservationWindow, directory / "relief.json")
    probe = load_model(Probe, directory / "probe.json")
    observation = load_model(ObservationRecord, directory / "observation.json")
    fingerprint = load_model(Fingerprint, directory / "fingerprint.json")

    assert isinstance(degraded, ObservationWindow)
    assert isinstance(relief, ObservationWindow)
    assert isinstance(probe, Probe)
    assert isinstance(observation, ObservationRecord)
    assert isinstance(fingerprint, Fingerprint)
    assert observation.degraded_window == degraded
    assert observation.relief_window == relief
    assert observation.probe == probe
    assert build_response_delta(degraded, relief, probe) == observation.response_delta
    assert normalize_response(observation.response_delta) == observation.normalized_response
    assert fingerprint.raw_response_delta == observation.response_delta
    assert fingerprint.normalized_response == observation.normalized_response
    assert fingerprint.provenance is ProvenanceKind.SYNTHETIC
    assert fingerprint.validation_status.value == "software_test_reference"
    assert fingerprint.context.compatibility_group == SYNTHETIC_COMPATIBILITY_GROUP


@pytest.mark.parametrize(("case_name", "vector"), REFERENCE_VECTORS.items())
def test_reference_vectors_are_inspectable(case_name: str, vector: Mapping[str, float]) -> None:
    path = DEFAULT_FIXTURE_DIRECTORY / "reference_cases" / case_name / "observation.json"
    observation = load_model(ObservationRecord, path)
    assert isinstance(observation, ObservationRecord)

    actual = {
        feature: normalized.value
        for feature, normalized in observation.normalized_response.features.items()
    }
    assert actual == pytest.approx(vector)


@pytest.mark.parametrize("case_name", QUERY_CASES)
def test_query_case_contract_records_are_consistent(case_name: str) -> None:
    directory = DEFAULT_FIXTURE_DIRECTORY / "query_cases" / case_name
    degraded = load_model(ObservationWindow, directory / "degraded.json")
    relief = load_model(ObservationWindow, directory / "relief.json")
    probe = load_model(Probe, directory / "probe.json")
    observation = load_model(ObservationRecord, directory / "observation.json")
    expected = load_model(MatchResult, directory / "expected-match-result.json")

    assert isinstance(degraded, ObservationWindow)
    assert isinstance(relief, ObservationWindow)
    assert isinstance(probe, Probe)
    assert isinstance(observation, ObservationRecord)
    assert isinstance(expected, MatchResult)
    assert observation.degraded_window == degraded
    assert observation.relief_window == relief
    assert observation.probe == probe
    assert build_response_delta(degraded, relief, probe) == observation.response_delta
    assert normalize_response(observation.response_delta) == observation.normalized_response
    assert observation.provenance is ProvenanceKind.SYNTHETIC

    expectation = QUERY_EXPECTATIONS[case_name]
    assert expected.decision is expectation.decision
    assert expected.accepted_label == expectation.label
    assert expected.unknown_reason is expectation.unknown_reason


def test_clear_query_expectations_are_matched_and_unknown_cases_are_conservative() -> None:
    for case_name in ("similar_network", "similar_encoder"):
        path = DEFAULT_FIXTURE_DIRECTORY / "query_cases" / case_name / "expected-match-result.json"
        result = load_model(MatchResult, path)
        assert isinstance(result, MatchResult)
        assert result.decision is MatchDecision.MATCHED
        assert result.match_strength is not None
        assert result.match_strength >= result.thresholds.minimum_match_strength

    for case_name in ("weak", "ambiguous", "conflicting", "incompatible_context"):
        path = DEFAULT_FIXTURE_DIRECTORY / "query_cases" / case_name / "expected-match-result.json"
        result = load_model(MatchResult, path)
        assert isinstance(result, MatchResult)
        assert result.decision is MatchDecision.UNKNOWN
        assert result.accepted_label is None
        assert result.unknown_reason is not None


def test_incompatible_query_uses_an_explicitly_different_group() -> None:
    path = DEFAULT_FIXTURE_DIRECTORY / "query_cases" / "incompatible_context" / "observation.json"
    observation = load_model(ObservationRecord, path)
    assert isinstance(observation, ObservationRecord)
    assert observation.context.compatibility_group != SYNTHETIC_COMPATIBILITY_GROUP


def test_fixture_documentation_preserves_synthetic_truthfulness() -> None:
    for path in DEFAULT_FIXTURE_DIRECTORY.rglob("README.md"):
        text = path.read_text(encoding="utf-8").lower()
        assert "synthetic" in text
        assert "not engine measurements" in text
        assert "no live" in text


def test_fixture_files_do_not_contain_personal_absolute_paths() -> None:
    for relative_path in rendered_fixture_files():
        text = (DEFAULT_FIXTURE_DIRECTORY / relative_path).read_text(encoding="utf-8")
        assert "/Users/" not in text
