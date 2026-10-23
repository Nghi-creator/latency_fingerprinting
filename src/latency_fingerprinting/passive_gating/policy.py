"""Strict approved N9 policy; changed parameters cannot approve themselves."""

from typing import Annotated, Literal

from pydantic import Field, StrictBool, model_validator

from ..analytical.policy_release import canonical_payload_bytes
from ..calibration.contracts import check_json_size
from .contracts import GateModel, RootModel, Time
from .policy_release import approved_policy_payload


class PolicyBaselineMinimumAvailability(GateModel):
    denominator: Time
    numerator: Time


class PolicyBaseline(GateModel):
    center: Literal["median_of_group_medians"]
    center_strictly_positive: StrictBool
    confirmed_healthy_only: StrictBool
    minimum_availability: PolicyBaselineMinimumAvailability
    minimum_contributing_groups: Time
    minimum_groups: Time
    spread: Literal["raw_median_absolute_deviation"]
    training_only: StrictBool
    weighting: Literal["one_connected_source_group_one_vote"]
    zero_spread_allowed: StrictBool


class PolicyClock(GateModel):
    cross_domain_rebase: StrictBool
    expiration: Literal["explicit_same_stream_tick"]
    generation: Literal["externally_declared"]
    integral_milliseconds_only: StrictBool
    maximum_elapsed_ms: Time
    monotonic_guarantee: StrictBool


class PolicyEvaluation(GateModel):
    automatic_tuning: StrictBool
    empirically_calibrated: StrictBool
    live_execution: StrictBool
    trust_promotion: StrictBool


class PolicyGatesLowMaximumRatio(GateModel):
    denominator: Time
    numerator: Time


class PolicyGatesRecoveredMinimumRatio(GateModel):
    denominator: Time
    numerator: Time


class PolicyGates(GateModel):
    low_maximum_ratio: PolicyGatesLowMaximumRatio
    maximum_proposals: Time
    minimum_bad_duration_ms: Time
    minimum_bad_windows: Time
    minimum_good_duration_ms: Time
    minimum_good_windows: Time
    proposal_cooldown_ms: Time
    recovered_minimum_ratio: PolicyGatesRecoveredMinimumRatio
    stale_after_ms: Time


class PolicyLimits(GateModel):
    maximum_baseline_windows: Time
    maximum_depth: Time
    maximum_entries: Time
    maximum_events: Time
    maximum_group_entry_references: Time
    maximum_groups: Time
    maximum_replay_windows: Time
    maximum_root_bytes: Time
    maximum_strata: Time


class PolicyMetric(GateModel):
    canonical_unit: Literal["fps"]
    clock_basis: Literal["source_elapsed_ms"]
    kind: Literal["gauge"]
    name: Literal["client.received_fps"]
    primary_aggregation: Literal["median"]
    raw_fields: Annotated[tuple[Literal["fps"], ...], Field(min_length=1, max_length=1)]
    semantic_version: Literal["1.0.0"]
    source: Literal["browser_webrtc"]


class PolicyQuality(GateModel):
    imputation: None
    maximum_window_ms: Time
    minimum_usable_samples: Time
    minimum_window_ms: Time
    role: Literal["analytical_candidate"]
    summary_status: Literal["complete"]
    support: Literal["supported"]
    temporal_coverage_claim: StrictBool


class PolicyQuery(GateModel):
    cause_label: None
    ignored_n6_reasons: Annotated[
        tuple[Literal["label_unverified"], ...], Field(min_length=1, max_length=1)
    ]
    modes: Annotated[
        tuple[Literal["validation", "final_test"], ...], Field(min_length=2, max_length=2)
    ]
    profile_hypotheses: Literal["unavailable"]
    source_overlap_scope: Literal["all_contributing_baseline_groups"]
    use_labels: StrictBool


class PolicyRegistry(GateModel):
    content_hash: Literal["sha256:50329d193303c271194b28e9164ae8627dd257d7620174c5ab136ba209864884"]
    registry_version: Literal["latency-metrics-v2.0.0"]


class PolicyScope(GateModel):
    context_excluded_fields: Annotated[
        tuple[Literal["context_id", "node_id", "network_scenario"], ...],
        Field(min_length=3, max_length=3),
    ]
    fields: Annotated[
        tuple[
            Literal[
                "registry",
                "provenance",
                "capture_method",
                "clock",
                "source_format",
                "context",
                "effective_settings",
            ],
            ...,
        ],
        Field(min_length=7, max_length=7),
    ]


class PassiveGatePolicy(RootModel):
    assurance: Literal["software_provisional_declared_elapsed_not_live_authority"]
    baseline: PolicyBaseline
    calibration_method_release: Literal["n6-calibration-evidence-v1"]
    clock: PolicyClock
    content_hash: Literal["sha256:07beb342e6ae7387a6edb2235ba0b26a5122fb3fffb5f83b7da2e7109f48a5ca"]
    evaluation: PolicyEvaluation
    gates: PolicyGates
    limits: PolicyLimits
    method_release: Literal["n9-passive-gating-v1"]
    metric: PolicyMetric
    operating_mode: Literal["offline_provisional"]
    policy_id: Literal[
        "passive-gate-policy-07beb342e6ae7387a6edb2235ba0b26a5122fb3fffb5f83b7da2e7109f48a5ca"
    ]
    quality: PolicyQuality
    query: PolicyQuery
    registry: PolicyRegistry
    schema_version: Literal["passive-gate-policy-v1"]
    scope: PolicyScope

    @model_validator(mode="after")
    def approved(self):
        if canonical_payload_bytes(self.model_dump(mode="json")) != canonical_payload_bytes(
            approved_policy_payload()
        ):
            raise ValueError("passive policy is not an approved release")
        check_json_size(self)
        return self
