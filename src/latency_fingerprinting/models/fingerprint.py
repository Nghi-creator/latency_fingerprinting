"""Fingerprint storage and compatibility contract models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

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
    contract_version: NonEmptyStr = CONTRACT_VERSION


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
    source_case_ids: list[NonEmptyStr]
    source_window_ids: list[NonEmptyStr]
    source_run_ids: list[NonEmptyStr] = Field(default_factory=list)
    created_at: datetime
    software_version: NonEmptyStr
    validation_status: ValidationStatus
    notes: list[NonEmptyStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_fingerprint(self) -> Fingerprint:
        if self.compatibility.compatibility_group != self.context.compatibility_group:
            raise ValueError("fingerprint compatibility group must equal its context group")
        missing_weights = set(self.normalized_response.features).difference(self.feature_weights)
        if missing_weights:
            raise ValueError(f"missing feature weights: {sorted(missing_weights)}")
        if (
            self.provenance is ProvenanceKind.SYNTHETIC
            and self.validation_status is ValidationStatus.VALIDATED
        ):
            raise ValueError("synthetic fingerprints cannot be marked validated")
        return self
