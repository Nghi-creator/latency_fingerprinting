"""Additive standalone N4 trace commands, with atomic output and fixed errors."""

from pathlib import Path

from .observability.bundle import ingest_trace_bundle
from .observability.output import write_trace_output
from .pipeline import canonical_json


def _ingest_trace(args):
    try:
        trace = ingest_trace_bundle(args.bundle)
        write_trace_output(args.output, canonical_json(trace).encode("utf-8"))
    except (OSError, ValueError):
        raise ValueError("ingest-trace: invalid_input_or_output") from None


def register_trace_commands(subparsers):
    parser = subparsers.add_parser("ingest-trace", help="adopt a standalone v1 stage trace")
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.set_defaults(handler=_ingest_trace)
