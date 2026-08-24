"""Candidate evidence evaluation and weighted-distance scoring."""

from __future__ import annotations

from dataclasses import dataclass

from ..evidence import CandidateEvidence, EvidenceError, build_candidate_evidence
from ..models import Fingerprint, MatchThresholds, NormalizedResponse


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    fingerprint: Fingerprint
    evidence: CandidateEvidence
    match_strength: float


@dataclass(frozen=True, slots=True)
class ScoringResult:
    evidence: tuple[CandidateEvidence, ...]
    eligible: tuple[CandidateEvidence, ...]
    scored: tuple[ScoredCandidate, ...]
    warnings: tuple[str, ...]


def best_availability(evidence: tuple[CandidateEvidence, ...]) -> CandidateEvidence | None:
    return min(
        evidence,
        key=lambda item: (
            -item.feature_coverage,
            -item.shared_feature_count,
            item.fingerprint_id,
        ),
        default=None,
    )


def score_candidates(
    response: NormalizedResponse,
    candidates: tuple[Fingerprint, ...],
    thresholds: MatchThresholds,
    *,
    support_residual_threshold: float,
) -> ScoringResult:
    """Build evidence, apply availability gates, and score usable candidates."""

    candidate_evidence: list[CandidateEvidence] = []
    warnings: list[str] = []
    for candidate in candidates:
        try:
            evidence = build_candidate_evidence(
                response,
                candidate,
                support_residual_threshold=support_residual_threshold,
            )
        except EvidenceError as error:
            warnings.append(f"Could not score {candidate.fingerprint_id}: {error}")
            continue
        candidate_evidence.append(evidence)

    eligible = tuple(
        evidence
        for evidence in candidate_evidence
        if evidence.shared_feature_count >= thresholds.minimum_shared_feature_count
        and evidence.feature_coverage >= thresholds.minimum_feature_coverage
    )
    candidates_by_id = {candidate.fingerprint_id: candidate for candidate in candidates}
    scored: list[ScoredCandidate] = []
    for evidence in eligible:
        if evidence.distance is None:
            warnings.append(
                f"Candidate {evidence.fingerprint_id} has no positive shared feature weight."
            )
            continue
        base_strength = 1 / (1 + evidence.distance)
        scored.append(
            ScoredCandidate(
                fingerprint=candidates_by_id[evidence.fingerprint_id],
                evidence=evidence,
                match_strength=base_strength * evidence.feature_coverage,
            )
        )
    scored.sort(key=lambda item: (-item.match_strength, item.fingerprint.fingerprint_id))
    return ScoringResult(
        evidence=tuple(candidate_evidence),
        eligible=eligible,
        scored=tuple(scored),
        warnings=tuple(warnings),
    )


__all__ = ["ScoredCandidate", "ScoringResult", "best_availability", "score_candidates"]
