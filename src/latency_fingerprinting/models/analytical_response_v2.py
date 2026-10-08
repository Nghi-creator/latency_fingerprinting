"""Strict auditable N3 analytical records, separate from frozen observation roots."""

import math
from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal

from pydantic import (
    FieldSerializationInfo,
    StrictBool,
    field_serializer,
    field_validator,
    model_validator,
)

from ..analytical.policy_release import payload_hash
from .common import (
    FiniteFloat,
    NonEmptyStr,
    NonNegativeFiniteFloat,
    NonNegativeInt,
    PositiveFiniteFloat,
    UnitInterval,
)
from .feature_policy import FeaturePolicyV1
from .measurement import AggregationKind, MetricName, MetricSeriesStatus, MetricUnit
from .observation_pair_v2 import ObservationRecordV2
from .v2_common import V2Model
from .v2_support import SupportState

ANALYTICAL_RESPONSE_V2_SCHEMA_VERSION = "analytical-response-v2"
FeatureExclusionCode = Literal[
    "confounded_pair",
    "degraded_unsupported",
    "degraded_unavailable",
    "degraded_missing",
    "degraded_rejected",
    "degraded_incomplete",
    "degraded_coverage",
    "degraded_samples",
    "degraded_intervals",
    "degraded_no_value",
    "relief_unsupported",
    "relief_unavailable",
    "relief_missing",
    "relief_rejected",
    "relief_incomplete",
    "relief_coverage",
    "relief_samples",
    "relief_intervals",
    "relief_no_value",
]


class WindowFeatureEvidenceV2(V2Model):
    window_id: NonEmptyStr
    support_state: SupportState
    summary_status: MetricSeriesStatus
    primary_value: NonNegativeFiniteFloat | None
    source_sample_count: NonNegativeInt
    usable_sample_count: NonNegativeInt
    accepted_interval_count: NonNegativeInt
    observed_duration_ms: NonNegativeFiniteFloat
    coverage: UnitInterval


class FeatureResponseV2(V2Model):
    unit: MetricUnit
    aggregation: AggregationKind
    state: Literal["eligible", "excluded"]
    degraded: WindowFeatureEvidenceV2
    relief: WindowFeatureEvidenceV2
    exclusion_codes: tuple[FeatureExclusionCode, ...]
    raw_delta: FiniteFloat | None
    reference_value: NonNegativeFiniteFloat | None
    denominator: PositiveFiniteFloat | None
    normalized_value: FiniteFloat | None
    was_clipped: StrictBool
    unclipped_value: FiniteFloat | None

    @model_validator(mode="after")
    def validate_state(self):
        if self.was_clipped or self.unclipped_value is not None:
            raise ValueError("initial approved analytical policy does not clip")
        numbers = (self.raw_delta, self.reference_value, self.denominator, self.normalized_value)
        if self.state == "eligible":
            if self.exclusion_codes or any(value is None for value in numbers):
                raise ValueError("eligible features require numbers and no exclusions")
        elif not self.exclusion_codes or any(value is not None for value in numbers):
            raise ValueError("excluded features require reasons and null calculations")
        return self


def _window_evidence(window, name):
    measurement = window.measurements[name]
    summary = measurement.summary
    return WindowFeatureEvidenceV2(
        window_id=window.window_id,
        support_state=measurement.support.state,
        summary_status=summary.status,
        primary_value=summary.value,
        source_sample_count=summary.source_sample_count,
        usable_sample_count=summary.usable_sample_count,
        accepted_interval_count=summary.accepted_interval_count,
        observed_duration_ms=summary.observed_duration_ms,
        coverage=summary.coverage,
    )


def _window_exclusion(evidence, parameter, phase):
    if evidence.support_state != "supported":
        return f"{phase}_{evidence.support_state}"
    if evidence.summary_status not in parameter.allowed_statuses:
        return f"{phase}_{evidence.summary_status}"
    if evidence.coverage < parameter.minimum_coverage:
        return f"{phase}_coverage"
    if evidence.usable_sample_count < parameter.minimum_usable_samples:
        return f"{phase}_samples"
    if evidence.accepted_interval_count < parameter.minimum_accepted_intervals:
        return f"{phase}_intervals"
    if evidence.primary_value is None:
        return f"{phase}_no_value"
    return None


class AnalyticalResponseV2(V2Model):
    schema_version: Literal["analytical-response-v2"]
    contract_version: Literal["2.0.0"]
    response_id: NonEmptyStr
    observation: ObservationRecordV2
    policy: FeaturePolicyV1
    features: Mapping[MetricName, FeatureResponseV2]
    is_valid: StrictBool
    invalid_reason_codes: tuple[Literal["confounded_pair", "no_eligible_features"], ...]

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
    def validate_response(self):
        observation = self.observation
        if observation.degraded_window.registry != self.policy.registry:
            raise ValueError("observation and analytical policy registry meanings disagree")
        hash_input = {
            "observation": observation.model_dump(mode="json", by_alias=True),
            "policy": self.policy.model_dump(mode="json", by_alias=True),
        }
        if self.response_id != "response-v2-" + payload_hash(hash_input)[7:]:
            raise ValueError("response identity must derive from its observation and policy")
        if set(self.features) != set(self.policy.features):
            raise ValueError("analytical response requires exactly the 22 policy feature entries")
        confounded = bool(
            observation.degraded_window.confounder_codes
            or observation.relief_window.confounder_codes
            or observation.intervention.confounder_codes
        )
        eligible_count = 0
        for name, parameter in self.policy.features.items():
            feature = self.features[name]
            degraded = _window_evidence(observation.degraded_window, name)
            relief = _window_evidence(observation.relief_window, name)
            if feature.degraded != degraded or feature.relief != relief:
                raise ValueError("feature audit evidence must equal the embedded window summaries")
            if feature.unit != parameter.unit or feature.aggregation != parameter.aggregation:
                raise ValueError("feature unit/aggregation must match its approved policy binding")
            exclusions = (
                ("confounded_pair",)
                if confounded
                else tuple(
                    code
                    for code in (
                        _window_exclusion(degraded, parameter, "degraded"),
                        _window_exclusion(relief, parameter, "relief"),
                    )
                    if code is not None
                )
            )
            expected_state = "excluded" if exclusions else "eligible"
            if feature.state != expected_state or feature.exclusion_codes != exclusions:
                raise ValueError("feature eligibility/exclusions must follow window evidence")
            if exclusions:
                continue
            eligible_count += 1
            reference = degraded.primary_value
            delta = relief.primary_value - reference
            denominator = max(abs(reference), parameter.epsilon)
            normalized = delta / denominator
            if not all(math.isfinite(value) for value in (delta, denominator, normalized)):
                raise ValueError("analytical response exceeds the finite numeric range")
            for actual, expected in (
                (feature.raw_delta, delta),
                (feature.reference_value, reference),
                (feature.denominator, denominator),
                (feature.normalized_value, normalized),
            ):
                if not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12):
                    raise ValueError("analytical calculations must reconstruct from primary values")
        reasons = (
            ("confounded_pair",)
            if confounded
            else (("no_eligible_features",) if not eligible_count else ())
        )
        if self.is_valid != (not reasons) or self.invalid_reason_codes != reasons:
            raise ValueError("analytical validity must match confounders and feature eligibility")
        return self
