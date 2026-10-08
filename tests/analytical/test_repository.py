"""Bounded fail-closed v2 repository loading, independently of the P0 loader."""

import json
import os
from pathlib import Path

import pytest

from latency_fingerprinting.analytical import repository as module
from latency_fingerprinting.analytical.repository import (
    FingerprintRepositoryErrorV2,
    load_fingerprint_repository_v2,
)

from .cases import fingerprint_payload


def write_fingerprint(path, label="declared", status="software_checked"):
    path.write_text(json.dumps(fingerprint_payload(label=label, status=status)))


def test_empty_sorted_nested_repository_and_audit_statuses(tmp_path):
    assert load_fingerprint_repository_v2(tmp_path).fingerprints == ()
    child = tmp_path / "nested"
    child.mkdir()
    write_fingerprint(child / "a.json", "a")
    write_fingerprint(tmp_path / "z.json", "z", "unreviewed")
    write_fingerprint(tmp_path / "r.json", "r", "rejected")
    (tmp_path / "ignored.txt").write_text("not JSON")
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    repository = load_fingerprint_repository_v2(tmp_path)
    ids = [r.fingerprint_id for r in repository.fingerprints]
    assert ids == sorted(ids) and len(ids) == 3
    assert {r.validation_status for r in repository.fingerprints} == {
        "software_checked",
        "unreviewed",
        "rejected",
    }
    assert before == {p: p.read_bytes() for p in before}
    assert load_fingerprint_repository_v2(tmp_path) == repository


def test_duplicate_ids_abort_whole_load(tmp_path):
    for name in ("a.json", "b.json"):
        write_fingerprint(tmp_path / name)
    with pytest.raises(FingerprintRepositoryErrorV2, match="duplicate_fingerprint_id"):
        load_fingerprint_repository_v2(tmp_path)


@pytest.mark.parametrize(
    "text",
    [
        "{",
        "[]",
        "{}",
        '{"schemaVersion":"fingerprint-v1"}',
        '{"schemaVersion":"observation-v2"}',
        '{"secret":NaN}',
        '{"secret":1e9999}',
        '{"secret":1,"secret":2}',
        "[" * 129 + "0" + "]" * 129,
    ],
)
def test_malformed_and_mixed_roots_abort_without_sensitive_error(tmp_path, text):
    write_fingerprint(tmp_path / "a.json")
    (tmp_path / "private_filename.json").write_text(text)
    with pytest.raises(FingerprintRepositoryErrorV2) as caught:
        load_fingerprint_repository_v2(tmp_path)
    assert str(caught.value) == "invalid_fingerprint"
    assert "private" not in str(caught.value) and "secret" not in str(caught.value)


def test_invalid_utf8_is_rejected(tmp_path):
    (tmp_path / "a.json").write_bytes(b"\xff")
    with pytest.raises(FingerprintRepositoryErrorV2, match="invalid_fingerprint"):
        load_fingerprint_repository_v2(tmp_path)


def test_actual_release_limits_are_separate_from_p0():
    assert module.MAX_FINGERPRINT_FILES_V2 == 128
    assert module.MAX_DIRECTORY_ENTRIES_V2 == 4096
    assert module.MAX_DIRECTORY_DEPTH_V2 == 16
    assert module.MAX_CONTRACT_JSON_BYTES == 10 * 1024 * 1024


def test_file_count_limit_accepts_boundary_rejects_next(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "MAX_FINGERPRINT_FILES_V2", 2)
    for label in ("a", "b"):
        write_fingerprint(tmp_path / f"{label}.json", label)
    assert len(load_fingerprint_repository_v2(tmp_path).fingerprints) == 2
    write_fingerprint(tmp_path / "c.json", "c")
    with pytest.raises(FingerprintRepositoryErrorV2, match="fingerprint_file_limit"):
        load_fingerprint_repository_v2(tmp_path)


def test_entry_count_includes_non_json_files(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "MAX_DIRECTORY_ENTRIES_V2", 2)
    for label in ("a", "b"):
        (tmp_path / f"{label}.txt").touch()
    assert load_fingerprint_repository_v2(tmp_path).fingerprints == ()
    (tmp_path / "c.txt").touch()
    with pytest.raises(FingerprintRepositoryErrorV2, match="directory_entry_limit"):
        load_fingerprint_repository_v2(tmp_path)


