"""Public orchestration for conservative weighted-distance matching."""

from __future__ import annotations

import math

from .evidence import DEFAULT_SUPPORT_RESIDUAL_THRESHOLD
from .fingerprints import FingerprintRepository
from .matching.compatibility import filter_compatible_fingerprints
from .matching.decision import decide_ranked_match, unranked_unknown
from .matching.scoring import best_availability, score_candidates
from .models import MatchResult, MatchThresholds, ObservationRecord, UnknownReason
from .validation import SUPPORTED_P0_PROBE_TYPES

DEFAULT_CONFLICT_CONTRIBUTION_RATIO = 0.50


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

    candidates, compatibility, repository_warnings = filter_compatible_fingerprints(
        query, repository
    )
    warnings = repository_warnings + list(query.normalized_response.warnings)

    if query.probe.probe_type not in SUPPORTED_P0_PROBE_TYPES:
        return unranked_unknown(
            reason=UnknownReason.UNSUPPORTED_PROBE,
            decision_reason=f"Probe type {query.probe.probe_type!r} is not supported by P0.",
            compatibility=compatibility,
            thresholds=thresholds,
            warnings=warnings,
        )

    if not candidates:
        return unranked_unknown(
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
        return unranked_unknown(
            reason=UnknownReason.INVALID_OBSERVATION,
            decision_reason="The query response is invalid and cannot be scored.",
            compatibility=compatibility,
            thresholds=thresholds,
            warnings=warnings + query.normalized_response.invalid_reasons,
            missing_features=list(query.normalized_response.missing_features),
        )

    scoring = score_candidates(
        query.normalized_response,
        candidates,
        thresholds,
        support_residual_threshold=support_residual_threshold,
    )
    warnings.extend(scoring.warnings)
    if not scoring.eligible:
        best_available = best_availability(scoring.evidence)
        missing = (
            sorted(set(best_available.missing_features) | set(best_available.rejected_features))
            if best_available is not None
            else []
        )
        return unranked_unknown(
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

    if not scoring.scored:
        best_available = best_availability(scoring.eligible)
        assert best_available is not None
        return unranked_unknown(
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

    return decide_ranked_match(
        scoring.scored,
        compatibility=compatibility,
        thresholds=thresholds,
        warnings=warnings,
        conflict_contribution_ratio=conflict_contribution_ratio,
    )


__all__ = [
    "DEFAULT_CONFLICT_CONTRIBUTION_RATIO",
    "match_observation",
]
