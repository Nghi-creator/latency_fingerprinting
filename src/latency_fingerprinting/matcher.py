"""Interpretable weighted-distance matching with conservative unknown handling."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .evidence import (
    DEFAULT_SUPPORT_RESIDUAL_THRESHOLD,
    CandidateEvidence,
    EvidenceError,
    build_candidate_evidence,
)
from .fingerprints import FingerprintRepository
from .models import (
    CompatibilityResult,
    Fingerprint,
    MatchDecision,
    MatchResult,
    MatchThresholds,
    ObservationRecord,
    RankedCandidate,
    UnknownReason,
)
from .validation import SUPPORTED_P0_PROBE_TYPES

DEFAULT_CONFLICT_CONTRIBUTION_RATIO = 0.50


@dataclass(frozen=True, slots=True)
class _ScoredCandidate:
    fingerprint: Fingerprint
    evidence: CandidateEvidence
    match_strength: float


def _unique_messages(messages: list[str]) -> list[str]:
    return list(dict.fromkeys(messages))


def _add_rejection(rejected: dict[str, str], identifier: str, reason: str) -> None:
    if identifier in rejected:
        rejected[identifier] = f"{rejected[identifier]}; {reason}"
    else:
        rejected[identifier] = reason


def _compatibility(
    query: ObservationRecord,
    repository: FingerprintRepository,
) -> tuple[tuple[Fingerprint, ...], CompatibilityResult, list[str]]:
    compatible: list[Fingerprint] = []
    rejected: dict[str, str] = {}
    warnings: list[str] = []
    for entry in sorted(repository.entries, key=lambda item: item.fingerprint.fingerprint_id):
        fingerprint = entry.fingerprint
        reasons: list[str] = []
        if fingerprint.contract_version != query.contract_version:
            reasons.append("contract version mismatch")
        if fingerprint.compatibility.compatibility_group != query.context.compatibility_group:
            reasons.append("compatibility group mismatch")
        if fingerprint.compatibility.probe_type != query.probe.probe_type:
            reasons.append("probe type mismatch")
        if reasons:
            _add_rejection(
                rejected,
                fingerprint.fingerprint_id,
                ", ".join(reasons),
            )
        else:
            compatible.append(fingerprint)

    for rejection in repository.rejections:
        identifier = rejection.fingerprint_id or f"file:{rejection.path.name}"
        reason = f"repository {rejection.reason.value}: {rejection.message}"
        _add_rejection(rejected, identifier, reason)
        warnings.append(f"Rejected fingerprint source {rejection.path}: {reason}")

    compatible.sort(key=lambda fingerprint: fingerprint.fingerprint_id)
    return (
        tuple(compatible),
        CompatibilityResult(
            is_compatible=bool(compatible),
            compatibility_group=query.context.compatibility_group,
            compatible_fingerprint_ids=[fingerprint.fingerprint_id for fingerprint in compatible],
            rejected_fingerprints=rejected,
        ),
        warnings,
    )


def _unranked_unknown(
    *,
    reason: UnknownReason,
    decision_reason: str,
    compatibility: CompatibilityResult,
    thresholds: MatchThresholds,
    warnings: list[str],
    shared_feature_count: int = 0,
    feature_coverage: float = 0.0,
    missing_features: list[str] | None = None,
) -> MatchResult:
    return MatchResult(
        decision=MatchDecision.UNKNOWN,
        shared_feature_count=shared_feature_count,
        feature_coverage=feature_coverage,
        missing_features=missing_features or [],
        compatibility=compatibility,
        thresholds=thresholds,
        warnings=_unique_messages(warnings),
        decision_reason=decision_reason,
        unknown_reason=reason,
    )


def _best_availability(evidence: list[CandidateEvidence]) -> CandidateEvidence | None:
    return max(
        evidence,
        key=lambda item: (
            item.feature_coverage,
            item.shared_feature_count,
            item.fingerprint_id,
        ),
        default=None,
    )


def _conflict_ratio(evidence: CandidateEvidence) -> float:
    if evidence.weighted_squared_residual_sum == 0:
        return 0.0
    conflict_sum = sum(item.weighted_squared_residual for item in evidence.conflicting_evidence)
    return conflict_sum / evidence.weighted_squared_residual_sum


def match_observation(
    query: ObservationRecord,
    repository: FingerprintRepository,
    *,
    thresholds: MatchThresholds | None = None,
    support_residual_threshold: float = DEFAULT_SUPPORT_RESIDUAL_THRESHOLD,
    conflict_contribution_ratio: float = DEFAULT_CONFLICT_CONTRIBUTION_RATIO,
) -> MatchResult:
    """Match one P0 observation against compatible stored fingerprints."""

    thresholds = thresholds or MatchThresholds()
    if not math.isfinite(conflict_contribution_ratio) or not 0 <= conflict_contribution_ratio <= 1:
        raise ValueError("conflict_contribution_ratio must be finite and between 0 and 1")

    candidates, compatibility, repository_warnings = _compatibility(query, repository)
    warnings = repository_warnings + list(query.normalized_response.warnings)

    if query.probe.probe_type not in SUPPORTED_P0_PROBE_TYPES:
        return _unranked_unknown(
            reason=UnknownReason.UNSUPPORTED_PROBE,
            decision_reason=f"Probe type {query.probe.probe_type!r} is not supported by P0.",
            compatibility=compatibility,
            thresholds=thresholds,
            warnings=warnings,
        )

    if not candidates:
        return _unranked_unknown(
            reason=UnknownReason.INCOMPATIBLE_CONTEXT,
            decision_reason=(
                "No stored fingerprint matches the query contract, compatibility group, "
                "and probe type."
            ),
            compatibility=compatibility,
            thresholds=thresholds,
            warnings=warnings,
        )

    if not query.response_delta.is_valid or not query.normalized_response.is_valid:
        return _unranked_unknown(
            reason=UnknownReason.INVALID_OBSERVATION,
            decision_reason="The query response is invalid and cannot be scored.",
            compatibility=compatibility,
            thresholds=thresholds,
            warnings=warnings + query.normalized_response.invalid_reasons,
            missing_features=list(query.normalized_response.missing_features),
        )

    candidate_evidence: list[CandidateEvidence] = []
    for candidate in candidates:
        try:
            evidence = build_candidate_evidence(
                query.normalized_response,
                candidate,
                support_residual_threshold=support_residual_threshold,
            )
        except EvidenceError as error:
            warnings.append(f"Could not score {candidate.fingerprint_id}: {error}")
            continue
        candidate_evidence.append(evidence)

    eligible = [
        evidence
        for evidence in candidate_evidence
        if evidence.shared_feature_count >= thresholds.minimum_shared_feature_count
        and evidence.feature_coverage >= thresholds.minimum_feature_coverage
    ]
    if not eligible:
        best_available = _best_availability(candidate_evidence)
        missing = (
            sorted(set(best_available.missing_features) | set(best_available.rejected_features))
            if best_available is not None
            else []
        )
        return _unranked_unknown(
            reason=UnknownReason.INSUFFICIENT_FEATURE_COVERAGE,
            decision_reason=(
                "No compatible fingerprint meets the minimum shared-feature count and coverage."
            ),
            compatibility=compatibility,
            thresholds=thresholds,
            warnings=warnings,
            shared_feature_count=(
                best_available.shared_feature_count if best_available is not None else 0
            ),
            feature_coverage=(
                best_available.feature_coverage if best_available is not None else 0.0
            ),
            missing_features=missing,
        )

    scored: list[_ScoredCandidate] = []
    for evidence in eligible:
        if evidence.distance is None:
            warnings.append(
                f"Candidate {evidence.fingerprint_id} has no positive shared feature weight."
            )
            continue
        fingerprint = next(
            candidate
            for candidate in candidates
            if candidate.fingerprint_id == evidence.fingerprint_id
        )
        base_strength = 1 / (1 + evidence.distance)
        scored.append(
            _ScoredCandidate(
                fingerprint=fingerprint,
                evidence=evidence,
                match_strength=base_strength * evidence.feature_coverage,
            )
        )

    if not scored:
        best_available = _best_availability(eligible)
        assert best_available is not None
        return _unranked_unknown(
            reason=UnknownReason.DEGENERATE_VECTOR,
            decision_reason="Compatible evidence has no positive total feature weight.",
            compatibility=compatibility,
            thresholds=thresholds,
            warnings=warnings,
            shared_feature_count=best_available.shared_feature_count,
            feature_coverage=best_available.feature_coverage,
            missing_features=sorted(
                set(best_available.missing_features) | set(best_available.rejected_features)
            ),
        )

    scored.sort(key=lambda item: (-item.match_strength, item.fingerprint.fingerprint_id))
    ranked: list[RankedCandidate] = []
    for item in scored:
        distance = item.evidence.distance
        if distance is None:
            continue
        ranked.append(
            RankedCandidate(
                fingerprint_id=item.fingerprint.fingerprint_id,
                bottleneck_label=item.fingerprint.bottleneck_label,
                distance=distance,
                match_strength=item.match_strength,
            )
        )
    best = scored[0]
    margin = scored[0].match_strength - scored[1].match_strength if len(scored) >= 2 else None
    best_missing = sorted(
        set(best.evidence.missing_features) | set(best.evidence.rejected_features)
    )
    if best.evidence.rejected_features:
        warnings.append(
            "Best candidate comparison excluded rejected query features: "
            + ", ".join(best.evidence.rejected_features)
        )
    if best.evidence.ignored_evidence:
        warnings.append(
            "Best candidate comparison ignored zero-weight features: "
            + ", ".join(item.feature for item in best.evidence.ignored_evidence)
        )

    result_fields = {
        "match_strength": best.match_strength,
        "score_margin": margin,
        "ranked_candidates": ranked,
        "shared_feature_count": best.evidence.shared_feature_count,
        "feature_coverage": best.evidence.feature_coverage,
        "supporting_evidence": list(best.evidence.supporting_evidence),
        "conflicting_evidence": list(best.evidence.conflicting_evidence),
        "missing_features": best_missing,
        "compatibility": compatibility,
        "thresholds": thresholds,
        "warnings": _unique_messages(warnings),
    }

    if best.match_strength < thresholds.minimum_match_strength:
        return MatchResult(
            decision=MatchDecision.UNKNOWN,
            decision_reason="The best match strength is below the provisional threshold.",
            unknown_reason=UnknownReason.WEAK_MATCH,
            **result_fields,
        )
    if margin is not None and margin < thresholds.minimum_score_margin:
        return MatchResult(
            decision=MatchDecision.UNKNOWN,
            decision_reason="The top-two score margin is below the provisional threshold.",
            unknown_reason=UnknownReason.AMBIGUOUS_MARGIN,
            **result_fields,
        )
    if (
        best.evidence.conflicting_evidence
        and _conflict_ratio(best.evidence) >= conflict_contribution_ratio
    ):
        return MatchResult(
            decision=MatchDecision.UNKNOWN,
            decision_reason=(
                "Conflicting features dominate the best candidate's weighted residual."
            ),
            unknown_reason=UnknownReason.CONFLICTING_EVIDENCE,
            **result_fields,
        )
    return MatchResult(
        decision=MatchDecision.MATCHED,
        accepted_label=best.fingerprint.bottleneck_label,
        decision_reason="The best compatible response exceeds all provisional thresholds.",
        **result_fields,
    )


__all__ = [
    "DEFAULT_CONFLICT_CONTRIBUTION_RATIO",
    "match_observation",
]
