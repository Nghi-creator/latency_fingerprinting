"""Pixelated JSON, CSV, TAR, and filesystem boundary tests."""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest

from latency_fingerprinting.adapters import pixelated_bundle_io
from latency_fingerprinting.adapters.pixelated_bundle import PixelatedBundleError
from latency_fingerprinting.models import ContextKey

from .support import (
    VALID_BUNDLE,
    copy_bundle,
    copy_v2_bundle,
    ingest,
)


def test_bundle_json_rejects_duplicate_keys(tmp_path: Path, context_v2: ContextKey) -> None:
    bundle = copy_v2_bundle(tmp_path)
    summary_path = bundle / "summary.json"
    summary_path.write_text(
        summary_path.read_text(encoding="utf-8").replace(
            '"runId": "pixelated-sanitized-run-v2-001",',
            '"runId": "pixelated-sanitized-run-v2-001",\n  "runId": "different-run",',
        ),
        encoding="utf-8",
    )

    with pytest.raises(PixelatedBundleError, match="duplicate JSON object key"):
        ingest(bundle, context_v2)


def test_missing_required_file_is_rejected(tmp_path: Path, context: ContextKey) -> None:
    bundle = copy_bundle(tmp_path)
    (bundle / "summary.json").unlink()

    with pytest.raises(PixelatedBundleError, match="missing required files: summary.json"):
        ingest(bundle, context)


def test_missing_required_telemetry_column_is_rejected(
    tmp_path: Path,
    context: ContextKey,
) -> None:
    bundle = copy_bundle(tmp_path)
    telemetry = bundle / "stream-telemetry.csv"
    telemetry.write_text(
        telemetry.read_text(encoding="utf-8").replace(",jitter_ms,", ","),
        encoding="utf-8",
    )

    with pytest.raises(PixelatedBundleError, match="missing required columns: jitter_ms"):
        ingest(bundle, context)


def test_tar_path_traversal_is_rejected(tmp_path: Path, context: ContextKey) -> None:
    archive_path = tmp_path / "unsafe.tar"
    with tarfile.open(archive_path, "w") as archive:
        member = tarfile.TarInfo("../../outside.txt")
        payload = b"unsafe"
        member.size = len(payload)
        archive.addfile(member, io.BytesIO(payload))

    with pytest.raises(PixelatedBundleError, match="unsafe TAR member path"):
        ingest(archive_path, context)


def test_tar_links_are_rejected(tmp_path: Path, context: ContextKey) -> None:
    archive_path = tmp_path / "link.tar"
    with tarfile.open(archive_path, "w") as archive:
        member = tarfile.TarInfo("run-metadata.json")
        member.type = tarfile.SYMTYPE
        member.linkname = "elsewhere.json"
        archive.addfile(member)

    with pytest.raises(PixelatedBundleError, match="TAR links are not allowed"):
        ingest(archive_path, context)


def test_duplicate_tar_members_are_rejected(tmp_path: Path, context: ContextKey) -> None:
    archive_path = tmp_path / "duplicate.tar"
    with tarfile.open(archive_path, "w") as archive:
        for _ in range(2):
            member = tarfile.TarInfo("run-metadata.json")
            payload = b"{}"
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))

    with pytest.raises(PixelatedBundleError, match="duplicate TAR member"):
        ingest(archive_path, context)


def test_bundle_root_symlinks_are_rejected(tmp_path: Path, context: ContextKey) -> None:
    link = tmp_path / "bundle-link"
    link.symlink_to(VALID_BUNDLE, target_is_directory=True)

    with pytest.raises(PixelatedBundleError, match="bundle links are not allowed"):
        ingest(link, context)


def test_archive_input_bytes_are_bounded_before_tar_decoding(
    tmp_path: Path, context: ContextKey
) -> None:
    archive_path = tmp_path / "oversized.tar"
    with archive_path.open("wb") as archive_file:
        archive_file.truncate(pixelated_bundle_io.MAX_ARCHIVE_BYTES + 1)

    with pytest.raises(PixelatedBundleError, match="TAR archive is too large"):
        ingest(archive_path, context)


def test_directory_readable_bytes_are_bounded(
    tmp_path: Path,
    context: ContextKey,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = copy_bundle(tmp_path)
    monkeypatch.setattr(pixelated_bundle_io, "MAX_BUNDLE_BYTES", 1)

    with pytest.raises(PixelatedBundleError, match="directory contents exceed"):
        ingest(bundle, context)
