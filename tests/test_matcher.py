"""End-to-end matcher tests, including every required P0 unknown reason."""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path
from typing import TypeVar

import pytest
from pydantic import BaseModel

from latency_fingerprinting.evidence import CandidateEvidence
from latency_fingerprinting.fingerprints import (
    FingerprintEntry,
    FingerprintRejection,
    FingerprintRejectionReason,
    FingerprintRepository,
    load_fingerprint_repository,
)
from latency_fingerprinting.matcher import match_observation
from latency_fingerprinting.matching.scoring import best_availability
from latency_fingerprinting.models import (
    MatchDecision,
    MatchResult,
    MatchThresholds,
    ObservationRecord,
    UnknownReason,
    ValidationStatus,
)
from latency_fingerprinting.synthetic_fixtures import (
    DEFAULT_FIXTURE_DIRECTORY,
    QUERY_EXPECTATIONS,
)

ModelT = TypeVar("ModelT", bound=BaseModel)
REFERENCE_DIRECTORY = DEFAULT_FIXTURE_DIRECTORY / "reference_cases"


def load_model(model_type: type[ModelT], path: Path) -> ModelT:
    return model_type.model_validate_json(path.read_text(encoding="utf-8"))


def load_query(case_name: str) -> ObservationRecord:
    return load_model(
        ObservationRecord,
        DEFAULT_FIXTURE_DIRECTORY / "query_cases" / case_name / "observation.json",
    )


def load_expected(case_name: str) -> MatchResult:
    return load_model(
        MatchResult,
        DEFAULT_FIXTURE_DIRECTORY / "query_cases" / case_name / "expected-match-result.json",
    )


def load_repository() -> FingerprintRepository:
    return load_fingerprint_repository(REFERENCE_DIRECTORY)


def rebuild(model: ModelT, **changes: object) -> ModelT:
    payload = model.model_dump()
    payload.update(changes)
    return type(model).model_validate(payload)


def with_feature_subset(query: ObservationRecord, retained: set[str]) -> ObservationRecord:
    raw = query.response_delta.model_dump()
    removed = sorted(set(raw["features"]) - retained)
    raw["features"] = {
        feature: value for feature, value in raw["features"].items() if feature in retained
    }
    raw["missing_features"] = removed

    normalized = query.normalized_response.model_dump()
    normalized["features"] = {
        feature: value for feature, value in normalized["features"].items() if feature in retained
    }
    normalized["missing_features"] = removed
    return rebuild(query, response_delta=raw, normalized_response=normalized)


@pytest.mark.parametrize("case_name", sorted(QUERY_EXPECTATIONS))
def test_fixture_query_emits_expected_decision(case_name: str) -> None:
    result = match_observation(load_query(case_name), load_repository())
    expectation = QUERY_EXPECTATIONS[case_name]

    assert result.decision is expectation.decision
    assert result.accepted_label == expectation.label
    assert result.unknown_reason is expectation.unknown_reason


@pytest.mark.parametrize("case_name", ["similar_network", "similar_encoder", "ambiguous"])
def test_rankings_and_scores_match_declared_fixture_expectations(case_name: str) -> None:
    result = match_observation(load_query(case_name), load_repository())
    expected = load_expected(case_name)

    assert [candidate.fingerprint_id for candidate in result.ranked_candidates] == [
        candidate.fingerprint_id for candidate in expected.ranked_candidates
    ]
    assert result.match_strength == pytest.approx(expected.match_strength)
    assert result.score_margin == pytest.approx(expected.score_margin)


def test_best_candidate_evidence_reconstructs_ranked_distance() -> None:
    result = match_observation(load_query("similar_network"), load_repository())
    evidence = result.supporting_evidence + result.conflicting_evidence
    weighted_sum = sum(item.weighted_squared_residual for item in evidence)
    total_weight = sum(item.weight for item in evidence)

    assert result.ranked_candidates[0].distance == pytest.approx(
        math.sqrt(weighted_sum / total_weight)
    )
    assert result.shared_feature_count == len(evidence)
    assert result.feature_coverage == 1.0


def test_best_availability_ties_use_the_lowest_stable_identifier() -> None:
    base = CandidateEvidence(
        fingerprint_id="fingerprint-z",
        evidence=(),
        supporting_evidence=(),
        conflicting_evidence=(),
        ignored_evidence=(),
        missing_features=(),
        rejected_features=(),
        shared_feature_count=2,
        feature_coverage=0.5,
        observable_feature_count=2,
        observable_feature_coverage=0.5,
        total_weight=2,
        weighted_squared_residual_sum=0,
        distance=0,
    )

    selected = best_availability((base, replace(base, fingerprint_id="fingerprint-a")))

    assert selected is not None
    assert selected.fingerprint_id == "fingerprint-a"


