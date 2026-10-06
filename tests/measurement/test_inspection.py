"""Migration reports retain semantic boundaries, deterministic bytes and privacy."""

import csv
import json
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

from latency_fingerprinting import measurement_inspection as inspection
from latency_fingerprinting.adapters.pixelated_bundle import ingest_pixelated_bundle
from latency_fingerprinting.cli import main
from latency_fingerprinting.json_io import load_model_file
from latency_fingerprinting.measurement import P0_FEATURE_CONFIG
from latency_fingerprinting.measurement.metric_registry import CANONICAL_METRIC_REGISTRY
from latency_fingerprinting.models import (
    ContextKey,
    ObservationWindow,
    WindowPhase,
)

FIXTURES = Path(__file__).resolve().parents[1] / "data/pixelated_bundle"


def inspect(path=FIXTURES / "valid-v2", *, version="2"):
    return inspection.inspect_measurements(
        path,
        context=load_model_file(
            FIXTURES / f"context{'-v2' if version == '2' else ''}.json", ContextKey
        ),
        phase=WindowPhase.DEGRADED,
        comparison_case_id="controlled-case-001",
    )


def entries(report):
    return {entry["p0Feature"]: entry for entry in report["features"]}


def copy_bundle(tmp_path):
    path = tmp_path / "private-directory"
    shutil.copytree(FIXTURES / "valid-v2", path)
    return path


def edit_row(bundle, filename, index, **changes):
    path = bundle / filename
    with path.open(newline="") as file:
        reader = csv.DictReader(file)
        columns = reader.fieldnames
        rows = list(reader)
    rows[index].update(changes)
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def test_complete_reviewed_mapping_and_shadow_boundary():
    report = inspect()
    mapped = entries(report)
    assert set(mapped) == set(P0_FEATURE_CONFIG) == set(inspection.P0_TO_N1)
    assert sorted(
        output["definition"]["name"] for entry in mapped.values() for output in entry["outputs"]
    ) == sorted(definition.name for definition in CANONICAL_METRIC_REGISTRY.definitions)
    assert report["schemaVersion"] == "measurement-inspection-v1"
    assert report["matcherInput"] is False
    assert "not observation-v2" in report["notice"]
    assert report["p0Ingestion"] == "accepted"
    assert report["p0WindowValid"] is True
    assert report["warnings"]
    assert [entry["p0Feature"] for entry in report["features"]] == sorted(mapped)


@pytest.mark.parametrize("name", [name for name in inspection.P0_TO_N1 if name.endswith("_delta")])
def test_counter_changes_recompute_from_raw_but_never_from_frozen_medians(name):
    entry = entries(inspect())[name]
    assert entry["classification"] == "recomputable_from_raw"
    for output in entry["outputs"]:
        assert output["classification"] == "recomputable_from_raw"
        assert output["frozenAggregateClassification"] == "not_recoverable_from_aggregate"
        assert output["summary"]["acceptedIntervalCount"] == 2
        assert output["summary"]["observedDurationMs"] == 10000
        assert output["summary"]["coverage"] == 1
        assert output["value"] is not None


@pytest.mark.parametrize(
    "name",
    [
        name
        for name in inspection.P0_TO_N1
        if not name.endswith("_delta") and name != "encoder.pipeline_delay_proxy_ms"
    ],
)
def test_unchanged_gauge_meaning_is_identity_safe_including_binary_rss_rename(name):
    entry = entries(inspect())[name]
    assert entry["classification"] == "identity_safe"
    output = entry["outputs"][0]
    assert output["value"] == entry["p0"]["aggregate"]["value"]
    assert output["frozenAggregateClassification"] == "identity_safe"
    if "rss_mb" in name:
        assert output["definition"]["name"] == name.replace("_rss_mb", "_rss_mib")
        assert output["definition"]["canonicalUnit"] == "MiB"


def test_directory_and_tar_are_identical_and_leave_files_unchanged(tmp_path):
    bundle = copy_bundle(tmp_path)
    before = {path.name: path.read_bytes() for path in bundle.iterdir()}
    archive = tmp_path / "private-bundle.tar"
    with tarfile.open(archive, "w") as file:
        for path in sorted(bundle.iterdir()):
            file.add(path, arcname=path.name)
    first = inspection.render_measurement_inspection(inspect(bundle))
    assert first == inspection.render_measurement_inspection(inspect(archive))
    assert first == inspection.render_measurement_inspection(inspect(bundle))
    assert before == {path.name: path.read_bytes() for path in bundle.iterdir()}
    assert str(tmp_path) not in first


