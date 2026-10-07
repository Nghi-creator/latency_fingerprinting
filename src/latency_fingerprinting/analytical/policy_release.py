"""Trusted provisional feature-policy release, independent of supplied JSON paths."""

import hashlib
import json

POLICY_CONTENT_HASH = "sha256:96457b318cc714f3d9d0d63a35b12548f6e030b10057b2c8e5a3a77e352fe1af"


def canonical_payload_bytes(payload: dict) -> bytes:
    return (
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode("utf-8")


def payload_hash(payload: dict) -> str:
    return "sha256:" + hashlib.sha256(canonical_payload_bytes(payload)).hexdigest()


def approved_policy_payload() -> dict:
    # Resolve lazily: models -> policy -> registry -> schemas must not form an
    # import cycle. The registry renderer verifies its frozen release first.
    from ..models.v2_common import REGISTRY_CONTENT_HASH, trusted_registry

    registry = trusted_registry()
    features = {
        definition.name: {
            "semanticVersion": definition.semantic_version,
            "source": definition.source.value,
            "unit": definition.canonical_unit.value,
            "aggregation": definition.primary_aggregation.value,
            "epsilon": 1.0,
            "weight": 1.0,
            "clipMinimum": None,
            "clipMaximum": None,
            "minimumCoverage": 1.0,
            "minimumUsableSamples": 2,
            "minimumAcceptedIntervals": 1,
            "allowedStatuses": ["complete"],
        }
        for definition in registry.definitions
        if definition.primary_aggregation != "window_total"
        and definition.name != "encoder.pipeline_delay_proxy_ms"
    }
    payload = {
        "schemaVersion": "feature-policy-v1",
        "contractVersion": "1.0.0",
        "policyId": "n3-offline-conservative",
        "policyVersion": "1.0.0",
        "parameterProvenance": "software_provisional",
        "registry": {
            "registryVersion": registry.registry_version,
            "contentHash": REGISTRY_CONTENT_HASH,
        },
        "responseMethod": "signed_relative_primary_v1",
        "deltaDirection": "relief_minus_degraded",
        "normalizationReference": "absolute_degraded_with_epsilon_floor",
        "confounderHandling": "reject_pair",
        "compatibilityMethod": "structural_context_probe_v1",
        "distanceMethod": "weighted_rms_v1",
        "strengthMethod": "inverse_one_plus_distance_v1",
        "repositoryFailurePolicy": "error",
        "maximumRankedCandidates": 5,
        "decision": {
            "minimumSharedFeatures": 4,
            "minimumFeatureCoverage": 0.75,
            "minimumMatchStrength": 0.8,
            "minimumScoreMargin": 0.1,
            "conflictingResidualThreshold": 0.5,
            "maximumConflictContribution": 0.5,
        },
        "features": features,
    }
    if payload_hash(payload) != POLICY_CONTENT_HASH:
        raise ValueError("trusted feature policy changed without a reviewed release")
    return {**payload, "contentHash": POLICY_CONTENT_HASH}
