"""Feature-evidence and match-result model invariants."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from latency_fingerprinting.models import (
    CompatibilityResult,
    FeatureEvidence,
    MatchDecision,
    MatchResult,
    RankedCandidate,
    UnknownReason,
)

from .factories import make_match_result


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
