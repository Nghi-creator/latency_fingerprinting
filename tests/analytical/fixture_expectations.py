"""Independent numerical expectations for N3 synthetic fixture release 1.0.0."""

import math
from pathlib import Path

# These values are authored from the field contract, not from matcher outputs.
MATCH_EXPECTATIONS = {
    "matched": (None, 1, 0.25, 0.8, None, 0.0),
    "invalid_response": ("invalid_response", 0, None, None, None, None),
    "no_fingerprints": ("no_fingerprints", 0, None, None, None, None),
    "no_compatible_fingerprints": ("no_compatible_fingerprints", 0, None, None, None, None),
    "insufficient_features": ("insufficient_features", 0, None, None, None, None),
    "weak_match": ("weak_match", 1, 0.3, 1 / 1.3, None, 0.0),
    "ambiguous_margin": ("ambiguous_margin", 2, 0.1, 1 / 1.1, 1 / 1.1 - 1 / 1.12, 0.0),
    "conflicting_evidence": (
        "conflicting_evidence",
        1,
        0.6 / math.sqrt(22),
        1 / (1 + 0.6 / math.sqrt(22)),
        None,
        1.0,
    ),
}


def _equal_number(actual, expected):
    return (
        actual is None
        if expected is None
        else actual is not None and math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
    )


def check_expectations(records):
    """Raise on wrong primary evidence/math/decision before approving snapshots."""
    query = records[Path("responses/complete.json")]
    if (
        not query.is_valid
        or len(query.features) != 22
        or any(
            feature.state != "eligible" or feature.normalized_value != 0
            for feature in query.features.values()
        )
    ):
        raise ValueError("complete synthetic response expectation failed")
    for name, primary in (
        ("transport.jitter_ms", 60),
        ("client.frames_decoded_rate_fps", 60),
        ("client.freeze_count_rate_per_min", 3600),
    ):
        feature = query.features[name]
        if (feature.degraded.primary_value, feature.relief.primary_value, feature.denominator) != (
            primary,
            primary,
            primary,
        ):
            raise ValueError("synthetic primary unit/rate expectation failed")
    partial = records[Path("responses/insufficient.json")]
    if not partial.is_valid or sum(f.state == "eligible" for f in partial.features.values()) != 16:
        raise ValueError("partial synthetic response expectation failed")
    invalid = records[Path("responses/confounded.json")]
    if (
        invalid.is_valid
        or invalid.invalid_reason_codes != ("confounded_pair",)
        or any(
            f.normalized_value is not None or f.exclusion_codes != ("confounded_pair",)
            for f in invalid.features.values()
        )
    ):
        raise ValueError("confounded synthetic response expectation failed")
    matched_reference = records[Path("references/matched/fingerprint.json")]
    if len(matched_reference.feature_vector) != 22 or any(
        not _equal_number(value, -0.25) for value in matched_reference.feature_vector.values()
    ):
        raise ValueError("synthetic reference vector expectation failed")
    for name, (reason, count, distance, strength, margin, conflict) in MATCH_EXPECTATIONS.items():
        result = records[Path("matches") / f"{name}.json"]
        if (
            result.unknown_reason != reason
            or len(result.comparisons) != count
            or result.decision != ("unknown" if reason else "matched")
            or result.accepted_label != (None if reason else "synthetic_reference")
            or not _equal_number(result.match_strength, strength)
            or not _equal_number(result.score_margin, margin)
        ):
            raise ValueError("synthetic match decision expectation failed")
        if count:
            best = result.comparisons[result.ranked_candidates[0].fingerprint_id]
            if (
                best.shared_weight != 22
                or best.feature_coverage != 1
                or not _equal_number(best.distance, distance)
                or not _equal_number(best.conflict_contribution, conflict)
            ):
                raise ValueError("synthetic match distance/conflict expectation failed")
        if name == "matched" and any(
            (
                e.query_value,
                e.reference_value,
                e.residual,
                e.weight,
                e.weighted_squared_residual,
                e.classification,
            )
            != (0, -0.25, 0.25, 1, 0.0625, "supporting")
            for e in best.evidence.values()
        ):
            raise ValueError("synthetic residual evidence expectation failed")
        if name == "insufficient_features" and tuple(result.candidate_rejections.values()) != (
            ("feature_coverage",),
        ):
            raise ValueError("synthetic shared coverage expectation failed")
    return None
