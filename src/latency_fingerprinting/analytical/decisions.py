"""Deterministic ranking and ordered conservative v2 decisions."""


def decision_payload(query, references, rejections, comparisons):
    ranked = sorted(
        comparisons.values(), key=lambda item: (item["distance"], item["fingerprintId"])
    )
    best = ranked[0] if ranked else None
    strength = best["matchStrength"] if best else None
    margin = strength - ranked[1]["matchStrength"] if len(ranked) > 1 else None
    policy = query.policy
    if not query.is_valid:
        reason = "invalid_response"
    elif not references:
        reason = "no_fingerprints"
    elif not ranked:
        reason = (
            "insufficient_features"
            if any(
                codes
                and all(code in {"shared_feature_count", "feature_coverage"} for code in codes)
                for codes in rejections.values()
            )
            else "no_compatible_fingerprints"
        )
    elif strength < policy.decision.minimum_match_strength:
        reason = "weak_match"
    elif margin is not None and margin < policy.decision.minimum_score_margin:
        reason = "ambiguous_margin"
    elif best["conflictContribution"] >= policy.decision.maximum_conflict_contribution:
        reason = "conflicting_evidence"
    else:
        reason = None
    return {
        "rankedCandidates": [
            {
                key: candidate[key]
                for key in ("fingerprintId", "bottleneckLabel", "distance", "matchStrength")
            }
            for candidate in ranked[: policy.maximum_ranked_candidates]
        ],
        "decision": "unknown" if reason else "matched",
        "acceptedLabel": None if reason else best["bottleneckLabel"],
        "unknownReason": reason,
        "matchStrength": strength,
        "scoreMargin": margin,
    }
