"""Tampering, reconstruction, resource bounds and repository authentication limits."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from latency_fingerprinting.analytical.matching import match_response_v2, verify_match_repository_v2
from latency_fingerprinting.analytical.repository import FingerprintRepositoryV2
from latency_fingerprinting.models import MatchResultV2
from latency_fingerprinting.pipeline import canonical_json

from .matching_cases import fingerprint, match, response


@pytest.mark.parametrize(
    "field,value",
    [
        ("matchId", "forged"),
        ("contractVersion", "1.0.0"),
        ("noticeCode", "confidence"),
        ("acceptedLabel", "forged"),
        ("unknownReason", "weak_match"),
        ("decision", "unknown"),
        ("matchStrength", True),
        ("matchStrength", 0.7),
        ("scoreMargin", 0.1),
        ("notes", "private"),
    ],
)
def test_tampered_root_fields_fail(field, value):
    payload = match(records=[fingerprint(normalized=-0.25)]).model_dump(mode="json", by_alias=True)
    payload[field] = value
    with pytest.raises(ValidationError):
        MatchResultV2.model_validate(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("distance", 0.1),
        ("sharedWeight", 1),
        ("featureCoverage", 0.5),
        ("matchStrength", 0.9),
        ("conflictContribution", 1),
        ("fingerprintId", "forged"),
        ("fingerprintContentHash", "sha256:" + "0" * 64),
        ("sharedFeatures", []),
        ("excludedFeatures", {}),
        ("evidence", {}),
    ],
)
def test_tampered_comparison_fails(field, value):
    result = match(response(excluded=["transport.jitter_ms"]), [fingerprint(normalized=-0.25)])
    payload = result.model_dump(mode="json", by_alias=True)
    comparison = next(iter(payload["comparisons"].values()))
    comparison[field] = value
    with pytest.raises(ValidationError):
        MatchResultV2.model_validate(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("queryValue", 0.1),
        ("referenceValue", 0.1),
        ("residual", 0.1),
        ("weight", 1.0000000000001),
        ("weightedSquaredResidual", 0),
        ("classification", "conflicting"),
        ("weight", True),
    ],
)
def test_tampered_feature_evidence_fails(field, value):
    payload = match(records=[fingerprint(normalized=-0.25)]).model_dump(mode="json", by_alias=True)
    evidence = next(iter(next(iter(payload["comparisons"].values()))["evidence"].values()))
    evidence[field] = value
    with pytest.raises(ValidationError):
        MatchResultV2.model_validate(payload)


def test_retained_vectors_cannot_authenticate_external_repository():
    record = fingerprint(normalized=-0.25)
    result = match(records=[record])
    payload = result.model_dump(mode="json", by_alias=True)
    payload["acceptedLabel"] = payload["rankedCandidates"][0]["bottleneckLabel"] = "other"
    next(iter(payload["comparisons"].values()))["bottleneckLabel"] = "other"
    structurally_valid = MatchResultV2.model_validate(payload)
    with pytest.raises(ValueError, match="full fingerprint repository"):
        verify_match_repository_v2(structurally_valid, FingerprintRepositoryV2((record,)))
    with pytest.raises(ValueError):
        verify_match_repository_v2(result, FingerprintRepositoryV2(()))


def test_immutable_deterministic_inputs_and_instance_revalidation():
    query, record = response(), fingerprint(normalized=-0.25)
    before = (canonical_json(query), canonical_json(record))
    result = match(query, [record])
    payload = result.model_dump(mode="json", by_alias=True)
    original = deepcopy(payload)
    parsed = MatchResultV2.model_validate(payload)
    assert original == payload and before == (canonical_json(query), canonical_json(record))
    with pytest.raises(TypeError):
        parsed.comparisons[record.fingerprint_id] = result.comparisons[record.fingerprint_id]
    with pytest.raises(TypeError):
        parsed.comparisons[record.fingerprint_id].evidence["transport.jitter_ms"] = None
    payload["comparisons"].clear()
    assert len(parsed.comparisons) == 1
    with pytest.raises(ValidationError):
        MatchResultV2.model_validate(parsed.model_copy(update={"match_strength": True}))
    with pytest.raises(ValidationError):
        match_response_v2(
            query,
            query.policy.model_copy(update={"maximum_ranked_candidates": True}),
            FingerprintRepositoryV2((record,)),
        )
    with pytest.raises(ValidationError):
        match(query, [record.model_copy(update={"provenance": "controlled_real"})])
    with pytest.raises(ValueError, match="duplicate"):
        match(query, [record, record])


def test_repository_and_output_bounds_are_enforced(monkeypatch):
    from latency_fingerprinting.models import match_v2

    record = fingerprint()
    with pytest.raises(ValueError, match="fingerprint limit"):
        match(records=[record] * 129)
    monkeypatch.setattr(match_v2, "MAX_CONTRACT_JSON_BYTES", 1)
    with pytest.raises(ValidationError, match="10 MiB"):
        match(records=[record])


@pytest.mark.parametrize(
    "kind",
    [
        "partition",
        "duplicate",
        "unsorted",
        "rejection_empty",
        "rejection_duplicate",
        "rejection_mixed",
        "query_valid_code",
        "rank_order",
        "ranking_omit",
        "vector_extra",
    ],
)
def test_partition_ordering_inventory_and_closed_rejection_stage(kind):
    records = [fingerprint(label="a"), fingerprint(label="b")]
    if kind.startswith("rejection") or kind == "query_valid_code":
        records = [fingerprint(status="unreviewed")]
    payload = match(records=records).model_dump(mode="json", by_alias=True)
    if kind == "partition":
        payload["comparisons"].clear()
    elif kind == "duplicate":
        payload["repositoryReferences"].append(payload["repositoryReferences"][0])
    elif kind == "unsorted":
        payload["repositoryReferences"].reverse()
    elif kind in ("rank_order", "ranking_omit"):
        if kind == "rank_order":
            payload["rankedCandidates"].reverse()
        else:
            payload["rankedCandidates"].pop()
    elif kind == "vector_extra":
        next(iter(payload["comparisons"].values()))["referenceVector"][
            "client.frames_decoded_window_total"
        ] = 0
    else:
        payload["candidateRejections"][records[0].fingerprint_id] = {
            "rejection_empty": [],
            "rejection_duplicate": ["validation_status", "validation_status"],
            "rejection_mixed": ["validation_status", "feature_coverage"],
            "query_valid_code": ["query_invalid"],
        }[kind]
    with pytest.raises(ValidationError):
        MatchResultV2.model_validate(payload)


def test_match_api_revalidates_query_instances():
    query = response()
    with pytest.raises(ValidationError):
        match(
            query.model_copy(
                update={"is_valid": True, "invalid_reason_codes": ("confounded_pair",)}
            )
        )
