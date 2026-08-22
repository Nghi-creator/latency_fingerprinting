"""Fingerprint storage and compatibility contract models."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import (
    CONTRACT_VERSION,
    FINGERPRINT_SCHEMA_VERSION,
    ContractModel,
    NonEmptyStr,
    NonNegativeFiniteFloat,
    ProvenanceKind,
    ValidationStatus,
)
from .context import ContextKey
from .response import NormalizedResponse, ResponseDelta


class CompatibilityKey(ContractModel):
    compatibility_group: NonEmptyStr
    probe_type: NonEmptyStr
    contract_version: Literal["1.0.0"] = CONTRACT_VERSION


class Fingerprint(ContractModel):
    schema_version: Literal["fingerprint-v1"] = FINGERPRINT_SCHEMA_VERSION
    contract_version: Literal["1.0.0"] = CONTRACT_VERSION
    fingerprint_id: NonEmptyStr
    bottleneck_label: NonEmptyStr
    context: ContextKey
    compatibility: CompatibilityKey
    raw_response_delta: ResponseDelta
    normalized_response: NormalizedResponse
    feature_weights: dict[NonEmptyStr, NonNegativeFiniteFloat]
    provenance: ProvenanceKind
    source_case_ids: Annotated[list[NonEmptyStr], Field(min_length=1)]
    source_window_ids: Annotated[list[NonEmptyStr], Field(min_length=1)]
    source_run_ids: list[NonEmptyStr] = Field(default_factory=list)
    created_at: datetime
    software_version: NonEmptyStr
    validation_status: ValidationStatus
    notes: list[NonEmptyStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_fingerprint(self) -> Fingerprint:
        if self.compatibility.compatibility_group != self.context.compatibility_group:
            raise ValueError("fingerprint compatibility group must equal its context group")
        if self.compatibility.contract_version != self.contract_version:
            raise ValueError(
                "fingerprint compatibility contract version must equal its root version"
            )
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be a timezone-aware UTC timestamp")
        if self.created_at.utcoffset().total_seconds() != 0:
            raise ValueError("created_at must use a UTC offset")
        if not self.source_case_ids or not self.source_window_ids:
            raise ValueError("fingerprints require source case and window identifiers")
        missing_weights = set(self.normalized_response.features).difference(self.feature_weights)
        if missing_weights:
            raise ValueError(f"missing feature weights: {sorted(missing_weights)}")
        extra_weights = set(self.feature_weights).difference(self.normalized_response.features)
        if extra_weights:
            raise ValueError(f"feature weights without response features: {sorted(extra_weights)}")
        if self.raw_response_delta.is_valid != self.normalized_response.is_valid:
            raise ValueError("raw and normalized fingerprint response validity must agree")
        if not self.raw_response_delta.is_valid:
            raise ValueError("a stored fingerprint requires a valid response pattern")
        if set(self.raw_response_delta.features) != set(self.normalized_response.features):
            raise ValueError("raw and normalized fingerprint feature sets must agree")
        if set(self.raw_response_delta.missing_features) != set(
            self.normalized_response.missing_features
        ):
            raise ValueError("raw and normalized fingerprint missing-feature sets must agree")
        if set(self.raw_response_delta.rejected_features) != set(
            self.normalized_response.rejected_features
        ):
            raise ValueError("raw and normalized fingerprint rejected-feature sets must agree")
        for feature, raw in self.raw_response_delta.features.items():
            normalized = self.normalized_response.features[feature]
            if not math.isclose(normalized.reference_value, raw.degraded_value, abs_tol=1e-12):
                raise ValueError(f"normalized feature {feature!r} has the wrong reference value")
            expected = raw.raw_delta / max(abs(raw.degraded_value), normalized.epsilon)
            represented = normalized.unclipped_value if normalized.was_clipped else normalized.value
            if represented is None:
                raise ValueError(f"normalized feature {feature!r} is missing its unclipped value")
            if not math.isclose(represented, expected, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError(f"normalized feature {feature!r} disagrees with its raw delta")
        for field_name, identifiers in (
            ("source_case_ids", self.source_case_ids),
            ("source_window_ids", self.source_window_ids),
            ("source_run_ids", self.source_run_ids),
        ):
            if len(set(identifiers)) != len(identifiers):
                raise ValueError(f"{field_name} cannot contain duplicates")
        if self.provenance is not ProvenanceKind.SYNTHETIC and not self.source_run_ids:
            raise ValueError("real fingerprints require source run identifiers")
        if (
            self.provenance is ProvenanceKind.SYNTHETIC
            and self.validation_status is ValidationStatus.VALIDATED
        ):
            raise ValueError("synthetic fingerprints cannot be marked validated")
        return self