def test_depth_limit_accepts_boundary_rejects_next(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "MAX_DIRECTORY_DEPTH_V2", 2)
    leaf = tmp_path / "one" / "two"
    leaf.mkdir(parents=True)
    write_fingerprint(leaf / "a.json")
    assert len(load_fingerprint_repository_v2(tmp_path).fingerprints) == 1
    (leaf / "three").mkdir()
    with pytest.raises(FingerprintRepositoryErrorV2, match="directory_depth_limit"):
        load_fingerprint_repository_v2(tmp_path)


def test_file_bytes_accept_boundary_reject_next(tmp_path, monkeypatch):
    path = tmp_path / "a.json"
    write_fingerprint(path)
    monkeypatch.setattr(module, "MAX_CONTRACT_JSON_BYTES", path.stat().st_size)
    assert len(load_fingerprint_repository_v2(tmp_path).fingerprints) == 1
    with path.open("a") as output:
        output.write(" ")
    with pytest.raises(FingerprintRepositoryErrorV2, match="file_too_large"):
        load_fingerprint_repository_v2(tmp_path)


@pytest.mark.parametrize("kind", ["file", "directory", "non_json", "root", "ancestor"])
def test_symlinks_are_rejected(tmp_path, kind):
    root = tmp_path / "repository"
    root.mkdir()
    write_fingerprint(root / "a.json")
    target = root
    if kind in ("file", "non_json"):
        (root / ("link.json" if kind == "file" else "link.txt")).symlink_to(root / "a.json")
    elif kind == "directory":
        (root / "loop").symlink_to(root, target_is_directory=True)
    else:
        link = tmp_path / "link"
        link.symlink_to(root if kind == "root" else tmp_path, target_is_directory=True)
        target = link if kind == "root" else link / "repository"
    with pytest.raises(FingerprintRepositoryErrorV2, match="unsafe_link"):
        load_fingerprint_repository_v2(target)


def test_non_regular_json_file_does_not_block(tmp_path):
    os.mkfifo(tmp_path / "pipe.json")
    with pytest.raises(FingerprintRepositoryErrorV2, match="non_regular_file"):
        load_fingerprint_repository_v2(tmp_path)


@pytest.mark.parametrize("kind", ["missing", "file"])
def test_invalid_repository_path_fails(tmp_path, kind):
    path = tmp_path / kind
    if kind == "file":
        path.touch()
    with pytest.raises(FingerprintRepositoryErrorV2, match="repository_read_error"):
        load_fingerprint_repository_v2(path)


def test_file_replaced_with_link_before_open_is_rejected(tmp_path, monkeypatch):
    path = tmp_path / "a.json"
    write_fingerprint(path)
    real_open = os.open

    def racing_open(name, flags, **kwargs):
        if name == "a.json":
            path.unlink()
            path.symlink_to(tmp_path / "missing")
        return real_open(name, flags, **kwargs)

    monkeypatch.setattr(os, "open", racing_open)
    with pytest.raises(FingerprintRepositoryErrorV2, match="unsafe_or_unreadable_file"):
        load_fingerprint_repository_v2(tmp_path)


def test_directory_read_error_fails_closed(tmp_path, monkeypatch):
    def fail_scandir(fd):
        raise PermissionError("private path details")

    monkeypatch.setattr(os, "scandir", fail_scandir)
    with pytest.raises(FingerprintRepositoryErrorV2) as caught:
        load_fingerprint_repository_v2(Path(tmp_path))
    assert str(caught.value) == "repository_read_error"


def test_file_growth_after_stat_still_hits_read_bound(tmp_path, monkeypatch):
    from types import SimpleNamespace

    path = tmp_path / "a.json"
    write_fingerprint(path)
    limit = path.stat().st_size - 1
    monkeypatch.setattr(module, "MAX_CONTRACT_JSON_BYTES", limit)
    real_fstat = os.fstat

    def stale_fstat(fd):
        metadata = real_fstat(fd)
        return SimpleNamespace(st_mode=metadata.st_mode, st_size=limit)

    monkeypatch.setattr(os, "fstat", stale_fstat)
    with pytest.raises(FingerprintRepositoryErrorV2, match="file_too_large"):
        load_fingerprint_repository_v2(tmp_path)
