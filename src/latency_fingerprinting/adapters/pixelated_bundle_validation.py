"""Cross-file identity and stream-sequence validation for Pixelated bundles."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from .pixelated_bundle_common import PixelatedBundleError, finite_number, utc_datetime

FORMAL_CAPTURE_EVENTS = frozenset(
    {
        "research_recording_completed",
        "research_recording_started",
        "research_run_cancelled",
        "research_run_invalidated",
        "research_warmup_started",
    }
)


def validate_cross_file_identity(
    summary: Mapping[str, Any],
    telemetry_rows: Sequence[Mapping[str, str]],
    event_rows: Sequence[Mapping[str, str]],
    *,
    run_id: str,
    session_id: str,
    workload_id: str,
    player_mode: str,
) -> None:
    if summary.get("runId") != run_id or summary.get("sessionId") != session_id:
        raise PixelatedBundleError("summary.json run/session identity disagrees with metadata")
    recording = summary.get("recording")
    if not isinstance(recording, dict):
        raise PixelatedBundleError("summary.json requires object 'recording'")
    if recording.get("sampleCount") != len(telemetry_rows):
        raise PixelatedBundleError("summary.json sample count disagrees with telemetry")
    final_session_event_count = sum(row.get("session_id") == session_id for row in event_rows)
    if summary.get("eventCount") != final_session_event_count:
        raise PixelatedBundleError("summary.json event count disagrees with events")

    for index, row in enumerate(telemetry_rows, start=2):
        if row.get("session_id") != session_id:
            raise PixelatedBundleError(
                f"stream-telemetry.csv row {index} session_id disagrees with metadata"
            )
        if row.get("game_id") != workload_id:
            raise PixelatedBundleError(
                f"stream-telemetry.csv row {index} workload disagrees with metadata"
            )
        if row.get("player_mode") != player_mode:
            raise PixelatedBundleError(
                f"stream-telemetry.csv row {index} player mode disagrees with metadata"
            )

    final_session_seen = False
    previous_elapsed: float | None = None
    previous_timestamp: datetime | None = None
    first_elapsed: float | None = None
    first_timestamp: datetime | None = None
    for index, row in enumerate(event_rows, start=2):
        if row.get("run_id") != run_id:
            raise PixelatedBundleError(
                f"stream-events.csv row {index} run_id disagrees with metadata"
            )
        elapsed = finite_number(
            row.get("elapsed_ms", ""),
            source=f"stream-events.csv row {index} elapsed_ms",
        )
        if elapsed < 0 or (previous_elapsed is not None and elapsed < previous_elapsed):
            raise PixelatedBundleError(
                "stream-events.csv elapsed_ms must be non-negative and monotonic"
            )
        timestamp = utc_datetime(
            row.get("captured_at", ""),
            source=f"stream-events.csv row {index} captured_at",
        )
        if previous_timestamp is not None and timestamp < previous_timestamp:
            raise PixelatedBundleError("stream-events.csv captured_at must be monotonic")
        if first_elapsed is None or first_timestamp is None:
            first_elapsed = elapsed
            first_timestamp = timestamp
        wall_elapsed_s = (timestamp - first_timestamp).total_seconds()
        declared_elapsed_s = (elapsed - first_elapsed) / 1000
        if not math.isclose(wall_elapsed_s, declared_elapsed_s, rel_tol=1e-6, abs_tol=0.001):
            raise PixelatedBundleError(
                f"stream-events.csv row {index} wall-clock and elapsed times disagree"
            )
        previous_elapsed = elapsed
        previous_timestamp = timestamp
        row_session_id = row.get("session_id")
        if row_session_id == session_id:
            final_session_seen = True
            continue
        if row.get("event") in FORMAL_CAPTURE_EVENTS:
            raise PixelatedBundleError(
                f"stream-events.csv row {index} formal capture event "
                "disagrees with metadata session"
            )
        if final_session_seen:
            raise PixelatedBundleError(
                f"stream-events.csv row {index} switches away from metadata session"
            )
    if event_rows and not final_session_seen:
        raise PixelatedBundleError("stream-events.csv never binds to the metadata session")


def validate_packet_loss_deltas(telemetry_rows: Sequence[Mapping[str, str]]) -> None:
    previous_total: float | None = None
    for index, row in enumerate(telemetry_rows, start=2):
        total = finite_number(
            row["packets_lost_total"],
            source=f"stream-telemetry.csv row {index} packets_lost_total",
        )
        delta = finite_number(
            row["packets_lost_delta"],
            source=f"stream-telemetry.csv row {index} packets_lost_delta",
        )
        if total < 0 or delta < 0:
            raise PixelatedBundleError("stream telemetry packet-loss counters cannot be negative")
        if previous_total is None:
            expected_delta = 0.0
        else:
            expected_delta = total - previous_total
            if expected_delta < 0:
                raise PixelatedBundleError("packet-loss counter reset during the telemetry window")
        if not math.isclose(delta, expected_delta, rel_tol=0, abs_tol=1e-9):
            raise PixelatedBundleError(
                f"stream-telemetry.csv row {index} packets_lost_delta "
                "disagrees with cumulative counter"
            )
        previous_total = total


def validity_reasons(
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


__all__ = [
    "validate_cross_file_identity",
    "validate_packet_loss_deltas",
    "validity_reasons",
]
