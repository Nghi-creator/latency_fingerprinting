"""Pixelated bundle-v2 identity, privacy, timing, and summary contracts."""

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
    VALID_V2_BUNDLE,
    copy_v2_bundle,
    ingest,
)


def test_v2_manifest_identity_and_privacy_are_enforced(
    tmp_path: Path,
    context_v2: ContextKey,
) -> None:
    bundle = copy_v2_bundle(tmp_path)
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


def test_v2_nested_metadata_privacy_fields_are_rejected(
    tmp_path: Path,
    context_v2: ContextKey,
) -> None:
    bundle = copy_v2_bundle(tmp_path)
    metadata_path = bundle / "run-metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["client"]["connection"] = {"shareUrl": "https://private.test/join"}
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(PixelatedBundleError, match="shareUrl"):
        ingest(bundle, context_v2)


def test_bundle_schema_version_must_match_explicit_context(context: ContextKey) -> None:
    with pytest.raises(PixelatedBundleError, match="pixelatedBundleSchema disagrees"):
        ingest(VALID_V2_BUNDLE, context)


def test_bundle_workload_must_match_explicit_context(context_v2: ContextKey) -> None:
    incompatible = context_v2.model_copy(update={"workload_id": "different-workload"})
    with pytest.raises(PixelatedBundleError, match="workload identity disagrees"):
        ingest(VALID_V2_BUNDLE, incompatible)


def test_each_telemetry_timestamp_must_match_elapsed_time(
    tmp_path: Path,
    context_v2: ContextKey,
) -> None:
    bundle = copy_v2_bundle(tmp_path)
    telemetry_path = bundle / "stream-telemetry.csv"
    telemetry_path.write_text(
        telemetry_path.read_text(encoding="utf-8").replace(
            "2026-08-10T02:03:09.000Z,5000,",
            "2026-08-10T02:03:09.000Z,4000,",
        ),
        encoding="utf-8",
    )

    with pytest.raises(PixelatedBundleError, match="wall-clock and elapsed times disagree"):
        ingest(bundle, context_v2)


def test_event_timestamps_must_be_valid_and_match_elapsed_time(
    tmp_path: Path,
    context_v2: ContextKey,
) -> None:
    bundle = copy_v2_bundle(tmp_path)
    events_path = bundle / "stream-events.csv"
    events_path.write_text(
        events_path.read_text(encoding="utf-8").replace(
            "2026-08-10T02:03:04.000Z",
            "not-a-timestamp",
        ),
        encoding="utf-8",
    )
    with pytest.raises(PixelatedBundleError, match="must be an ISO 8601 timestamp"):
        ingest(bundle, context_v2)

    bundle = copy_v2_bundle(tmp_path, name="event-clock-mismatch")
    events_path = bundle / "stream-events.csv"
    with events_path.open("a", encoding="utf-8") as events_file:
        events_file.write(
            "2026-08-10T02:03:15.000Z,0,pixelated-sanitized-run-v2-001,"
            "anonymous-session-v2-001,research_recording_completed,\n"
        )
    summary_path = bundle / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["eventCount"] = 2
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(PixelatedBundleError, match="wall-clock and elapsed times disagree"):
        ingest(bundle, context_v2)


def test_v2_summary_available_counts_must_match_telemetry(
    tmp_path: Path,
    context_v2: ContextKey,
) -> None:
    bundle = copy_v2_bundle(tmp_path)
    summary_path = bundle / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["validity"]["sources"]["encoderPipeline"]["availableSampleCount"] = 999_999
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    with pytest.raises(PixelatedBundleError, match="available sample count disagrees"):
        ingest(bundle, context_v2)


def test_engine_samples_must_align_with_browser_window(
    tmp_path: Path,
    context_v2: ContextKey,
) -> None:
    bundle = copy_v2_bundle(tmp_path)
    engine_path = bundle / "engine-telemetry.csv"
    engine_path.write_text(
        engine_path.read_text(encoding="utf-8").replace("2026-08-10", "2026-08-11"),
        encoding="utf-8",
    )

    with pytest.raises(PixelatedBundleError, match="outside the browser capture window"):
        ingest(bundle, context_v2)


def test_v2_summary_invalidity_is_preserved_in_window(
    tmp_path: Path,
    context_v2: ContextKey,
) -> None:
    bundle = copy_v2_bundle(tmp_path)
    summary_path = bundle / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["validity"].update(
        {"isValid": False, "reasons": ["capture exporter marked the run invalid"]}
    )
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    window = ingest(bundle, context_v2)

    assert not window.validity.is_valid
    assert "bundle summary: capture exporter marked the run invalid" in window.validity.reasons


def test_v2_summary_duration_must_match_telemetry(
    tmp_path: Path,
    context_v2: ContextKey,
) -> None:
    bundle = copy_v2_bundle(tmp_path)
    summary_path = bundle / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["recording"]["durationMs"] = 1
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    with pytest.raises(PixelatedBundleError, match="duration disagrees"):
        ingest(bundle, context_v2)


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
    bundle = copy_v2_bundle(tmp_path, name=manifest_phase)
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
