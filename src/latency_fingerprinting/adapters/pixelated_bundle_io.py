"""Safe archive and text decoding for Pixelated research bundles."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import tarfile
from collections.abc import Mapping, Set
from pathlib import Path, PurePosixPath
from typing import Any

from .pixelated_bundle_common import PixelatedBundleError

MAX_ARCHIVE_MEMBERS = 64
MAX_TEXT_FILE_BYTES = 10 * 1024 * 1024


def _safe_archive_name(name: str) -> str:
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts:
        raise PixelatedBundleError(f"unsafe TAR member path: {name!r}")
    return path.as_posix()


def _read_tar(path: Path, readable_files: Set[str]) -> dict[str, bytes]:
    try:
        with tarfile.open(path, mode="r:*") as archive:
            return _read_tar_members(archive, readable_files)
    except (OSError, tarfile.TarError) as error:
        raise PixelatedBundleError(f"cannot read TAR archive: {error}") from error


def _read_tar_members(
    archive: tarfile.TarFile,
    readable_files: Set[str],
) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    members = archive.getmembers()
    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise PixelatedBundleError(
            f"TAR contains {len(members)} members; maximum is {MAX_ARCHIVE_MEMBERS}"
        )
    for member in members:
        name = _safe_archive_name(member.name)
        if member.issym() or member.islnk():
            raise PixelatedBundleError(f"TAR links are not allowed: {name!r}")
        if member.isdir():
            continue
        if not member.isfile():
            raise PixelatedBundleError(f"unsupported TAR member type: {name!r}")
        if name not in readable_files:
            continue
        if name in files:
            raise PixelatedBundleError(f"duplicate TAR member: {name!r}")
        if member.size > MAX_TEXT_FILE_BYTES:
            raise PixelatedBundleError(f"bundle file is too large: {name!r}")
        extracted = archive.extractfile(member)
        if extracted is None:
            raise PixelatedBundleError(f"cannot read TAR member: {name!r}")
        files[name] = extracted.read(MAX_TEXT_FILE_BYTES + 1)
    return files


def _read_directory(path: Path, readable_files: Set[str]) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for name in readable_files:
        candidate = path / name
        if candidate.is_symlink():
            raise PixelatedBundleError(f"bundle links are not allowed: {name!r}")
        if not candidate.is_file():
            continue
        if candidate.stat().st_size > MAX_TEXT_FILE_BYTES:
            raise PixelatedBundleError(f"bundle file is too large: {name!r}")
        files[name] = candidate.read_bytes()
    return files


def read_bundle(
    path: Path,
    *,
    readable_files: Set[str],
    required_files: Set[str],
) -> dict[str, bytes]:
    if path.is_dir():
        files = _read_directory(path, readable_files)
    elif path.is_file():
        files = _read_tar(path, readable_files)
    else:
        raise PixelatedBundleError(f"bundle path does not exist: {path}")
    missing = sorted(required_files - files.keys())
    if missing:
        raise PixelatedBundleError(f"bundle is missing required files: {', '.join(missing)}")
    return files


def _decode(files: Mapping[str, bytes], name: str) -> str:
    try:
        return files[name].decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise PixelatedBundleError(f"{name} is not valid UTF-8: {error}") from error


def json_object(files: Mapping[str, bytes], name: str) -> dict[str, Any]:
    try:
        payload = json.loads(_decode(files, name))
    except json.JSONDecodeError as error:
        raise PixelatedBundleError(f"{name} is not valid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise PixelatedBundleError(f"{name} JSON root must be an object")
    return payload


def csv_rows(
    files: Mapping[str, bytes],
    name: str,
    required_columns: Set[str],
) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(_decode(files, name), newline=""), strict=True)
    headers = reader.fieldnames
    if headers is None:
        raise PixelatedBundleError(f"{name} requires a header row")
    if len(headers) != len(set(headers)):
        raise PixelatedBundleError(f"{name} contains duplicate columns")
    missing = sorted(required_columns - set(headers))
    if missing:
        raise PixelatedBundleError(f"{name} is missing required columns: {', '.join(missing)}")
    try:
        rows = [dict(row) for row in reader]
    except csv.Error as error:
        raise PixelatedBundleError(f"{name} is not valid CSV: {error}") from error
    for index, row in enumerate(rows, start=2):
        if None in row or any(row.get(header) is None for header in headers):
            raise PixelatedBundleError(f"{name} row {index} has the wrong number of columns")
    return rows


def bundle_checksum(files: Mapping[str, bytes]) -> str:
    digest = hashlib.sha256()
    for name in sorted(files):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(files[name])
        digest.update(b"\0")
    return digest.hexdigest()


__all__ = ["bundle_checksum", "csv_rows", "json_object", "read_bundle"]
