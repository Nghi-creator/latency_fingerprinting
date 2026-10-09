"""Bounded no-follow reading of standalone validated N4 trace JSON."""

import os
from pathlib import Path

from ..adapters.pixelated_bundle_io import _open_bundle
from ..json_io import MAX_CONTRACT_JSON_BYTES
from .bundle import _read_file
from .trace import StageTraceRecord


def read_trace_record(path: Path) -> StageTraceRecord:
    try:
        descriptor = _open_bundle(Path(path))
        try:
            with os.fdopen(descriptor, "rb", closefd=False) as source:
                payload = _read_file(source, MAX_CONTRACT_JSON_BYTES)
        finally:
            os.close(descriptor)
        return StageTraceRecord.model_validate_json(payload)
    except (OSError, ValueError):
        raise ValueError("invalid_trace_record") from None
