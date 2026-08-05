"""Interpretable match-result and later validated-outcome contract models."""

from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import (
    CONTRACT_VERSION,
    MATCH_RESULT_SCHEMA_VERSION,
    ContractModel,
    FiniteFloat,
    MatchDecision,
    NonEmptyStr,
    NonNegativeFiniteFloat,
    NonNegativeInt,
    OutcomeResult,
    PositiveInt,
    ProvenanceKind,
    RestorationStatus,
    UnknownReason,
)
from .context import MetricAggregate


class RankedCandidate(ContractModel):
    fingerprint_id: NonEmptyStr
    bottleneck_label: NonEmptyStr
    distance: NonNegativeFiniteFloat
    match_strength: NonNegativeFiniteFloat


class FeatureEvidence(ContractModel):
    feature: NonEmptyStr
    observed_value: FiniteFloat
    candidate_value: FiniteFloat
    residual: FiniteFloat
    weight: NonNegativeFiniteFloat
    weighted_squared_residual: NonNegativeFiniteFloat

    @model_validator(mode="after")
    def validate_residual(self) -> FeatureEvidence:
        if not math.isclose(
            self.residual,
            self.observed_value - self.candidate_value,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise ValueError("residual must equal observed_value minus candidate_value")
        expected = self.weight * self.residual**2
        if not math.isclose(self.weighted_squared_residual, expected, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError("weighted_squared_residual must equal weight times residual squared")
        return self


class CompatibilityResult(ContractModel):
    is_compatible: bool
    compatibility_group: NonEmptyStr
    compatible_fingerprint_ids: list[NonEmptyStr] = Field(default_factory=list)
    rejected_fingerprints: dict[NonEmptyStr, NonEmptyStr] = Field(default_factory=dict)


class MatchThresholds(ContractModel):
    minimum_match_strength: NonNegativeFiniteFloat = 0.75
    minimum_score_margin: NonNegativeFiniteFloat = 0.10
    minimum_shared_feature_count: PositiveInt = 3
    minimum_feature_coverage: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)] = 0.60


class MatchResult(ContractModel):
    schema_version: Literal["match-result-v1"] = MATCH_RESULT_SCHEMA_VERSION
    contract_version: Literal["1.0.0"] = CONTRACT_VERSION
    decision: MatchDecision
    accepted_label: NonEmptyStr | None = None
    match_strength: NonNegativeFiniteFloat | None = None
    score_margin: NonNegativeFiniteFloat | None = None
    ranked_candidates: list[RankedCandidate] = Field(default_factory=list)
    shared_feature_count: NonNegativeInt
    feature_coverage: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    supporting_evidence: list[FeatureEvidence] = Field(default_factory=list)
    conflicting_evidence: list[FeatureEvidence] = Field(default_factory=list)
    missing_features: list[NonEmptyStr] = Field(default_factory=list)
    compatibility: CompatibilityResult
    thresholds: MatchThresholds = Field(default_factory=MatchThresholds)
    warnings: list[NonEmptyStr] = Field(default_factory=list)
    decision_reason: NonEmptyStr
    unknown_reason: UnknownReason | None = None

    @model_validator(mode="after")
    def validate_decision(self) -> MatchResult:
        if self.decision is MatchDecision.MATCHED:
            if self.accepted_label is None or self.match_strength is None:
                raise ValueError("a matched result requires accepted_label and match_strength")
            if self.unknown_reason is not None:
                raise ValueError("a matched result cannot have an unknown_reason")
        else:
            if self.accepted_label is not None:
                raise ValueError("an unknown result must not have an accepted_label")
            if self.unknown_reason is None:
                raise ValueError("an unknown result requires an unknown_reason")
        return self


class ValidatedOutcome(ContractModel):
    """Later real-run evidence; synthetic fixtures cannot become observed fact."""

    outcome_id: NonEmptyStr
    action_or_probe_id: NonEmptyStr
    provenance: Literal[ProvenanceKind.CONTROLLED_REAL, ProvenanceKind.ORGANIC_REAL]
    before_indicators: dict[NonEmptyStr, MetricAggregate]
    after_indicators: dict[NonEmptyStr, MetricAggregate]
    recovery_time_s: NonNegativeFiniteFloat | None = None
    quality_cost: dict[NonEmptyStr, MetricAggregate] = Field(default_factory=dict)
    stability_impact: NonEmptyStr | None = None
    restoration_status: RestorationStatus
    result: OutcomeResult
