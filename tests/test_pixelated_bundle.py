"""Happy-path tests for the strict Pixelated research-bundle adapter."""

from __future__ import annotations

import json
from pathlib import Path

from latency_fingerprinting.models import ContextKey, ProvenanceKind, WindowPhase

from .pixelated_bundle_support import (
    VALID_BUNDLE,
    VALID_V2_BUNDLE,
    copy_v2_bundle,
    ingest,
    write_tar,
)


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
    bundle = copy_v2_bundle(tmp_path, name="browser-only-v2")

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
