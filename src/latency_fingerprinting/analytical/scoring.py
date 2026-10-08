"""Reconstructable finite weighted RMS scoring using the approved policy only."""

import math


def shared_feature_rejections(query, reference_vector):
    shared = sum(
        name in reference_vector and feature.state == "eligible"
        for name, feature in query.features.items()
    )
    decision = query.policy.decision
    return tuple(
        code
        for code, failed in (
            ("shared_feature_count", shared < decision.minimum_shared_features),
            (
                "feature_coverage",
                shared / len(query.policy.features) < decision.minimum_feature_coverage,
            ),
        )
        if failed
    )


def comparison_payload(query, fingerprint_id, content_hash, label, reference_vector):
    policy = query.policy
    if not set(reference_vector).issubset(policy.features):
        raise ValueError("reference vector contains non-policy features")
    if shared_feature_rejections(query, reference_vector):
        raise ValueError("comparison requires sufficient shared features")
    evidence, excluded = {}, {}
    for name, parameter in policy.features.items():
        feature = query.features[name]
        codes = tuple(
            code
            for code, failed in (
                ("query_excluded", feature.state != "eligible"),
                ("reference_excluded", name not in reference_vector),
            )
            if failed
        )
        if codes:
            excluded[name] = codes
            continue
        reference = reference_vector[name]
        residual = feature.normalized_value - reference
        squared = parameter.weight * residual * residual
        if not math.isfinite(residual) or not math.isfinite(squared):
            raise ValueError("analytical comparison exceeds the finite numeric range")
        evidence[name] = {
            "queryValue": feature.normalized_value,
            "referenceValue": reference,
            "residual": residual,
            "weight": parameter.weight,
            "weightedSquaredResidual": squared,
            "classification": "conflicting"
            if abs(residual) > (policy.decision.conflicting_residual_threshold)
            else "supporting",
        }
    try:
        shared_weight = math.fsum(item["weight"] for item in evidence.values())
        residual_sum = math.fsum(item["weightedSquaredResidual"] for item in evidence.values())
        conflicting_sum = math.fsum(
            item["weightedSquaredResidual"]
            for item in evidence.values()
            if item["classification"] == "conflicting"
        )
    except OverflowError as error:
        raise ValueError("analytical comparison exceeds the finite numeric range") from error
    if not math.isfinite(shared_weight) or shared_weight <= 0 or not math.isfinite(residual_sum):
        raise ValueError("analytical comparison requires finite positive usable weight")
    distance = math.sqrt(residual_sum / shared_weight)
    return {
        "fingerprintId": fingerprint_id,
        "fingerprintContentHash": content_hash,
        "bottleneckLabel": label,
        "referenceVector": dict(reference_vector),
        "sharedFeatures": tuple(evidence),
        "excludedFeatures": excluded,
        "sharedWeight": shared_weight,
        "featureCoverage": len(evidence) / len(policy.features),
        "distance": distance,
        "matchStrength": 1 / (1 + distance),
        "conflictContribution": conflicting_sum / residual_sum if residual_sum else 0.0,
        "evidence": evidence,
    }
