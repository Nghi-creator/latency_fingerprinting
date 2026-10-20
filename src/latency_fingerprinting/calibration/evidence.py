"""Immutable declarations; these models never open artifacts or authenticate reviews."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .contracts import (
    ARCHIVE_BYTES,
    JSON_BYTES,
    Alias,
    CalibrationModel,
    GroupID,
    Hash,
    InputKind,
    Label,
    OriginalID,
    Role,
    SplitID,
    SplitMode,
    check_identity,
    unique_order,
)


class CalibrationArtifact(CalibrationModel):
    artifact_id: Alias
    kind: Literal["analytical_response", "observation_window", "experiment_bundle"]
    file_name: Annotated[str, Field(strict=True, max_length=135)]
    sha256: Hash
    bytes: Annotated[int, Field(strict=True, ge=1, le=ARCHIVE_BYTES)]

    @model_validator(mode="after")
    def consistency(self):
        archive = self.kind == "experiment_bundle"
        suffix = ".tar.gz" if archive else ".json"
        if self.file_name != self.artifact_id + suffix:
            raise ValueError("artifact filename must follow its identity and kind")
        if self.bytes > (ARCHIVE_BYTES if archive else JSON_BYTES):
            raise ValueError("artifact exceeds kind byte limit")
        return self


class CalibrationSource(CalibrationModel):
    source_id: Alias
    acquisition_namespace: Alias
    run_id: OriginalID
    session_id: Alias
    independence_group: Alias
    source_type: Literal["pixelated_bundle", "synthetic_series"]
    source_content_hash: Hash
    bundle_schema_version: Literal["1", "2"] | None
    review_id: Alias | None

    @model_validator(mode="after")
    def consistency(self):
        if (self.source_type == "pixelated_bundle") != (self.bundle_schema_version is not None):
            raise ValueError("source type and bundle schema disagree")
        return self

    def original_identity(self):
        return (
            self.acquisition_namespace,
            self.run_id,
            self.source_type,
            self.source_content_hash,
            self.bundle_schema_version,
        )


class SourceEdge(CalibrationModel):
    parent_source_id: Alias
    child_source_id: Alias

    @model_validator(mode="after")
    def consistency(self):
        if self.parent_source_id == self.child_source_id:
            raise ValueError("self derivation is invalid")
        return self


class EvidenceReview(CalibrationModel):
    review_id: Alias
    reviewer_id: Alias
    kind: Literal["independence", "label_binding", "split_freeze"]
    # Derived split IDs are also safe strings within the alias length limit.
    subject_ids: Annotated[tuple[Alias, ...], Field(min_length=1, max_length=256)]
    outcome: Literal["confirmed", "rejected", "uncertain"]
    evidence_sha256: Hash

    @model_validator(mode="after")
    def consistency(self):
        unique_order(self.subject_ids, lambda item: item)
        if self.kind != "independence" and len(self.subject_ids) != 1:
            raise ValueError("label/freeze reviews require exactly one subject")
        return self


class SourceBinding(CalibrationModel):
    window_role: Literal["degraded", "relief", "healthy"]
    source_id: Alias
    window_id: OriginalID


class CalibrationEntry(CalibrationModel):
    entry_id: Alias
    input_kind: InputKind
    artifact_id: Alias | None
    source_bindings: Annotated[tuple[SourceBinding, ...], Field(max_length=2)]
    label: Label | None
    label_basis: Literal["controlled_effect", "external_confirmation", "declared_only", "unknown"]
    label_review_id: Alias | None
    experiment_artifact_id: Alias | None
    experiment_phase: Literal["healthy", "degraded"] | None

    @model_validator(mode="after")
    def consistency(self):
        missing = self.input_kind == "missing"
        roles = {"response": ("degraded", "relief"), "healthy_window": ("healthy",), "missing": ()}
        if (self.artifact_id is None) != missing or tuple(
            binding.window_role for binding in self.source_bindings
        ) != roles[self.input_kind]:
            raise ValueError("entry input and source roles disagree")
        if missing and (
            self.label is not None
            or self.label_basis != "unknown"
            or self.label_review_id is not None
        ):
            raise ValueError("missing entry cannot claim label evidence")
        if (self.label is None) != (self.label_basis == "unknown"):
            raise ValueError("label and support basis disagree")
        if self.input_kind == "healthy_window" and self.label not in (None, "healthy"):
            raise ValueError("healthy window cannot carry a fault label")
        controlled = self.label_basis == "controlled_effect"
        if controlled:
            expected_phase = "healthy" if self.input_kind == "healthy_window" else "degraded"
            if self.experiment_artifact_id is None or self.experiment_phase != expected_phase:
                raise ValueError("controlled support requires an experiment and matching phase")
        elif self.experiment_artifact_id is not None or self.experiment_phase is not None:
            raise ValueError("uncontrolled support cannot borrow an experiment")
        return self


class SplitAssignment(CalibrationModel):
    group_id: GroupID
    role: Role


class SplitDeclaration(CalibrationModel):
    split_id: SplitID
    mode: SplitMode
    protocol_sha256: Hash
    assignments: Annotated[tuple[SplitAssignment, ...], Field(max_length=256)]
    freeze_review_id: Alias | None

    @model_validator(mode="after")
    def consistency(self):
        unique_order(self.assignments, lambda item: item.group_id)
        if self.mode == "retrospective" and self.freeze_review_id is not None:
            raise ValueError("retrospective split cannot claim a freeze review")
        check_identity(self, "split_id", "split-", ("split_id", "freeze_review_id"))
        return self
