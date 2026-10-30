"""Self-consistent inspection records, without asserting external evidence truth."""

from typing import Annotated, Literal

from pydantic import Field, StrictBool, model_validator

from ..analytical.policy_release import payload_hash
from .contracts import (
    REASONS,
    Alias,
    CalibrationModel,
    Count,
    DatasetID,
    GroupID,
    Hash,
    InputKind,
    Label,
    PartitionID,
    Reason,
    Release,
    ReportID,
    ReviewState,
    Role,
    SplitID,
    SplitMode,
    check_identity,
    check_json_size,
    unique_order,
)
from .evidence import CalibrationArtifact


class GroupInspection(CalibrationModel):
    group_id: GroupID
    source_ids: Annotated[tuple[Alias, ...], Field(min_length=1, max_length=256)]
    role: Role
    independence_review_state: ReviewState

    @model_validator(mode="after")
    def consistency(self):
        unique_order(self.source_ids, lambda item: item)
        digest = payload_hash({"source_ids": list(self.source_ids)})
        if self.group_id != "group-" + digest[7:]:
            raise ValueError("source group identity mismatch")
        return self


class EntryInspection(CalibrationModel):
    entry_id: Alias
    input_kind: InputKind
    group_id: GroupID | None
    role: Role | None
    partition_id: PartitionID | None
    label: Label | None
    eligible: StrictBool
    reason_codes: Annotated[tuple[Reason, ...], Field(max_length=len(REASONS))]
    representative_entry_id: Alias
    eligible_feature_count: Annotated[int, Field(strict=True, ge=0, le=22)] | None

    @model_validator(mode="after")
    def consistency(self):
        unique_order(self.reason_codes, REASONS.index)
        if self.eligible != (not self.reason_codes):
            raise ValueError("eligibility must agree with exclusion reasons")
        if self.input_kind == "missing":
            if (
                self.group_id is not None
                or self.role is not None
                or self.partition_id is not None
                or self.label is not None
                or self.eligible_feature_count is not None
                or self.reason_codes != ("missing_measurements",)
                or self.representative_entry_id != self.entry_id
            ):
                raise ValueError("missing measurements cannot invent evidence")
            return self
        if self.group_id is None or self.role is None or self.partition_id is None:
            raise ValueError("measured evidence requires group, role and partition")
        if "missing_measurements" in self.reason_codes:
            raise ValueError("measured entry cannot claim missing input")
        response = self.input_kind == "response"
        if response != (self.eligible_feature_count is not None):
            raise ValueError("only responses retain analytical feature counts")
        if not response and (
            self.label not in (None, "healthy")
            or {"confounded_response", "insufficient_response_features"} & set(self.reason_codes)
        ):
            raise ValueError("healthy baseline cannot claim response evidence")
        if response and (
            "baseline_invalid" in self.reason_codes
            or ("confounded_response" in self.reason_codes and self.eligible_feature_count != 0)
            or (
                self.eligible_feature_count < 17
                and "insufficient_response_features" not in self.reason_codes
            )
        ):
            raise ValueError("response feature support contradicts eligibility")
        if self.label is None and "label_unverified" not in self.reason_codes:
            raise ValueError("missing label requires unverified support")
        if (self.role == "engineering") != ("engineering_only" in self.reason_codes):
            raise ValueError("engineering role cannot qualify for calibration")
        if (self.representative_entry_id != self.entry_id) != (
            "duplicate_evidence" in self.reason_codes
        ):
            raise ValueError("duplicate evidence requires an explicit representative")
        return self


class EvidenceCounts(CalibrationModel):
    retained_entries: Count
    eligible_entries: Count
    excluded_entries: Count
    retained_groups: Count
    eligible_groups: Count

    @model_validator(mode="after")
    def consistency(self):
        if (
            self.eligible_entries + self.excluded_entries != self.retained_entries
            or self.eligible_groups > self.retained_groups
            or self.eligible_groups > self.eligible_entries
            or self.retained_groups > self.retained_entries
        ):
            raise ValueError("evidence counts disagree")
        return self


class RoleCounts(CalibrationModel):
    engineering: EvidenceCounts
    training: EvidenceCounts
    validation: EvidenceCounts
    final_test: EvidenceCounts


class CalibrationCounts(EvidenceCounts):
    by_role: RoleCounts


class PartitionInspection(CalibrationModel):
    partition_id: PartitionID
    input_kind: Literal["response", "healthy_window"]
    retained_entries: Count
    eligible_entries: Count
    eligible_groups: Count

    @model_validator(mode="after")
    def consistency(self):
        if (
            self.eligible_entries > self.retained_entries
            or self.eligible_groups > self.eligible_entries
        ):
            raise ValueError("partition counts disagree")
        return self


