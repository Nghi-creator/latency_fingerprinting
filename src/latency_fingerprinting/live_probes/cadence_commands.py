"""Protected offline cadence import; no runtime or network control."""

from pathlib import Path

from ..analytical.policy_release import canonical_payload_bytes
from ..observability.output import write_trace_output
from ..profiles.commands import _Operands
from .cadence import CadenceWorkerReport, import_cadence_worker_report


def register_cadence_command(subparsers):
    parser = subparsers.add_parser(
        "import-cadence-report", help="seal isolated cadence observations"
    )
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    for name in ("acquisition-id", "producer-revision", "image-hash", "source-manifest-hash"):
        parser.add_argument("--" + name, required=True)
    parser.set_defaults(handler=_run)


def _run(args):
    operands = _Operands()
    try:
        report = operands.read(args.report, CadenceWorkerReport)
        evidence = import_cadence_worker_report(
            report,
            acquisition_id=args.acquisition_id,
            producer_revision=args.producer_revision,
            image_hash=args.image_hash,
            source_manifest_hash=args.source_manifest_hash,
        )
        write_trace_output(
            args.output,
            canonical_payload_bytes(evidence.model_dump(mode="json")),
            target_guard=operands.protect_target,
        )
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError("import-cadence-report: invalid_input_or_output") from None
