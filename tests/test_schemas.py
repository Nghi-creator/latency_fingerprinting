"""Regression tests for checked-in P0 JSON Schemas."""

from __future__ import annotations

import json

from latency_fingerprinting.schemas import SCHEMA_MODELS, render_schema, schema_drift


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