def test_optional_sources_remain_explicit_for_legacy_browser_bundle():
    report = inspect(FIXTURES / "valid", version="1")
    for entry in report["features"]:
        if entry["p0Feature"].startswith(("host.", "encoder.")):
            assert entry["classification"] == "unsupported_source"
            assert entry["p0"]["status"] == "missing"
            assert all(output["value"] is None for output in entry["outputs"])
            assert all(output["summary"]["sourceSampleCount"] == 0 for output in entry["outputs"])


def test_header_only_engine_source_is_explicit(tmp_path):
    bundle = copy_bundle(tmp_path)
    path = bundle / "engine-telemetry.csv"
    path.write_text(path.read_text().splitlines()[0] + "\n")
    metadata = json.loads((bundle / "run-metadata.json").read_text())
    metadata["scenario"] = "browser_only_baseline"
    (bundle / "run-metadata.json").write_text(json.dumps(metadata))
    manifest = json.loads((bundle / "bundle-manifest.json").read_text())
    # Mirror the exporter-declared absence, including per-field support.
    manifest["telemetrySources"].update(
        engine_runtime="unavailable", encoder_pipeline="unsupported"
    )
    (bundle / "bundle-manifest.json").write_text(json.dumps(manifest))
    summary = json.loads((bundle / "summary.json").read_text())
    for source in ("engineRuntime", "encoderPipeline"):
        summary["validity"]["sources"][source] = {"sampleCount": 0, "availableSampleCount": 0}
    (bundle / "summary.json").write_text(json.dumps(summary))
    report = inspect(bundle)
    assert entries(report)["host.node_cpu_percent"]["classification"] == "unsupported_source"


def test_rejected_numeric_content_does_not_leak_private_strings(tmp_path):
    bundle = copy_bundle(tmp_path)
    private_marker = "PRIVATE_IDENTITY_/home/private-key@example.test"
    for index in range(3):
        edit_row(bundle, "stream-telemetry.csv", index, jitter_ms=private_marker)
    report = inspect(bundle)
    output = entries(report)["transport.jitter_ms"]["outputs"][0]
    assert output["classification"] == "rejected"
    assert output["value"] is None
    assert entries(report)["transport.jitter_ms"]["p0"]["status"] == "rejected"
    rendered = inspection.render_measurement_inspection(report)
    assert private_marker not in rendered
    assert str(bundle) not in rendered


def test_missing_numeric_series_never_infers_zero_or_identity(tmp_path):
    bundle = copy_bundle(tmp_path)
    for index in range(3):
        edit_row(bundle, "stream-telemetry.csv", index, jitter_ms="")
    output = entries(inspect(bundle))["transport.jitter_ms"]["outputs"][0]
    assert output["classification"] == "not_recoverable_from_aggregate"
    assert output["value"] is None


def test_partial_gauge_rejection_requires_raw_recomputation(tmp_path):
    bundle = copy_bundle(tmp_path)
    edit_row(bundle, "stream-telemetry.csv", 1, jitter_ms="malformed")
    entry = entries(inspect(bundle))["transport.jitter_ms"]
    assert entry["classification"] == "recomputable_from_raw"
    assert entry["outputs"][0]["frozenAggregateClassification"] == "not_recoverable_from_aggregate"
    assert entry["outputs"][0]["summary"]["status"] == "incomplete"


def test_p0_only_packet_loss_rejection_preserves_raw_n1_results(tmp_path):
    bundle = copy_bundle(tmp_path)
    edit_row(bundle, "stream-telemetry.csv", 1, packets_lost_delta="malformed-private")
    report = inspect(bundle)
    assert report["p0Ingestion"] == "rejected"
    assert report["p0WindowValid"] is None
    entry = entries(report)["transport.packets_lost_delta"]
    assert entry["p0"]["status"] == "unavailable"
    assert entry["classification"] == "recomputable_from_raw"
    assert entry["outputs"][0]["value"] is not None
    assert "malformed-private" not in inspection.render_measurement_inspection(report)


def frozen_window():
    return ingest_pixelated_bundle(
        FIXTURES / "valid-v2",
        context=load_model_file(FIXTURES / "context-v2.json", ContextKey),
        phase=WindowPhase.DEGRADED,
        comparison_case_id="controlled-case-001",
    )


