"""Canonical N1 semantics, exact artifact reproduction and safe CLI export/check."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as SchemaValidationError

from latency_fingerprinting.cli import main
from latency_fingerprinting.json_io import load_model_file
from latency_fingerprinting.measurement.metric_registry import (
    CANONICAL_METRIC_REGISTRY,
    DEFAULT_METRIC_REGISTRY_PATH,
    METRIC_REGISTRY_VERSION,
    build_metric_registry,
    export_metric_registry,
    get_metric_definition,
    metric_registry_drift,
    render_metric_registry,
)
from latency_fingerprinting.models import AggregationKind, MetricKind, MetricRegistry
from latency_fingerprinting.schemas import DEFAULT_SCHEMA_DIRECTORY

from .test_metric_inventory import ROOT, inventory_table


def test_canonical_registry_matches_each_reviewed_output_and_policy() -> None:
    registry = CANONICAL_METRIC_REGISTRY
    outputs = inventory_table("Proposed output inventory")
    mapping = {row["P0 feature"]: row for row in inventory_table("P0 mapping")}
    definitions = {definition.name: definition for definition in registry.definitions}
    assert len(definitions) == len(outputs) == 31
    assert set(definitions) == {output["proposed v2 feature"] for output in outputs}
    for output in outputs:
        definition = definitions[output["proposed v2 feature"]]
        p0 = mapping[output["P0 feature"]]
        assert definition.semantic_version == "1.0.0"
        assert definition.source == output["source"]
        assert definition.raw_fields == (output["raw field"],)
        assert definition.kind == output["metric kind"]
        assert definition.canonical_unit == output["canonical unit"]
        assert definition.primary_aggregation == output["primary aggregation"]
        assert definition.clock_basis == p0["clock basis"]
        assert definition.missing_data_policy == p0["gap policy"]
        assert definition.counter_reset_policy == (
            None if p0["reset policy"] == "none" else p0["reset policy"]
        )
        assert definition.non_negative
        assert definition.expected_cadence_ms is None
        assert definition.cadence_tolerance_ratio is None
        assert definition.counter_width_bits is None
        expected_aggregations = (
            {
                AggregationKind.MEDIAN,
                AggregationKind.MINIMUM,
                AggregationKind.MAXIMUM,
                AggregationKind.NEAREST_RANK_P95,
            }
            if definition.kind is MetricKind.GAUGE
            else {definition.primary_aggregation}
        )
        assert set(definition.available_aggregations) == expected_aggregations


def test_canonical_fields_belong_to_the_declared_fixture_source() -> None:
    fixture = ROOT / "tests/data/pixelated_bundle/valid-v2"
    browser = next(csv.DictReader((fixture / "stream-telemetry.csv").read_text().splitlines()))
    engine_rows = list(csv.DictReader((fixture / "engine-telemetry.csv").read_text().splitlines()))
    for definition in CANONICAL_METRIC_REGISTRY.definitions:
        rows = (
            [browser]
            if definition.source == "browser_webrtc"
            else [row for row in engine_rows if row["source"] == definition.source]
        )
        assert rows
        assert all(set(definition.raw_fields) <= row.keys() for row in rows)


def test_fixed_release_and_versioned_bytes_require_explicit_review_to_change() -> None:
    registry = build_metric_registry()
    assert registry == CANONICAL_METRIC_REGISTRY == build_metric_registry()
    assert registry.registry_version == METRIC_REGISTRY_VERSION == "latency-metrics-v2.0.0"
    assert registry.created_at == datetime(2026, 10, 6, tzinfo=UTC)
    # This release pin is deliberately independent of the checked-in artifact.
    # Changing source and regenerating the artifact cannot silently change v2.0.0.
    assert hashlib.sha256(render_metric_registry().encode()).hexdigest() == (
        "50329d193303c271194b28e9164ae8627dd257d7620174c5ab136ba209864884"
    )


def test_checked_in_registry_is_exact_and_model_valid() -> None:
    assert not metric_registry_drift()
    assert DEFAULT_METRIC_REGISTRY_PATH.read_bytes() == render_metric_registry().encode("utf-8")
    assert (
        load_model_file(DEFAULT_METRIC_REGISTRY_PATH, MetricRegistry) == CANONICAL_METRIC_REGISTRY
    )
    assert render_metric_registry() == render_metric_registry()


def test_registry_passes_its_checked_in_json_schema() -> None:
    schema = json.loads(
        (DEFAULT_SCHEMA_DIRECTORY / "metric-registry-v1.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    payload = json.loads(render_metric_registry())
    validator.validate(payload)
    payload["definitions"][0]["canonicalUnit"] = "unknown"
    with pytest.raises(SchemaValidationError):
        validator.validate(payload)


def test_lookup_accepts_registered_names_and_rejects_old_delta_names() -> None:
    for definition in CANONICAL_METRIC_REGISTRY.definitions:
        assert get_metric_definition(definition.name) is definition
    for name in ("client.frames_decoded_delta", "not.registered", "", None):
        with pytest.raises(ValueError):
            get_metric_definition(name)  # type: ignore[arg-type]


def test_registry_export_uses_atomic_replacement_and_preserves_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "registry.json"
    path.write_bytes(b"old\n")
    path.chmod(0o600)
    original_replace = Path.replace
    replacements = []

    def record_replace(source: Path, target: Path) -> Path:
        replacements.append((source, target))
        assert target.read_bytes() == b"old\n"
        assert source.read_bytes() == render_metric_registry().encode()
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", record_replace)
    assert export_metric_registry(path) == path
    assert len(replacements) == 1
    assert replacements[0][0].parent == path.parent
    assert replacements[0][0] != path
    assert path.stat().st_mode & 0o777 == 0o600
    assert not metric_registry_drift(path)
    assert list(tmp_path.glob(".*.tmp")) == []


def test_failed_export_preserves_artifact_and_cleans_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "registry.json"
    path.write_bytes(b"old\n")

    def fail_replace(source: Path, target: Path) -> Path:
        raise OSError("replacement failed")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError, match="replacement failed"):
        export_metric_registry(path)
    assert path.read_bytes() == b"old\n"
    assert list(tmp_path.glob(".*.tmp")) == []


@pytest.mark.parametrize("mode", ["changed", "same_size", "bom", "crlf", "invalid_utf8"])
def test_check_detects_byte_drift_without_touching_artifact(
    tmp_path: Path, mode: str, capsys: pytest.CaptureFixture[str]
) -> None:
    path = export_metric_registry(tmp_path / "registry.json")
    expected = path.read_bytes()
    content = {
        "changed": b"changed\n",
        "same_size": expected.replace(b'"gauge"', b'"xxxxx"'),
        "bom": b"\xef\xbb\xbf" + expected,
        "crlf": expected.replace(b"\n", b"\r\n"),
        "invalid_utf8": b"\xff" + expected[1:],
    }[mode]
    path.write_bytes(content)
    before = path.stat()
    assert main(["export-metric-registry", "--output", str(path), "--check"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "metric registry drift detected" in captured.err
    assert "Traceback" not in captured.err
    assert path.read_bytes() == content
    assert path.stat().st_mtime_ns == before.st_mtime_ns
    assert path.stat().st_mode == before.st_mode


def test_missing_check_does_not_create_directories(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "absent" / "registry.json"
    assert main(["export-metric-registry", "--output", str(path), "--check"]) == 1
    assert "drift detected" in capsys.readouterr().err
    assert not path.parent.exists()


def test_oversize_drift_is_detected_without_reading_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "registry.json"
    path.write_bytes(b"x" * (len(render_metric_registry().encode()) + 1))

    def fail_open(path: Path, *args: object, **kwargs: object) -> None:
        pytest.fail("a wrong-sized registry must not be read")

    monkeypatch.setattr(Path, "open", fail_open)
    assert metric_registry_drift(path)


def test_cli_export_check_and_validate_are_deterministic(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "nested" / "registry.json"
    assert main(["export-metric-registry", "--output", str(path)]) == 0
    exported = capsys.readouterr()
    assert exported.err == ""
    assert json.loads(exported.out) == {
        "exported": "registry.json",
        "registryVersion": METRIC_REGISTRY_VERSION,
        "status": "written",
    }
    before = path.stat()
    assert main(["export-metric-registry", "--output", str(path), "--check"]) == 0
    checked = capsys.readouterr()
    assert checked.err == ""
    assert json.loads(checked.out)["status"] == "current"
    assert path.stat().st_mtime_ns == before.st_mtime_ns
    for _ in range(2):
        assert main(["validate", str(path)]) == 0
        validated = capsys.readouterr()
        assert validated.err == ""
        assert validated.out == render_metric_registry()


def test_default_cli_check_targets_checked_in_artifact(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["export-metric-registry", "--check"]) == 0
    assert json.loads(capsys.readouterr().out)["checked"] == "metric-registry-v1.json"


def test_cli_reports_filesystem_failure_without_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    parent = tmp_path / "file"
    parent.write_text("not a directory", encoding="utf-8")
    assert main(["export-metric-registry", "--output", str(parent / "registry.json")]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "error:" in captured.err
    assert "Traceback" not in captured.err


def test_cli_registry_validation_retains_duplicate_safe_boundary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "registry.json"
    text = render_metric_registry().replace(
        '"registryVersion":', '"registryVersion": "fake", "registryVersion":'
    )
    path.write_text(text, encoding="utf-8")
    assert main(["validate", str(path)]) == 1
    captured = capsys.readouterr()
    assert "duplicate JSON object key" in captured.err
    assert "Traceback" not in captured.err
    assert captured.out == ""
