"""Protected offline evaluation and single-window extraction commands."""

from collections.abc import Mapping
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from ..adapters.pixelated_source_local import ingest_pixelated_source_local
from ..adapters.pixelated_windows import WindowBounds, ingest_pixelated_windows
from ..analytical.policy_release import canonical_payload_bytes
from ..calibration.contracts import Alias
from ..models import ContextKey
from ..observability.json import decode_trace_json
from ..observability.output import write_trace_output
from ..profiles.commands import _Operands
from .contracts import EvaluationManifest, EvaluationReport
from .runner import _run_evaluation


class _PathMap(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paths: Annotated[
        Mapping[Alias, Annotated[str, Field(strict=True, min_length=1)]], Field(max_length=4096)
    ]

    @classmethod
    def model_validate_json(cls, raw, **kwargs):
        return cls.model_validate(decode_trace_json(raw), **kwargs)


class _Context:
    @staticmethod
    def model_validate_json(raw):
        return ContextKey.model_validate(decode_trace_json(raw))


def register_evaluation_commands(subparsers):
    parser = subparsers.add_parser(
        "evaluate-study", help="reconstruct an explicit offline study ledger"
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--operands", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-report", type=Path)
    parser.set_defaults(handler=_evaluate)
    window = subparsers.add_parser(
        "ingest-pixelated-window", help="extract an exact-anchor 1–10 s raw window"
    )
    for name in ("bundle", "context", "output"):
        window.add_argument("--" + name, type=Path, required=True)
    window.add_argument(
        "--phase", choices=("baseline", "degraded", "relief", "recovery"), required=True
    )
    window.add_argument("--comparison-case-id", required=True)
    window.add_argument("--start-ms", type=int, required=True)
    window.add_argument("--end-ms", type=int, required=True)
    window.add_argument(
        "--provenance", choices=("controlled_real", "organic_real"), default="controlled_real"
    )
    window.add_argument(
        "--confounder-code",
        action="append",
        default=[],
        choices=("composite_profile_change", "other_setting_change", "operator_declared"),
    )
    window.set_defaults(handler=_window)
    local = subparsers.add_parser(
        "ingest-pixelated-source-local",
        help="adopt a declared source-local stable phase",
    )
    for name in ("bundle", "context", "output"):
        local.add_argument("--" + name, type=Path, required=True)
    local.add_argument(
        "--phase", choices=("baseline", "degraded", "relief", "recovery"), required=True
    )
    local.add_argument("--comparison-case-id", required=True)
    local.add_argument(
        "--provenance", choices=("controlled_real", "organic_real"), default="controlled_real"
    )
    local.add_argument(
        "--confounder-code",
        action="append",
        default=[],
        choices=("composite_profile_change", "other_setting_change", "operator_declared"),
    )
    local.set_defaults(handler=_window, source_local=True)


def _evaluate(args):
    operands = _Operands()
    try:
        manifest = operands.read(args.manifest, EvaluationManifest)
        paths = dict(operands.read(args.operands, _PathMap).paths)
        supplied = (
            operands.read(args.verify_report, EvaluationReport) if args.verify_report else None
        )
        execution, inputs = _run_evaluation(manifest, paths)
        if supplied is not None and supplied.model_dump(mode="json") != execution.report.model_dump(
            mode="json"
        ):
            raise ValueError("retained report differs from reconstruction")

        def guard(parent, name, metadata):
            operands.protect_target(parent, name, metadata)
            inputs.protect_target(parent, name, metadata)

        write_trace_output(
            args.output,
            canonical_payload_bytes(execution.report.model_dump(mode="json")),
            target_guard=guard,
        )
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError("evaluate-study: invalid_input_or_output") from None


def _window(args):
    # Snapshot an archive into private storage so output cannot overwrite an input
    # whose path was renamed during raw adoption. Directory bundles are SDK-only.
    import tempfile

    from .inputs import FileOperands

    operands = FileOperands()
    source_local = getattr(args, "source_local", False)
    command = "ingest-pixelated-source-local" if source_local else "ingest-pixelated-window"
    try:
        context = operands.read(args.context, _Context)
        raw = operands._archive(args.bundle, 64 * 1024 * 1024)
        with tempfile.TemporaryDirectory(prefix="n11-window-") as temporary:
            path = Path(temporary).resolve() / "bundle.tar"
            path.write_bytes(raw)
            arguments = dict(
                context=context,
                phase=args.phase,
                comparison_case_id=args.comparison_case_id,
                provenance=args.provenance,
                confounder_codes=args.confounder_code,
            )
            if source_local:
                result = ingest_pixelated_source_local(path, **arguments)
            else:
                result = ingest_pixelated_windows(
                    path,
                    windows=[WindowBounds(start_ms=args.start_ms, end_ms=args.end_ms)],
                    **arguments,
                )[0]
        write_trace_output(
            args.output,
            canonical_payload_bytes(result.model_dump(mode="json", by_alias=True)),
            target_guard=operands.protect_target,
        )
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError(f"{command}: invalid_input_or_output") from None
