"""Translate Pixelated research bundles into core observation windows."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..models import (
    ContextKey,
    ObservationWindow,
    ProvenanceKind,
    SourceArtifact,
    TimeBounds,
    ValidityState,
    WindowPhase,
)
from .pixelated_bundle_common import (
    PixelatedBundleError,
)
from .pixelated_bundle_common import (
    finite_number as _finite_number,
)
from .pixelated_bundle_common import (
    required_string as _required_string,
)
from .pixelated_bundle_common import (
    utc_datetime as _utc_datetime,
)
from .pixelated_bundle_io import (
    bundle_checksum as _bundle_checksum,
)
from .pixelated_bundle_io import (
    csv_rows as _csv_rows,
)
from .pixelated_bundle_io import (
    json_object as _json_object,
)
from .pixelated_bundle_io import (
    read_bundle as _read_bundle_files,
)
from .pixelated_bundle_metrics import (
    BROWSER_METRIC_COLUMNS as METRIC_COLUMNS,
)
from .pixelated_bundle_metrics import (
    STREAM_COUNTER_METRICS,
)
from .pixelated_bundle_metrics import (
    counter_metrics as _counter_metrics,
)
from .pixelated_bundle_metrics import (
    engine_metrics as _engine_metrics,
)
from .pixelated_bundle_metrics import (
    mapped_metrics as _metrics,
)
from .pixelated_bundle_v2 import (
    ENGINE_TELEMETRY_COLUMNS,
    V2_REQUIRED_FILES,
)
from .pixelated_bundle_v2 import (
    engine_effective_settings as _engine_effective_settings,
)
from .pixelated_bundle_v2 import (
    validate_engine_rows as _validate_engine_rows,
)
from .pixelated_bundle_v2 import (
    validate_manifest as _validate_manifest,
)
from .pixelated_bundle_v2 import (
    validate_metadata_privacy as _validate_v2_metadata_privacy,
)
from .pixelated_bundle_v2 import (
    validate_summary as _validate_v2_summary,
)
from .pixelated_bundle_v2 import (
    validity_reasons as _v2_validity_reasons,
)

V1_REQUIRED_FILES = frozenset(
    {
        "run-metadata.json",
        "stream-telemetry.csv",
        "stream-events.csv",
        "summary.json",
    }
)
READABLE_FILES = V2_REQUIRED_FILES
# Kept as the public v1 alias for callers that froze the original contract.
REQUIRED_FILES = V1_REQUIRED_FILES
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


def _read_bundle(path: Path) -> dict[str, bytes]:
    return _read_bundle_files(
        path,
        readable_files=READABLE_FILES,
        required_files=V1_REQUIRED_FILES,
    )


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
    manifest = (
        _json_object(files, "bundle-manifest.json") if "bundle-manifest.json" in files else None
    )
    bundle_schema_version = "2" if manifest is not None else "1"
    declared_bundle_version = context.versions.get("pixelatedBundleSchema")
    if declared_bundle_version and declared_bundle_version != bundle_schema_version:
        raise PixelatedBundleError(
            "context pixelatedBundleSchema disagrees with the ingested bundle"
        )
    telemetry_rows = _csv_rows(files, "stream-telemetry.csv", TELEMETRY_COLUMNS)
    event_rows = _csv_rows(files, "stream-events.csv", EVENT_COLUMNS)
    if not telemetry_rows:
        raise PixelatedBundleError("stream-telemetry.csv requires at least one data row")

    run_id, session_id, effective_settings = _validate_metadata(metadata)
    engine_rows: list[dict[str, str]] = []
    if manifest is not None:
        _validate_v2_metadata_privacy(metadata)
        _validate_manifest(
            manifest,
            files,
            comparison_case_id=comparison_case_id,
            phase=phase,
            run_id=run_id,
        )
        engine_rows = _csv_rows(
            files,
            "engine-telemetry.csv",
            ENGINE_TELEMETRY_COLUMNS,
        )
        _validate_engine_rows(
            engine_rows,
            run_id=run_id,
            session_id=session_id,
            allow_empty=metadata.get("scenario") == "browser_only_baseline",
        )
        _validate_v2_summary(summary, engine_rows)
        effective_settings.update(_engine_effective_settings(engine_rows))
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
    counter_metrics, counter_missing, counter_rejected = _counter_metrics(
        telemetry_rows,
        STREAM_COUNTER_METRICS,
        source_name="stream-telemetry.csv",
    )
    metrics.update(counter_metrics)
    missing_metrics.extend(counter_missing)
    rejected_metrics.update(counter_rejected)
    if manifest is not None:
        engine_metrics, engine_missing, engine_rejected = _engine_metrics(engine_rows)
        metrics.update(engine_metrics)
        missing_metrics.extend(engine_missing)
        rejected_metrics.update(engine_rejected)
    reasons = _validity_reasons(telemetry_rows, event_rows)
    if manifest is not None:
        reasons.extend(_v2_validity_reasons(metadata, manifest, engine_rows))
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
        missing_metrics=sorted(set(missing_metrics)),
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
    "ENGINE_TELEMETRY_COLUMNS",
    "METRIC_COLUMNS",
    "REQUIRED_FILES",
    "TELEMETRY_COLUMNS",
    "V1_REQUIRED_FILES",
    "V2_REQUIRED_FILES",
    "PixelatedBundleError",
    "ingest_pixelated_bundle",
]
