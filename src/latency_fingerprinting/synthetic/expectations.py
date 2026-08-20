"""Expected matcher outputs for the deterministic synthetic corpus."""

from __future__ import annotations

import math
from collections.abc import Mapping

from ..models import (
    CompatibilityResult,
    MatchDecision,
    MatchResult,
    MatchThresholds,
    ObservationRecord,
    RankedCandidate,
    UnknownReason,
)
from .definitions import (
    FEATURE_BASELINES,
    QUERY_EXPECTATIONS,
    QUERY_VECTORS,
    REFERENCE_VECTORS,
)


def _candidate_scores(query_vector: Mapping[str, float]) -> list[RankedCandidate]:
    candidates: list[RankedCandidate] = []
    for label, candidate_vector in REFERENCE_VECTORS.items():
        squared_residuals = [
            (query_vector[feature] - candidate_vector[feature]) ** 2
            for feature in sorted(query_vector)
        ]
        # Keep generated fixtures stable across Python versions. Python 3.12
        # changed ordinary float summation, whereas ``fsum`` has the accurate
        # reduction semantics required for persisted regression artifacts.
        distance = math.sqrt(math.fsum(squared_residuals) / len(squared_residuals))
        candidates.append(
            RankedCandidate(
                fingerprint_id=f"fingerprint-{label}-v1",
                bottleneck_label=label,
                distance=distance,
                match_strength=1 / (1 + distance),
            )
        )
    return sorted(
        candidates, key=lambda candidate: (-candidate.match_strength, candidate.fingerprint_id)
    )


def expected_match_result(case_name: str, observation: ObservationRecord) -> MatchResult:
    expectation = QUERY_EXPECTATIONS[case_name]
    compatibility_group = observation.context.compatibility_group
    if expectation.unknown_reason is UnknownReason.INCOMPATIBLE_CONTEXT:
        return MatchResult(
            decision=MatchDecision.UNKNOWN,
            shared_feature_count=0,
            feature_coverage=0,
            compatibility=CompatibilityResult(
                is_compatible=False,
                compatibility_group=compatibility_group,
                rejected_fingerprints={
                    f"fingerprint-{label}-v1": "compatibility group mismatch"
                    for label in REFERENCE_VECTORS
                },
            ),
            decision_reason="No fingerprint belongs to the query compatibility group.",
            unknown_reason=UnknownReason.INCOMPATIBLE_CONTEXT,
        )

    candidates = _candidate_scores(QUERY_VECTORS[case_name])
    score_margin = candidates[0].match_strength - candidates[1].match_strength
    return MatchResult(
        decision=expectation.decision,
        accepted_label=expectation.label,
        match_strength=candidates[0].match_strength,
        score_margin=score_margin,
        ranked_candidates=candidates,
        shared_feature_count=len(FEATURE_BASELINES),
        feature_coverage=1.0,
        compatibility=CompatibilityResult(
            is_compatible=True,
            compatibility_group=compatibility_group,
            compatible_fingerprint_ids=[candidate.fingerprint_id for candidate in candidates],
        ),
        thresholds=MatchThresholds(),
        decision_reason=(
            "Synthetic expected match for matcher regression."
            if expectation.decision is MatchDecision.MATCHED
            else "Synthetic expected unknown decision for matcher regression."
        ),
        unknown_reason=expectation.unknown_reason,
        warnings=["Expected software-test result; not measured diagnostic evidence."],
    )


__all__ = ["expected_match_result"]
