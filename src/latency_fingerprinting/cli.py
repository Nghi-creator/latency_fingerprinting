"""Command-line interface for the offline P0 analytical workflow."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from .adapters.pixelated_bundle import ingest_pixelated_bundle
from .fingerprints import load_fingerprint_repository
from .matcher import match_observation
from .models import (
    FINGERPRINT_SCHEMA_VERSION,
    MATCH_RESULT_SCHEMA_VERSION,
    OBSERVATION_SCHEMA_VERSION,
    ContextKey,
    Fingerprint,
    MatchResult,
    ObservationRecord,
    ObservationWindow,
    Probe,
    ProvenanceKind,
    WindowPhase,
)
from .pipeline import build_observation_record, canonical_json
from .schemas import DEFAULT_SCHEMA_DIRECTORY, SCHEMA_MODELS, export_schemas, schema_drift

CommandHandler = Callable[[argparse.Namespace], None]
ModelT = TypeVar("ModelT", bound=BaseModel)

ROOT_MODELS: dict[str, type[BaseModel]] = {
    OBSERVATION_SCHEMA_VERSION: ObservationRecord,
    FINGERPRINT_SCHEMA_VERSION: Fingerprint,
    MATCH_RESULT_SCHEMA_VERSION: MatchResult,
}


def _write_json(payload: Any) -> None:
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def _load_model(path: Path, model: type[ModelT]) -> ModelT:
    return model.model_validate_json(path.read_text(encoding="utf-8"))


def _validate(args: argparse.Namespace) -> None:
    path: Path = args.path
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON root must be an object")

    schema_version = payload.get("schemaVersion")
    if not isinstance(schema_version, str):
        raise ValueError("JSON root requires a string schemaVersion")
    model = ROOT_MODELS.get(schema_version)
    if model is None:
        supported = ", ".join(sorted(ROOT_MODELS))
        raise ValueError(
            f"unsupported schemaVersion {schema_version!r}; expected one of: {supported}"
        )

    sys.stdout.write(canonical_json(model.model_validate(payload)))


def _export_schemas(args: argparse.Namespace) -> None:
    output: Path = args.output
    if args.check:
        drift = schema_drift(output)
        if drift:
            names = ", ".join(sorted(path.name for path in drift))
            raise ValueError(f"schema drift detected: {names}")
        _write_json(
            {
                "checked": sorted(SCHEMA_MODELS),
                "status": "current",
            }
        )
        return

    paths = export_schemas(output)
    _write_json({"exported": [path.name for path in paths], "status": "written"})


def _build_response(args: argparse.Namespace) -> None:
    degraded = _load_model(args.degraded, ObservationWindow)
    relief = _load_model(args.relief, ObservationWindow)
    probe = _load_model(args.probe, Probe)
    observation = build_observation_record(degraded, relief, probe)
    sys.stdout.write(canonical_json(observation))


def _ingest_pixelated(args: argparse.Namespace) -> None:
    context = _load_model(args.context, ContextKey)
    window = ingest_pixelated_bundle(
        args.bundle,
        phase=WindowPhase(args.phase),
        comparison_case_id=args.comparison_case_id,
        context=context,
        provenance=ProvenanceKind(args.provenance),
        confounders=args.confounder,
    )
    sys.stdout.write(canonical_json(window))


def _match(args: argparse.Namespace) -> None:
    observation = _load_model(args.observation, ObservationRecord)
    repository = load_fingerprint_repository(
        args.fingerprints,
        strict=not args.allow_rejected_fingerprints,
    )
    if repository.rejections:
        print(
            f"warning: ignored {len(repository.rejections)} rejected fingerprint file(s)",
            file=sys.stderr,
        )
    result = match_observation(observation, repository)
    sys.stdout.write(canonical_json(result))


def build_parser() -> argparse.ArgumentParser:
    """Build the public command parser without performing any I/O."""

    parser = argparse.ArgumentParser(
        prog="latency-fingerprint",
        description="Validate and run the offline P0 latency-fingerprinting pipeline.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate a P0 root record")
    validate.add_argument("path", type=Path)
    validate.set_defaults(handler=_validate)

    schemas = subparsers.add_parser("export-schemas", help="write or check JSON Schemas")
    schemas.add_argument("--output", type=Path, default=DEFAULT_SCHEMA_DIRECTORY)
    schemas.add_argument(
        "--check",
        action="store_true",
        help="report drift without writing any files",
    )
    schemas.set_defaults(handler=_export_schemas)

    response = subparsers.add_parser(
        "build-response",
        help="build an observation from a comparable degraded/relief pair",
    )
    response.add_argument("--degraded", type=Path, required=True)
    response.add_argument("--relief", type=Path, required=True)
    response.add_argument("--probe", type=Path, required=True)
    response.set_defaults(handler=_build_response)

    ingest = subparsers.add_parser(
        "ingest-pixelated",
        help="translate a Pixelated research bundle into an observation window",
    )
    ingest.add_argument("bundle", type=Path)
    ingest.add_argument("--phase", choices=[phase.value for phase in WindowPhase], required=True)
    ingest.add_argument("--comparison-case-id", required=True)
    ingest.add_argument(
        "--context",
        type=Path,
        required=True,
        help="explicit core ContextKey JSON shared by comparable runs",
    )
    ingest.add_argument(
        "--provenance",
        choices=[kind.value for kind in ProvenanceKind],
        default=ProvenanceKind.CONTROLLED_REAL.value,
    )
    ingest.add_argument(
        "--confounder",
        action="append",
        default=[],
        help="record one known confounder; may be repeated",
    )
    ingest.set_defaults(handler=_ingest_pixelated)

    match = subparsers.add_parser("match", help="match an observation to fingerprints")
    match.add_argument("observation", type=Path)
    match.add_argument("--fingerprints", type=Path, required=True)
    match.add_argument(
        "--allow-rejected-fingerprints",
        action="store_true",
        help="ignore rejected fingerprint files and match against valid records",
    )
    match.set_defaults(handler=_match)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one CLI command and return a process exit code."""

    parser = build_parser()
    args = parser.parse_args(argv)
    handler: CommandHandler = args.handler
    try:
        handler(args)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


__all__ = ["build_parser", "main"]
