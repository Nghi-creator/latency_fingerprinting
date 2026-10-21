"""Explicit immutable N7 revisions; linked fitting always inspects actual N6 files."""

from ..analytical.policy_release import payload_hash
from .evidence import InputSelection, SelectionCounts
from .lifecycle import LifecycleReview
from .policy import ProfilePolicy
from .reconstruction import reconstruct
from .selection import selection_reasons
from .snapshot import ProfileSnapshot


def _seal(payload):
    digest = payload_hash(
        {k: v for k, v in payload.items() if k not in ("snapshot_id", "content_hash")}
    )
    return ProfileSnapshot.model_validate(
        {**payload, "snapshot_id": "profile-snapshot-" + digest[7:], "content_hash": digest}
    )


def _draft(policy):
    return dict(
        schema_version="profile-snapshot-v1",
        method_release="n7-profile-statistics-v1",
        policy=policy.model_dump(mode="json"),
        source_report=None,
        inputs=[],
        profiles=[],
        counts={name: 0 for name in SelectionCounts.model_fields},
        lifecycle=dict(
            state="created",
            operation="create",
            parent_snapshot_id=None,
            replacement_snapshot_id=None,
            reason_code="draft",
            review=None,
        ),
        assurance="software_provisional_external_reviews_not_authenticated",
    )


def create_profile_snapshot(policy):
    """Return an empty approved-policy draft; no files or measurements are read."""
    try:
        return _seal(_draft(ProfilePolicy.model_validate(policy)))
    except (ValueError, TypeError, OverflowError):
        raise ValueError("invalid_profile_snapshot") from None


def _inspect_dataset(directory, **anchors):
    # Lazy to keep importing models independent of N2/N3 inspector import cycles.
    from ..calibration.inspection import _inspect_calibration_snapshot

    return _inspect_calibration_snapshot(directory, **anchors)


def _build_profile_snapshot(
    directory, policy, *, parent=None, expected_split_id=None, expected_dataset_content_hash=None
):
    """Return snapshot plus the actual pinned N6 root identity for output protection."""
    policy = ProfilePolicy.model_validate(policy)
    if parent is not None:
        parent = ProfileSnapshot.model_validate(parent)
        if parent.lifecycle.state == "superseded" or (
            parent.lifecycle.state == "created" and parent.policy != policy
        ):
            raise ValueError("invalid profile build parent")
    inspected, origin = _inspect_dataset(
        directory,
        expected_split_id=expected_split_id,
        expected_dataset_content_hash=expected_dataset_content_hash,
    )
    reasons, _ = selection_reasons(inspected.report.entries)
    declarations = {e.entry_id: e for e in inspected.dataset.entries}
    records = {a.artifact_id: a.record for a in inspected.artifacts}
    inputs = []
    for entry in inspected.report.entries:
        codes = reasons[entry.entry_id]
        values = None
        if not codes:
            # Do not touch .features/.observation on any unselected artifact.
            record = records[declarations[entry.entry_id].artifact_id]
            if (
                record.policy.content_hash != policy.response_policy_hash
                or record.observation.degraded_window.registry.model_dump(mode="json")
                != policy.registry.model_dump(mode="json")
            ):
                raise ValueError("profile source registry/policy mismatch")
            values = {
                name: record.features[name].normalized_value
                if record.features[name].state == "eligible"
                else None
                for name in policy.feature_names
            }
        inputs.append(
            InputSelection.model_validate(
                dict(
                    entry_id=entry.entry_id,
                    selected=not codes,
                    reason_codes=codes,
                    feature_values=values,
                )
            )
        )
    profiles, counts = reconstruct(inspected.report, inputs, policy.content_hash)
    supported = any(p["state"] == "provisional" for p in profiles)
    payload = _draft(policy)
    payload.update(
        source_report=inspected.report.model_dump(mode="json"),
        inputs=[item.model_dump(mode="json") for item in inputs],
        profiles=profiles,
        counts=counts,
        lifecycle=dict(
            state="provisional" if supported else "rejected",
            operation="build",
            parent_snapshot_id=parent.snapshot_id if parent is not None else None,
            replacement_snapshot_id=None,
            reason_code="supported_profiles" if supported else "no_supported_profiles",
            review=None,
        ),
    )
    return _seal(payload), origin


def build_profile_snapshot(
    directory, policy, *, parent=None, expected_split_id=None, expected_dataset_content_hash=None
):
    """Inspect bounded N6 artifacts; fit only selected training source-group votes."""
    try:
        return _build_profile_snapshot(
            directory,
            policy,
            parent=parent,
            expected_split_id=expected_split_id,
            expected_dataset_content_hash=expected_dataset_content_hash,
        )[0]
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError("invalid_profile_build") from None


def transition_profile_snapshot(snapshot, *, operation, reason_code, review, replacement=None):
    """Withdraw/supersede an exact parent without altering its evidence or statistics."""
    try:
        parent = ProfileSnapshot.model_validate(snapshot)
        review = LifecycleReview.model_validate(review)
        allowed = dict(
            mark_stale={"provisional", "rejected"},
            reject={"created", "provisional", "stale"},
            supersede={"provisional", "rejected", "stale"},
        )
        if (
            type(operation) is not str
            or operation not in allowed
            or parent.lifecycle.state not in allowed[operation]
        ):
            raise ValueError("disallowed profile transition")
        if parent.source_report is None and operation != "reject":
            raise ValueError("unbuilt draft may only be rejected or rebuilt")
        if operation == "supersede":
            replacement = ProfileSnapshot.model_validate(replacement)
            if (
                replacement.lifecycle.state != "provisional"
                or replacement.snapshot_id == parent.snapshot_id
            ):
                raise ValueError("replacement must be a distinct provisional snapshot")
        elif replacement is not None:
            raise ValueError("unexpected replacement")
        replacement_id = replacement.snapshot_id if replacement is not None else None
        payload = parent.model_dump(mode="json")
        payload["lifecycle"] = dict(
            state=dict(mark_stale="stale", reject="rejected", supersede="superseded")[operation],
            operation=operation,
            parent_snapshot_id=parent.snapshot_id,
            replacement_snapshot_id=replacement_id,
            reason_code=reason_code,
            review=review.model_dump(mode="json"),
        )
        return _seal(payload)
    except (ValueError, TypeError, KeyError, OverflowError):
        raise ValueError("invalid_profile_snapshot") from None
