"""Deterministic JSON Schema generation for the P0 contract roots."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import TypeAlias

from pydantic import BaseModel

from .models import Fingerprint, MatchResult, ObservationRecord

SchemaModel: TypeAlias = type[BaseModel]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA_DIRECTORY = PROJECT_ROOT / "schemas"

SCHEMA_MODELS: Mapping[str, SchemaModel] = {
    "observation-v1.schema.json": ObservationRecord,
    "fingerprint-v1.schema.json": Fingerprint,
    "match-result-v1.schema.json": MatchResult,
}


def render_schema(model: SchemaModel) -> str:
    """Return one canonical, newline-terminated JSON Schema document."""

    schema = model.model_json_schema(by_alias=True)
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def rendered_schemas() -> dict[str, str]:
    """Return every P0 root schema keyed by its checked-in filename."""

    return {filename: render_schema(model) for filename, model in SCHEMA_MODELS.items()}


def export_schemas(output_directory: Path = DEFAULT_SCHEMA_DIRECTORY) -> tuple[Path, ...]:
    """Write all generated schemas and return their paths in stable order."""

    output_directory.mkdir(parents=True, exist_ok=True)
    schemas = rendered_schemas()
    paths = tuple(output_directory / filename for filename in sorted(schemas))
    for path in paths:
        path.write_text(schemas[path.name], encoding="utf-8")
    return paths


def schema_drift(output_directory: Path = DEFAULT_SCHEMA_DIRECTORY) -> dict[Path, str]:
    """Return files whose contents differ from the current Pydantic models."""

    drift: dict[Path, str] = {}
    for filename, expected in rendered_schemas().items():
        path = output_directory / filename
        if not path.is_file() or path.read_text(encoding="utf-8") != expected:
            drift[path] = expected
    return drift
