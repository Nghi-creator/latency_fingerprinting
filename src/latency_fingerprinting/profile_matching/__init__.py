"""N8 provisional matching, offline evaluation and immutable standalone roots."""

from .models import ProfileEvaluationResult, ProfileMatchResult
from .policy import ProfileMatchPolicy

__all__ = ["ProfileMatchPolicy", "ProfileMatchResult", "ProfileEvaluationResult"]


def match_profile_snapshot(
    directory,
    snapshot,
    policy,
    *,
    query_entry_id,
    expected_split_id=None,
    expected_dataset_content_hash=None,
):
    from .operations import match_profile_snapshot as match

    return match(
        directory,
        snapshot,
        policy,
        query_entry_id=query_entry_id,
        expected_split_id=expected_split_id,
        expected_dataset_content_hash=expected_dataset_content_hash,
    )


def evaluate_profile_snapshot(
    directory,
    snapshot,
    policy,
    *,
    mode,
    expected_split_id=None,
    expected_dataset_content_hash=None,
):
    from .operations import evaluate_profile_snapshot as evaluate

    return evaluate(
        directory,
        snapshot,
        policy,
        mode=mode,
        expected_split_id=expected_split_id,
        expected_dataset_content_hash=expected_dataset_content_hash,
    )


__all__ += ["match_profile_snapshot", "evaluate_profile_snapshot"]
