"""Bounded immutable primitives for additive N7 policy/snapshot models."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Literal

from pydantic import Field, field_serializer, field_validator

from ..calibration.contracts import exact_string
from ..observability.contracts import TraceModel
from .policy_release import FEATURE_NAMES

RELEASE = "n7-profile-statistics-v1"
FeatureName = Literal[*FEATURE_NAMES]
ProfileID = exact_string(r"profile-[a-f0-9]{64}")
PolicyID = exact_string(r"profile-policy-[a-f0-9]{64}")
SnapshotID = exact_string(r"profile-snapshot-[a-f0-9]{64}")
Finite = Annotated[float, Field(strict=True, allow_inf_nan=False)]
FeatureCount = Annotated[int, Field(strict=True, ge=0, le=22)]
SELECTION_REASONS = (
    "missing_measurements",
    "baseline_only",
    "not_training",
    "n6_excluded",
    "duplicate_evidence",
    "unknown_label",
    "mixed_group_labels",
)
FEATURE_REASONS = (
    "missing_measurements",
    "insufficient_group_support",
    "insufficient_availability",
    "zero_dispersion",
)
CANDIDATE_REASONS = (
    "insufficient_training_groups",
    "insufficient_active_features",
    "insufficient_active_coverage",
)


class ProfileModel(TraceModel):
    collection_limits = {
        "feature_names": 22,
        "inputs": 256,
        "profiles": 256,
        "reason_codes": 7,
        "training_group_ids": 256,
        "selected_entry_ids": 256,
        "entry_ids": 256,
        "group_values": 256,
    }

    @field_validator("features", "feature_values", check_fields=False, mode="before")
    @classmethod
    def bound_maps(cls, value):
        if value is None:
            return value
        if not isinstance(value, Mapping) or len(value) != 22 or set(value) != set(FEATURE_NAMES):
            raise ValueError("profile maps require the exact feature inventory")
        return dict(value)

    @field_validator("features", "feature_values", check_fields=False, mode="after")
    @classmethod
    def freeze_maps(cls, value):
        return None if value is None else MappingProxyType(dict(sorted(value.items())))

    @field_serializer("features", "feature_values", check_fields=False)
    def serialize_maps(self, value, info):
        if value is None:
            return None
        return {
            key: item.model_dump(mode=info.mode) if isinstance(item, ProfileModel) else item
            for key, item in value.items()
        }
