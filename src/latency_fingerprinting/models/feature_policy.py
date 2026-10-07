"""Immutable N3 policy with exact approved content and registry binding."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal

from pydantic import FieldSerializationInfo, field_serializer, field_validator, model_validator

from ..analytical.policy_release import approved_policy_payload, payload_hash
from .common import FiniteFloat, PositiveFiniteFloat, PositiveInt, UnitInterval
from .measurement import AggregationKind, MetricName, MetricSource, MetricUnit, SemanticVersion
from .v2_common import ContentHash, RegistryReference, V2Model

FEATURE_POLICY_SCHEMA_VERSION = "feature-policy-v1"


class FeaturePolicyParameterV1(V2Model):
    semantic_version: SemanticVersion
    source: MetricSource
    unit: MetricUnit
    aggregation: AggregationKind
    epsilon: PositiveFiniteFloat
    weight: PositiveFiniteFloat
    clip_minimum: FiniteFloat | None
    clip_maximum: FiniteFloat | None
    minimum_coverage: UnitInterval
    minimum_usable_samples: PositiveInt
    minimum_accepted_intervals: PositiveInt
    allowed_statuses: tuple[Literal["complete"], ...]


class AnalyticalDecisionPolicyV1(V2Model):
    minimum_shared_features: PositiveInt
    minimum_feature_coverage: UnitInterval
    minimum_match_strength: UnitInterval
    minimum_score_margin: UnitInterval
    conflicting_residual_threshold: PositiveFiniteFloat
    maximum_conflict_contribution: UnitInterval


class FeaturePolicyV1(V2Model):
    schema_version: Literal["feature-policy-v1"]
    contract_version: Literal["1.0.0"]
    policy_id: Literal["n3-offline-conservative"]
    policy_version: Literal["1.0.0"]
    content_hash: ContentHash
    parameter_provenance: Literal["software_provisional"]
    registry: RegistryReference
    response_method: Literal["signed_relative_primary_v1"]
    delta_direction: Literal["relief_minus_degraded"]
    normalization_reference: Literal["absolute_degraded_with_epsilon_floor"]
    confounder_handling: Literal["reject_pair"]
    compatibility_method: Literal["structural_context_probe_v1"]
    distance_method: Literal["weighted_rms_v1"]
    strength_method: Literal["inverse_one_plus_distance_v1"]
    repository_failure_policy: Literal["error"]
    maximum_ranked_candidates: PositiveInt
    decision: AnalyticalDecisionPolicyV1
    features: Mapping[MetricName, FeaturePolicyParameterV1]

    @field_validator("features", mode="after")
    @classmethod
    def freeze_features(cls, value):
        return MappingProxyType(dict(sorted(value.items())))

    @field_serializer("features")
    def serialize_features(self, value, info: FieldSerializationInfo):
        return {
            key: item.model_dump(mode=info.mode, by_alias=info.by_alias)
            for key, item in value.items()
        }

    @model_validator(mode="after")
    def validate_release(self):
        actual = self.model_dump(mode="json", by_alias=True)
        hash_input = {key: value for key, value in actual.items() if key != "contentHash"}
        if payload_hash(hash_input) != self.content_hash:
            raise ValueError("feature policy content hash disagrees with its canonical content")
        if actual != approved_policy_payload():
            raise ValueError("feature policy identity/content is not an approved release")
        return self
