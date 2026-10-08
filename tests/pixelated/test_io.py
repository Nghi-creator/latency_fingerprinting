"""Pixelated JSON, CSV, TAR, and filesystem boundary tests."""

from __future__ import annotations

import io
import os
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
    write_tar,
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


@pytest.mark.parametrize("payload", [b'"unterminated', b"x" * 131_073])
def test_malformed_csv_headers_raise_bundle_errors(payload: bytes) -> None:
    with pytest.raises(PixelatedBundleError, match="not valid CSV"):
        pixelated_bundle_io.csv_rows({"test.csv": payload}, "test.csv", frozenset())


def test_directory_file_growth_cannot_cause_an_unbounded_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "test.csv").write_bytes(b"x")
    read_sizes: list[int] = []

    class GrowingFile(io.BytesIO):
        def __init__(self, descriptor):
            super().__init__(b"x" * 100)
            self.descriptor = descriptor

        def fileno(self):
            return self.descriptor

        def close(self):
            if not self.closed:
                os.close(self.descriptor)
            super().close()

        def read(self, size: int = -1) -> bytes:
            read_sizes.append(size)
            return super().read(size)

    monkeypatch.setattr(pixelated_bundle_io, "MAX_TEXT_FILE_BYTES", 8)
    monkeypatch.setattr(os, "fdopen", lambda descriptor, *_args, **_kwargs: GrowingFile(descriptor))
    with pytest.raises(PixelatedBundleError, match="too large"):
        pixelated_bundle_io.read_bundle(
            tmp_path, readable_files={"test.csv"}, required_files={"test.csv"}
        )
    assert read_sizes == [9]


@pytest.mark.parametrize("kind", ["directory", "tar"])
def test_bundle_ancestor_symlinks_are_rejected(tmp_path, context, kind):
    bundle = copy_bundle(tmp_path)
    if kind == "tar":
        archive = tmp_path / "bundle.tar"
        write_tar(bundle, archive)
        bundle = archive
    link = tmp_path / "parent-link"
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(PixelatedBundleError, match="links are not allowed"):
        ingest(link / bundle.name, context)


@pytest.mark.parametrize("kind", ["directory", "tar", "file", "fifo"])
def test_bundle_replacement_during_open_never_follows_links_or_blocks(
    tmp_path, context, monkeypatch, kind
):
    bundle = copy_bundle(tmp_path)
    if kind == "tar":
        archive = tmp_path / "bundle.tar"
        write_tar(bundle, archive)
        bundle = archive
    target = bundle / "summary.json" if kind in {"file", "fifo"} else bundle
    saved = target.with_name(target.name + ".original")
    real_open = os.open
    replaced = False

    def replace_before_open(path, flags, *args, **kwargs):
        nonlocal replaced
        if path == target.name and not replaced:
            replaced = True
            target.rename(saved)
            if kind == "fifo":
                os.mkfifo(target)
            else:
                target.symlink_to(saved, target_is_directory=kind == "directory")
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", replace_before_open)
    with pytest.raises(PixelatedBundleError, match="links are not allowed|must be regular"):
        ingest(bundle, context)
    assert replaced


def test_tar_growth_is_bounded_after_open(tmp_path, monkeypatch):
    archive = tmp_path / "bundle.tar"
    archive.write_bytes(b"x")
    real_fstat = os.fstat
    regular_stats = 0
    monkeypatch.setattr(pixelated_bundle_io, "MAX_ARCHIVE_BYTES", 8)

    def grow_after_stat(descriptor):
        nonlocal regular_stats
        metadata = real_fstat(descriptor)
        if metadata.st_size == 1:
            regular_stats += 1
            if regular_stats == 2:
                archive.write_bytes(b"x" * 100)
        return metadata

    monkeypatch.setattr(os, "fstat", grow_after_stat)
    with pytest.raises(PixelatedBundleError, match="too large after reading"):
        pixelated_bundle_io.read_bundle(archive, readable_files=set(), required_files=set())


def test_opened_bundle_directory_stays_pinned_after_path_replacement(
    tmp_path, context, monkeypatch
):
    bundle = copy_bundle(tmp_path)
    expected = ingest(bundle, context)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "summary.json").write_text('{"unexpected":true}')
    real_open = os.open
    replaced = False

    def replace_after_root_open(path, flags, *args, **kwargs):
        nonlocal replaced
        if path.endswith(".json") and not replaced:
            replaced = True
            bundle.rename(tmp_path / "original")
            bundle.symlink_to(outside, target_is_directory=True)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", replace_after_root_open)
    assert ingest(bundle, context) == expected
    assert replaced


@pytest.mark.parametrize("name", ["../outside.json", "/outside.json", ".", ""])
def test_directory_reader_rejects_non_leaf_requested_names(tmp_path, name):
    with pytest.raises(PixelatedBundleError, match="unsafe bundle file name"):
        pixelated_bundle_io.read_bundle(tmp_path, readable_files={name}, required_files=set())


def test_malformed_csv_header_is_a_clean_cli_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from latency_fingerprinting.cli import main

    from .support import FIXTURE_ROOT

    bundle = copy_bundle(tmp_path)
    (bundle / "stream-telemetry.csv").write_bytes(b'"unterminated')
    result = main(
        [
            "ingest-pixelated",
            str(bundle),
            "--context",
            str(FIXTURE_ROOT / "context.json"),
            "--phase",
            "degraded",
            "--comparison-case-id",
            "test",
        ]
    )
    output = capsys.readouterr()
    assert result == 1
    assert "not valid CSV" in output.err
    assert "Traceback" not in output.err
    assert output.out == ""
