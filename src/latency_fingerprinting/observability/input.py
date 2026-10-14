"""Bounded no-follow reading of standalone validated N4 trace JSON."""

import os
from pathlib import Path

from ..adapters.pixelated_bundle_io import _open_bundle
from ..json_io import MAX_CONTRACT_JSON_BYTES
from .browser_v2 import StageTraceRecordV2, parse_trace_record
from .bundle import _read_file
from .json import decode_trace_json
from .trace import StageTraceRecord


def read_trace_record(path: Path) -> StageTraceRecord | StageTraceRecordV2:
    try:
        descriptor = _open_bundle(Path(path))
        try:
            with os.fdopen(descriptor, "rb", closefd=False) as source:
                payload = _read_file(source, MAX_CONTRACT_JSON_BYTES)
        finally:
            os.close(descriptor)
        return parse_trace_record(decode_trace_json(payload))
    except (OSError, ValueError):
        raise ValueError("invalid_trace_record") from None
