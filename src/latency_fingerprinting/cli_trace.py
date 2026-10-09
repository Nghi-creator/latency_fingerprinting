"""Additive standalone N4 trace commands, with atomic output and fixed errors."""

from pathlib import Path

from .observability.bundle import ingest_trace_bundle
from .observability.input import read_trace_record
from .observability.output import write_trace_output
from .observability.reconstruct import reconstruct_trace
from .pipeline import canonical_json


def _ingest_trace(args):
    try:
        trace = ingest_trace_bundle(args.bundle)
        write_trace_output(args.output, canonical_json(trace).encode("utf-8"))
    except (OSError, ValueError):
        raise ValueError("ingest-trace: invalid_input_or_output") from None


def _inspect_trace(args):
    try:
        summary = reconstruct_trace(read_trace_record(args.trace))
        write_trace_output(args.output, canonical_json(summary).encode("utf-8"))
    except (OSError, ValueError):
        raise ValueError("inspect-trace: invalid_input_or_output") from None


def register_trace_commands(subparsers):
    parser = subparsers.add_parser("ingest-trace", help="adopt a standalone v1 stage trace")
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.set_defaults(handler=_ingest_trace)
    inspect = subparsers.add_parser("inspect-trace", help="reconstruct same-domain v1 stage timing")
    inspect.add_argument("--trace", type=Path, required=True)
    inspect.add_argument("--output", type=Path, required=True)
    inspect.set_defaults(handler=_inspect_trace)