def test_frozen_only_report_never_reconstructs_counter_values():
    window = frozen_window()
    before = window.model_dump_json()
    report = inspection.inspect_frozen_window(window)
    assert window.model_dump_json() == before
    assert report["inputMode"] == "frozen_window"
    assert report["bundleChecksum"] is None
    for entry in report["features"]:
        for output in entry["outputs"]:
            assert output["summary"] is None
            if entry["p0Feature"].endswith("_delta") or entry["p0"]["status"] != "available":
                assert output["classification"] == "not_recoverable_from_aggregate"
                assert output["value"] is None
            else:
                assert output["classification"] == "identity_safe"
                assert output["value"] == entry["p0"]["aggregate"]["value"]


@pytest.mark.parametrize("changes", [{"unit": "private-path"}, {"aggregation": "private-identity"}])
def test_incompatible_frozen_gauge_is_not_declared_migratable_or_echoed(changes):
    window = frozen_window()
    data = window.model_dump()
    data["metrics"]["transport.jitter_ms"].update(changes)
    window = ObservationWindow.model_validate(data)
    report = inspection.inspect_frozen_window(window)
    entry = entries(report)["transport.jitter_ms"]
    assert entry["classification"] == "not_recoverable_from_aggregate"
    assert entry["outputs"][0]["value"] is None
    rendered = inspection.render_measurement_inspection(report)
    assert all(value not in rendered for value in changes.values())


def test_checksum_disagreement_fails_closed(monkeypatch):
    window = frozen_window()
    window.source_artifact.checksum = "sha256:" + "0" * 64
    monkeypatch.setattr(inspection, "ingest_pixelated_bundle", lambda *args, **kwargs: window)
    with pytest.raises(ValueError, match="bundle changed"):
        inspect()


def cli_args():
    return [
        "inspect-measurements",
        str(FIXTURES / "valid-v2"),
        "--context",
        str(FIXTURES / "context-v2.json"),
        "--phase",
        "degraded",
        "--comparison-case-id",
        "controlled-case-001",
    ]