class CalibrationReport(CalibrationModel):
    schema_version: Literal["calibration-report-v1"]
    method_release: Release
    report_id: ReportID
    dataset_id: DatasetID
    dataset_content_hash: Hash
    split_id: SplitID
    split_mode: SplitMode
    artifact_receipts: Annotated[tuple[CalibrationArtifact, ...], Field(max_length=256)]
    groups: Annotated[tuple[GroupInspection, ...], Field(max_length=256)]
    entries: Annotated[tuple[EntryInspection, ...], Field(min_length=1, max_length=256)]
    partitions: Annotated[tuple[PartitionInspection, ...], Field(max_length=256)]
    counts: CalibrationCounts
    assurance: Literal["external_review_declarations_not_authenticated"]

    @model_validator(mode="after")
    def consistency(self):
        for items, field in (
            (self.artifact_receipts, "artifact_id"),
            (self.groups, "group_id"),
            (self.entries, "entry_id"),
            (self.partitions, "partition_id"),
        ):
            unique_order(items, lambda item, field=field: getattr(item, field))
        if self.dataset_id != "dataset-" + self.dataset_content_hash[7:]:
            raise ValueError("report dataset identity and hash disagree")
        groups = {group.group_id: group for group in self.groups}
        sources = [source for group in self.groups for source in group.source_ids]
        if len(sources) > 256 or len(set(sources)) != len(sources):
            raise ValueError("report source groups overlap or exceed bounds")
        entries = {entry.entry_id: entry for entry in self.entries}
        measured = [entry for entry in self.entries if entry.input_kind != "missing"]
        if {entry.group_id for entry in measured} != set(groups):
            raise ValueError("report group inventory disagrees with entries")
        freeze_states = {"split_unverified" in entry.reason_codes for entry in measured}
        if len(freeze_states) > 1 or (self.split_mode == "retrospective" and True in freeze_states):
            raise ValueError("split freeze evidence must be consistent across the report")
        duplicate_labels = {}
        for entry in measured:
            group = groups[entry.group_id]
            if entry.role != group.role:
                raise ValueError("report entry split disagrees with its group")
            if (self.split_mode == "retrospective") != (
                "retrospective_split" in entry.reason_codes
            ):
                raise ValueError("retrospective evidence cannot qualify for calibration")
            if (group.independence_review_state != "confirmed") != (
                "independence_unverified" in entry.reason_codes
            ):
                raise ValueError("entry independence contradicts group review")
            representative = entries.get(entry.representative_entry_id)
            if representative is None or (
                representative.representative_entry_id != representative.entry_id
                or representative.entry_id > entry.entry_id
                or (
                    representative.input_kind,
                    representative.group_id,
                    representative.partition_id,
                    representative.eligible_feature_count,
                )
                != (
                    entry.input_kind,
                    entry.group_id,
                    entry.partition_id,
                    entry.eligible_feature_count,
                )
            ):
                raise ValueError("invalid duplicate representative")
            labels = duplicate_labels.setdefault(entry.representative_entry_id, set())
            if entry.label is not None:
                labels.add(entry.label)
                if len(labels) > 1:
                    raise ValueError("duplicate content has conflicting nonnull labels")
        expected = _counts(self.entries, self.groups)
        if self.counts.model_dump(exclude={"by_role"}) != expected:
            raise ValueError("global evidence counts do not reconstruct")
        for role in type(self.counts.by_role).model_fields:
            expected = _counts(
                [entry for entry in self.entries if entry.role == role],
                [group for group in self.groups if group.role == role],
            )
            if getattr(self.counts.by_role, role).model_dump() != expected:
                raise ValueError("role evidence counts do not reconstruct")
        partition_ids = {entry.partition_id for entry in measured}
        if partition_ids != {partition.partition_id for partition in self.partitions}:
            raise ValueError("partition inventory does not reconstruct")
        for partition in self.partitions:
            items = [entry for entry in measured if entry.partition_id == partition.partition_id]
            eligible = [entry for entry in items if entry.eligible]
            if (
                any(entry.input_kind != partition.input_kind for entry in items)
                or partition.retained_entries != len(items)
                or partition.eligible_entries != len(eligible)
                or partition.eligible_groups != len({entry.group_id for entry in eligible})
            ):
                raise ValueError("partition counts/kind do not reconstruct")
        check_identity(self, "report_id", "calibration-report-", ("report_id",))
        check_json_size(self)
        return self


def _counts(entries, groups):
    eligible = [entry for entry in entries if entry.eligible]
    return dict(
        retained_entries=len(entries),
        eligible_entries=len(eligible),
        excluded_entries=len(entries) - len(eligible),
        retained_groups=len(groups),
        eligible_groups=len({entry.group_id for entry in eligible}),
    )