def test_unsupported_probe_returns_unknown_before_candidate_scoring() -> None:
    query = load_query("similar_network")
    probe = rebuild(query.probe, probe_type="unsupported-probe")
    query = rebuild(query, probe=probe)

    result = match_observation(query, load_repository())

    assert result.decision is MatchDecision.UNKNOWN
    assert result.unknown_reason is UnknownReason.UNSUPPORTED_PROBE
    assert result.ranked_candidates == []
    assert not result.compatibility.is_compatible


@pytest.mark.parametrize("threshold", [-1.0, math.inf, math.nan])
def test_support_threshold_is_validated_before_early_matcher_returns(threshold: float) -> None:
    with pytest.raises(ValueError, match="support_residual_threshold"):
        match_observation(
            load_query("similar_network"),
            FingerprintRepository(entries=()),
            support_residual_threshold=threshold,
        )


def test_invalid_observation_returns_unknown_with_retained_reason() -> None:
    query = load_query("similar_network")
    features = sorted(query.response_delta.features)
    raw = query.response_delta.model_dump()
    raw.update(
        features={},
        missing_features=features,
        is_valid=False,
        invalid_reasons=["invalid_observation: synthetic invalid query"],
    )
    normalized = query.normalized_response.model_dump()
    normalized.update(
        features={},
        missing_features=features,
        is_valid=False,
        invalid_reasons=["invalid_observation: synthetic invalid query"],
    )
    query = rebuild(query, response_delta=raw, normalized_response=normalized)

    result = match_observation(query, load_repository())

    assert result.unknown_reason is UnknownReason.INVALID_OBSERVATION
    assert result.compatibility.is_compatible
    assert result.ranked_candidates == []
    assert "invalid_observation: synthetic invalid query" in result.warnings


def test_invalid_observation_takes_precedence_over_an_empty_repository() -> None:
    query = load_query("similar_network")
    features = sorted(query.response_delta.features)
    raw = query.response_delta.model_dump()
    raw.update(
        features={},
        missing_features=features,
        is_valid=False,
        invalid_reasons=["invalid_observation: invalid query"],
    )
    normalized = query.normalized_response.model_dump()
    normalized.update(
        features={},
        missing_features=features,
        is_valid=False,
        invalid_reasons=["invalid_observation: invalid query"],
    )
    query = rebuild(query, response_delta=raw, normalized_response=normalized)

    result = match_observation(query, FingerprintRepository(entries=()))

    assert result.unknown_reason is UnknownReason.INVALID_OBSERVATION
    assert not result.compatibility.is_compatible


def test_insufficient_shared_features_returns_unknown_without_scores() -> None:
    query = load_query("similar_network")
    query = with_feature_subset(
        query,
        {"client.received_fps", "transport.jitter_ms"},
    )

    result = match_observation(query, load_repository())

    assert result.unknown_reason is UnknownReason.INSUFFICIENT_FEATURE_COVERAGE
    assert result.shared_feature_count == 2
    assert result.feature_coverage == 0.5
    assert result.match_strength is None
    assert set(result.missing_features) == {
        "client.received_bitrate_kbps",
        "transport.packets_lost_delta",
    }


def test_coverage_adjusts_strength_after_weighted_distance() -> None:
    query = load_query("similar_network")
    retained = set(query.normalized_response.features) - {"transport.packets_lost_delta"}
    query = with_feature_subset(query, retained)
    thresholds = MatchThresholds(
        minimum_match_strength=0.5,
        minimum_score_margin=0.1,
        minimum_shared_feature_count=3,
        minimum_feature_coverage=0.6,
    )

    result = match_observation(query, load_repository(), thresholds=thresholds)
    best = result.ranked_candidates[0]
    expected_strength = (1 / (1 + best.distance)) * 0.75

    assert result.decision is MatchDecision.MATCHED
    assert result.feature_coverage == 0.75
    assert result.match_strength == pytest.approx(expected_strength)


def test_all_zero_candidate_weights_return_degenerate_vector() -> None:
    repository = load_repository()
    entries: list[FingerprintEntry] = []
    for entry in repository.entries:
        fingerprint = rebuild(
            entry.fingerprint,
            feature_weights={feature: 0.0 for feature in entry.fingerprint.feature_weights},
        )
        entries.append(FingerprintEntry(path=entry.path, fingerprint=fingerprint))
    degenerate_repository = FingerprintRepository(entries=tuple(entries))

    result = match_observation(load_query("similar_network"), degenerate_repository)

    assert result.unknown_reason is UnknownReason.DEGENERATE_VECTOR
    assert result.match_strength is None
    assert result.ranked_candidates == []
    assert any("no positive shared feature weight" in warning for warning in result.warnings)


def test_zero_weight_features_cannot_satisfy_the_evidence_gate() -> None:
    entry = load_repository().entries[1]
    weighted_feature = next(iter(entry.fingerprint.feature_weights))
    weights = {feature: 0.0 for feature in entry.fingerprint.feature_weights}
    weights[weighted_feature] = 1.0
    fingerprint = rebuild(entry.fingerprint, feature_weights=weights)
    repository = FingerprintRepository(
        entries=(FingerprintEntry(path=entry.path, fingerprint=fingerprint),)
    )

    result = match_observation(load_query("similar_network"), repository)

    assert result.unknown_reason is UnknownReason.INSUFFICIENT_FEATURE_COVERAGE
    assert result.shared_feature_count == 1


