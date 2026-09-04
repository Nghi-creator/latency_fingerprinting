"""Regression tests for checked-in P0 JSON Schemas."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from latency_fingerprinting.schemas import (
    SCHEMA_MODELS,
    export_schemas,
    render_schema,
    schema_drift,
)


def test_schema_generation_is_deterministic() -> None:
    for model in SCHEMA_MODELS.values():
        assert render_schema(model) == render_schema(model)


def test_checked_in_schemas_match_models() -> None:
    assert schema_drift() == {}


def test_root_schemas_use_contract_json_aliases() -> None:
    for model in SCHEMA_MODELS.values():
        schema = json.loads(render_schema(model))
        assert "schemaVersion" in schema["properties"]
        assert "contractVersion" in schema["properties"]


def test_schema_export_uses_sibling_atomic_replacements(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_replace = Path.replace
    replacements: list[tuple[Path, Path]] = []

    def recording_replace(source: Path, target: Path) -> Path:
        destination = Path(target)
        replacements.append((source, destination))
        return original_replace(source, destination)

    monkeypatch.setattr(Path, "replace", recording_replace)

    paths = export_schemas(tmp_path)

    assert len(replacements) == len(SCHEMA_MODELS)
    assert all(source.parent == destination.parent for source, destination in replacements)
    assert all(source != destination for source, destination in replacements)
    assert set(paths) == {destination for _, destination in replacements}
    assert list(tmp_path.glob(".*.tmp")) == []


def test_schema_export_cleans_temporary_file_when_replacement_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "fingerprint-v1.schema.json"
    target.write_text("existing\n", encoding="utf-8")

    def failing_replace(source: Path, destination: Path) -> Path:
        raise OSError("replacement failed")

    monkeypatch.setattr(Path, "replace", failing_replace)

    with pytest.raises(OSError, match="replacement failed"):
        export_schemas(tmp_path)

    assert target.read_text(encoding="utf-8") == "existing\n"
    assert list(tmp_path.glob(".*.tmp")) == []
