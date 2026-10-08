"""Strict v2 comparison evidence and reconstructable conservative match records."""

import math
from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Literal

from pydantic import (
    Field,
    FieldSerializationInfo,
    field_serializer,
    field_validator,
    model_validator,
)

from ..analytical.compatibility import COMPATIBILITY_CODES
from ..analytical.decisions import decision_payload
from ..analytical.policy_release import canonical_payload_bytes, payload_hash
from ..analytical.scoring import comparison_payload
from ..json_io import MAX_CONTRACT_JSON_BYTES
from .analytical_response_v2 import AnalyticalResponseV2
from .common import (
    FiniteFloat,
    NonEmptyStr,
    NonNegativeFiniteFloat,
    PositiveFiniteFloat,
    UnitInterval,
)
from .fingerprint_v2 import BottleneckLabelV2
from .measurement import MetricName
from .v2_common import ContentHash, V2Model

MATCH_RESULT_V2_SCHEMA_VERSION = "match-result-v2"
CandidateRejectionCodeV2 = Literal[
    "query_invalid",
    "validation_status",
    "registry_mismatch",
    "policy_mismatch",
    "provenance_mismatch",
    "capture_method_mismatch",
    "clock_meaning_mismatch",
    "context_mismatch",
    "probe_mismatch",
    "settings_mismatch",
    "shared_feature_count",
    "feature_coverage",
]
UnknownReasonV2 = Literal[
    "invalid_response",
    "no_fingerprints",
    "no_compatible_fingerprints",
    "insufficient_features",
    "weak_match",
    "ambiguous_margin",
    "conflicting_evidence",
]


class RepositoryReferenceV2(V2Model):
    fingerprint_id: NonEmptyStr
    content_hash: ContentHash


class AnalyticalFeatureEvidenceV2(V2Model):
    query_value: FiniteFloat
    reference_value: FiniteFloat
    residual: FiniteFloat
    weight: PositiveFiniteFloat
    weighted_squared_residual: NonNegativeFiniteFloat
    classification: Literal["supporting", "conflicting"]


class CandidateComparisonV2(V2Model):
    fingerprint_id: NonEmptyStr
    fingerprint_content_hash: ContentHash
    bottleneck_label: BottleneckLabelV2
    reference_vector: Annotated[Mapping[MetricName, FiniteFloat], Field(max_length=22)]
    shared_features: Annotated[tuple[MetricName, ...], Field(max_length=22)]
    excluded_features: Annotated[
        Mapping[MetricName, tuple[Literal["query_excluded", "reference_excluded"], ...]],
        Field(max_length=22),
    ]
    shared_weight: PositiveFiniteFloat
    feature_coverage: UnitInterval
    distance: NonNegativeFiniteFloat
    match_strength: UnitInterval
    conflict_contribution: UnitInterval
    evidence: Annotated[Mapping[MetricName, AnalyticalFeatureEvidenceV2], Field(max_length=22)]

    @field_validator("reference_vector", "excluded_features", "evidence", mode="after")
    @classmethod
    def freeze_maps(cls, value):
        return MappingProxyType(dict(sorted(value.items())))

    @field_serializer("reference_vector", "excluded_features", "evidence")
    def serialize_maps(self, value, info: FieldSerializationInfo):
        return {
            key: item.model_dump(mode=info.mode, by_alias=info.by_alias)
            if isinstance(item, V2Model)
            else item
            for key, item in value.items()
        }


class RankedCandidateV2(V2Model):
    fingerprint_id: NonEmptyStr
    bottleneck_label: BottleneckLabelV2
    distance: NonNegativeFiniteFloat
    match_strength: UnitInterval


def _calculations_agree(actual, expected):
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            _calculations_agree(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, (list, tuple)):
        return len(actual) == len(expected) and all(
            _calculations_agree(a, b) for a, b in zip(actual, expected, strict=True)
        )
    if isinstance(expected, float):
        return actual is not None and math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
    return actual == expected


