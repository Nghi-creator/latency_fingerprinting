"""Exact approved policy models; self-rehashing altered policy is not approval."""

from typing import Annotated, Literal

from pydantic import Field, StrictBool, model_validator

from ..calibration.contracts import Count, Hash, check_json_size
from .contracts import FeatureName, Finite, PolicyID, ProfileModel
from .policy_release import approved_policy_payload


class Registry(ProfileModel):
    registry_version: Literal["latency-metrics-v2.0.0"]
    content_hash: Hash


class Threshold(ProfileModel):
    numerator: Count
    denominator: Count


class SelectionPolicy(ProfileModel):
    input_kind: Literal["response"]
    role: Literal["training"]
    require_n6_eligible: StrictBool
    exclude_duplicates: StrictBool
    mixed_group_labels: Literal["exclude_partition_group"]
    partition_method: Literal["n6_exact_partition_v1"]


class StatisticsPolicy(ProfileModel):
    within_group: Literal["median"]
    center: Literal["median"]
    dispersion: Literal["raw_mad"]
    even_median: Literal["exact_binary64_midpoint_round_once"]
    absolute_deviation: Literal["exact_binary64_difference_round_once"]
    empty_feature: Literal["unavailable"]
    zero_dispersion: Literal["exclude"]
    dispersion_floor: None
    nonzero_to_zero: Literal["reject"]
    finite_arithmetic: Literal["reject_unrepresentable"]
    computed_zero: Literal["positive_zero"]


class Gates(ProfileModel):
    minimum_training_groups: Count
    minimum_feature_groups: Count
    minimum_feature_availability: Threshold
    minimum_active_features: Count
    minimum_active_coverage: Threshold


class Weights(ProfileModel):
    supported: Finite
    excluded: Finite


class ProfilePolicy(ProfileModel):
    schema_version: Literal["profile-policy-v1"]
    method_release: Literal["n7-profile-statistics-v1"]
    policy_id: PolicyID
    content_hash: Hash
    policy_version: Literal["1.0.0"]
    parameter_provenance: Literal["software_provisional"]
    calibration_method_release: Literal["n6-calibration-evidence-v1"]
    registry: Registry
    response_policy_hash: Hash
    feature_names: Annotated[tuple[FeatureName, ...], Field(min_length=22, max_length=22)]
    selection: SelectionPolicy
    statistics: StatisticsPolicy
    gates: Gates
    weights: Weights

    @model_validator(mode="after")
    def approved(self):
        if self.model_dump(mode="json") != approved_policy_payload():
            raise ValueError("profile policy is not an approved release")
        check_json_size(self)
        return self
