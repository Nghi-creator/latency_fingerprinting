"""Probe, response-delta, normalization, and paired-observation models."""

from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import Field, JsonValue, StrictBool, model_validator

from ..feature_config import P0_FEATURE_CONFIG, normalize_feature_value
from .common import (
    CONTRACT_VERSION,
    OBSERVATION_SCHEMA_VERSION,
    ContractModel,
    FiniteFloat,
    NonEmptyStr,
    PositiveFiniteFloat,
    ProbeApplicationMethod,
    ProbeExecutionStatus,
    ProvenanceKind,
    RestorationStatus,
    WindowPhase,
)
from .context import ContextKey, MetricAggregate, ObservationWindow


class Probe(ContractModel):
    probe_id: NonEmptyStr
    probe_type: NonEmptyStr
    probe_version: NonEmptyStr
    requested_settings: dict[str, JsonValue]
    observed_settings: dict[str, JsonValue] | None = None
    intensity: PositiveFiniteFloat
    application_method: ProbeApplicationMethod
    degraded_window_id: NonEmptyStr
    relief_window_id: NonEmptyStr
    execution_status: ProbeExecutionStatus
    paired_window_order: Annotated[
        list[Literal["degraded", "relief"]], Field(min_length=2, max_length=2)
    ] = Field(default_factory=lambda: ["degraded", "relief"])
    restoration_status: RestorationStatus
    safety_notes: list[NonEmptyStr] = Field(default_factory=list)
    known_confounders: list[NonEmptyStr] = Field(default_factory=list)
    quality_cost: dict[str, MetricAggregate] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_simulated_probe(self) -> Probe:
        if self.degraded_window_id == self.relief_window_id:
            raise ValueError("a probe requires distinct degraded and relief windows")
        if len(self.paired_window_order) != 2 or set(self.paired_window_order) != {
            "degraded",
            "relief",
        }:
            raise ValueError("paired_window_order must contain degraded and relief exactly once")
        if not self.requested_settings:
            raise ValueError("a probe requires at least one requested setting")
        if any(not key.strip() for key in self.requested_settings):
            raise ValueError("requested setting names cannot be empty")
        if self.observed_settings is not None and not self.observed_settings:
            raise ValueError("observed_settings cannot be empty when provided")
        if self.application_method is ProbeApplicationMethod.SIMULATED_PAIR:
            if self.execution_status is not ProbeExecutionStatus.NOT_EXECUTED:
                raise ValueError("simulated_pair probes must not claim execution")
            if self.restoration_status is not RestorationStatus.NOT_EXECUTED:
                raise ValueError("simulated_pair probes must state restoration was not executed")
            if self.observed_settings is not None:
                raise ValueError("simulated_pair probes cannot have observed runtime settings")
        elif (
            self.execution_status is ProbeExecutionStatus.EXECUTED
            and self.observed_settings is None
        ):
            raise ValueError("executed probes require observed runtime settings")
        elif (
            self.execution_status is ProbeExecutionStatus.NOT_EXECUTED
            and self.observed_settings is not None
        ):
            raise ValueError("a probe that was not executed cannot have observed runtime settings")
        if self.execution_status is ProbeExecutionStatus.EXECUTED and self.restoration_status in {
            RestorationStatus.NOT_APPLICABLE,
            RestorationStatus.NOT_EXECUTED,
        }:
            raise ValueError("executed probes require an applicable restoration outcome")
        return self


