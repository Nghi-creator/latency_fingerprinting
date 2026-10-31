"""Privacy declarations and recursive metadata/event checks for Pixelated v2 bundles."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ..json_io import strict_json_loads
from .pixelated_bundle_common import PixelatedBundleError


def validate_manifest_privacy(manifest: Mapping[str, Any]) -> None:
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
