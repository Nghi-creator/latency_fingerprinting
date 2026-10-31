"""Additive experiment inspection with private atomic output and fixed failures."""

from pathlib import Path

from .json_io import canonical_json
from .observability.output import write_trace_output
from .scenarios.inspect import inspect_experiment_bundle


def _inspect(args):
    try:
        inspected = inspect_experiment_bundle(args.bundle)
        write_trace_output(args.output, canonical_json(inspected.result).encode("utf-8"))
    except (OSError, ValueError):
        raise ValueError("inspect-experiment: invalid_input_or_output") from None


def register_experiment_commands(subparsers):
    parser = subparsers.add_parser(
        "inspect-experiment", help="verify linked v1/v2 experiment evidence"
    )
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.set_defaults(handler=_inspect)