class FeatureDelta(ContractModel):
    unit: NonEmptyStr
    aggregation: NonEmptyStr
    degraded_value: FiniteFloat
    relief_value: FiniteFloat
    raw_delta: FiniteFloat

    @model_validator(mode="after")
    def validate_delta(self) -> FeatureDelta:
        expected = self.relief_value - self.degraded_value
        if not math.isclose(self.raw_delta, expected, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError("raw_delta must equal relief_value minus degraded_value")
        return self


class ResponseDelta(ContractModel):
    degraded_window_id: NonEmptyStr
    relief_window_id: NonEmptyStr
    features: dict[NonEmptyStr, FeatureDelta]
    missing_features: list[NonEmptyStr] = Field(default_factory=list)
    rejected_features: dict[NonEmptyStr, NonEmptyStr] = Field(default_factory=dict)
    is_valid: StrictBool
    invalid_reasons: list[NonEmptyStr] = Field(default_factory=list)
    warnings: list[NonEmptyStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_response_status(self) -> ResponseDelta:
        if self.degraded_window_id == self.relief_window_id:
            raise ValueError("response delta requires distinct windows")
        if not self.is_valid and not self.invalid_reasons:
            raise ValueError("an invalid response delta requires at least one reason")
        if self.is_valid and self.invalid_reasons:
            raise ValueError("a valid response delta cannot have invalidity reasons")
        if not self.is_valid and self.features:
            raise ValueError("an invalid response delta cannot contain calculated features")
        measured = set(self.features)
        missing = set(self.missing_features)
        rejected = set(self.rejected_features)
        overlap = (measured & missing) | (measured & rejected) | (missing & rejected)
        if overlap:
            raise ValueError(
                "response features must have exactly one measured, missing or rejected state: "
                f"{sorted(overlap)}"
            )
        if len(missing) != len(self.missing_features):
            raise ValueError("missing_features cannot contain duplicates")
        return self


class NormalizedFeature(ContractModel):
    value: FiniteFloat
    epsilon: PositiveFiniteFloat
    reference_value: FiniteFloat
    was_clipped: StrictBool = False
    unclipped_value: FiniteFloat | None = None

    @model_validator(mode="after")
    def validate_clipping_metadata(self) -> NormalizedFeature:
        if self.was_clipped and self.unclipped_value is None:
            raise ValueError("a clipped normalized feature requires its unclipped_value")
        if not self.was_clipped and self.unclipped_value is not None:
            raise ValueError("an unclipped normalized feature cannot have an unclipped_value")
        return self


def validate_canonical_normalization(
    feature: str,
    raw: FeatureDelta,
    normalized: NormalizedFeature,
) -> None:
    """Ensure persisted P0 normalized values use the frozen feature contract."""

    config = P0_FEATURE_CONFIG.get(feature)
    if config is None:
        raise ValueError(f"normalized feature {feature!r} is not supported by P0")
    if raw.unit != config.unit:
        raise ValueError(
            f"normalized feature {feature!r} uses unit {raw.unit!r}; P0 expects {config.unit!r}"
        )
    if normalized.epsilon != config.epsilon:
        raise ValueError(f"normalized feature {feature!r} has a non-canonical epsilon")
    expected_value, expected_clipped, expected_unclipped = normalize_feature_value(
        raw.raw_delta,
        raw.degraded_value,
        config,
    )
    if normalized.was_clipped is not expected_clipped:
        raise ValueError(f"normalized feature {feature!r} has incorrect clipping metadata")
    if not math.isclose(normalized.value, expected_value, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError(
            f"normalized feature {feature!r} disagrees with its raw delta "
            "under canonical normalization"
        )
    if expected_unclipped is None:
        if normalized.unclipped_value is not None:
            raise ValueError(f"normalized feature {feature!r} has unexpected unclipped metadata")
    elif normalized.unclipped_value is None or not math.isclose(
        normalized.unclipped_value,
        expected_unclipped,
        rel_tol=1e-12,
        abs_tol=1e-12,
    ):
        raise ValueError(f"normalized feature {feature!r} has the wrong unclipped value")


class NormalizedResponse(ContractModel):
    features: dict[NonEmptyStr, NormalizedFeature]
    missing_features: list[NonEmptyStr] = Field(default_factory=list)
    rejected_features: dict[NonEmptyStr, NonEmptyStr] = Field(default_factory=dict)
    is_valid: StrictBool = True
    invalid_reasons: list[NonEmptyStr] = Field(default_factory=list)
    warnings: list[NonEmptyStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_normalized_status(self) -> NormalizedResponse:
        if not self.is_valid and not self.invalid_reasons:
            raise ValueError("an invalid normalized response requires at least one reason")
        if self.is_valid and self.invalid_reasons:
            raise ValueError("a valid normalized response cannot have invalidity reasons")
        if not self.is_valid and self.features:
            raise ValueError("an invalid normalized response cannot contain calculated features")
        measured = set(self.features)
        missing = set(self.missing_features)
        rejected = set(self.rejected_features)
        overlap = (measured & missing) | (measured & rejected) | (missing & rejected)
        if overlap:
            raise ValueError(
                "normalized features must have exactly one measured, missing or rejected state: "
                f"{sorted(overlap)}"
            )
        if len(missing) != len(self.missing_features):
            raise ValueError("missing_features cannot contain duplicates")
        return self


class ObservationRecord(ContractModel):
    """The ``observation-v1`` root: paired windows plus their response."""

    schema_version: Literal["observation-v1"] = OBSERVATION_SCHEMA_VERSION
    contract_version: Literal["1.0.0"] = CONTRACT_VERSION
    context: ContextKey
    degraded_window: ObservationWindow
    relief_window: ObservationWindow
    probe: Probe
    response_delta: ResponseDelta
    normalized_response: NormalizedResponse
    provenance: ProvenanceKind

    @model_validator(mode="after")
    def validate_pair(self) -> ObservationRecord:
        degraded, relief = self.degraded_window, self.relief_window
        if degraded.phase is not WindowPhase.DEGRADED or relief.phase is not WindowPhase.RELIEF:
            raise ValueError("observation records require degraded and relief windows")
        if degraded.context != self.context or relief.context != self.context:
            raise ValueError("both windows must use the record context")
        if degraded.provenance is not self.provenance or relief.provenance is not self.provenance:
            raise ValueError("window provenance must equal record provenance")
        if (
            self.provenance is ProvenanceKind.SYNTHETIC
            and self.probe.application_method is not ProbeApplicationMethod.SIMULATED_PAIR
        ):
            raise ValueError("synthetic observations require a simulated_pair probe")
        if (
            self.provenance is not ProvenanceKind.SYNTHETIC
            and self.probe.application_method is ProbeApplicationMethod.SIMULATED_PAIR
        ):
            raise ValueError("real observations cannot use a simulated_pair probe")
        if (
            self.provenance is not ProvenanceKind.SYNTHETIC
            and self.normalized_response.is_valid
            and self.probe.execution_status is not ProbeExecutionStatus.EXECUTED
        ):
            raise ValueError("valid real observations require an executed probe")
        if degraded.comparison_case_id != relief.comparison_case_id:
            raise ValueError("paired windows must share comparison_case_id")
        if (
            self.probe.degraded_window_id != degraded.window_id
            or self.probe.relief_window_id != relief.window_id
        ):
            raise ValueError("probe window identifiers must reference this pair")
        if (
            self.response_delta.degraded_window_id != degraded.window_id
            or self.response_delta.relief_window_id != relief.window_id
        ):
            raise ValueError("response delta window identifiers must reference this pair")
        if self.response_delta.is_valid != self.normalized_response.is_valid:
            raise ValueError("raw and normalized response validity must agree")
        if set(self.response_delta.features) != set(self.normalized_response.features):
            raise ValueError("raw and normalized response feature sets must agree")
        if set(self.response_delta.missing_features) != set(
            self.normalized_response.missing_features
        ):
            raise ValueError("raw and normalized missing-feature sets must agree")
        if set(self.response_delta.rejected_features) != set(
            self.normalized_response.rejected_features
        ):
            raise ValueError("raw and normalized rejected-feature sets must agree")
        for feature, raw in self.response_delta.features.items():
            degraded_metric = degraded.metrics.get(feature)
            relief_metric = relief.metrics.get(feature)
            if degraded_metric is None or relief_metric is None:
                raise ValueError(f"response feature {feature!r} requires both window metrics")
            if (
                raw.unit != degraded_metric.unit
                or raw.aggregation != degraded_metric.aggregation
                or not math.isclose(raw.degraded_value, degraded_metric.value, abs_tol=1e-12)
                or not math.isclose(raw.relief_value, relief_metric.value, abs_tol=1e-12)
            ):
                raise ValueError(f"response feature {feature!r} disagrees with its source windows")
            normalized = self.normalized_response.features[feature]
            if not math.isclose(normalized.reference_value, raw.degraded_value, abs_tol=1e-12):
                raise ValueError(f"normalized feature {feature!r} has the wrong reference value")
            validate_canonical_normalization(feature, raw, normalized)
        if not set(self.response_delta.warnings).issubset(self.normalized_response.warnings):
            raise ValueError("normalized response must retain raw response warnings")
        if self.response_delta.invalid_reasons != self.normalized_response.invalid_reasons:
            raise ValueError("raw and normalized invalid reasons must agree")
        return self