class MatchResultV2(V2Model):
    schema_version: Literal["match-result-v2"]
    contract_version: Literal["2.0.0"]
    match_id: NonEmptyStr
    query_response: AnalyticalResponseV2
    repository_references: Annotated[tuple[RepositoryReferenceV2, ...], Field(max_length=128)]
    candidate_rejections: Annotated[
        Mapping[NonEmptyStr, tuple[CandidateRejectionCodeV2, ...]], Field(max_length=128)
    ]
    comparisons: Annotated[Mapping[NonEmptyStr, CandidateComparisonV2], Field(max_length=128)]
    ranked_candidates: Annotated[tuple[RankedCandidateV2, ...], Field(max_length=5)]
    decision: Literal["matched", "unknown"]
    accepted_label: BottleneckLabelV2 | None
    unknown_reason: UnknownReasonV2 | None
    match_strength: UnitInterval | None
    score_margin: UnitInterval | None
    notice_code: Literal["software_similarity_not_causal_confidence"]

    @field_validator("candidate_rejections", "comparisons", mode="after")
    @classmethod
    def freeze_maps(cls, value):
        return MappingProxyType(dict(sorted(value.items())))

    @field_serializer("candidate_rejections", "comparisons")
    def serialize_maps(self, value, info: FieldSerializationInfo):
        return {
            key: item.model_dump(mode=info.mode, by_alias=info.by_alias)
            if isinstance(item, V2Model)
            else item
            for key, item in value.items()
        }

    @model_validator(mode="after")
    def validate_match(self):
        query = self.query_response
        ids = [reference.fingerprint_id for reference in self.repository_references]
        if ids != sorted(set(ids)):
            raise ValueError("repository references require sorted unique identities")
        if set(self.comparisons) & set(self.candidate_rejections) or (
            set(self.comparisons) | set(self.candidate_rejections) != set(ids)
        ):
            raise ValueError("comparisons and rejections must partition repository references")
        references = [
            reference.model_dump(mode="json", by_alias=True)
            for reference in self.repository_references
        ]
        digest = payload_hash(
            {
                "queryResponseId": query.response_id,
                "policyHash": query.policy.content_hash,
                "repositoryReferences": references,
            }
        )
        if self.match_id != "match-v2-" + digest[7:]:
            raise ValueError(
                "match identity must derive from query, policy and repository references"
            )
        for codes in self.candidate_rejections.values():
            allowed = (
                ("query_invalid",)
                if not query.is_valid
                else (
                    ("shared_feature_count", "feature_coverage")
                    if all(code in {"shared_feature_count", "feature_coverage"} for code in codes)
                    else COMPATIBILITY_CODES
                )
            )
            if not codes or tuple(code for code in allowed if code in codes) != codes:
                raise ValueError("candidate rejection codes must follow their closed ordered stage")
        if not query.is_valid and (
            self.comparisons
            or any(codes != ("query_invalid",) for codes in self.candidate_rejections.values())
        ):
            raise ValueError("invalid query requires every candidate to be rejected")
        hashes = {
            reference.fingerprint_id: reference.content_hash
            for reference in self.repository_references
        }
        reconstructed = {}
        for key, comparison in self.comparisons.items():
            if (
                key != comparison.fingerprint_id
                or comparison.fingerprint_content_hash != hashes[key]
            ):
                raise ValueError("comparison identity/hash must agree with repository references")
            expected = comparison_payload(
                query, key, hashes[key], comparison.bottleneck_label, comparison.reference_vector
            )
            for name, evidence in comparison.evidence.items():
                if name not in expected["evidence"] or any(
                    getattr(evidence, field) != expected["evidence"][name][alias]
                    for field, alias in (
                        ("query_value", "queryValue"),
                        ("reference_value", "referenceValue"),
                        ("weight", "weight"),
                    )
                ):
                    raise ValueError(
                        "evidence values and weights must equal retained vectors/policy"
                    )
            if not _calculations_agree(comparison.model_dump(mode="json", by_alias=True), expected):
                raise ValueError("comparison calculations/evidence must reconstruct")
            reconstructed[key] = expected
        expected = decision_payload(query, references, self.candidate_rejections, reconstructed)
        actual = self.model_dump(mode="json", by_alias=True)
        if not _calculations_agree({key: actual[key] for key in expected}, expected):
            raise ValueError("ranking and conservative decision must reconstruct")
        if len(canonical_payload_bytes(actual)) > MAX_CONTRACT_JSON_BYTES:
            raise ValueError("analytical match output exceeds the 10 MiB bound")
        return self
