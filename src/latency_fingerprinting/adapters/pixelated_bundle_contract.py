"""Shared raw bundle layouts and run-metadata v1 validation for Pixelated ingestion."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .pixelated_bundle_common import PixelatedBundleError
from .pixelated_bundle_common import finite_json_number as _finite_json_number
from .pixelated_bundle_common import required_string as _required_string
from .pixelated_bundle_v2 import V2_REQUIRED_FILES

V1_REQUIRED_FILES = frozenset(
    {
        "run-metadata.json",
        "stream-telemetry.csv",
        "stream-events.csv",
        "summary.json",
    }
)
READABLE_FILES = V2_REQUIRED_FILES
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


def validate_metadata(
    metadata: Mapping[str, Any],
) -> tuple[str, str, str, str, dict[str, Any]]:
    if type(metadata.get("schemaVersion")) is not int or metadata["schemaVersion"] != 1:
        raise PixelatedBundleError("run-metadata.json requires schemaVersion 1")
    run_id = _required_string(metadata, "runId", "run-metadata.json")
    session_id = _required_string(metadata, "sessionId", "run-metadata.json")
    game = metadata.get("game")
    if not isinstance(game, dict):
        raise PixelatedBundleError("run-metadata.json requires object 'game'")
    workload_id = _required_string(game, "id", "run-metadata.json game")
    player_mode = _required_string(metadata, "playerMode", "run-metadata.json")
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
        try:
            number = _finite_json_number(
                value,
                source=f"run-metadata.json streamProfile {key!r}",
            )
        except PixelatedBundleError as error:
            raise PixelatedBundleError(
                f"run-metadata.json streamProfile {key!r} must be finite, "
                "non-negative, numeric, or null"
            ) from error
        if number < 0:
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
    return run_id, session_id, workload_id, player_mode, settings
