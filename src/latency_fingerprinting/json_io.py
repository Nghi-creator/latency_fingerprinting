"""Bounded, duplicate-safe JSON input helpers for public file boundaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

MAX_CONTRACT_JSON_BYTES = 10 * 1024 * 1024

ModelT = TypeVar("ModelT", bound=BaseModel)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def _reject_non_finite_constant(value: str) -> None:
    raise ValueError(f"JSON number must be finite, received {value}")


def strict_json_loads(text: str) -> Any:
    """Decode standards-compliant JSON while rejecting ambiguous object keys."""

    return json.loads(
        text,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_non_finite_constant,
    )


def read_bounded_text(
    path: Path,
    *,
    maximum_bytes: int = MAX_CONTRACT_JSON_BYTES,
) -> str:
    """Read one UTF-8 file with a pre- and post-read size bound."""

    if maximum_bytes <= 0:
        raise ValueError("maximum_bytes must be greater than zero")
    size = path.stat().st_size
    if size > maximum_bytes:
        raise ValueError(f"JSON file is too large: {path} ({size} bytes; max {maximum_bytes})")
    payload = path.read_bytes()
    if len(payload) > maximum_bytes:
        raise ValueError(
            f"JSON file is too large: {path} ({len(payload)} bytes; max {maximum_bytes})"
        )
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError(f"JSON file is not valid UTF-8: {path}: {error}") from error


def load_json_file(path: Path, *, maximum_bytes: int = MAX_CONTRACT_JSON_BYTES) -> Any:
    return strict_json_loads(read_bounded_text(path, maximum_bytes=maximum_bytes))


def load_model_file(path: Path, model: type[ModelT]) -> ModelT:
    """Load a contract model without Pydantic's duplicate-key JSON ambiguity."""

    return model.model_validate(load_json_file(path))


__all__ = [
    "MAX_CONTRACT_JSON_BYTES",
    "load_json_file",
    "load_model_file",
    "read_bounded_text",
    "strict_json_loads",
]
