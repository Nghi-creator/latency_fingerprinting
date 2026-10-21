"""Strict standalone snapshot reconstruction; actual artifact linking is a separate gate."""

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import Field, model_validator

from ..calibration.contracts import Hash, check_identity, check_json_size, unique_order
from ..calibration.report import CalibrationReport
from .contracts import ProfileModel, SnapshotID
from .evidence import Candidate, InputSelection, SelectionCounts
from .lifecycle import Lifecycle
from .policy import ProfilePolicy
from .reconstruction import reconstruct


class ProfileSnapshot(ProfileModel):
    schema_version: Literal["profile-snapshot-v1"]
    method_release: Literal["n7-profile-statistics-v1"]
    snapshot_id: SnapshotID
    content_hash: Hash
    policy: ProfilePolicy
    source_report: CalibrationReport | None
    inputs: Annotated[tuple[InputSelection, ...], Field(max_length=256)]
    profiles: Annotated[tuple[Candidate, ...], Field(max_length=256)]
    counts: SelectionCounts
    lifecycle: Lifecycle
    assurance: Literal["software_provisional_external_reviews_not_authenticated"]

    @model_validator(mode="before")
    @classmethod
    def global_reference_budget(cls, value):
        def field(obj, key, default=None):
            if isinstance(obj, Mapping):
                return obj.get(key, default)
            return getattr(obj, key, default) if isinstance(obj, ProfileModel) else default

        inputs, profiles = field(value, "inputs", ()), field(value, "profiles", ())
        if (
            not isinstance(inputs, (list, tuple))
            or not isinstance(profiles, (list, tuple))
            or max(len(inputs), len(profiles)) > 256
        ):
            raise ValueError("profile top-level collection exceeds bound")
        limit = 22 * sum(field(item, "selected") is True for item in inputs)
        group_records = entry_references = 0
        for profile in profiles:
            features = field(profile, "features", {})
            if not isinstance(features, Mapping) or len(features) > 22:
                raise ValueError("profile feature map exceeds bound")
            for feature in features.values():
                rows = field(feature, "group_values", ())
                if not isinstance(rows, (list, tuple)) or len(rows) > 256:
                    raise ValueError("profile group collection exceeds bound")
                group_records += len(rows)
                if group_records > limit:
                    raise ValueError("global profile group/reference budget exceeded")
                for row in rows:
                    references = field(row, "entry_ids", ())
                    if not isinstance(references, (list, tuple)) or len(references) > 256:
                        raise ValueError("profile entry-reference collection exceeds bound")
                    entry_references += len(references)
                    if entry_references > limit:
                        raise ValueError("global profile group/reference budget exceeded")
        return value

    @model_validator(mode="after")
    def consistency(self):
        unique_order(self.inputs, lambda item: item.entry_id)
        unique_order(self.profiles, lambda item: (item.partition_id, item.label))
        if self.source_report is None:
            if (
                self.inputs
                or self.profiles
                or any(self.counts.model_dump().values())
                or self.lifecycle.operation not in ("create", "reject")
            ):
                raise ValueError("unbuilt draft cannot invent source evidence")
        else:
            if self.lifecycle.operation == "create":
                raise ValueError("created draft cannot contain acquired evidence")
            expected, counts = reconstruct(
                self.source_report, self.inputs, self.policy.content_hash
            )
            if [
                item.model_dump(mode="json") for item in self.profiles
            ] != expected or self.counts.model_dump() != counts:
                raise ValueError("profile snapshot statistics/counts do not reconstruct")
            if self.lifecycle.operation == "build":
                state = (
                    "provisional"
                    if any(p.state == "provisional" for p in self.profiles)
                    else "rejected"
                )
                if self.lifecycle.state != state:
                    raise ValueError("built lifecycle disagrees with supported candidates")
        if self.snapshot_id in (
            self.lifecycle.parent_snapshot_id,
            self.lifecycle.replacement_snapshot_id,
        ):
            raise ValueError("snapshot cannot reference itself")
        digest = check_identity(
            self, "snapshot_id", "profile-snapshot-", ("snapshot_id", "content_hash")
        )
        if self.content_hash != digest:
            raise ValueError("profile snapshot content hash mismatch")
        check_json_size(self)
        return self
