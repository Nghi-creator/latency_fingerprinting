"""Shared types, versions, and strict base model for the P0 contract."""

from __future__ import annotations

import math
from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

CONTRACT_VERSION = "1.0.0"
OBSERVATION_SCHEMA_VERSION = "observation-v1"
FINGERPRINT_SCHEMA_VERSION = "fingerprint-v1"
MATCH_RESULT_SCHEMA_VERSION = "match-result-v1"

NonEmptyStr = Annotated[str, Field(min_length=1)]
FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
NonNegativeFiniteFloat = Annotated[float, Field(ge=0, allow_inf_nan=False)]
PositiveFiniteFloat = Annotated[float, Field(gt=0, allow_inf_nan=False)]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]
UnitInterval = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


def _camel_case(name: str) -> str:
    """Convert a Python field name to its contract JSON spelling."""

    head, *tail = name.split("_")
    return head + "".join(word.capitalize() for word in tail)


class ContractModel(BaseModel):
    """Strict base class shared by every public P0 record."""

    model_config = ConfigDict(
        alias_generator=_camel_case,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    @model_validator(mode="after")
    def reject_nested_non_finite_numbers(self) -> ContractModel:
        """Reject NaN and infinity, including values nested in JSON settings."""

        def is_non_finite(value: object) -> bool:
            if isinstance(value, float):
                return not math.isfinite(value)
            if isinstance(value, BaseModel):
                return any(is_non_finite(item) for item in value.__dict__.values())
            if isinstance(value, Mapping):
                return any(is_non_finite(item) for item in value.values())
            if isinstance(value, (list, tuple, set, frozenset)):
                return any(is_non_finite(item) for item in value)
            return False

        if any(is_non_finite(value) for value in self.__dict__.values()):
            raise ValueError("contract records cannot contain NaN or infinity")
        return self


class WindowPhase(StrEnum):
    BASELINE = "baseline"
    DEGRADED = "degraded"
    RELIEF = "relief"
    RECOVERY = "recovery"


class ProvenanceKind(StrEnum):
    SYNTHETIC = "synthetic"
    CONTROLLED_REAL = "controlled_real"
    ORGANIC_REAL = "organic_real"


class ProbeApplicationMethod(StrEnum):
    SIMULATED_PAIR = "simulated_pair"
    PAIRED_RUN = "paired_run"
    LIVE_BOUNDED_PROBE = "live_bounded_probe"


class ProbeExecutionStatus(StrEnum):
    NOT_EXECUTED = "not_executed"
    EXECUTED = "executed"
    FAILED = "failed"


class RestorationStatus(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    NOT_EXECUTED = "not_executed"
    RESTORED = "restored"
    NOT_RESTORED = "not_restored"
    UNKNOWN = "unknown"


class ValidationStatus(StrEnum):
    UNVALIDATED = "unvalidated"
    SOFTWARE_TEST_REFERENCE = "software_test_reference"
    VALIDATED = "validated"
    REJECTED = "rejected"


class MatchDecision(StrEnum):
    MATCHED = "matched"
    UNKNOWN = "unknown"


class UnknownReason(StrEnum):
    INCOMPATIBLE_CONTEXT = "incompatible_context"
    UNSUPPORTED_PROBE = "unsupported_probe"
    INSUFFICIENT_FEATURE_COVERAGE = "insufficient_feature_coverage"
    DEGENERATE_VECTOR = "degenerate_vector"
    WEAK_MATCH = "weak_match"
    AMBIGUOUS_MARGIN = "ambiguous_margin"
    INVALID_OBSERVATION = "invalid_observation"
    CONFLICTING_EVIDENCE = "conflicting_evidence"


class OutcomeResult(StrEnum):
    IMPROVED = "improved"
    UNCHANGED = "unchanged"
    WORSENED = "worsened"
    INCONCLUSIVE = "inconclusive"
