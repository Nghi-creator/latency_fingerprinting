"""Protected local custody and declaration inspection for integrated game reports."""

import json
import sys
from pathlib import Path

from ..analytical.policy_release import canonical_payload_bytes
from ..observability.output import write_trace_output
from ..profiles.commands import _Operands
from .integrated_game import (
    IntegratedGameRecord,
    import_integrated_game_cohort,
    inspect_integrated_game_record,
)
from .integrated_game_lifetimes import reconstruct_integrated_game_lifetimes
from .integrated_game_reconstruction import reconstruct_integrated_game_record


class _RawBytes:
    @staticmethod
    def model_validate_json(raw):
        return raw


def register_integrated_game_commands(subparsers):
    parser = subparsers.add_parser(
        "import-integrated-game-cohort", help="preserve integrated game engineering report bytes"
    )
    for name in ("report", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("acquisition-id", "producer-revision"):
        parser.add_argument("--" + name, required=True)
    parser.set_defaults(handler=_import)
    inspect = subparsers.add_parser(
        "inspect-integrated-game-record", help="inspect declarations without qualification"
    )
    inspect.add_argument("record", type=Path)
    inspect.set_defaults(handler=_inspect)
    reconstruct = subparsers.add_parser(
        "reconstruct-integrated-game-record", help="recompute supplied engineering observations"
    )
    reconstruct.add_argument("record", type=Path)
    reconstruct.add_argument(
        "--lifetimes", action="store_true", help="also compare lifetime/journal observations"
    )
    reconstruct.set_defaults(handler=_reconstruct)


def _import(args):
    operands = _Operands()
    try:
        record = import_integrated_game_cohort(
            operands.read(args.report, _RawBytes),
            acquisition_id=args.acquisition_id,
            producer_revision=args.producer_revision,
        )
        write_trace_output(
            args.output,
            canonical_payload_bytes(record.model_dump(mode="json")),
            target_guard=operands.protect_target,
        )
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError("import-integrated-game-cohort: invalid_input_or_output") from None


def _inspect(args):
    record = _Operands().read(args.record, IntegratedGameRecord)
    sys.stdout.write(json.dumps(inspect_integrated_game_record(record), sort_keys=True) + "\n")


def _reconstruct(args):
    record = _Operands().read(args.record, IntegratedGameRecord)
    operation = (
        reconstruct_integrated_game_lifetimes
        if args.lifetimes
        else reconstruct_integrated_game_record
    )
    sys.stdout.write(json.dumps(operation(record), sort_keys=True) + "\n")
