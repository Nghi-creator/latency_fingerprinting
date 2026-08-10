"""Tests for the strict Pixelated research-bundle translation boundary."""

from __future__ import annotations

import io
import json
import shutil
import tarfile
from pathlib import Path

import pytest

from latency_fingerprinting.adapters.pixelated_bundle import (
    PixelatedBundleError,
    ingest_pixelated_bundle,
)
from latency_fingerprinting.models import (
    ContextKey,
    ProvenanceKind,
    WindowPhase,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = PROJECT_ROOT / "tests" / "data" / "pixelated_bundle"
VALID_BUNDLE = FIXTURE_ROOT / "valid"
VALID_V2_BUNDLE = FIXTURE_ROOT / "valid-v2"


@pytest.fixture
def context() -> ContextKey:
    return ContextKey.model_validate_json(
        (FIXTURE_ROOT / "context.json").read_text(encoding="utf-8")
    )


@pytest.fixture
def context_v2() -> ContextKey:
    return ContextKey.model_validate_json(
        (FIXTURE_ROOT / "context-v2.json").read_text(encoding="utf-8")
    )


def ingest(path: Path, context: ContextKey):
    return ingest_pixelated_bundle(
        path,
        phase=WindowPhase.DEGRADED,
        comparison_case_id="controlled-case-001",
        context=context,
    )


def copy_bundle(tmp_path: Path) -> Path:
    destination = tmp_path / "bundle"
    shutil.copytree(VALID_BUNDLE, destination)
    return destination


def write_tar(source: Path, destination: Path) -> None:
    with tarfile.open(destination, "w") as archive:
        for path in sorted(source.iterdir()):
            archive.add(path, arcname=path.name)


def test_extracted_bundle_maps_only_supported_metrics(context: ContextKey) -> None:
    window = ingest(VALID_BUNDLE, context)

    assert window.phase is WindowPhase.DEGRADED
    assert window.provenance is ProvenanceKind.CONTROLLED_REAL
    assert window.context == context
    assert window.run_id == "pixelated-sanitized-run-001"
    assert window.window_id == "pixelated-sanitized-run-001-degraded"
    assert window.duration_s == 10
    assert window.bounds.started_at is not None
    assert window.bounds.started_at.isoformat() == "2026-07-04T02:03:04+00:00"
    assert window.bounds.elapsed_start_s is None
    assert window.sample_count == 3
    assert window.effective_settings == {
        "bitrateKbps": 1400,
        "fps": 60,
        "streamProfileId": "balanced",
    }
    assert set(window.metrics) == {
        "client.received_bitrate_kbps",
        "client.received_fps",
        "transport.jitter_ms",
        "transport.packets_lost_delta",
    }
    assert window.metrics["client.received_fps"].value == 54
    assert window.metrics["client.received_fps"].p95 == 58
    assert window.metrics["transport.jitter_ms"].value == 6
    assert window.metrics["transport.packets_lost_delta"].value == 0
    assert window.validity.is_valid
    assert window.source_artifact.checksum is not None
    serialized = window.model_dump_json(by_alias=True)
    assert "anonymous-session-001" not in serialized
    assert "userAgent" not in serialized


def test_tar_bundle_produces_the_same_window(tmp_path: Path, context: ContextKey) -> None:
    archive = tmp_path / "bundle.tar"
    write_tar(VALID_BUNDLE, archive)

    assert ingest(archive, context) == ingest(VALID_BUNDLE, context)


def test_v2_bundle_maps_browser_engine_and_encoder_metrics(context_v2: ContextKey) -> None:
    window = ingest(VALID_V2_BUNDLE, context_v2)

    assert window.run_id == "pixelated-sanitized-run-v2-001"
    assert window.validity.is_valid
    assert window.effective_settings["runtimeKind"] == "libretro"
    assert window.effective_settings["cpuCapacityCores"] == 4
    assert window.effective_settings["encoderCpuUsed"] == 6
    assert window.metrics["transport.round_trip_time_ms"].value == 16
    assert window.metrics["client.decode_time_mean_ms"].value == 3
    assert window.metrics["client.frames_decoded_delta"].value == 300
    assert window.metrics["host.game_cpu_percent"].value == 75
    assert window.metrics["host.camera_cpu_percent"].value == 35
    assert window.metrics["encoder.frames_in_delta"].value == 300
    assert window.metrics["encoder.frames_dropped_delta"].value == 1.5
    assert window.metrics["encoder.queue_level_buffers"].value == 2
    assert "encoder.pipeline_delay_proxy_ms" in window.missing_metrics
    assert "encoder.pipeline_delay_proxy_ms" not in window.metrics


def test_v2_tar_bundle_produces_the_same_window(
    tmp_path: Path,
    context_v2: ContextKey,
) -> None:
    archive = tmp_path / "bundle-v2.tar"
    write_tar(VALID_V2_BUNDLE, archive)

    assert ingest(archive, context_v2) == ingest(VALID_V2_BUNDLE, context_v2)


def test_v2_browser_only_baseline_accepts_header_only_engine_csv(
    tmp_path: Path,
    context_v2: ContextKey,
) -> None:
    bundle = tmp_path / "browser-only-v2"
    shutil.copytree(VALID_V2_BUNDLE, bundle)

    metadata_path = bundle / "run-metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["scenario"] = "browser_only_baseline"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    engine_path = bundle / "engine-telemetry.csv"
    engine_path.write_text(
        engine_path.read_text(encoding="utf-8").splitlines()[0] + "\n",
        encoding="utf-8",
    )

    summary_path = bundle / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    for source in ("engineRuntime", "encoderPipeline"):
        summary["validity"]["sources"][source] = {
            "sampleCount": 0,
            "availableSampleCount": 0,
        }
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    manifest_path = bundle / "bundle-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["telemetrySources"]["engine_runtime"] = "unavailable"
    manifest["telemetrySources"]["encoder_pipeline"] = "unavailable"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    window = ingest(bundle, context_v2)

    assert window.validity.is_valid
    assert "host.node_cpu_percent" in window.missing_metrics
    assert "encoder.frames_out_delta" in window.missing_metrics


def test_v2_manifest_identity_and_privacy_are_enforced(
    tmp_path: Path,
    context_v2: ContextKey,
) -> None:
    bundle = tmp_path / "bundle-v2"
    shutil.copytree(VALID_V2_BUNDLE, bundle)
    manifest_path = bundle / "bundle-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["phase"] = "relief"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(PixelatedBundleError, match="phase disagrees"):
        ingest(bundle, context_v2)

    manifest["phase"] = "degraded"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    metadata_path = bundle / "run-metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["shareUrl"] = "https://private.test/join"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(PixelatedBundleError, match="must omit privacy field"):
        ingest(bundle, context_v2)


def test_v2_counter_resets_are_rejected_not_fabricated(
    tmp_path: Path,
    context_v2: ContextKey,
) -> None:
    bundle = tmp_path / "bundle-v2"
    shutil.copytree(VALID_V2_BUNDLE, bundle)
    telemetry_path = bundle / "engine-telemetry.csv"
    telemetry_path.write_text(
        telemetry_path.read_text(encoding="utf-8").replace(
            ",400,395,3,2,,1500,60,6,48",
            ",50,395,3,2,,1500,60,6,48",
        ),
        encoding="utf-8",
    )

    window = ingest(bundle, context_v2)

    assert "encoder.frames_in_delta" in window.rejected_metrics
    assert "encoder.frames_in_delta" not in window.metrics


def test_bundle_schema_version_must_match_explicit_context(
    context: ContextKey,
) -> None:
    with pytest.raises(PixelatedBundleError, match="pixelatedBundleSchema disagrees"):
        ingest(VALID_V2_BUNDLE, context)


@pytest.mark.parametrize(
    ("manifest_phase", "window_phase"),
    [
        ("healthy", WindowPhase.BASELINE),
        ("degraded", WindowPhase.DEGRADED),
        ("relief", WindowPhase.RELIEF),
    ],
)
def test_v2_phase_contract_ingests_every_controlled_run_phase(
    tmp_path: Path,
    context_v2: ContextKey,
    manifest_phase: str,
    window_phase: WindowPhase,
) -> None:
    bundle = tmp_path / manifest_phase
    shutil.copytree(VALID_V2_BUNDLE, bundle)
    original_run_id = "pixelated-sanitized-run-v2-001"
    run_id = f"pixelated-sanitized-run-v2-{manifest_phase}"
    for path in bundle.iterdir():
        path.write_text(
            path.read_text(encoding="utf-8").replace(original_run_id, run_id),
            encoding="utf-8",
        )
    manifest_path = bundle / "bundle-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["phase"] = manifest_phase
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    window = ingest_pixelated_bundle(
        bundle,
        phase=window_phase,
        comparison_case_id="controlled-case-001",
        context=context_v2,
    )

    assert window.phase is window_phase
    assert window.run_id == run_id
    assert window.validity.is_valid


def test_missing_required_file_is_rejected(tmp_path: Path, context: ContextKey) -> None:
    bundle = copy_bundle(tmp_path)
    (bundle / "summary.json").unlink()

    with pytest.raises(PixelatedBundleError, match="missing required files: summary.json"):
        ingest(bundle, context)


def test_missing_required_telemetry_column_is_rejected(
    tmp_path: Path,
    context: ContextKey,
) -> None:
    bundle = copy_bundle(tmp_path)
    telemetry = bundle / "stream-telemetry.csv"
    telemetry.write_text(
        telemetry.read_text(encoding="utf-8").replace(",jitter_ms,", ","),
        encoding="utf-8",
    )

    with pytest.raises(PixelatedBundleError, match="missing required columns: jitter_ms"):
        ingest(bundle, context)


def test_missing_metric_values_remain_missing(tmp_path: Path, context: ContextKey) -> None:
    bundle = copy_bundle(tmp_path)
    telemetry = bundle / "stream-telemetry.csv"
    text = telemetry.read_text(encoding="utf-8")
    text = text.replace(",8,connected", ",,connected")
    text = text.replace(",6,connected", ",,connected")
    text = text.replace(",4,completed", ",,completed")
    telemetry.write_text(text, encoding="utf-8")

    window = ingest(bundle, context)

    assert "transport.jitter_ms" in window.missing_metrics
    assert "transport.jitter_ms" not in window.metrics
    assert "transport.jitter_ms" not in window.rejected_metrics


def test_malformed_metric_values_are_rejected_not_fabricated(
    tmp_path: Path,
    context: ContextKey,
) -> None:
    bundle = copy_bundle(tmp_path)
    telemetry = bundle / "stream-telemetry.csv"
    telemetry.write_text(
        telemetry.read_text(encoding="utf-8").replace(",54,1200,", ",broken,1200,"),
        encoding="utf-8",
    )

    window = ingest(bundle, context)

    assert "client.received_fps" in window.rejected_metrics
    assert "client.received_fps" not in window.metrics


def test_inactive_playback_is_preserved_as_invalid_window(
    tmp_path: Path,
    context: ContextKey,
) -> None:
    bundle = copy_bundle(tmp_path)
    telemetry = bundle / "stream-telemetry.csv"
    telemetry.write_text(
        telemetry.read_text(encoding="utf-8").replace(",host,playing,54", ",host,error,54"),
        encoding="utf-8",
    )

    window = ingest(bundle, context)

    assert not window.validity.is_valid
    assert "telemetry window includes inactive playback" in window.validity.reasons


def test_cross_file_identity_mismatch_is_rejected(
    tmp_path: Path,
    context: ContextKey,
) -> None:
    bundle = copy_bundle(tmp_path)
    summary_path = bundle / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["runId"] = "different-run"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    with pytest.raises(PixelatedBundleError, match="identity disagrees"):
        ingest(bundle, context)


def test_tar_path_traversal_is_rejected(tmp_path: Path, context: ContextKey) -> None:
    archive_path = tmp_path / "unsafe.tar"
    with tarfile.open(archive_path, "w") as archive:
        member = tarfile.TarInfo("../../outside.txt")
        payload = b"unsafe"
        member.size = len(payload)
        archive.addfile(member, io.BytesIO(payload))

    with pytest.raises(PixelatedBundleError, match="unsafe TAR member path"):
        ingest(archive_path, context)


def test_tar_links_are_rejected(tmp_path: Path, context: ContextKey) -> None:
    archive_path = tmp_path / "link.tar"
    with tarfile.open(archive_path, "w") as archive:
        member = tarfile.TarInfo("run-metadata.json")
        member.type = tarfile.SYMTYPE
        member.linkname = "elsewhere.json"
        archive.addfile(member)

    with pytest.raises(PixelatedBundleError, match="TAR links are not allowed"):
        ingest(archive_path, context)


def test_context_and_comparison_case_are_not_silently_invented(context: ContextKey) -> None:
    with pytest.raises(PixelatedBundleError, match="comparison_case_id cannot be empty"):
        ingest_pixelated_bundle(
            VALID_BUNDLE,
            phase=WindowPhase.DEGRADED,
            comparison_case_id=" ",
            context=context,
        )
