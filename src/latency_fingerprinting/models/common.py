"""Shared strict model foundation, numeric types and cross-version vocabulary."""

from __future__ import annotations

import math
from collections.abc import Mapping
from enum import StrEnum
from numbers import Real
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

NonEmptyStr = Annotated[str, Field(min_length=1, strict=True)]
FiniteFloat = Annotated[float, Field(allow_inf_nan=False, strict=True)]
NonNegativeFiniteFloat = Annotated[float, Field(ge=0, allow_inf_nan=False, strict=True)]
PositiveFiniteFloat = Annotated[float, Field(gt=0, allow_inf_nan=False, strict=True)]
NonNegativeInt = Annotated[int, Field(ge=0, strict=True)]
PositiveInt = Annotated[int, Field(gt=0, strict=True)]
UnitInterval = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False, strict=True)]


def _camel_case(name: str) -> str:
    """Convert a Python field name to its contract JSON spelling."""

    head, *tail = name.split("_")
    return head + "".join(word.capitalize() for word in tail)


def json_values_equal(left: object, right: object) -> bool:
    """Compare JSON values without treating booleans as the integers 0 and 1."""

    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if isinstance(left, Real) and isinstance(right, Real):
        return left == right
    if isinstance(left, dict) and isinstance(right, dict):
        return set(left) == set(right) and all(
            json_values_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            json_values_equal(left_item, right_item)
            for left_item, right_item in zip(left, right, strict=True)
        )
    return type(left) is type(right) and left == right


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


class RestorationStatus(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    NOT_EXECUTED = "not_executed"
    RESTORED = "restored"
    NOT_RESTORED = "not_restored"
    UNKNOWN = "unknown"
