"""Protected private N9 commands; reuse pinned operands and atomic output."""

from pathlib import Path

from ..analytical.policy_release import canonical_payload_bytes
from ..observability.output import write_trace_output
from ..profiles.commands import _Operands
from .models import PassiveBaseline, PassiveReplay
from .operations import _build_passive_baseline, _replay_passive_gate
from .policy import PassiveGatePolicy


def register_passive_commands(subparsers):
    for name in ("build-passive-baseline", "replay-passive-gate"):
        parser = subparsers.add_parser(name, help="inspect N6 evidence for offline passive gating")
        for argument in ("directory", "policy", "output"):
            parser.add_argument("--" + argument, type=Path, required=True)
        if name == "replay-passive-gate":
            for argument in ("baseline", "replay"):
                parser.add_argument("--" + argument, type=Path, required=True)
        parser.add_argument("--expected-split-id")
        parser.add_argument("--expected-dataset-content-hash")
        parser.set_defaults(passive_command=name, handler=_run)


def _run(args):
    operands = _Operands()
    try:
        policy = operands.read(args.policy, PassiveGatePolicy)
        anchors = dict(
            expected_split_id=args.expected_split_id,
            expected_dataset_content_hash=args.expected_dataset_content_hash,
        )
        if args.passive_command == "build-passive-baseline":
            result, origin, files = _build_passive_baseline(args.directory, policy, **anchors)
        else:
            result, origin, files = _replay_passive_gate(
                args.directory,
                operands.read(args.baseline, PassiveBaseline),
                operands.read(args.replay, PassiveReplay),
                policy,
                **anchors,
            )
        operands.directories.add(origin)
        operands.files.update(files)
        write_trace_output(
            args.output,
            canonical_payload_bytes(result.model_dump(mode="json")),
            target_guard=operands.protect_target,
        )
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError(args.passive_command + ": invalid_input_or_output") from None