def test_weak_ambiguous_and_conflicting_reasons_have_stable_precedence() -> None:
    repository = load_repository()
    assert (
        match_observation(load_query("weak"), repository).unknown_reason is UnknownReason.WEAK_MATCH
    )
    assert (
        match_observation(load_query("ambiguous"), repository).unknown_reason
        is UnknownReason.AMBIGUOUS_MARGIN
    )
    assert (
        match_observation(load_query("conflicting"), repository).unknown_reason
        is UnknownReason.CONFLICTING_EVIDENCE
    )


def test_conflict_policy_is_explicit_and_configurable() -> None:
    query = load_query("conflicting")
    repository = load_repository()
    conservative = match_observation(query, repository)
    relaxed = match_observation(query, repository, conflict_contribution_ratio=1.0)

    assert conservative.unknown_reason is UnknownReason.CONFLICTING_EVIDENCE
    assert relaxed.decision is MatchDecision.MATCHED
    assert relaxed.accepted_label == "network_pressure"


@pytest.mark.parametrize("ratio", [-0.01, 1.01, float("nan"), float("inf")])
def test_invalid_conflict_ratio_is_rejected(ratio: float) -> None:
    with pytest.raises(ValueError, match="conflict_contribution_ratio"):
        match_observation(
            load_query("conflicting"),
            load_repository(),
            conflict_contribution_ratio=ratio,
        )


def test_custom_strength_threshold_can_conservatively_reject_clear_match() -> None:
    thresholds = MatchThresholds(minimum_match_strength=0.99)
    result = match_observation(
        load_query("similar_network"),
        load_repository(),
        thresholds=thresholds,
    )
    assert result.unknown_reason is UnknownReason.WEAK_MATCH


def test_repository_rejections_are_visible_in_match_output(tmp_path: Path) -> None:
    repository = load_repository()
    rejection = FingerprintRejection(
        path=tmp_path / "broken.json",
        reason=FingerprintRejectionReason.INVALID_JSON,
        message="invalid test JSON",
    )
    partial_repository = FingerprintRepository(
        entries=repository.entries,
        rejections=(rejection,),
    )

    result = match_observation(load_query("similar_network"), partial_repository)

    assert result.decision is MatchDecision.MATCHED
    assert "file:broken.json" in result.compatibility.rejected_fingerprints
    assert any("broken.json" in warning for warning in result.warnings)


def test_rejected_repository_id_cannot_collide_with_a_valid_candidate(tmp_path: Path) -> None:
    repository = load_repository()
    valid_id = repository.entries[0].fingerprint.fingerprint_id
    rejection = FingerprintRejection(
        path=tmp_path / "invalid-copy.json",
        reason=FingerprintRejectionReason.CONTRACT_VERSION_MISMATCH,
        message="invalid test contract",
        fingerprint_id=valid_id,
    )
    partial_repository = FingerprintRepository(
        entries=repository.entries,
        rejections=(rejection,),
    )

    result = match_observation(load_query("similar_network"), partial_repository)

    assert result.decision is MatchDecision.MATCHED
    assert valid_id in result.compatibility.compatible_fingerprint_ids
    assert "file:invalid-copy.json" in result.compatibility.rejected_fingerprints


def test_rejected_validation_status_is_never_scored() -> None:
    entry = load_repository().entries[0]
    rejected = rebuild(entry.fingerprint, validation_status=ValidationStatus.REJECTED)
    repository = FingerprintRepository(
        entries=(FingerprintEntry(path=entry.path, fingerprint=rejected),)
    )

    result = match_observation(load_query("similar_network"), repository)

    assert result.unknown_reason is UnknownReason.INCOMPATIBLE_CONTEXT
    assert result.ranked_candidates == []
    assert (
        "validation status is rejected"
        in result.compatibility.rejected_fingerprints[rejected.fingerprint_id]
    )


def test_matcher_is_deterministic_and_does_not_mutate_inputs() -> None:
    query = load_query("similar_encoder")
    repository = load_repository()
    query_before = query.model_dump()
    repository_before = repository

    first = match_observation(query, repository)
    second = match_observation(query, repository)

    assert first == second
    assert query.model_dump() == query_before
    assert repository == repository_before
    assert MatchResult.model_validate_json(first.model_dump_json(by_alias=True)) == first


def test_empty_repository_returns_incompatible_context_unknown() -> None:
    result = match_observation(
        load_query("similar_network"),
        FingerprintRepository(entries=()),
    )
    assert result.unknown_reason is UnknownReason.INCOMPATIBLE_CONTEXT
    assert not result.compatibility.is_compatible
    assert result.match_strength is None
