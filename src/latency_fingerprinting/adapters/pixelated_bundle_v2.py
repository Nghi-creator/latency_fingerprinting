"""Validation and effective settings for Pixelated bundle schema v2."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any

from ..json_io import strict_json_loads
from ..models import WindowPhase
from .pixelated_bundle_common import (
    PixelatedBundleError,
    finite_number,
    required_string,
    utc_datetime,
)

V2_REQUIRED_FILES = frozenset(
    {
        "bundle-manifest.json",
        "engine-telemetry.csv",
        "run-metadata.json",
        "stream-events.csv",
        "stream-telemetry.csv",
        "summary.json",
    }
)
ENGINE_TELEMETRY_COLUMNS = frozenset(
    {
        "captured_at",
        "elapsed_ms",
        "schema_version",
        "run_id",
        "session_id",
        "game_id",
        "source",
        "available",
        "error",
        "node_cpu_percent",
        "node_rss_mb",
        "emulator_cpu_percent",
        "emulator_rss_mb",
        "camera_cpu_percent",
        "camera_rss_mb",
        "logical_cpu_count",
        "cpu_capacity_cores",
        "runtime_kind",
        "node_running",
        "emulator_running",
        "camera_running",
        "peer_count",
        "frames_in_total",
        "frames_out_total",
        "frames_dropped_total",
        "queue_level_buffers",
        "pipeline_delay_proxy_ms",
        "target_bitrate_kbps",
        "target_fps",
        "cpu_used",
        "max_quantizer",
    }
)


def validate_manifest(
    manifest: Mapping[str, Any],
    files: Mapping[str, bytes],
    *,
    comparison_case_id: str,
    phase: WindowPhase,
    run_id: str,
) -> None:
    if manifest.get("schemaVersion") != 2:
        raise PixelatedBundleError("bundle-manifest.json requires schemaVersion 2")
    if manifest.get("bundleType") != "pixelated_research_run":
        raise PixelatedBundleError("bundle-manifest.json bundleType is unsupported")
    if manifest.get("runId") != run_id:
        raise PixelatedBundleError("bundle manifest run identity disagrees with metadata")
    if manifest.get("comparisonCaseId") != comparison_case_id:
        raise PixelatedBundleError("bundle manifest comparison case disagrees with ingestion")
    expected_phase = "healthy" if phase is WindowPhase.BASELINE else phase.value
    if manifest.get("phase") != expected_phase:
        raise PixelatedBundleError("bundle manifest phase disagrees with ingestion")
    declared_files = manifest.get("files")
    if not isinstance(declared_files, list):
        raise PixelatedBundleError("bundle-manifest.json requires array 'files'")
    names: list[str] = []
    for entry in declared_files:
        if not isinstance(entry, dict):
            raise PixelatedBundleError("bundle manifest file entries must be objects")
        names.append(required_string(entry, "name", "bundle-manifest.json file entry"))
        if not isinstance(entry.get("required"), bool):
            raise PixelatedBundleError("bundle manifest file entries require boolean 'required'")
        required_string(entry, "mediaType", "bundle-manifest.json file entry")
    if len(names) != len(set(names)):
        raise PixelatedBundleError("bundle manifest contains duplicate file entries")
    missing_declarations = sorted(V2_REQUIRED_FILES - set(names))
    if missing_declarations:
        raise PixelatedBundleError(
            "bundle manifest omits required files: " + ", ".join(missing_declarations)
        )
    missing_files = sorted(V2_REQUIRED_FILES - files.keys())
    if missing_files:
        raise PixelatedBundleError("bundle is missing v2 files: " + ", ".join(missing_files))
    _validate_manifest_privacy(manifest)
    _validate_manifest_support(manifest)


def _validate_manifest_privacy(manifest: Mapping[str, Any]) -> None:
    privacy = manifest.get("privacy")
    if not isinstance(privacy, dict) or privacy.get("sanitized") is not True:
        raise PixelatedBundleError("bundle manifest must declare sanitized privacy state")
    omitted = privacy.get("omittedFields")
    required_omissions = {
        "absolutePath",
        "engineToken",
        "hostname",
        "rawPeerId",
        "shareUrl",
        "username",
    }
    if not isinstance(omitted, list) or not required_omissions.issubset(
        {item for item in omitted if isinstance(item, str)}
    ):
        raise PixelatedBundleError("bundle manifest privacy omissions are incomplete")


def _validate_manifest_support(manifest: Mapping[str, Any]) -> None:
    support_states = {"supported", "unsupported", "unavailable"}
    sources = manifest.get("telemetrySources")
    if not isinstance(sources, dict) or set(sources) != {
        "browser_webrtc",
        "engine_runtime",
        "encoder_pipeline",
    }:
        raise PixelatedBundleError("bundle manifest telemetry source support is incomplete")
    if any(value not in support_states for value in sources.values()):
        raise PixelatedBundleError("bundle manifest has an invalid telemetry support state")
    measurements = manifest.get("measurementSupport")
    if not isinstance(measurements, dict) or any(
        not isinstance(key, str) or value not in support_states
        for key, value in measurements.items()
    ):
        raise PixelatedBundleError("bundle manifest measurement support is invalid")


def validate_metadata_privacy(metadata: Mapping[str, Any]) -> None:
    forbidden = _forbidden_private_key(metadata, include_notes=True)
    if forbidden is not None:
        raise PixelatedBundleError(f"v2 run metadata must omit privacy field {forbidden!r}")


def _forbidden_private_key(value: Any, *, include_notes: bool = False) -> str | None:
    forbidden_keys = {
        "absolutepath",
        "enginetoken",
        "hostname",
        "peerid",
        "rawpeerid",
        "shareurl",
        "username",
    }
    if include_notes:
        forbidden_keys.add("notes")
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = "".join(character for character in str(key).lower() if character.isalnum())
            if normalized in forbidden_keys:
                return str(key)
            forbidden = _forbidden_private_key(nested, include_notes=include_notes)
            if forbidden is not None:
                return forbidden
    elif isinstance(value, list):
        for nested in value:
            forbidden = _forbidden_private_key(nested, include_notes=include_notes)
            if forbidden is not None:
                return forbidden
    return None


def validate_event_privacy(event_rows: Sequence[Mapping[str, str]]) -> None:
    for index, row in enumerate(event_rows, start=2):
        raw_details = (row.get("details_json") or "").strip()
        if not raw_details:
            continue
        try:
            details = strict_json_loads(raw_details)
        except ValueError as error:
            raise PixelatedBundleError(
                f"stream-events.csv row {index} details_json must be valid JSON"
            ) from error
        if not isinstance(details, dict):
            raise PixelatedBundleError(
                f"stream-events.csv row {index} details_json must be an object"
            )
        forbidden = _forbidden_private_key(details)
        if forbidden is not None:
            raise PixelatedBundleError(
                f"stream-events.csv row {index} exposes private peer identity {forbidden!r}"
            )


def _boolean_cell(value: str, *, source: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise PixelatedBundleError(f"{source} must be true or false")


def validate_engine_rows(
    rows: Sequence[Mapping[str, str]],
    *,
    run_id: str,
    session_id: str,
    workload_id: str,
    allow_empty: bool = False,
) -> None:
    if not rows:
        if allow_empty:
            return
        raise PixelatedBundleError("engine-telemetry.csv requires at least one data row")
    by_source: dict[str, list[Mapping[str, str]]] = {
        "engine_runtime": [],
        "encoder_pipeline": [],
    }
    for index, row in enumerate(rows, start=2):
        source = row.get("source", "")
        if source not in by_source:
            raise PixelatedBundleError(
                f"engine-telemetry.csv row {index} has unsupported source {source!r}"
            )
        by_source[source].append(row)
        if row.get("run_id") != run_id or row.get("session_id") != session_id:
            raise PixelatedBundleError(
                f"engine-telemetry.csv row {index} identity disagrees with metadata"
            )
        if row.get("game_id") != workload_id:
            raise PixelatedBundleError(
                f"engine-telemetry.csv row {index} workload disagrees with metadata"
            )
        if row.get("schema_version") != "1":
            raise PixelatedBundleError(
                f"engine-telemetry.csv row {index} requires schema_version 1"
            )
        available = _boolean_cell(
            row.get("available", ""),
            source=f"engine-telemetry.csv row {index} available",
        )
        error = (row.get("error") or "").strip()
        if available and error:
            raise PixelatedBundleError(
                f"engine-telemetry.csv row {index} cannot be available with an error"
            )
        if not available and not error:
            raise PixelatedBundleError(
                f"engine-telemetry.csv row {index} unavailable samples require an error"
            )
    for source, source_rows in by_source.items():
        _validate_source_sequence(source, source_rows)


def _validate_source_sequence(source: str, rows: Sequence[Mapping[str, str]]) -> None:
    if not rows:
        raise PixelatedBundleError(f"engine-telemetry.csv requires source {source!r}")
    elapsed = [
        finite_number(
            row["elapsed_ms"],
            source=f"engine-telemetry.csv {source} elapsed_ms",
        )
        for row in rows
    ]
    timestamps = [
        utc_datetime(
            row["captured_at"],
            source=f"engine-telemetry.csv {source} captured_at",
        )
        for row in rows
    ]
    if any(value < 0 for value in elapsed) or any(
        current <= previous for previous, current in zip(elapsed, elapsed[1:], strict=False)
    ):
        raise PixelatedBundleError(
            f"engine-telemetry.csv {source} elapsed_ms must be non-negative and strictly increasing"
        )
    if any(
        current <= previous for previous, current in zip(timestamps, timestamps[1:], strict=False)
    ):
        raise PixelatedBundleError(
            f"engine-telemetry.csv {source} captured_at must be strictly increasing"
        )
    for timestamp, elapsed_ms in zip(timestamps, elapsed, strict=True):
        wall_elapsed_s = (timestamp - timestamps[0]).total_seconds()
        declared_elapsed_s = (elapsed_ms - elapsed[0]) / 1000
        if abs(wall_elapsed_s - declared_elapsed_s) > 0.001:
            raise PixelatedBundleError(
                f"engine-telemetry.csv {source} wall-clock and elapsed times disagree"
            )


def validate_engine_window_alignment(
    rows: Sequence[Mapping[str, str]],
    *,
    started_at: datetime,
    ended_at: datetime,
    elapsed_start_ms: float,
    elapsed_end_ms: float,
) -> None:
    """Ensure engine samples belong to the browser observation interval."""

    timestamp_margin = timedelta(seconds=1)
    elapsed_margin_ms = 1000
    for index, row in enumerate(rows, start=2):
        timestamp = utc_datetime(
            row["captured_at"], source=f"engine-telemetry.csv row {index} captured_at"
        )
        elapsed_ms = finite_number(
            row["elapsed_ms"], source=f"engine-telemetry.csv row {index} elapsed_ms"
        )
        if not started_at - timestamp_margin <= timestamp <= ended_at + timestamp_margin:
            raise PixelatedBundleError(
                f"engine-telemetry.csv row {index} falls outside the browser capture window"
            )
        if not (
            elapsed_start_ms - elapsed_margin_ms <= elapsed_ms <= elapsed_end_ms + elapsed_margin_ms
        ):
            raise PixelatedBundleError(
                f"engine-telemetry.csv row {index} elapsed time falls outside the browser window"
            )


def engine_effective_settings(rows: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    settings: dict[str, Any] = {}
    fields = {
        "cpuCapacityCores": "cpu_capacity_cores",
        "encoderCpuUsed": "cpu_used",
        "encoderMaxQuantizer": "max_quantizer",
        "logicalCpuCount": "logical_cpu_count",
        "runtimeKind": "runtime_kind",
        "targetBitrateKbps": "target_bitrate_kbps",
        "targetFps": "target_fps",
    }
    for setting, column in fields.items():
        values = {
            (row.get(column) or "").strip()
            for row in rows
            if row.get("available", "").strip().lower() == "true"
        }
        values.discard("")
        if len(values) > 1:
            raise PixelatedBundleError(
                f"engine-telemetry.csv {column} changed during the controlled window"
            )
        if not values:
            continue
        value = next(iter(values))
        if column == "runtime_kind":
            settings[setting] = value
        else:
            number = finite_number(value, source=f"engine-telemetry.csv {column}")
            if number < 0:
                raise PixelatedBundleError(f"engine-telemetry.csv {column} cannot be negative")
            settings[setting] = number
    return settings


def validate_summary(
    summary: Mapping[str, Any],
    engine_rows: Sequence[Mapping[str, str]],
    *,
    telemetry_count: int,
    duration_ms: float,
) -> None:
    if summary.get("schemaVersion") != 2:
        raise PixelatedBundleError("v2 summary.json requires schemaVersion 2")
    validity = summary.get("validity")
    if not isinstance(validity, dict) or not isinstance(validity.get("isValid"), bool):
        raise PixelatedBundleError("v2 summary.json requires validity state")
    sources = validity.get("sources")
    if not isinstance(sources, dict):
        raise PixelatedBundleError("v2 summary.json requires source counts")
    reasons = validity.get("reasons")
    if not isinstance(reasons, list) or any(
        not isinstance(reason, str) or not reason.strip() for reason in reasons
    ):
        raise PixelatedBundleError("v2 summary.json requires string validity reasons")
    if validity["isValid"] == bool(reasons):
        raise PixelatedBundleError("v2 summary.json validity and reasons disagree")
    recording = summary.get("recording")
    if not isinstance(recording, dict):
        raise PixelatedBundleError("v2 summary.json requires recording metadata")
    if recording.get("sampleCount") != telemetry_count:
        raise PixelatedBundleError("summary.json browser sample count disagrees with telemetry")
    declared_duration = recording.get("durationMs")
    if isinstance(declared_duration, bool) or not isinstance(declared_duration, (int, float)):
        raise PixelatedBundleError("summary.json recording durationMs must be numeric")
    if abs(float(declared_duration) - duration_ms) > 1:
        raise PixelatedBundleError("summary.json recording duration disagrees with telemetry")
    expected_counts = {
        "browserWebrtc": (telemetry_count, telemetry_count),
        "engineRuntime": (
            sum(row.get("source") == "engine_runtime" for row in engine_rows),
            sum(
                row.get("source") == "engine_runtime"
                and row.get("available", "").strip().lower() == "true"
                for row in engine_rows
            ),
        ),
        "encoderPipeline": (
            sum(row.get("source") == "encoder_pipeline" for row in engine_rows),
            sum(
                row.get("source") == "encoder_pipeline"
                and row.get("available", "").strip().lower() == "true"
                for row in engine_rows
            ),
        ),
    }
    if set(sources) != set(expected_counts):
        raise PixelatedBundleError("summary.json source count declarations are incomplete")
    for source, (expected_total, expected_available) in expected_counts.items():
        payload = sources.get(source)
        if not isinstance(payload, dict):
            raise PixelatedBundleError(f"summary.json {source} source counts must be an object")
        sample_count = payload.get("sampleCount")
        available_count = payload.get("availableSampleCount")
        if type(sample_count) is not int or sample_count != expected_total:
            raise PixelatedBundleError(
                f"summary.json {source} sample count disagrees with engine telemetry"
            )
        if type(available_count) is not int or available_count != expected_available:
            raise PixelatedBundleError(
                f"summary.json {source} available sample count disagrees with telemetry"
            )


def validity_reasons(
    metadata: Mapping[str, Any],
    manifest: Mapping[str, Any],
    engine_rows: Sequence[Mapping[str, str]],
) -> list[str]:
    reasons: list[str] = []
    sources = manifest["telemetrySources"]
    available = {
        source: any(
            row.get("source") == source and row.get("available", "").lower() == "true"
            for row in engine_rows
        )
        for source in ("engine_runtime", "encoder_pipeline")
    }
    for source, is_available in available.items():
        if (sources[source] == "supported") != is_available:
            raise PixelatedBundleError(
                f"bundle manifest support for {source} disagrees with telemetry"
            )
    if metadata.get("scenario") != "browser_only_baseline":
        source_rows = {
            source: [row for row in engine_rows if row.get("source") == source]
            for source in ("engine_runtime", "encoder_pipeline")
        }
        if not available["engine_runtime"]:
            reasons.append("required engine runtime telemetry is unavailable")
        elif any(
            row.get("available", "").strip().lower() != "true"
            for row in source_rows["engine_runtime"]
        ):
            reasons.append("engine runtime telemetry has unavailable samples")
        if not available["encoder_pipeline"]:
            reasons.append("required encoder pipeline telemetry is unavailable")
        elif any(
            row.get("available", "").strip().lower() != "true"
            for row in source_rows["encoder_pipeline"]
        ):
            reasons.append("encoder pipeline telemetry has unavailable samples")
    return reasons


__all__ = [
    "ENGINE_TELEMETRY_COLUMNS",
    "V2_REQUIRED_FILES",
    "engine_effective_settings",
    "validate_engine_rows",
    "validate_engine_window_alignment",
    "validate_manifest",
    "validate_metadata_privacy",
    "validate_summary",
    "validity_reasons",
]
