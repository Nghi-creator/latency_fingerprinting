"""Current-revision lifecycle shape, without authenticating unseen parent history."""

from typing import Literal

from pydantic import model_validator

from ..calibration.contracts import Alias, Hash
from .contracts import ProfileModel, SnapshotID

Reason = Literal[
    "draft",
    "supported_profiles",
    "no_supported_profiles",
    "method_changed",
    "context_changed",
    "policy_changed",
    "external_review",
    "operator_rejected",
    "evidence_rejected",
    "replacement_selected",
]


class LifecycleReview(ProfileModel):
    actor_id: Alias
    subject_snapshot_id: SnapshotID
    replacement_snapshot_id: SnapshotID | None
    reason_code: Reason
    evidence_sha256: Hash


class Lifecycle(ProfileModel):
    state: Literal["created", "provisional", "rejected", "stale", "superseded"]
    operation: Literal["create", "build", "mark_stale", "reject", "supersede"]
    parent_snapshot_id: SnapshotID | None
    replacement_snapshot_id: SnapshotID | None
    reason_code: Reason
    review: LifecycleReview | None

    @model_validator(mode="after")
    def shape(self):
        if self.operation == "create":
            valid = (
                self.state == "created"
                and self.reason_code == "draft"
                and self.parent_snapshot_id is None
            )
        elif self.operation == "build":
            valid = (self.state, self.reason_code) in (
                ("provisional", "supported_profiles"),
                ("rejected", "no_supported_profiles"),
            )
        else:
            allowed = {
                "mark_stale": (
                    "stale",
                    {"method_changed", "context_changed", "policy_changed", "external_review"},
                ),
                "reject": ("rejected", {"operator_rejected", "evidence_rejected"}),
                "supersede": ("superseded", {"replacement_selected"}),
            }
            state, reasons = allowed[self.operation]
            valid = (
                self.state == state
                and self.reason_code in reasons
                and self.parent_snapshot_id is not None
            )
        if not valid:
            raise ValueError("invalid profile lifecycle shape")
        if self.operation in ("create", "build"):
            if self.review is not None or self.replacement_snapshot_id is not None:
                raise ValueError("create/build cannot borrow administrative reviews")
        elif self.review is None or (
            self.review.subject_snapshot_id != self.parent_snapshot_id
            or self.review.reason_code != self.reason_code
            or self.review.replacement_snapshot_id != self.replacement_snapshot_id
        ):
            raise ValueError("lifecycle review ownership mismatch")
        if (self.operation == "supersede") != (self.replacement_snapshot_id is not None):
            raise ValueError("supersession requires exactly one replacement")
        if (
            self.replacement_snapshot_id is not None
            and self.replacement_snapshot_id == self.parent_snapshot_id
        ):
            raise ValueError("parent cannot replace itself")
        return self
