"""Deterministic file-based fingerprint repository for P0."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from pydantic import ValidationError

from .json_io import read_bounded_text, strict_json_loads
from .models import (
    CONTRACT_VERSION,
    FINGERPRINT_SCHEMA_VERSION,
    Fingerprint,
    ValidationStatus,
)

MAX_FINGERPRINT_FILES = 4096
MAX_FINGERPRINT_DIRECTORY_ENTRIES = 32_768
MAX_FINGERPRINT_DIRECTORY_DEPTH = 32


class FingerprintRejectionReason(StrEnum):
    READ_ERROR = "read_error"
    INVALID_JSON = "invalid_json"
    INVALID_ROOT = "invalid_root"
    MISSING_VERSION = "missing_version"
    SCHEMA_VERSION_MISMATCH = "schema_version_mismatch"
    CONTRACT_VERSION_MISMATCH = "contract_version_mismatch"
    VALIDATION_ERROR = "validation_error"
    DUPLICATE_FINGERPRINT_ID = "duplicate_fingerprint_id"
    FILE_TOO_LARGE = "file_too_large"
    UNSAFE_LINK = "unsafe_link"


@dataclass(frozen=True, slots=True)
class FingerprintEntry:
    path: Path
    fingerprint: Fingerprint


@dataclass(frozen=True, slots=True)
class FingerprintRejection:
    path: Path
    reason: FingerprintRejectionReason
    message: str
    fingerprint_id: str | None = None


@dataclass(frozen=True, slots=True)
class FingerprintRepository:
    entries: tuple[FingerprintEntry, ...]
    rejections: tuple[FingerprintRejection, ...] = ()

    @property
    def fingerprints(self) -> tuple[Fingerprint, ...]:
        return tuple(entry.fingerprint for entry in self.entries)

    @property
    def is_clean(self) -> bool:
        return not self.rejections

    def get(self, fingerprint_id: str) -> Fingerprint | None:
        return next(
            (
                entry.fingerprint
                for entry in self.entries
                if entry.fingerprint.fingerprint_id == fingerprint_id
            ),
            None,
        )

    def compatible_candidates(
        self,
        *,
        compatibility_group: str,
        probe_type: str,
        contract_version: str = CONTRACT_VERSION,
    ) -> tuple[Fingerprint, ...]:
        """Return compatible fingerprints in stable identifier order."""

        return tuple(
            entry.fingerprint
            for entry in self.entries
            if entry.fingerprint.compatibility.compatibility_group == compatibility_group
            and entry.fingerprint.compatibility.probe_type == probe_type
            and entry.fingerprint.compatibility.contract_version == contract_version
            and entry.fingerprint.validation_status is not ValidationStatus.REJECTED
        )

    def require_clean(self) -> None:
        if self.rejections:
            raise FingerprintRepositoryError(self)


class FingerprintRepositoryError(ValueError):
    """Raised when strict loading encounters one or more rejected files."""

    def __init__(self, repository: FingerprintRepository) -> None:
        self.repository = repository
        details = "; ".join(
            f"{rejection.path}: {rejection.reason.value}: {rejection.message}"
            for rejection in repository.rejections
        )
        super().__init__(f"fingerprint repository contains rejected files: {details}")


def _discover_files(directory: Path) -> tuple[Path, ...]:
    named_fingerprints: list[Path] = []
    json_files: list[Path] = []
    pending: list[tuple[Path, int]] = [(directory, 0)]
    entries_seen = 0

    while pending:
        current, depth = pending.pop()
        with os.scandir(current) as iterator:
            entries = sorted(iterator, key=lambda entry: entry.name)
        child_directories: list[Path] = []
        for entry in entries:
            entries_seen += 1
            if entries_seen > MAX_FINGERPRINT_DIRECTORY_ENTRIES:
                raise ValueError(
                    "fingerprint repository contains more than "
                    f"{MAX_FINGERPRINT_DIRECTORY_ENTRIES} directory entries"
                )

            path = Path(entry.path)
            if entry.is_symlink():
                if entry.name.endswith(".json"):
                    json_files.append(path)
                    if entry.name == "fingerprint.json":
                        named_fingerprints.append(path)
                continue
            if entry.is_dir(follow_symlinks=False):
                if depth >= MAX_FINGERPRINT_DIRECTORY_DEPTH:
                    raise ValueError(
                        "fingerprint repository exceeds the maximum directory depth of "
                        f"{MAX_FINGERPRINT_DIRECTORY_DEPTH}"
                    )
                child_directories.append(path)
                continue
            if entry.is_file(follow_symlinks=False) and entry.name.endswith(".json"):
                json_files.append(path)
                if entry.name == "fingerprint.json":
                    named_fingerprints.append(path)

        pending.extend((path, depth + 1) for path in reversed(child_directories))

    matches = named_fingerprints or json_files
    if len(matches) > MAX_FINGERPRINT_FILES:
        raise ValueError(f"fingerprint repository contains more than {MAX_FINGERPRINT_FILES} files")
    return tuple(sorted(matches, key=lambda path: path.relative_to(directory).as_posix()))


def _load_file(path: Path) -> FingerprintEntry | FingerprintRejection:
    if path.is_symlink():
        return FingerprintRejection(
            path=path,
            reason=FingerprintRejectionReason.UNSAFE_LINK,
            message="fingerprint repository links are not allowed",
        )
    try:
        text = read_bounded_text(path)
    except ValueError as error:
        reason = (
            FingerprintRejectionReason.FILE_TOO_LARGE
            if "too large" in str(error)
            else FingerprintRejectionReason.INVALID_JSON
        )
        return FingerprintRejection(path=path, reason=reason, message=str(error))
    except OSError as error:
        return FingerprintRejection(
            path=path,
            reason=FingerprintRejectionReason.READ_ERROR,
            message=str(error),
        )

    try:
        payload = strict_json_loads(text)
    except ValueError as error:
        return FingerprintRejection(
            path=path,
            reason=FingerprintRejectionReason.INVALID_JSON,
            message=str(error),
        )

    if not isinstance(payload, dict):
        return FingerprintRejection(
            path=path,
            reason=FingerprintRejectionReason.INVALID_ROOT,
            message="fingerprint JSON root must be an object",
        )

    fingerprint_id = payload.get("fingerprintId")
    known_id = fingerprint_id if isinstance(fingerprint_id, str) else None
    if "schemaVersion" not in payload or "contractVersion" not in payload:
        return FingerprintRejection(
            path=path,
            reason=FingerprintRejectionReason.MISSING_VERSION,
            message="fingerprint root requires schemaVersion and contractVersion",
            fingerprint_id=known_id,
        )
    if payload["schemaVersion"] != FINGERPRINT_SCHEMA_VERSION:
        return FingerprintRejection(
            path=path,
            reason=FingerprintRejectionReason.SCHEMA_VERSION_MISMATCH,
            message=(
                f"expected {FINGERPRINT_SCHEMA_VERSION!r}, received {payload['schemaVersion']!r}"
            ),
            fingerprint_id=known_id,
        )
    if payload["contractVersion"] != CONTRACT_VERSION:
        return FingerprintRejection(
            path=path,
            reason=FingerprintRejectionReason.CONTRACT_VERSION_MISMATCH,
            message=f"expected {CONTRACT_VERSION!r}, received {payload['contractVersion']!r}",
            fingerprint_id=known_id,
        )

    try:
        fingerprint = Fingerprint.model_validate(payload)
    except ValidationError as error:
        return FingerprintRejection(
            path=path,
            reason=FingerprintRejectionReason.VALIDATION_ERROR,
            message=str(error),
            fingerprint_id=known_id,
        )
    return FingerprintEntry(path=path, fingerprint=fingerprint)


def load_fingerprint_repository(
    directory: Path,
    *,
    strict: bool = True,
) -> FingerprintRepository:
    """Load and validate a directory of versioned fingerprint JSON files."""

    if not directory.exists():
        raise FileNotFoundError(directory)
    if directory.is_symlink():
        raise ValueError(f"fingerprint repository links are not allowed: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(directory)

    loaded_entries: list[FingerprintEntry] = []
    rejections: list[FingerprintRejection] = []
    for path in _discover_files(directory):
        result = _load_file(path)
        if isinstance(result, FingerprintEntry):
            loaded_entries.append(result)
        else:
            rejections.append(result)

    identifiers: dict[str, list[FingerprintEntry]] = {}
    for entry in loaded_entries:
        identifiers.setdefault(entry.fingerprint.fingerprint_id, []).append(entry)
    duplicate_ids = {
        fingerprint_id for fingerprint_id, entries in identifiers.items() if len(entries) > 1
    }
    if duplicate_ids:
        for entry in loaded_entries:
            fingerprint_id = entry.fingerprint.fingerprint_id
            if fingerprint_id in duplicate_ids:
                rejections.append(
                    FingerprintRejection(
                        path=entry.path,
                        reason=FingerprintRejectionReason.DUPLICATE_FINGERPRINT_ID,
                        message=f"fingerprint ID {fingerprint_id!r} appears more than once",
                        fingerprint_id=fingerprint_id,
                    )
                )
        loaded_entries = [
            entry
            for entry in loaded_entries
            if entry.fingerprint.fingerprint_id not in duplicate_ids
        ]

    repository = FingerprintRepository(
        entries=tuple(
            sorted(
                loaded_entries,
                key=lambda entry: (entry.fingerprint.fingerprint_id, entry.path.as_posix()),
            )
        ),
        rejections=tuple(
            sorted(
                rejections,
                key=lambda rejection: (
                    rejection.path.as_posix(),
                    rejection.reason.value,
                ),
            )
        ),
    )
    if strict:
        repository.require_clean()
    return repository


__all__ = [
    "FingerprintEntry",
    "FingerprintRejection",
    "FingerprintRejectionReason",
    "FingerprintRepository",
    "FingerprintRepositoryError",
    "load_fingerprint_repository",
]
