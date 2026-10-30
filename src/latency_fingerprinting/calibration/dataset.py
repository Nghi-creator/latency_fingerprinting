"""Intrinsic dataset validation, independent of files and source-component inference."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from ..analytical.policy_release import canonical_payload_bytes
from .contracts import (
    AGGREGATE_BYTES,
    CalibrationModel,
    DatasetID,
    Hash,
    Release,
    check_identity,
    check_json_size,
    unique_order,
)
from .evidence import (
    CalibrationArtifact,
    CalibrationEntry,
    CalibrationSource,
    EvidenceReview,
    SourceEdge,
    SplitDeclaration,
)


class CalibrationDataset(CalibrationModel):
    schema_version: Literal["calibration-dataset-v1"]
    method_release: Release
    dataset_id: DatasetID
    content_hash: Hash
    artifacts: Annotated[tuple[CalibrationArtifact, ...], Field(max_length=256)]
    sources: Annotated[tuple[CalibrationSource, ...], Field(max_length=256)]
    derivations: Annotated[tuple[SourceEdge, ...], Field(max_length=512)]
    reviews: Annotated[tuple[EvidenceReview, ...], Field(max_length=256)]
    split: SplitDeclaration
    entries: Annotated[tuple[CalibrationEntry, ...], Field(min_length=1, max_length=256)]

    @model_validator(mode="after")
    def consistency(self):
        for items, key in (
            (self.artifacts, "artifact_id"),
            (self.sources, "source_id"),
            (self.reviews, "review_id"),
            (self.entries, "entry_id"),
        ):
            unique_order(items, lambda item, key=key: getattr(item, key))
        unique_order(self.derivations, lambda edge: (edge.parent_source_id, edge.child_source_id))
        artifacts = {a.artifact_id: a for a in self.artifacts}
        sources = {s.source_id: s for s in self.sources}
        reviews = {r.review_id: r for r in self.reviews}
        entries = {e.entry_id: e for e in self.entries}
        used_artifacts, used_sources, used_reviews = set(), set(), set()

        def review(identifier, kind, subject):
            if identifier is None:
                return
            record = reviews.get(identifier)
            if record is None or record.kind != kind or subject not in record.subject_ids:
                raise ValueError("review kind or subject mismatch")
            used_reviews.add(identifier)

        for source in self.sources:
            review(source.review_id, "independence", source.source_id)
        for record in self.reviews:
            valid_subjects = (
                sources
                if record.kind == "independence"
                else entries
                if record.kind == "label_binding"
                else {self.split.split_id}
            )
            if not set(record.subject_ids).issubset(valid_subjects):
                raise ValueError("review has nonexistent subjects")
        review(self.split.freeze_review_id, "split_freeze", self.split.split_id)
        for entry in self.entries:
            if entry.artifact_id is not None:
                expected = (
                    "analytical_response"
                    if entry.input_kind == "response"
                    else "observation_window"
                )
                self._artifact_kind(artifacts, entry.artifact_id, expected)
                used_artifacts.add(entry.artifact_id)
            if entry.experiment_artifact_id is not None:
                self._artifact_kind(artifacts, entry.experiment_artifact_id, "experiment_bundle")
                used_artifacts.add(entry.experiment_artifact_id)
            for binding in entry.source_bindings:
                if binding.source_id not in sources:
                    raise ValueError("source binding is dangling")
                used_sources.add(binding.source_id)
            review(entry.label_review_id, "label_binding", entry.entry_id)
        # Retain referenced ancestor/descendant lineage, without inferring components here.
        for edge in self.derivations:
            if edge.parent_source_id not in sources or edge.child_source_id not in sources:
                raise ValueError("source edge is dangling")
        # A directed cycle is intrinsically impossible derivation, even before
        # the later source-component/split inspector is applied.
        children = {identifier: [] for identifier in sources}
        incoming = dict.fromkeys(sources, 0)
        for edge in self.derivations:
            children[edge.parent_source_id].append(edge.child_source_id)
            incoming[edge.child_source_id] += 1
        ready = [identifier for identifier, count in incoming.items() if count == 0]
        visited = 0
        while ready:
            identifier = ready.pop()
            visited += 1
            for child in children[identifier]:
                incoming[child] -= 1
                if incoming[child] == 0:
                    ready.append(child)
        if visited != len(sources):
            raise ValueError("source derivation cycle")
        changed = True
        while changed:
            before = len(used_sources)
            for edge in self.derivations:
                if {edge.parent_source_id, edge.child_source_id} & used_sources:
                    used_sources.update((edge.parent_source_id, edge.child_source_id))
            changed = before != len(used_sources)
        if (
            used_sources != set(sources)
            or used_artifacts != set(artifacts)
            or used_reviews != set(reviews)
        ):
            raise ValueError("dataset inventory contains unreachable declarations")
        identities = {}
        for source in self.sources:
            declaration = (source.session_id, source.independence_group)
            previous = identities.setdefault(source.original_identity(), declaration)
            if previous != declaration:
                raise ValueError("source aliases contradict original identity")
        digest = check_identity(self, "dataset_id", "dataset-", ("dataset_id", "content_hash"))
        if self.content_hash != digest:
            raise ValueError("dataset content hash mismatch")
        check_json_size(self)
        if (
            len(canonical_payload_bytes(self.model_dump(mode="json")))
            + sum(item.bytes for item in self.artifacts)
            > AGGREGATE_BYTES
        ):
            raise ValueError("dataset declared aggregate exceeds byte limit")
        return self

    @staticmethod
    def _artifact_kind(artifacts, identifier, kind):
        if identifier not in artifacts or artifacts[identifier].kind != kind:
            raise ValueError("artifact reference or kind mismatch")
