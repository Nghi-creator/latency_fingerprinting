"""N7 policy, linked training-only profile builds and explicit immutable revisions."""

from .policy import ProfilePolicy
from .snapshot import ProfileSnapshot

__all__ = ["ProfilePolicy", "ProfileSnapshot"]


def create_profile_snapshot(policy):
    from .operations import create_profile_snapshot as create

    return create(policy)


def build_profile_snapshot(
    directory, policy, *, parent=None, expected_split_id=None, expected_dataset_content_hash=None
):
    from .operations import build_profile_snapshot as build

    return build(
        directory,
        policy,
        parent=parent,
        expected_split_id=expected_split_id,
        expected_dataset_content_hash=expected_dataset_content_hash,
    )


def transition_profile_snapshot(snapshot, *, operation, reason_code, review, replacement=None):
    from .operations import transition_profile_snapshot as transition

    return transition(
        snapshot,
        operation=operation,
        reason_code=reason_code,
        review=review,
        replacement=replacement,
    )


__all__ += ["create_profile_snapshot", "build_profile_snapshot", "transition_profile_snapshot"]
