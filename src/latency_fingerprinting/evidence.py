"""Per-feature evidence calculated from normalized response vectors."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .models import FeatureEvidence, Fingerprint, NormalizedResponse

DEFAULT_SUPPORT_RESIDUAL_THRESHOLD = 0.25


class EvidenceError(ValueError):
    """Raised when evidence cannot be calculated from the supplied records."""


@dataclass(frozen=True, slots=True)
class CandidateEvidence:
    """Auditable feature intersection and distance inputs for one candidate."""

    fingerprint_id: str
    evidence: tuple[FeatureEvidence, ...]
    supporting_evidence: tuple[FeatureEvidence, ...]
    conflicting_evidence: tuple[FeatureEvidence, ...]
    ignored_evidence: tuple[FeatureEvidence, ...]
    missing_features: tuple[str, ...]
    rejected_features: tuple[str, ...]
    shared_feature_count: int
    feature_coverage: float
    total_weight: float
    weighted_squared_residual_sum: float
    distance: float | None


def build_candidate_evidence(
    query: NormalizedResponse,
    candidate: Fingerprint,
    *,
    support_residual_threshold: float = DEFAULT_SUPPORT_RESIDUAL_THRESHOLD,
) -> CandidateEvidence:
    """Calculate deterministic evidence and weighted distance for a candidate.

    Positive-weight features with an absolute normalized residual at or below
    the provisional threshold are supporting evidence. Larger residuals are
    conflicting evidence. Zero-weight features are retained as ignored audit
    entries and do not influence distance.
    """

    if not math.isfinite(support_residual_threshold) or support_residual_threshold < 0:
        raise ValueError("support_residual_threshold must be finite and non-negative")
    if not query.is_valid:
        raise EvidenceError("cannot build candidate evidence from an invalid query response")
    if not candidate.normalized_response.is_valid:
        raise EvidenceError("cannot build evidence from an invalid candidate fingerprint")

    query_features = set(query.features)
    candidate_features = set(candidate.normalized_response.features)
    shared_features = tuple(sorted(query_features & candidate_features))
    rejected_features = tuple(sorted(candidate_features & set(query.rejected_features)))
    missing_features = tuple(
        sorted(candidate_features - set(shared_features) - set(rejected_features))
    )

    all_evidence: list[FeatureEvidence] = []
    supporting: list[FeatureEvidence] = []
    conflicting: list[FeatureEvidence] = []
    ignored: list[FeatureEvidence] = []
    for feature in shared_features:
        observed_value = query.features[feature].value
        candidate_value = candidate.normalized_response.features[feature].value
        weight = candidate.feature_weights[feature]
        residual = observed_value - candidate_value
        item = FeatureEvidence(
            feature=feature,
            observed_value=observed_value,
            candidate_value=candidate_value,
            residual=residual,
            weight=weight,
            weighted_squared_residual=weight * residual**2,
        )
        all_evidence.append(item)
        if weight == 0:
            ignored.append(item)
        elif abs(residual) <= support_residual_threshold:
            supporting.append(item)
        else:
            conflicting.append(item)

    total_weight = sum(item.weight for item in all_evidence)
    weighted_squared_residual_sum = sum(item.weighted_squared_residual for item in all_evidence)
    distance = math.sqrt(weighted_squared_residual_sum / total_weight) if total_weight > 0 else None
    feature_coverage = len(shared_features) / len(candidate_features) if candidate_features else 0.0
    return CandidateEvidence(
        fingerprint_id=candidate.fingerprint_id,
        evidence=tuple(all_evidence),
        supporting_evidence=tuple(supporting),
        conflicting_evidence=tuple(conflicting),
        ignored_evidence=tuple(ignored),
        missing_features=missing_features,
        rejected_features=rejected_features,
        shared_feature_count=len(shared_features),
        feature_coverage=feature_coverage,
        total_weight=total_weight,
        weighted_squared_residual_sum=weighted_squared_residual_sum,
        distance=distance,
    )


__all__ = [
    "DEFAULT_SUPPORT_RESIDUAL_THRESHOLD",
    "CandidateEvidence",
    "EvidenceError",
    "build_candidate_evidence",
]
