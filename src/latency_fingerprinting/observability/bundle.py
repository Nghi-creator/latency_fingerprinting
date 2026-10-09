"""Strict standalone Pixelated stage-trace adoption, independent of research v2."""

import gzip
import hashlib
import io
import os
import stat
import tarfile
import zlib
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from ..adapters.pixelated_bundle_io import _open_bundle
from ..json_io import MAX_CONTRACT_JSON_BYTES
from ..pipeline import canonical_json
from .contracts import Count, TraceModel
from .json import decode_trace_json
from .trace import StageTraceRecord

MAX_BUNDLE_BYTES = 32 * 1024 * 1024
FILES = frozenset({"trace-manifest.json", "trace-record.json"})


class TraceManifest(TraceModel):
    schema_version: Annotated[int, Field(strict=True, ge=1, le=1)]
    bundle_type: Literal["pixelated_stage_trace"]
    trace_schema_version: Literal["stage-trace-record-v1"]
    trace_sha256: Annotated[str, Field(strict=True, pattern=r"^[0-9a-f]{64}$")]
    trace_bytes: Count


def _read_file(source, maximum):
    metadata = os.fstat(source.fileno())
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > maximum:
        raise ValueError("input must be a bounded regular file")
    payload = source.read(maximum + 1)
    if len(payload) > maximum:
        raise ValueError("input exceeds byte limit")
    return payload


def _directory(descriptor):
    names = set()
    with os.scandir(descriptor) as entries:
        for entry in entries:
            if entry.name not in FILES or entry.name in names:
                raise ValueError("unexpected directory entry")
            names.add(entry.name)
    if names != FILES:
        raise ValueError("missing trace member")
    files = {}
    for name in sorted(FILES):
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
        with os.fdopen(fd, "rb") as source:
            files[name] = _read_file(source, MAX_CONTRACT_JSON_BYTES)
    return files


def _check_headers(expanded):
    # Check physical headers before tarfile can recursively interpret extensions.
    offset, names = 0, set()
    for _ in range(2):
        header = expanded[offset : offset + 512]
        name = header[:100].split(b"\0", 1)[0]
        if (
            len(header) != 512
            or name not in {item.encode("ascii") for item in FILES}
            or name in names
            or header[156:157] not in (b"0", b"\0")
        ):
            raise ValueError("invalid physical trace TAR header")
        names.add(name)
        size = int(header[124:136].strip(b"\0 "), 8)
        if not 0 <= size <= MAX_CONTRACT_JSON_BYTES:
            raise ValueError("trace TAR member exceeds byte limit")
        offset += 512 + ((size + 511) // 512) * 512
    if len(expanded) % 512 or len(expanded) < offset + 1024 or any(expanded[offset:]):
        raise ValueError("invalid trace TAR terminator")


def _archive(source):
    compressed = _read_file(source, MAX_BUNDLE_BYTES)
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as decoder:
        expanded = decoder.read(MAX_BUNDLE_BYTES + 1)
    if len(expanded) > MAX_BUNDLE_BYTES:
        raise ValueError("expanded archive exceeds byte limit")
    _check_headers(expanded)
    files = {}
    offset = 0
    with tarfile.open(fileobj=io.BytesIO(expanded), mode="r:") as archive:
        for member in archive:
            # Reject TAR extensions, hidden headers, aliases, links and directories.
            if (
                member.name not in FILES
                or member.name in files
                or not member.isfile()
                or member.offset != offset
                or member.offset_data != offset + 512
                or expanded[offset + 156 : offset + 157] not in (b"0", b"\0")
                or not 0 <= member.size <= MAX_CONTRACT_JSON_BYTES
                or member.pax_headers
            ):
                raise ValueError("invalid trace TAR member")
            extracted = archive.extractfile(member)
            if extracted is None:
                raise ValueError("unreadable trace member")
            with extracted:
                payload = extracted.read(MAX_CONTRACT_JSON_BYTES + 1)
            if len(payload) != member.size:
                raise ValueError("invalid trace member length")
            files[member.name] = payload
            offset = member.offset_data + ((member.size + 511) // 512) * 512
    if (
        len(expanded) % 512
        or len(expanded) < offset + 1024
        or any(expanded[offset:])
        or files.keys() != FILES
    ):
        raise ValueError("invalid trace TAR layout")
    return files


def ingest_trace_bundle(path: Path) -> StageTraceRecord:
    """Validate layout, bounded JSON, manifest identity and canonical record bytes."""
    try:
        descriptor = _open_bundle(Path(path))
        try:
            if stat.S_ISDIR(os.fstat(descriptor).st_mode):
                files = _directory(descriptor)
            else:
                with os.fdopen(descriptor, "rb", closefd=False) as source:
                    files = _archive(source)
        finally:
            os.close(descriptor)
        manifest_payload = decode_trace_json(files["trace-manifest.json"])
        manifest = TraceManifest.model_validate(manifest_payload)
        payload = files["trace-record.json"]
        if (
            len(payload) != manifest.trace_bytes
            or hashlib.sha256(payload).hexdigest() != manifest.trace_sha256
        ):
            raise ValueError("trace hash or byte count mismatch")
        trace = StageTraceRecord.model_validate_json(payload)
        if canonical_json(trace).encode("utf-8") != payload:
            raise ValueError("noncanonical trace serialization")
        return trace
    except (OSError, ValueError, tarfile.TarError, EOFError, KeyError, zlib.error):
        # Never echo paths, Pydantic inputs, TAR names or private supplied values.
        raise ValueError("invalid_trace_bundle") from None
