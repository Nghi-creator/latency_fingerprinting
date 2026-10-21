"""Immutable selected input vectors and reconstructable provisional profile statistics."""

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import Field, StrictBool, model_validator

from ..calibration.contracts import Alias, Count, GroupID, Label, PartitionID, unique_order
from .arithmetic import candidate_support, feature_statistics, ratio
from .contracts import (
    CANDIDATE_REASONS,
    FEATURE_REASONS,
    SELECTION_REASONS,
    FeatureCount,
    FeatureName,
    Finite,
    ProfileID,
    ProfileModel,
)


class Ratio(ProfileModel):
    numerator: Count
    denominator: Count
    value: Annotated[Finite, Field(ge=0, le=1)] | None

    @model_validator(mode="after")
    def reconstruct(self):
        if self.model_dump() != ratio(self.numerator, self.denominator):
            raise ValueError("profile ratio does not reconstruct")
        return self


class InputSelection(ProfileModel):
    entry_id: Alias
    selected: StrictBool
    reason_codes: Annotated[tuple[Literal[*SELECTION_REASONS], ...], Field(max_length=7)]
    feature_values: (
        Annotated[Mapping[FeatureName, Finite | None], Field(min_length=22, max_length=22)] | None
    )

    @model_validator(mode="after")
    def consistency(self):
        unique_order(self.reason_codes, SELECTION_REASONS.index)
        if self.selected != (not self.reason_codes) or self.selected != (
            self.feature_values is not None
        ):
            raise ValueError("selected input/reasons/values disagree")
        return self


class GroupValue(ProfileModel):
    group_id: GroupID
    entry_ids: Annotated[tuple[Alias, ...], Field(min_length=1, max_length=256)]
    median: Finite

    @model_validator(mode="after")
    def ordered_entries(self):
        unique_order(self.entry_ids, lambda item: item)
        return self


class FeatureStatistics(ProfileModel):
    state: Literal["supported", "excluded"]
    reason_codes: Annotated[tuple[Literal[*FEATURE_REASONS], ...], Field(max_length=4)]
    weight: Annotated[Finite, Field(ge=0, le=1)]
    group_values: Annotated[tuple[GroupValue, ...], Field(max_length=256)]
    contributing_groups: Count
    availability: Ratio
    center: Finite | None
    dispersion: Annotated[Finite, Field(ge=0)] | None

    @model_validator(mode="after")
    def reconstruct(self):
        unique_order(self.group_values, lambda group: group.group_id)
        expected = feature_statistics(
            [group.median for group in self.group_values], self.availability.denominator
        )
        if self.model_dump(mode="json", exclude={"group_values"}) != expected:
            raise ValueError("feature statistics do not reconstruct")
        return self


class Candidate(ProfileModel):
    profile_id: ProfileID
    partition_id: PartitionID
    label: Label
    state: Literal["provisional", "rejected"]
    reason_codes: Annotated[tuple[Literal[*CANDIDATE_REASONS], ...], Field(max_length=3)]
    training_group_ids: Annotated[tuple[GroupID, ...], Field(max_length=256)]
    selected_entry_ids: Annotated[tuple[Alias, ...], Field(max_length=256)]
    features: Annotated[
        Mapping[FeatureName, FeatureStatistics], Field(min_length=22, max_length=22)
    ]
    active_feature_count: FeatureCount
    active_feature_coverage: Ratio

    @model_validator(mode="after")
    def reconstruct(self):
        unique_order(self.training_group_ids, lambda item: item)
        unique_order(self.selected_entry_ids, lambda item: item)
        groups, entries = set(self.training_group_ids), set(self.selected_entry_ids)
        for feature in self.features.values():
            if feature.availability.denominator != len(groups) or any(
                row.group_id not in groups or not set(row.entry_ids).issubset(entries)
                for row in feature.group_values
            ):
                raise ValueError("feature source inventory disagrees with candidate")
        expected = candidate_support(
            len(groups), sum(f.state == "supported" for f in self.features.values())
        )
        if any(self.model_dump(mode="json")[key] != value for key, value in expected.items()):
            raise ValueError("candidate support does not reconstruct")
        return self


class SelectionCounts(ProfileModel):
    retained_entries: Count
    selected_entries: Count
    excluded_entries: Count
    selected_groups: Count
    baseline_entries: Count
    missing_entries: Count
    heldout_response_entries: Count
    mixed_label_groups: Count
