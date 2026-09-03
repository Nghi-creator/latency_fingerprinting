"""Interpretable match-result and later validated-outcome contract models."""

from __future__ import annotations

import math
from typing import Literal

from pydantic import Field, StrictBool, model_validator

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
    UnitInterval,
    UnknownReason,
)
from .context import MetricAggregate


class RankedCandidate(ContractModel):
    fingerprint_id: NonEmptyStr
    bottleneck_label: NonEmptyStr
    distance: NonNegativeFiniteFloat
    match_strength: UnitInterval


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
        # Multiplication yields ``inf`` for unrepresentable products, whereas
        # exponentiation can leak a raw ``OverflowError`` from model validation.
        expected = self.weight * self.residual * self.residual
        if not math.isfinite(expected):
            raise ValueError("weight times residual squared must be finite")
        if not math.isclose(self.weighted_squared_residual, expected, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError("weighted_squared_residual must equal weight times residual squared")
        return self


class CompatibilityResult(ContractModel):
    is_compatible: StrictBool
    compatibility_group: NonEmptyStr
    compatible_fingerprint_ids: list[NonEmptyStr] = Field(default_factory=list)
    rejected_fingerprints: dict[NonEmptyStr, NonEmptyStr] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_identifiers(self) -> CompatibilityResult:
        if len(set(self.compatible_fingerprint_ids)) != len(self.compatible_fingerprint_ids):
            raise ValueError("compatible_fingerprint_ids cannot contain duplicates")
        overlap = set(self.compatible_fingerprint_ids) & set(self.rejected_fingerprints)
        if overlap:
            raise ValueError(
                f"fingerprints cannot be both compatible and rejected: {sorted(overlap)}"
            )
        if self.is_compatible != bool(self.compatible_fingerprint_ids):
            raise ValueError("is_compatible must reflect compatible_fingerprint_ids")
        return self


class MatchThresholds(ContractModel):
    minimum_match_strength: UnitInterval = 0.75
    minimum_score_margin: UnitInterval = 0.10
    minimum_shared_feature_count: PositiveInt = 3
    minimum_feature_coverage: UnitInterval = 0.60


class MatchResult(ContractModel):
    schema_version: Literal["match-result-v1"] = MATCH_RESULT_SCHEMA_VERSION
    contract_version: Literal["1.0.0"] = CONTRACT_VERSION
    decision: MatchDecision
    accepted_label: NonEmptyStr | None = None
    match_strength: UnitInterval | None = None
    score_margin: UnitInterval | None = None
    ranked_candidates: list[RankedCandidate] = Field(default_factory=list)
    shared_feature_count: NonNegativeInt
    feature_coverage: UnitInterval
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
        candidate_ids = [candidate.fingerprint_id for candidate in self.ranked_candidates]
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("ranked candidate fingerprint IDs must be unique")
        if any(
            first.match_strength < second.match_strength
            for first, second in zip(
                self.ranked_candidates, self.ranked_candidates[1:], strict=False
            )
        ):
            raise ValueError("ranked candidates must use descending match strength")
        supporting = [item.feature for item in self.supporting_evidence]
        conflicting = [item.feature for item in self.conflicting_evidence]
        if len(set(supporting)) != len(supporting) or len(set(conflicting)) != len(conflicting):
            raise ValueError("feature evidence cannot contain duplicate features")
        if set(supporting) & set(conflicting):
            raise ValueError("features cannot be both supporting and conflicting evidence")
        if len(set(self.missing_features)) != len(self.missing_features):
            raise ValueError("missing_features cannot contain duplicates")
        if self.ranked_candidates:
            best = self.ranked_candidates[0]
            if self.match_strength is None:
                raise ValueError("ranked candidates require a best match_strength")
            if not math.isclose(self.match_strength, best.match_strength, abs_tol=1e-12):
                raise ValueError("match_strength must equal the top candidate strength")
        elif self.match_strength is not None:
            raise ValueError("match_strength requires at least one ranked candidate")

        if len(self.ranked_candidates) >= 2:
            if self.score_margin is None:
                raise ValueError("two or more ranked candidates require a score_margin")
            expected_margin = (
                self.ranked_candidates[0].match_strength - self.ranked_candidates[1].match_strength
            )
            if not math.isclose(self.score_margin, expected_margin, abs_tol=1e-12):
                raise ValueError("score_margin must equal the top-two strength difference")
        elif self.score_margin is not None:
            raise ValueError("score_margin requires at least two ranked candidates")

        if self.decision is MatchDecision.MATCHED:
            if self.accepted_label is None or self.match_strength is None:
                raise ValueError("a matched result requires accepted_label and match_strength")
            if self.unknown_reason is not None:
                raise ValueError("a matched result cannot have an unknown_reason")
            if not self.compatibility.is_compatible:
                raise ValueError("a matched result requires compatible context")
            if not self.ranked_candidates:
                raise ValueError("a matched result requires at least one ranked candidate")
            if self.accepted_label != self.ranked_candidates[0].bottleneck_label:
                raise ValueError("accepted_label must equal the top candidate label")
            if self.match_strength < self.thresholds.minimum_match_strength:
                raise ValueError("a matched result must meet the match-strength threshold")
            if self.shared_feature_count < self.thresholds.minimum_shared_feature_count:
                raise ValueError("a matched result must meet the shared-feature threshold")
            if self.feature_coverage < self.thresholds.minimum_feature_coverage:
                raise ValueError("a matched result must meet the feature-coverage threshold")
            if (
                self.score_margin is not None
                and self.score_margin < self.thresholds.minimum_score_margin
            ):
                raise ValueError("a matched result must meet the score-margin threshold")
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
