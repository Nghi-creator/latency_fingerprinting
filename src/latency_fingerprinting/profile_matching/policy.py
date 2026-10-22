"""Closed approved-policy schema; self-rehashing does not approve new parameters."""

from typing import Annotated, Literal

from pydantic import Field, StrictBool, model_validator

from ..calibration.contracts import check_json_size
from ..profiles.contracts import FeatureName, Finite
from .contracts import MatchModel
from .policy_release import approved_policy_payload


class ProfileMatchPolicyEvaluation(MatchModel):
    accuracy: Literal["correct_groups_over_all_known_truth_groups"]
    automatic_tuning: StrictBool
    fold_candidate_inventory: Literal["original_training_keys"]
    group_prediction: Literal["unanimous_nonduplicate_response_decisions"]
    modes: Annotated[
        tuple[Literal["validation", "final_test", "leave_training_group_out"], ...],
        Field(max_length=3),
    ]
    refit: Literal["remove_whole_component_then_n7_statistics"]
    trust_promotion: StrictBool
    truth_coverage: Literal["known_truth_groups_over_all_response_groups"]
    truth_invalid_reasons: Annotated[
        tuple[Literal["label_unverified", "effect_unverified", "binding_unverified"], ...],
        Field(max_length=3),
    ]
    unknown_rate: Literal["unknown_groups_over_all_response_groups"]
    voting_unit: Literal["one_n6_source_group"]


class ProfileMatchPolicyGatesMinimumCommonCoverage(MatchModel):
    denominator: Annotated[int, Field(strict=True, ge=0, le=10485760)]
    numerator: Annotated[int, Field(strict=True, ge=0, le=10485760)]


class ProfileMatchPolicyGates(MatchModel):
    maximum_best_distance: Finite
    minimum_absolute_margin: Finite
    minimum_common_coverage: ProfileMatchPolicyGatesMinimumCommonCoverage
    minimum_common_features: Annotated[int, Field(strict=True, ge=0, le=10485760)]
    minimum_scored_labels: Annotated[int, Field(strict=True, ge=0, le=10485760)]


class ProfileMatchPolicyLimits(MatchModel):
    maximum_candidates: Annotated[int, Field(strict=True, ge=0, le=10485760)]
    maximum_entries: Annotated[int, Field(strict=True, ge=0, le=10485760)]
    maximum_features: Annotated[int, Field(strict=True, ge=0, le=10485760)]
    maximum_json_bytes: Annotated[int, Field(strict=True, ge=0, le=10485760)]
    maximum_json_depth: Annotated[int, Field(strict=True, ge=0, le=10485760)]
    maximum_refits: Annotated[int, Field(strict=True, ge=0, le=10485760)]
    maximum_total_candidate_rows: Annotated[int, Field(strict=True, ge=0, le=10485760)]
    maximum_total_feature_rows: Annotated[int, Field(strict=True, ge=0, le=10485760)]
    maximum_total_refit_candidates: Annotated[int, Field(strict=True, ge=0, le=10485760)]
    maximum_total_refit_entry_references: Annotated[int, Field(strict=True, ge=0, le=10485760)]
    maximum_total_refit_group_values: Annotated[int, Field(strict=True, ge=0, le=10485760)]


class ProfileMatchPolicyRegistry(MatchModel):
    content_hash: Literal["sha256:50329d193303c271194b28e9164ae8627dd257d7620174c5ab136ba209864884"]
    registry_version: Literal["latency-metrics-v2.0.0"]


class ProfileMatchPolicyScoring(MatchModel):
    absolute_deviation: Literal["exact_binary64_difference_round_once"]
    computed_zero: Literal["positive_zero"]
    distance: Literal["positive_weight_mean_absolute_standardized_deviation"]
    finite_arithmetic: Literal["reject_unrepresentable"]
    imputation: None
    label_aggregation: Literal["one_candidate_per_exact_partition_label"]
    margin: Literal["rounded_score_difference_round_once"]
    nonzero_to_zero: Literal["reject"]
    rank_order: Annotated[
        tuple[Literal["distance", "label", "profile_id"], ...], Field(max_length=3)
    ]
    scale: Literal["n7_raw_mad"]
    scale_floor: None
    shared_features: Literal["intersection_across_all_prequalified_labels"]
    standardized_deviation: Literal["exact_binary64_ratio_round_once"]
    weighted_mean: Literal["exact_binary64_weighted_sum_and_division_round_once"]


class ProfileMatchPolicySource(MatchModel):
    compatibility: Literal["n6_exact_partition_v1"]
    exclude_duplicates: StrictBool
    label_use: Literal["evaluation_truth_only"]
    overlap: Literal["whole_n6_connected_component_and_receipts"]
    query_roles: Annotated[tuple[Literal["validation", "final_test"], ...], Field(max_length=2)]
    require_n6_eligible: StrictBool
    scope: Literal["one_fresh_n6_dataset"]
    snapshot_selection: Literal["one_explicit_revision"]
    snapshot_state: Literal["provisional"]


class ProfileMatchPolicy(MatchModel):
    calibration_method_release: Literal["n6-calibration-evidence-v1"]
    content_hash: Literal["sha256:b296df5c172d19e9470f64b3546fcb7af54c6623dd5951bc0c652a94e87b95db"]
    evaluation: ProfileMatchPolicyEvaluation
    feature_names: Annotated[tuple[FeatureName, ...], Field(min_length=22, max_length=22)]
    gates: ProfileMatchPolicyGates
    limits: ProfileMatchPolicyLimits
    method_release: Literal["n8-profile-matching-v1"]
    operating_mode: Literal["offline_provisional"]
    parameter_provenance: Literal["software_provisional"]
    policy_id: Literal[
        "profile-match-policy-b296df5c172d19e9470f64b3546fcb7af54c6623dd5951bc0c652a94e87b95db"
    ]
    policy_version: Literal["1.0.0"]
    profile_method_release: Literal["n7-profile-statistics-v1"]
    profile_policy_hash: Literal[
        "sha256:8e805ffb205e7808559c0eac30d286f3395f006c358b100aef1e95fc705ec641"
    ]
    registry: ProfileMatchPolicyRegistry
    response_policy_hash: Literal[
        "sha256:96457b318cc714f3d9d0d63a35b12548f6e030b10057b2c8e5a3a77e352fe1af"
    ]
    schema_version: Literal["profile-match-policy-v1"]
    scoring: ProfileMatchPolicyScoring
    source: ProfileMatchPolicySource

    @model_validator(mode="after")
    def approved(self):
        if self.model_dump(mode="json") != approved_policy_payload():
            raise ValueError("profile match policy is not an approved release")
        check_json_size(self)
        return self
