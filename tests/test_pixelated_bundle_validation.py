"""Pixelated metric availability, counter, validity, and identity tests."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from latency_fingerprinting.adapters.pixelated_bundle import (
    PixelatedBundleError,
    ingest_pixelated_bundle,
)
from latency_fingerprinting.models import ContextKey, WindowPhase

from .pixelated_bundle_support import (
    VALID_BUNDLE,
    copy_bundle,
    copy_v2_bundle,
    ingest,
)


def test_v2_counter_resets_are_rejected_not_fabricated(
    tmp_path: Path,
    context_v2: ContextKey,
) -> None:
    bundle = copy_v2_bundle(tmp_path)
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


def test_v2_counter_deltas_do_not_bridge_unavailable_samples(
    tmp_path: Path,
    context_v2: ContextKey,
) -> None:
    bundle = copy_v2_bundle(tmp_path)
    telemetry_path = bundle / "engine-telemetry.csv"
    with telemetry_path.open(newline="", encoding="utf-8") as telemetry_file:
        rows = list(csv.DictReader(telemetry_file))
    headers = list(rows[0])
    encoder_rows = [row for row in rows if row["source"] == "encoder_pipeline"]
    encoder_rows[1]["available"] = "false"
    encoder_rows[1]["error"] = "temporary exporter gap"
    for column in (
        "frames_in_total",
        "frames_out_total",
        "frames_dropped_total",
        "queue_level_buffers",
        "target_bitrate_kbps",
        "target_fps",
        "cpu_used",
        "max_quantizer",
    ):
        encoder_rows[1][column] = ""
    with telemetry_path.open("w", newline="", encoding="utf-8") as telemetry_file:
        writer = csv.DictWriter(telemetry_file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

    summary_path = bundle / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["validity"]["sources"]["encoderPipeline"]["availableSampleCount"] = 2
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    window = ingest(bundle, context_v2)

    assert "encoder.frames_in_delta" in window.missing_metrics
    assert "encoder.frames_in_delta" not in window.metrics
    assert not window.validity.is_valid
    assert "encoder pipeline telemetry has unavailable samples" in window.validity.reasons


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


def test_context_and_comparison_case_are_not_silently_invented(context: ContextKey) -> None:
    with pytest.raises(PixelatedBundleError, match="comparison_case_id cannot be empty"):
        ingest_pixelated_bundle(
            VALID_BUNDLE,
            phase=WindowPhase.DEGRADED,
            comparison_case_id=" ",
            context=context,
        )