def test_cli_matches_python_api_and_rejects_as_p0_root(capsys, tmp_path):
    assert main(cli_args()) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == inspection.render_measurement_inspection(inspect())
    path = tmp_path / "report.json"
    path.write_text(captured.out)
    assert main(["validate", str(path)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "unsupported schemaVersion" in captured.err


def test_cli_errors_have_no_partial_json(capsys):
    args = cli_args()
    args[-1] = "wrong-case"
    assert main(args) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "error:" in captured.err


def test_raw_contract_failures_fail_closed_before_p0_ingestion(monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("P0 must not run after N1 source-contract failure")

    monkeypatch.setattr(inspection, "ingest_pixelated_bundle", fail)
    with pytest.raises(ValueError):
        inspection.inspect_measurements(
            FIXTURES / "valid-v2",
            context=load_model_file(FIXTURES / "context-v2.json", ContextKey),
            phase=WindowPhase.RELIEF,
            comparison_case_id="wrong-case",
        )


def test_report_omits_source_identities_and_metadata_values():
    report = inspection.render_measurement_inspection(inspect())
    metadata = json.loads((FIXTURES / "valid-v2/run-metadata.json").read_text())
    context = json.loads((FIXTURES / "context-v2.json").read_text())
    for key in ("runId", "sessionId", "gameId"):
        if isinstance(metadata.get(key), str):
            assert metadata[key] not in report
    for key in ("nodeId", "contextId", "workloadId"):
        assert context[key] not in report
    assert "controlled-case-001" not in report
    assert str(FIXTURES) not in report


def test_cli_bytes_are_repeatable_in_separate_processes():
    import sys

    cmd = [sys.executable, "-m", "latency_fingerprinting", *cli_args()]
    first = subprocess.check_output(cmd)  # noqa: S603 -- fixed local CLI and fixture arguments
    second = subprocess.check_output(cmd)  # noqa: S603 -- fixed local CLI and fixture arguments
    assert first == second


def test_declared_unsupported_measurement_remains_explicit():
    entry = entries(inspect())["encoder.pipeline_delay_proxy_ms"]
    assert entry["classification"] == "unsupported_source"
    assert entry["outputs"][0]["value"] is None
    assert entry["outputs"][0]["frozenAggregateClassification"] == "not_recoverable_from_aggregate"


def test_existing_fixture_can_demonstrate_equivalent_one_second_cadence(tmp_path):
    from datetime import datetime, timedelta

    five_seconds = inspect()
    bundle = copy_bundle(tmp_path)
    for filename in ("stream-telemetry.csv", "engine-telemetry.csv"):
        path = bundle / filename
        with path.open(newline="") as file:
            reader = csv.DictReader(file)
            columns = reader.fieldnames
            rows = list(reader)
        start = datetime.fromisoformat(rows[0]["captured_at"].replace("Z", "+00:00"))
        for row in rows:
            elapsed = float(row["elapsed_ms"]) / 5
            row["elapsed_ms"] = str(elapsed)
            row["captured_at"] = (start + timedelta(milliseconds=elapsed)).isoformat()
        with path.open("w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
    # Keep one-second frame increments proportional to the original five-second series.
    for index, value in enumerate((100, 160, 220)):
        edit_row(bundle, "stream-telemetry.csv", index, frames_decoded=str(value))
    summary_path = bundle / "summary.json"
    summary = json.loads(summary_path.read_text())
    summary["recording"]["durationMs"] = 2000
    summary_path.write_text(json.dumps(summary))
    one_second = inspect(bundle)
    first = entries(one_second)["client.frames_decoded_delta"]
    second = entries(five_seconds)["client.frames_decoded_delta"]
    assert first["outputs"][0]["value"] == second["outputs"][0]["value"] == 60
    assert first["p0"]["aggregate"]["value"] == 60
    assert second["p0"]["aggregate"]["value"] == 300
    assert first["outputs"][1]["value"] == 120
    assert second["outputs"][1]["value"] == 600


def test_single_counter_baseline_is_not_recoverable_from_frozen_delta(tmp_path):
    bundle = copy_bundle(tmp_path)
    edit_row(bundle, "stream-telemetry.csv", 1, frames_decoded="")
    edit_row(bundle, "stream-telemetry.csv", 2, frames_decoded="")
    entry = entries(inspect(bundle))["client.frames_decoded_delta"]
    assert entry["classification"] == "not_recoverable_from_aggregate"
    assert entry["outputs"][0]["summary"]["status"] == "incomplete"
    assert entry["outputs"][0]["value"] is None


def test_inactive_browser_source_is_unsupported(tmp_path):
    bundle = copy_bundle(tmp_path)
    for index in range(3):
        edit_row(bundle, "stream-telemetry.csv", index, status="stopped")
    report = inspect(bundle)
    assert entries(report)["client.received_fps"]["classification"] == "unsupported_source"


def test_inspection_preserves_invalid_p0_window_flag(tmp_path):
    bundle = copy_bundle(tmp_path)
    path = bundle / "summary.json"
    summary = json.loads(path.read_text())
    summary["validity"].update(isValid=False, reasons=["private producer reason"])
    path.write_text(json.dumps(summary))
    report = inspect(bundle)
    assert report["p0WindowValid"] is False
    assert "private producer reason" not in inspection.render_measurement_inspection(report)


def test_rendered_fixture_hash_is_pinned_in_both_ci_python_versions():
    import hashlib

    digest = hashlib.sha256(
        inspection.render_measurement_inspection(inspect()).encode()
    ).hexdigest()
    assert digest == "295f57a6f0e0ab80f64c7323be3cd5fc4e278aac712825f0173955594513c423"


def test_mapping_matches_reviewed_inventory_exactly():
    inventory = (FIXTURES.parents[2] / "docs/measurement/METRIC_SEMANTICS_V2.md").read_text()
    body = inventory.split("## P0 mapping\n", 1)[1].split("\n## ", 1)[0]
    lines = [line for line in body.splitlines() if line.startswith("| ")]
    rows = [[cell.strip() for cell in line.strip("|").split("|")] for line in lines]
    reviewed = {}
    for row in rows[2:]:
        entry = dict(zip(rows[0], row, strict=True))
        reviewed[entry["P0 feature"]] = tuple(entry["proposed v2 feature"].split(", "))
    assert dict(inspection.P0_TO_N1) == reviewed


def test_frozen_gauge_outside_registered_domain_is_not_identity_safe():
    window = frozen_window()
    data = window.model_dump()
    data["metrics"]["transport.jitter_ms"] = {
        "unit": "ms",
        "aggregation": "median",
        "value": -1,
        "count": 1,
    }
    report = inspection.inspect_frozen_window(ObservationWindow.model_validate(data))
    output = entries(report)["transport.jitter_ms"]["outputs"][0]
    assert output["classification"] == "not_recoverable_from_aggregate"
    assert output["value"] is None
