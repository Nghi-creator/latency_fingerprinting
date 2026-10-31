"""Conservative matched-versus-unknown result construction."""

from __future__ import annotations

import math
from collections.abc import Sequence

from ..models import (
    CompatibilityResult,
    MatchDecision,
    MatchResult,
    MatchThresholds,
    RankedCandidate,
    UnknownReason,
)
from .scoring import ScoredCandidate


def _unique_messages(messages: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(messages))


def unranked_unknown(
    *,
    reason: UnknownReason,
    decision_reason: str,
    compatibility: CompatibilityResult,
    thresholds: MatchThresholds,
    warnings: Sequence[str],
    shared_feature_count: int = 0,
    feature_coverage: float = 0.0,
    missing_features: list[str] | None = None,
) -> MatchResult:
    """Build an unknown result for a request that cannot be ranked."""

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


def _conflict_ratio(candidate: ScoredCandidate) -> float:
    evidence = candidate.evidence
    if evidence.weighted_squared_residual_sum == 0:
        return 0.0
    conflict_sum = math.fsum(
        item.weighted_squared_residual for item in evidence.conflicting_evidence
    )
    return conflict_sum / evidence.weighted_squared_residual_sum


def decide_ranked_match(
    scored: tuple[ScoredCandidate, ...],
    *,
    compatibility: CompatibilityResult,
    thresholds: MatchThresholds,
    warnings: Sequence[str],
    conflict_contribution_ratio: float,
) -> MatchResult:
    """Apply final strength, margin, and conflicting-evidence policies."""

    if not scored:
        raise ValueError("decide_ranked_match requires at least one scored candidate")
    updated_warnings = list(warnings)
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
        updated_warnings.append(
            "Best candidate comparison excluded rejected query features: "
            + ", ".join(best.evidence.rejected_features)
        )
    if best.evidence.ignored_evidence:
        updated_warnings.append(
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
        "warnings": _unique_messages(updated_warnings),
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
    if best.evidence.conflicting_evidence and _conflict_ratio(best) >= conflict_contribution_ratio:
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


__all__ = ["decide_ranked_match", "unranked_unknown"]
