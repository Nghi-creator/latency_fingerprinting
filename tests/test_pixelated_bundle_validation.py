"""Pixelated metric availability, counter, validity, and identity tests."""

from __future__ import annotations

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
