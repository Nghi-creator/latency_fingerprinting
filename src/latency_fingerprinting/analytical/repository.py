"""Separate fail-closed, bounded local v2 fingerprint repository loading."""

import os
import stat
from dataclasses import dataclass
from pathlib import Path

from ..json_io import MAX_CONTRACT_JSON_BYTES, strict_json_loads
from ..models.fingerprint_v2 import FingerprintV2

MAX_FINGERPRINT_FILES_V2 = 128
MAX_DIRECTORY_ENTRIES_V2 = 4096
MAX_DIRECTORY_DEPTH_V2 = 16


class FingerprintRepositoryErrorV2(ValueError):
    """A closed reason code without exposing paths or malformed record contents."""


@dataclass(frozen=True, slots=True)
class FingerprintRepositoryV2:
    fingerprints: tuple[FingerprintV2, ...]


def _read_fingerprint(directory_fd: int, name: str) -> FingerprintV2:
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        file_fd = os.open(name, flags, dir_fd=directory_fd)
    except OSError as error:
        raise FingerprintRepositoryErrorV2("unsafe_or_unreadable_file") from error
    with os.fdopen(file_fd, "rb") as source:
        metadata = os.fstat(source.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise FingerprintRepositoryErrorV2("non_regular_file")
        if metadata.st_size > MAX_CONTRACT_JSON_BYTES:
            raise FingerprintRepositoryErrorV2("file_too_large")
        payload = source.read(MAX_CONTRACT_JSON_BYTES + 1)
        if len(payload) > MAX_CONTRACT_JSON_BYTES:
            raise FingerprintRepositoryErrorV2("file_too_large")
    try:
        return FingerprintV2.model_validate(strict_json_loads(payload.decode("utf-8-sig")))
    except ValueError as error:
        raise FingerprintRepositoryErrorV2("invalid_fingerprint") from error


def load_fingerprint_repository_v2(directory: Path) -> FingerprintRepositoryV2:
    """Validate every JSON file, returning all records in stable ID order.

    Traversal uses directory descriptors and no-follow opens. Any unsafe link,
    duplicate, malformed file or resource violation aborts the whole load. Empty
    directories are valid. Nothing is silently skipped except non-JSON files.
    """
    directory = Path(directory).absolute()
    entries_seen = 0
    records = {}
    files_seen = 0
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW

    def walk(directory_fd, depth):
        nonlocal entries_seen, files_seen
        with os.scandir(directory_fd) as iterator:
            entries = []
            for entry in iterator:
                entries_seen += 1
                if entries_seen > MAX_DIRECTORY_ENTRIES_V2:
                    raise FingerprintRepositoryErrorV2("directory_entry_limit")
                entries.append(entry)
        for entry in sorted(entries, key=lambda item: item.name):
            if entry.is_symlink():
                raise FingerprintRepositoryErrorV2("unsafe_link")
            if entry.is_dir(follow_symlinks=False):
                if depth >= MAX_DIRECTORY_DEPTH_V2:
                    raise FingerprintRepositoryErrorV2("directory_depth_limit")
                child_fd = os.open(entry.name, directory_flags, dir_fd=directory_fd)
                try:
                    walk(child_fd, depth + 1)
                finally:
                    os.close(child_fd)
            elif entry.name.endswith(".json"):
                files_seen += 1
                if files_seen > MAX_FINGERPRINT_FILES_V2:
                    raise FingerprintRepositoryErrorV2("fingerprint_file_limit")
                fingerprint = _read_fingerprint(directory_fd, entry.name)
                if fingerprint.fingerprint_id in records:
                    raise FingerprintRepositoryErrorV2("duplicate_fingerprint_id")
                records[fingerprint.fingerprint_id] = fingerprint

    try:
        for component in (directory, *directory.parents):
            if component.is_symlink():
                raise FingerprintRepositoryErrorV2("unsafe_link")
        directory_fd = os.open(directory, directory_flags)
        try:
            walk(directory_fd, 0)
        finally:
            os.close(directory_fd)
    except OSError as error:
        raise FingerprintRepositoryErrorV2("repository_read_error") from error
    return FingerprintRepositoryV2(tuple(records[key] for key in sorted(records)))
