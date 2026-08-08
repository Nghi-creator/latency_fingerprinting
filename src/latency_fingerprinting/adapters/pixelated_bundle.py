"""Translate Pixelated research bundles into core observation windows."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import statistics
import tarfile
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any

from ..models import (
    ContextKey,
    MetricAggregate,
    ObservationWindow,
    ProvenanceKind,
    SourceArtifact,
    TimeBounds,
    ValidityState,
    WindowPhase,
)

REQUIRED_FILES = frozenset(
    {
        "run-metadata.json",
        "stream-telemetry.csv",
        "stream-events.csv",
        "summary.json",
    }
)
TELEMETRY_COLUMNS = frozenset(
    {
        "captured_at",
        "elapsed_ms",
        "session_id",
        "game_id",
        "player_mode",
        "status",
        "fps",
        "bitrate_kbps",
        "packets_lost_total",
        "packets_lost_delta",
        "jitter_ms",
        "ice_connection_state",
        "connection_state",
        "last_engine_error",
    }
)
EVENT_COLUMNS = frozenset(
    {"captured_at", "elapsed_ms", "run_id", "session_id", "event", "details_json"}
)
METRIC_COLUMNS: Mapping[str, tuple[str, str]] = {
    "client.received_fps": ("fps", "fps"),
    "client.received_bitrate_kbps": ("bitrate_kbps", "kbps"),
    "transport.jitter_ms": ("jitter_ms", "ms"),
    "transport.packets_lost_delta": ("packets_lost_delta", "packets"),
}
MAX_ARCHIVE_MEMBERS = 64
MAX_TEXT_FILE_BYTES = 10 * 1024 * 1024


class PixelatedBundleError(ValueError):
    """Raised when a bundle cannot safely produce a contract window."""


def _safe_archive_name(name: str) -> str:
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts:
        raise PixelatedBundleError(f"unsafe TAR member path: {name!r}")
    return path.as_posix()


def _read_tar(path: Path) -> dict[str, bytes]:
    try:
        with tarfile.open(path, mode="r:*") as archive:
            return _read_tar_members(archive)
    except (OSError, tarfile.TarError) as error:
        raise PixelatedBundleError(f"cannot read TAR archive: {error}") from error


def _read_tar_members(archive: tarfile.TarFile) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    members = archive.getmembers()
    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise PixelatedBundleError(
            f"TAR contains {len(members)} members; maximum is {MAX_ARCHIVE_MEMBERS}"
        )
    for member in members:
        name = _safe_archive_name(member.name)
        if member.issym() or member.islnk():
            raise PixelatedBundleError(f"TAR links are not allowed: {name!r}")
        if member.isdir():
            continue
        if not member.isfile():
            raise PixelatedBundleError(f"unsupported TAR member type: {name!r}")
        if name not in REQUIRED_FILES:
            continue
        if name in files:
            raise PixelatedBundleError(f"duplicate TAR member: {name!r}")
        if member.size > MAX_TEXT_FILE_BYTES:
            raise PixelatedBundleError(f"bundle file is too large: {name!r}")
        extracted = archive.extractfile(member)
        if extracted is None:
            raise PixelatedBundleError(f"cannot read TAR member: {name!r}")
        files[name] = extracted.read(MAX_TEXT_FILE_BYTES + 1)
    return files


def _read_directory(path: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for name in REQUIRED_FILES:
        candidate = path / name
        if candidate.is_symlink():
            raise PixelatedBundleError(f"bundle links are not allowed: {name!r}")
        if not candidate.is_file():
            continue
        if candidate.stat().st_size > MAX_TEXT_FILE_BYTES:
            raise PixelatedBundleError(f"bundle file is too large: {name!r}")
        files[name] = candidate.read_bytes()
    return files


def _read_bundle(path: Path) -> dict[str, bytes]:
    if path.is_dir():
        files = _read_directory(path)
    elif path.is_file():
        files = _read_tar(path)
    else:
        raise PixelatedBundleError(f"bundle path does not exist: {path}")
    missing = sorted(REQUIRED_FILES - files.keys())
    if missing:
        raise PixelatedBundleError(f"bundle is missing required files: {', '.join(missing)}")
    return files


def _decode(files: Mapping[str, bytes], name: str) -> str:
    try:
        return files[name].decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise PixelatedBundleError(f"{name} is not valid UTF-8: {error}") from error


def _json_object(files: Mapping[str, bytes], name: str) -> dict[str, Any]:
    try:
        payload = json.loads(_decode(files, name))
    except json.JSONDecodeError as error:
        raise PixelatedBundleError(f"{name} is not valid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise PixelatedBundleError(f"{name} JSON root must be an object")
    return payload


def _csv_rows(
    files: Mapping[str, bytes],
    name: str,
    required_columns: frozenset[str],
) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(_decode(files, name), newline=""), strict=True)
    headers = reader.fieldnames
    if headers is None:
        raise PixelatedBundleError(f"{name} requires a header row")
    if len(headers) != len(set(headers)):
        raise PixelatedBundleError(f"{name} contains duplicate columns")
    missing = sorted(required_columns - set(headers))
    if missing:
        raise PixelatedBundleError(f"{name} is missing required columns: {', '.join(missing)}")
    try:
        rows = [dict(row) for row in reader]
    except csv.Error as error:
        raise PixelatedBundleError(f"{name} is not valid CSV: {error}") from error
    for index, row in enumerate(rows, start=2):
        if None in row or any(row.get(header) is None for header in headers):
            raise PixelatedBundleError(f"{name} row {index} has the wrong number of columns")
    return rows


def _required_string(payload: Mapping[str, Any], key: str, source: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PixelatedBundleError(f"{source} requires a non-empty string {key!r}")
    return value.strip()


def _finite_number(value: str, *, source: str) -> float:
    try:
        number = float(value)
    except ValueError as error:
        raise PixelatedBundleError(f"{source} must be numeric, received {value!r}") from error
    if not math.isfinite(number):
        raise PixelatedBundleError(f"{source} must be finite")
    return number


def _utc_datetime(value: str, *, source: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise PixelatedBundleError(f"{source} must be an ISO 8601 timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise PixelatedBundleError(f"{source} must use a UTC offset")
    return parsed


def _percentile_95(values: Sequence[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)]


def _aggregate(values: Sequence[float], unit: str) -> MetricAggregate:
    ordered = sorted(values)
    median = float(statistics.median(ordered))
    return MetricAggregate(
        unit=unit,
        aggregation="median",
        value=median,
        count=len(ordered),
        median=median,
        p95=_percentile_95(ordered),
        minimum=ordered[0],
        maximum=ordered[-1],
    )


def _metrics(
    rows: Sequence[Mapping[str, str]],
) -> tuple[dict[str, MetricAggregate], list[str], dict[str, str]]:
    metrics: dict[str, MetricAggregate] = {}
    missing: list[str] = []
    rejected: dict[str, str] = {}
    for metric, (column, unit) in METRIC_COLUMNS.items():
        values: list[float] = []
        invalid: list[str] = []
        for index, row in enumerate(rows, start=2):
            raw = (row.get(column) or "").strip()
            if not raw:
                continue
            try:
                value = _finite_number(raw, source=f"stream-telemetry.csv row {index} {column}")
            except PixelatedBundleError as error:
                invalid.append(str(error))
                continue
            if value < 0:
                invalid.append(f"stream-telemetry.csv row {index} {column} cannot be negative")
            else:
                values.append(value)
        if invalid:
            rejected[metric] = "; ".join(invalid)
        elif values:
            metrics[metric] = _aggregate(values, unit)
        else:
            missing.append(metric)
    return metrics, sorted(missing), rejected


def _bundle_checksum(files: Mapping[str, bytes]) -> str:
    digest = hashlib.sha256()
    for name in sorted(REQUIRED_FILES):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(files[name])
        digest.update(b"\0")
    return digest.hexdigest()


def _validate_metadata(metadata: Mapping[str, Any]) -> tuple[str, str, dict[str, Any]]:
    if metadata.get("schemaVersion") != 1:
        raise PixelatedBundleError("run-metadata.json requires schemaVersion 1")
    run_id = _required_string(metadata, "runId", "run-metadata.json")
    session_id = _required_string(metadata, "sessionId", "run-metadata.json")
    profile = metadata.get("streamProfile")
    if not isinstance(profile, dict):
        raise PixelatedBundleError("run-metadata.json requires object 'streamProfile'")

    settings: dict[str, Any] = {}
    for key in ("bitrateKbps", "fps", "id"):
        if key not in profile:
            raise PixelatedBundleError(f"run-metadata.json streamProfile requires {key!r}")
    for key in ("bitrateKbps", "fps"):
        value = profile[key]
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise PixelatedBundleError(
                f"run-metadata.json streamProfile {key!r} must be numeric or null"
            )
        if not math.isfinite(value) or value < 0:
            raise PixelatedBundleError(
                f"run-metadata.json streamProfile {key!r} must be finite and non-negative"
            )
        settings[key] = value
    profile_id = profile["id"]
    if profile_id is not None:
        if not isinstance(profile_id, str) or not profile_id.strip():
            raise PixelatedBundleError(
                "run-metadata.json streamProfile 'id' must be a non-empty string or null"
            )
        settings["streamProfileId"] = profile_id.strip()
    return run_id, session_id, settings


def _validate_cross_file_identity(
    summary: Mapping[str, Any],
    telemetry_rows: Sequence[Mapping[str, str]],
    event_rows: Sequence[Mapping[str, str]],
    *,
    run_id: str,
    session_id: str,
) -> None:
    if summary.get("runId") != run_id or summary.get("sessionId") != session_id:
        raise PixelatedBundleError("summary.json run/session identity disagrees with metadata")
    recording = summary.get("recording")
    if not isinstance(recording, dict):
        raise PixelatedBundleError("summary.json requires object 'recording'")
    if recording.get("sampleCount") != len(telemetry_rows):
        raise PixelatedBundleError("summary.json sample count disagrees with telemetry")
    for source, rows, run_column in (
        ("stream-telemetry.csv", telemetry_rows, None),
        ("stream-events.csv", event_rows, "run_id"),
    ):
        for index, row in enumerate(rows, start=2):
            if row.get("session_id") != session_id:
                raise PixelatedBundleError(
                    f"{source} row {index} session_id disagrees with metadata"
                )
            if run_column is not None and row.get(run_column) != run_id:
                raise PixelatedBundleError(f"{source} row {index} run_id disagrees with metadata")


def _validity_reasons(
    telemetry_rows: Sequence[Mapping[str, str]],
    event_rows: Sequence[Mapping[str, str]],
) -> list[str]:
    reasons: list[str] = []
    if any(row.get("status") != "playing" for row in telemetry_rows):
        reasons.append("telemetry window includes inactive playback")
    if any(row.get("connection_state") != "connected" for row in telemetry_rows):
        reasons.append("telemetry window includes a non-connected peer state")
    if any(
        row.get("ice_connection_state") not in {"connected", "completed"} for row in telemetry_rows
    ):
        reasons.append("telemetry window includes an unusable ICE state")
    if any((row.get("last_engine_error") or "").strip() for row in telemetry_rows):
        reasons.append("telemetry window includes an engine error")
    events = {row.get("event") for row in event_rows}
    if "connection_disconnected" in events:
        reasons.append("window includes a connection-disconnected event")
    if "engine_error" in events:
        reasons.append("window includes an engine-error event")
    return reasons


def ingest_pixelated_bundle(
    bundle_path: Path,
    *,
    phase: WindowPhase,
    comparison_case_id: str,
    context: ContextKey,
    provenance: ProvenanceKind = ProvenanceKind.CONTROLLED_REAL,
    confounders: Sequence[str] = (),
) -> ObservationWindow:
    """Ingest one complete Pixelated paired-run bundle as a core window.

    Context is explicit because Pixelated's browser bundle cannot truthfully
    supply node, runtime, encoder, and version identity on its own.
    """

    if not comparison_case_id.strip():
        raise PixelatedBundleError("comparison_case_id cannot be empty")
    files = _read_bundle(bundle_path)
    metadata = _json_object(files, "run-metadata.json")
    summary = _json_object(files, "summary.json")
    telemetry_rows = _csv_rows(files, "stream-telemetry.csv", TELEMETRY_COLUMNS)
    event_rows = _csv_rows(files, "stream-events.csv", EVENT_COLUMNS)
    if not telemetry_rows:
        raise PixelatedBundleError("stream-telemetry.csv requires at least one data row")

    run_id, session_id, effective_settings = _validate_metadata(metadata)
    _validate_cross_file_identity(
        summary,
        telemetry_rows,
        event_rows,
        run_id=run_id,
        session_id=session_id,
    )

    elapsed = [
        _finite_number(row["elapsed_ms"], source=f"stream-telemetry.csv row {index} elapsed_ms")
        for index, row in enumerate(telemetry_rows, start=2)
    ]
    if any(value < 0 for value in elapsed):
        raise PixelatedBundleError("telemetry elapsed_ms cannot be negative")
    if elapsed != sorted(elapsed):
        raise PixelatedBundleError("telemetry elapsed_ms must be monotonically non-decreasing")
    timestamps = [
        _utc_datetime(
            row["captured_at"],
            source=f"stream-telemetry.csv row {index} captured_at",
        )
        for index, row in enumerate(telemetry_rows, start=2)
    ]
    if timestamps != sorted(timestamps):
        raise PixelatedBundleError("telemetry captured_at must be monotonically non-decreasing")
    duration_s = (timestamps[-1] - timestamps[0]).total_seconds()
    if duration_s <= 0:
        raise PixelatedBundleError("telemetry window duration must be greater than zero")
    elapsed_duration_s = (elapsed[-1] - elapsed[0]) / 1000
    if not math.isclose(duration_s, elapsed_duration_s, rel_tol=1e-6, abs_tol=0.001):
        raise PixelatedBundleError("telemetry wall-clock and elapsed durations disagree")

    metrics, missing_metrics, rejected_metrics = _metrics(telemetry_rows)
    reasons = _validity_reasons(telemetry_rows, event_rows)
    checksum = _bundle_checksum(files)
    return ObservationWindow(
        run_id=run_id,
        window_id=f"{run_id}-{phase.value}",
        comparison_case_id=comparison_case_id,
        context=context,
        phase=phase,
        bounds=TimeBounds(
            started_at=timestamps[0],
            ended_at=timestamps[-1],
        ),
        duration_s=duration_s,
        sample_count=len(telemetry_rows),
        effective_settings=effective_settings,
        metrics=metrics,
        missing_metrics=missing_metrics,
        rejected_metrics=rejected_metrics,
        validity=ValidityState(is_valid=not reasons, reasons=reasons),
        source_artifact=SourceArtifact(
            artifact_id=f"pixelated-bundle-{checksum[:16]}",
            source_type="pixelated_research_bundle",
            checksum=f"sha256:{checksum}",
            producer="Pixelated Studio Edition research exporter",
        ),
        provenance=provenance,
        confounders=list(confounders),
    )


__all__ = [
    "EVENT_COLUMNS",
    "METRIC_COLUMNS",
    "REQUIRED_FILES",
    "TELEMETRY_COLUMNS",
    "PixelatedBundleError",
    "ingest_pixelated_bundle",
]
