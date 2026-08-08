"""End-to-end tests for the complete offline synthetic P0 pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from latency_fingerprinting.models import MatchDecision, MatchResult, ObservationRecord
from latency_fingerprinting.pipeline import (
    PipelineResult,
    canonical_json,
    run_pipeline_from_files,
)
from latency_fingerprinting.synthetic_fixtures import (
    DEFAULT_FIXTURE_DIRECTORY,
    QUERY_EXPECTATIONS,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIRECTORY = DEFAULT_FIXTURE_DIRECTORY / "reference_cases"
EXAMPLE_RESULT_PATH = PROJECT_ROOT / "tests" / "data" / "clear-network-match-result.json"
MATCH_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "match-result-v1.schema.json"


def run_case(case_name: str) -> PipelineResult:
    directory = DEFAULT_FIXTURE_DIRECTORY / "query_cases" / case_name
    return run_pipeline_from_files(
        directory / "degraded.json",
        directory / "relief.json",
        directory / "probe.json",
        REFERENCE_DIRECTORY,
    )


@pytest.mark.parametrize("case_name", sorted(QUERY_EXPECTATIONS))
def test_checked_in_pairs_run_through_the_complete_pipeline(case_name: str) -> None:
    result = run_case(case_name)
    directory = DEFAULT_FIXTURE_DIRECTORY / "query_cases" / case_name
    expected_observation = ObservationRecord.model_validate_json(
        (directory / "observation.json").read_text(encoding="utf-8")
    )
    expectation = QUERY_EXPECTATIONS[case_name]

    assert result.observation == expected_observation
    assert result.match_result.decision is expectation.decision
    assert result.match_result.accepted_label == expectation.label
    assert result.match_result.unknown_reason is expectation.unknown_reason


def test_clear_and_noisy_queries_match_the_intended_references() -> None:
    network = run_case("similar_network").match_result
    encoder = run_case("similar_encoder").match_result

    assert network.decision is MatchDecision.MATCHED
    assert network.accepted_label == "network_pressure"
    assert network.supporting_evidence
    assert encoder.decision is MatchDecision.MATCHED
    assert encoder.accepted_label == "host_encoder_pressure"
    assert encoder.supporting_evidence


def test_required_fixture_unknown_paths_remain_conservative() -> None:
    expected_reasons = {
        "weak": "weak_match",
        "ambiguous": "ambiguous_margin",
        "conflicting": "conflicting_evidence",
        "incompatible_context": "incompatible_context",
    }
    for case_name, reason in expected_reasons.items():
        result = run_case(case_name).match_result
        assert result.decision is MatchDecision.UNKNOWN
        assert result.accepted_label is None
        assert result.unknown_reason is not None
        assert result.unknown_reason.value == reason


def test_canonical_result_is_byte_stable_and_checked_in() -> None:
    first = canonical_json(run_case("similar_network").match_result)
    second = canonical_json(run_case("similar_network").match_result)

    assert first == second
    assert first.endswith("\n")
    assert first == EXAMPLE_RESULT_PATH.read_text(encoding="utf-8")


def test_example_output_conforms_to_checked_in_result_schema_contract() -> None:
    text = EXAMPLE_RESULT_PATH.read_text(encoding="utf-8")
    payload = json.loads(text)
    schema = json.loads(MATCH_SCHEMA_PATH.read_text(encoding="utf-8"))

    validated = MatchResult.model_validate_json(text)
    assert validated.schema_version == "match-result-v1"
    assert validated.contract_version == "1.0.0"
    assert schema["properties"]["schemaVersion"]["const"] == validated.schema_version
    assert schema["properties"]["contractVersion"]["const"] == validated.contract_version
    assert set(schema["required"]).issubset(payload)
    assert set(payload).issubset(schema["properties"])
    assert schema["additionalProperties"] is False


def test_pipeline_json_uses_contract_aliases_and_finite_numbers() -> None:
    result = run_case("similar_network")
    observation_payload = json.loads(canonical_json(result.observation))
    match_payload = json.loads(canonical_json(result.match_result))

    assert "schemaVersion" in observation_payload
    assert "responseDelta" in observation_payload
    assert "normalizedResponse" in observation_payload
    assert "matchStrength" in match_payload
    assert "rankedCandidates" in match_payload
    assert "unknownReason" in match_payload
