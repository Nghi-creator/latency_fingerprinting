"""Bounded linked N8 commands with pinned input protection and private atomic output."""

from pathlib import Path

from ..analytical.policy_release import canonical_payload_bytes
from ..observability.output import write_trace_output
from ..profiles.commands import _Operands
from ..profiles.snapshot import ProfileSnapshot
from .operations import _evaluate_profile_snapshot, _match_profile_snapshot
from .policy import ProfileMatchPolicy


def register_profile_matching_commands(subparsers):
    for name in ("match-profiles", "evaluate-profiles"):
        parser = subparsers.add_parser(
            name, help="inspect N6 evidence for provisional profile comparison"
        )
        for argument in ("directory", "snapshot", "policy", "output"):
            parser.add_argument("--" + argument, type=Path, required=True)
        parser.add_argument("--expected-split-id")
        parser.add_argument("--expected-dataset-content-hash")
        if name == "match-profiles":
            parser.add_argument("--query-entry-id", required=True)
        else:
            parser.add_argument(
                "--mode",
                choices=("validation", "final_test", "leave_training_group_out"),
                required=True,
            )
        parser.set_defaults(profile_matching_command=name, handler=_run)


def _run(args):
    operands = _Operands()
    try:
        snapshot = operands.read(args.snapshot, ProfileSnapshot)
        policy = operands.read(args.policy, ProfileMatchPolicy)
        kwargs = dict(
            expected_split_id=args.expected_split_id,
            expected_dataset_content_hash=args.expected_dataset_content_hash,
        )
        if args.profile_matching_command == "match-profiles":
            result, origin, files = _match_profile_snapshot(
                args.directory, snapshot, policy, query_entry_id=args.query_entry_id, **kwargs
            )
        else:
            result, origin, files = _evaluate_profile_snapshot(
                args.directory, snapshot, policy, mode=args.mode, **kwargs
            )
        operands.directories.add(origin)
        operands.files.update(files)
        write_trace_output(
            args.output,
            canonical_payload_bytes(result.model_dump(mode="json")),
            target_guard=operands.protect_target,
        )
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError(args.profile_matching_command + ": invalid_input_or_output") from None
