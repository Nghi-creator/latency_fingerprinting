"""N9 immutable models, pure replay and read-only linked source verification."""

from .models import PassiveBaseline, PassiveGateResult, PassiveReplay
from .policy import PassiveGatePolicy
from .pure import create_passive_replay, evaluate_passive_replay, fit_passive_baseline

__all__ = [
    "PassiveGatePolicy",
    "PassiveBaseline",
    "PassiveReplay",
    "PassiveGateResult",
    "fit_passive_baseline",
    "create_passive_replay",
    "evaluate_passive_replay",
]


def build_passive_baseline(
    directory, policy, *, expected_split_id=None, expected_dataset_content_hash=None
):
    from .operations import build_passive_baseline as build

    return build(
        directory,
        policy,
        expected_split_id=expected_split_id,
        expected_dataset_content_hash=expected_dataset_content_hash,
    )


def replay_passive_gate(
    directory,
    baseline,
    replay,
    policy,
    *,
    expected_split_id=None,
    expected_dataset_content_hash=None,
):
    from .operations import replay_passive_gate as evaluate

    return evaluate(
        directory,
        baseline,
        replay,
        policy,
        expected_split_id=expected_split_id,
        expected_dataset_content_hash=expected_dataset_content_hash,
    )


__all__ += ["build_passive_baseline", "replay_passive_gate"]
