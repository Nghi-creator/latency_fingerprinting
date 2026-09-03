"""Shared strict parsing helpers for Pixelated bundle adapters."""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any


class PixelatedBundleError(ValueError):
    """Raised when a bundle cannot safely produce a contract window."""


def required_string(payload: Mapping[str, Any], key: str, source: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PixelatedBundleError(f"{source} requires a non-empty string {key!r}")
    return value.strip()


def finite_number(value: str, *, source: str) -> float:
    try:
        number = float(value)
    except (OverflowError, ValueError) as error:
        raise PixelatedBundleError(f"{source} must be numeric, received {value!r}") from error
    if not math.isfinite(number):
        raise PixelatedBundleError(f"{source} must be finite")
    return number


def finite_json_number(value: Any, *, source: str) -> float:
    """Validate a decoded JSON number without leaking integer conversion overflow."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PixelatedBundleError(f"{source} must be numeric")
    try:
        number = float(value)
    except OverflowError as error:
        raise PixelatedBundleError(f"{source} must be finite") from error
    if not math.isfinite(number):
        raise PixelatedBundleError(f"{source} must be finite")
    return number


def utc_datetime(value: str, *, source: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise PixelatedBundleError(f"{source} must be an ISO 8601 timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise PixelatedBundleError(f"{source} must use a UTC offset")
    return parsed


__all__ = [
    "PixelatedBundleError",
    "finite_json_number",
    "finite_number",
    "required_string",
    "utc_datetime",
]
