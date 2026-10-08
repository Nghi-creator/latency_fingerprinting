"""Offline P0 analysis, N1 diagnostics and additive N2/N3 contract validation."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from .adapters.pixelated_bundle import ingest_pixelated_bundle
from .adapters.pixelated_observation_v2 import ingest_pixelated_v2
from .fingerprints import load_fingerprint_repository
from .json_io import load_json_file, load_model_file
from .matcher import match_observation
from .measurement.metric_registry import (
    DEFAULT_METRIC_REGISTRY_PATH,
    METRIC_REGISTRY_VERSION,
    export_metric_registry,
    metric_registry_drift,
)
from .measurement_inspection import inspect_measurements, render_measurement_inspection
from .models import (
    ANALYTICAL_RESPONSE_V2_SCHEMA_VERSION,
    FEATURE_POLICY_SCHEMA_VERSION,
    FINGERPRINT_SCHEMA_VERSION,
    FINGERPRINT_V2_SCHEMA_VERSION,
    MATCH_RESULT_SCHEMA_VERSION,
    METRIC_REGISTRY_SCHEMA_VERSION,
    OBSERVATION_SCHEMA_VERSION,
    OBSERVATION_V2_SCHEMA_VERSION,
    OBSERVATION_WINDOW_V2_SCHEMA_VERSION,
    AnalyticalResponseV2,
    ContextKey,
    FeaturePolicyV1,
    Fingerprint,
    FingerprintV2,
    MatchResult,
    MetricRegistry,
    ObservationRecord,
    ObservationRecordV2,
    ObservationWindow,
    ObservationWindowV2,
    Probe,
    ProvenanceKind,
    WindowPhase,
)
from .pipeline import build_observation_record, canonical_json
from .schemas import DEFAULT_SCHEMA_DIRECTORY, SCHEMA_MODELS, export_schemas, schema_drift

CommandHandler = Callable[[argparse.Namespace], None]
ModelT = TypeVar("ModelT", bound=BaseModel)

ROOT_MODELS: dict[str, type[BaseModel]] = {
    FINGERPRINT_V2_SCHEMA_VERSION: FingerprintV2,
    FEATURE_POLICY_SCHEMA_VERSION: FeaturePolicyV1,
    ANALYTICAL_RESPONSE_V2_SCHEMA_VERSION: AnalyticalResponseV2,
    OBSERVATION_SCHEMA_VERSION: ObservationRecord,
    FINGERPRINT_SCHEMA_VERSION: Fingerprint,
    MATCH_RESULT_SCHEMA_VERSION: MatchResult,
    METRIC_REGISTRY_SCHEMA_VERSION: MetricRegistry,
    OBSERVATION_V2_SCHEMA_VERSION: ObservationRecordV2,
    OBSERVATION_WINDOW_V2_SCHEMA_VERSION: ObservationWindowV2,
}


def _write_json(payload: Any) -> None:
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def _load_model(path: Path, model: type[ModelT]) -> ModelT:
    return load_model_file(path, model)


def _validate(args: argparse.Namespace) -> None:
    path: Path = args.path
    payload = load_json_file(path)
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


def _export_metric_registry(args: argparse.Namespace) -> None:
    output: Path = args.output
    if args.check:
        if metric_registry_drift(output):
            raise ValueError(f"metric registry drift detected: {output.name}")
        _write_json(
            {
                "checked": output.name,
                "registryVersion": METRIC_REGISTRY_VERSION,
                "status": "current",
            }
        )
        return
    path = export_metric_registry(output)
    _write_json(
        {"exported": path.name, "registryVersion": METRIC_REGISTRY_VERSION, "status": "written"}
    )


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


def _ingest_pixelated_v2(args: argparse.Namespace) -> None:
    window = ingest_pixelated_v2(
        args.bundle,
        context=_load_model(args.context, ContextKey),
        phase=WindowPhase(args.phase),
        comparison_case_id=args.comparison_case_id,
        provenance=ProvenanceKind(args.provenance),
        confounder_codes=args.confounder_code,
    )
    sys.stdout.write(canonical_json(window))


def _inspect_measurements(args: argparse.Namespace) -> None:
    report = inspect_measurements(
        args.bundle,
        context=_load_model(args.context, ContextKey),
        phase=WindowPhase(args.phase),
        comparison_case_id=args.comparison_case_id,
    )
    sys.stdout.write(render_measurement_inspection(report))


def build_parser() -> argparse.ArgumentParser:
    """Build the public command parser without performing any I/O."""

    parser = argparse.ArgumentParser(
        prog="latency-fingerprint",
        description="Offline P0 analysis, N1 diagnostics and additive N2 adoption.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser(
        "validate", help="validate a P0/N2/N3 root record or N1 registry"
    )
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

    registry = subparsers.add_parser(
        "export-metric-registry", help="write or check the canonical N1 metric registry"
    )
    registry.add_argument("--output", type=Path, default=DEFAULT_METRIC_REGISTRY_PATH)
    registry.add_argument("--check", action="store_true", help="report drift without writing files")
    registry.set_defaults(handler=_export_metric_registry)

    inspection = subparsers.add_parser(
        "inspect-measurements", help="compare P0 and N1 measurements in an offline shadow report"
    )
    inspection.add_argument("bundle", type=Path)
    inspection.add_argument("--context", type=Path, required=True)
    inspection.add_argument(
        "--phase", choices=[phase.value for phase in WindowPhase], required=True
    )
    inspection.add_argument("--comparison-case-id", required=True)
    inspection.set_defaults(handler=_inspect_measurements)

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

    adopt = subparsers.add_parser(
        "ingest-pixelated-v2", help="adopt raw evidence as an additive v2 window"
    )
    adopt.add_argument("bundle", type=Path)
    adopt.add_argument("--context", type=Path, required=True)
    adopt.add_argument("--phase", choices=[phase.value for phase in WindowPhase], required=True)
    adopt.add_argument("--comparison-case-id", required=True)
    adopt.add_argument(
        "--provenance", choices=["controlled_real", "organic_real"], default="controlled_real"
    )
    adopt.add_argument(
        "--confounder-code",
        action="append",
        default=[],
        choices=["composite_profile_change", "other_setting_change", "operator_declared"],
    )
    adopt.set_defaults(handler=_ingest_pixelated_v2)

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
