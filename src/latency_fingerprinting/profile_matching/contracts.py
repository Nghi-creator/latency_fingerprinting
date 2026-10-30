"""Closed N8 vocabularies, immutable maps and pre-validation aggregate budgets."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_serializer, field_validator

from ..calibration.contracts import exact_string
from ..profiles.contracts import ProfileModel
from ..profiles.policy_release import FEATURE_NAMES

RELEASE = "n8-profile-matching-v1"
LABELS = ("healthy", "host_contention", "render_capture_slowdown")
ASSURANCE = "software_provisional_external_reviews_not_authenticated"
CandidateID = exact_string(r"profile-(?:fold-)?[a-f0-9]{64}")
FoldID = exact_string(r"profile-fold-[a-f0-9]{64}")
RefitID = exact_string(r"profile-refit-[a-f0-9]{64}")
Mode = Literal["validation", "final_test", "leave_training_group_out"]
DECISION_REASONS = (
    "snapshot_unavailable",
    "missing_measurements",
    "baseline_only",
    "not_held_out",
    "n6_excluded",
    "duplicate_evidence",
    "no_compatible_profiles",
    "insufficient_common_features",
    "insufficient_common_coverage",
    "no_competing_label",
    "distance_exceeded",
    "ambiguous_labels",
)
CANDIDATE_REASONS = (
    "snapshot_unavailable",
    "query_unavailable",
    "partition_mismatch",
    "profile_rejected",
    "source_overlap",
    "insufficient_common_features",
    "insufficient_common_coverage",
)
FEATURE_REASONS = ("query_feature_missing", "profile_feature_excluded", "not_common_feature")
Nonnegative = Annotated[float, Field(strict=True, allow_inf_nan=False, ge=0)]


class MatchModel(ProfileModel):
    collection_limits = {
        **ProfileModel.collection_limits,
        "reason_codes": 12,
        "candidates": 256,
        "ranked_profile_ids": 256,
        "common_feature_names": 22,
        "decisions": 256,
        "refits": 64,
        "group_outcomes": 256,
        "representative_entry_ids": 256,
        "query_roles": 2,
        "rank_order": 3,
        "modes": 3,
        "truth_invalid_reasons": 3,
        "truth_reason_codes": 2,
        "prediction_reason_codes": 2,
    }

    @field_validator("*", mode="after")
    @classmethod
    def normalize_zero(cls, value, info):
        return (
            0.0
            if info.field_name != "query_value" and isinstance(value, float) and value == 0
            else value
        )

    @field_validator("query_feature_values", check_fields=False, mode="before")
    @classmethod
    def query_map(cls, value):
        if value is not None:
            if (
                not isinstance(value, Mapping)
                or len(value) != 22
                or set(value) != set(FEATURE_NAMES)
            ):
                raise ValueError("query requires the exact feature map")
            return dict(value)
        return value

    @field_validator("query_feature_values", "confusion_matrix", check_fields=False, mode="after")
    @classmethod
    def immutable_maps(cls, value):
        def freeze(item):
            return (
                MappingProxyType({k: freeze(v) for k, v in sorted(item.items())})
                if isinstance(item, Mapping)
                else item
            )

        return freeze(value)

    @field_serializer("query_feature_values", "confusion_matrix", check_fields=False)
    def serialize_query_maps(self, value, info):
        def thaw(item):
            return {k: thaw(v) for k, v in item.items()} if isinstance(item, Mapping) else item

        return thaw(value)


def field(value, name, default=None):
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default) if isinstance(value, BaseModel) else default


def sequence(value, maximum):
    if not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValueError("N8 collection exceeds bound")
    return value


def result_budget(value):
    """Bound all additive N8 trees before nested models or arithmetic are constructed."""
    matrix = field(value, "confusion_matrix")
    if matrix is not None and (
        not isinstance(matrix, Mapping)
        or len(matrix) > 4
        or any(not isinstance(row, Mapping) or len(row) > 4 for row in matrix.values())
    ):
        raise ValueError("N8 confusion matrix exceeds bound")
    decisions = field(value, "decisions", None)
    decisions = [field(value, "decision")] if decisions is None else sequence(decisions, 256)
    candidates = feature_rows = 0
    for decision in decisions:
        rows = sequence(field(decision, "candidates", ()), 256)
        candidates += len(rows)
        if candidates > 4096:
            raise ValueError("N8 global candidate budget exceeded")
        for row in rows:
            features = field(row, "features")
            if features is not None:
                if not isinstance(features, Mapping) or len(features) > 22:
                    raise ValueError("N8 feature map exceeds bound")
                feature_rows += len(features)
                if feature_rows > 5632:
                    raise ValueError("N8 global feature budget exceeded")
    refit_candidates = group_rows = references = 0
    for refit in sequence(field(value, "refits", ()), 64):
        inputs = field(refit, "inputs")
        if inputs is not None:
            sequence(inputs, 256)
        profiles = field(refit, "profiles")
        for profile in sequence(() if profiles is None else profiles, 256):
            refit_candidates += 1
            if refit_candidates > 256:
                raise ValueError("N8 global refit candidate budget exceeded")
            features = field(profile, "features", {})
            if not isinstance(features, Mapping) or len(features) > 22:
                raise ValueError("N8 refit feature map exceeds bound")
            for feature in features.values():
                rows = sequence(field(feature, "group_values", ()), 256)
                group_rows += len(rows)
                if group_rows > 32768:
                    raise ValueError("N8 global refit group budget exceeded")
                for row in rows:
                    references += len(sequence(field(row, "entry_ids", ()), 256))
                    if references > 32768:
                        raise ValueError("N8 global refit reference budget exceeded")
    return value
