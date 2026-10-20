"""Bounded directory/gzip USTAR reader; never extracts members to disk."""

import gzip
import io
import os
import re
import stat
import tarfile
from pathlib import Path

from ..adapters.pixelated_bundle_io import _open_bundle
from ..observability.bundle import _read_file

MAX_BUNDLE_BYTES = 64 * 1024 * 1024
MAX_JSON_BYTES = 10 * 1024 * 1024
ROOTS = frozenset({"experiment-manifest.json", "experiment-result.json"})


def _name(name):
    return name in ROOTS or re.fullmatch(r"artifact-[1-9][0-9]{0,9}\.json", name) is not None


def _directory(fd, maximum=MAX_BUNDLE_BYTES):
    names = []
    with os.scandir(fd) as entries:
        for entry in entries:
            if len(names) >= 20 or not _name(entry.name):
                raise ValueError("invalid experiment directory")
            names.append(entry.name)
    files, total = {}, 0
    for name in sorted(names):
        child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        try:
            with os.fdopen(child, "rb", closefd=False) as source:
                payload = _read_file(source, min(MAX_JSON_BYTES, maximum - total))
            total += len(payload)
            files[name] = payload
        finally:
            os.close(child)
    return files


def _archive(source, maximum=MAX_BUNDLE_BYTES):
    compressed = _read_file(source, MAX_BUNDLE_BYTES)
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as decoder:
        expanded = decoder.read(maximum + 1)
    if len(expanded) > maximum:
        raise ValueError("expanded experiment exceeds bound")
    # Preflight physical headers before tarfile can interpret any extension.
    offset, names = 0, []
    while expanded[offset : offset + 512] != bytes(512):
        header = expanded[offset : offset + 512]
        name = header[:100].split(b"\0", 1)[0].decode("ascii")
        if (
            len(header) != 512
            or len(names) >= 20
            or not _name(name)
            or name in names
            or header[156:157] not in (b"0", b"\0")
            or header[257:263] != b"ustar\0"
            or any(header[345:500])
        ):
            raise ValueError("invalid physical experiment header")
        size = int(header[124:136].strip(b"\0 "), 8)
        if not 1 <= size <= MAX_JSON_BYTES:
            raise ValueError("invalid experiment member size")
        names.append(name)
        offset += 512 + (size + 511) // 512 * 512
    if len(expanded) % 512 or len(expanded) < offset + 1024 or any(expanded[offset:]):
        raise ValueError("invalid experiment terminator")
    files, offset = {}, 0
    with tarfile.open(fileobj=io.BytesIO(expanded), mode="r:") as archive:
        for member in archive:
            if (
                member.name not in names
                or member.name in files
                or not member.isfile()
                or member.pax_headers
                or member.offset != offset
                or member.offset_data != offset + 512
            ):
                raise ValueError("invalid experiment member")
            source = archive.extractfile(member)
            if source is None:
                raise ValueError("unreadable experiment member")
            with source:
                files[member.name] = source.read(MAX_JSON_BYTES + 1)
            if len(files[member.name]) != member.size:
                raise ValueError("invalid experiment length")
            offset = member.offset_data + (member.size + 511) // 512 * 512
    if set(files) != set(names):
        raise ValueError("experiment physical/logical mismatch")
    return files


def read_members(path, *, max_expanded_bytes=MAX_BUNDLE_BYTES):
    if type(max_expanded_bytes) is not int or not 1 <= max_expanded_bytes <= MAX_BUNDLE_BYTES:
        raise ValueError("invalid experiment expanded-byte budget")
    fd = _open_bundle(Path(path))
    try:
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            return _directory(fd, max_expanded_bytes)
        with os.fdopen(fd, "rb", closefd=False) as source:
            return _archive(source, max_expanded_bytes)
    finally:
        os.close(fd)
