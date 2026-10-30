"""Bounded exact-byte snapshots, hostile directories and fixed CLI failure surfaces."""

import errno
import gzip
import os

import pytest

from latency_fingerprinting.calibration import bundle_io, inspect_calibration_dataset, inspection
from latency_fingerprinting.cli import main
from latency_fingerprinting.scenarios.bundle_io import read_members
from tests.scenarios.test_bundle import archive, members

from .cases import canonical, seal_dataset
from .inspection_cases import case, write


def invalid(path):
    with pytest.raises(ValueError, match="^invalid_calibration_dataset$"):
        inspect_calibration_dataset(path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("run_id", "other"),
        ("source_content_hash", "sha256:" + "0" * 64),
        ("source_type", "pixelated_bundle"),
    ],
)
def test_actual_source_identity_mismatch(tmp_path, field, value):
    p, files = case()
    p["sources"][0][field] = value
    if field == "source_type":
        p["sources"][0]["bundle_schema_version"] = "2"
    invalid(write(tmp_path, p, files))


def test_actual_window_id_mismatch(tmp_path):
    p, files = case()
    p["entries"][0]["source_bindings"][0]["window_id"] = "unrelated"
    invalid(write(tmp_path, p, files))


@pytest.mark.parametrize(
    "change",
    [
        "hash",
        "length",
        "missing",
        "extra",
        "manifest_identity",
        "manifest_duplicate",
        "manifest_collision",
    ],
)
def test_exact_receipts_inventory_and_manifest(tmp_path, change):
    p, files = case()
    path = write(tmp_path, p, files)
    manifest = path / bundle_io.MANIFEST
    artifact = path / "response-a.json"
    if change == "hash":
        artifact.write_bytes(artifact.read_bytes().replace(b"1.0.0", b"2.0.0", 1))
    elif change == "length":
        artifact.write_bytes(artifact.read_bytes() + b" ")
    elif change == "missing":
        artifact.unlink()
    elif change == "extra":
        (path / "extra.json").write_bytes(b"{}")
    elif change == "manifest_identity":
        p["dataset_id"] = "dataset-" + "0" * 64
        manifest.write_bytes(canonical(p))
    elif change == "manifest_duplicate":
        manifest.write_bytes(
            manifest.read_bytes().replace(b'"entries":', b'"entries": [], "entries":', 1)
        )
    else:
        p["artifacts"][0].update(artifact_id="calibration-dataset", file_name=bundle_io.MANIFEST)
        p["entries"][0]["artifact_id"] = "calibration-dataset"
        manifest.write_bytes(canonical(seal_dataset(p)))
    invalid(path)


@pytest.mark.parametrize(
    "raw", [b"{}", b"{} {}", b'{"a":1,"a":2}', b'{"a":NaN}', b"\xff", b"[" * 33 + b"0" + b"]" * 33]
)
def test_artifact_json_rebound_receipts_still_requires_valid_root(tmp_path, raw):
    p, files = case()
    files["response-a.json"] = raw
    invalid(write(tmp_path, p, files))


@pytest.mark.parametrize("member", [bundle_io.MANIFEST, "response-a.json"])
@pytest.mark.parametrize("kind", ["symlink", "directory", "fifo"])
def test_links_and_special_files_reject_without_blocking(tmp_path, member, kind):
    p, files = case()
    path = write(tmp_path / "input", p, files)
    target = path / member
    raw = target.read_bytes()
    target.unlink()
    if kind == "symlink":
        external = tmp_path / "outside.json"
        external.write_bytes(raw)
        target.symlink_to(external)
    elif kind == "directory":
        target.mkdir()
    else:
        os.mkfifo(target)
    invalid(path)


def test_directory_and_ancestor_symlinks_are_not_followed(tmp_path):
    p, files = case()
    path = write(tmp_path / "input", p, files)
    alias = tmp_path / "alias"
    alias.symlink_to(path, target_is_directory=True)
    invalid(alias)
    parent = tmp_path / "parent"
    parent.symlink_to(tmp_path, target_is_directory=True)
    invalid(parent / "input")


def test_pinned_root_survives_path_replacement(tmp_path, monkeypatch):
    p, files = case()
    path = write(tmp_path / "input", p, files)
    moved = tmp_path / "original"
    original = bundle_io.read_at
    renamed = False

    def replace_root(fd, name, maximum, **kwargs):
        nonlocal renamed
        if not renamed:
            renamed = True
            path.rename(moved)
            path.mkdir()
            (path / bundle_io.MANIFEST).write_bytes(b"untrusted replacement")
        return original(fd, name, maximum, **kwargs)

    monkeypatch.setattr(bundle_io, "read_at", replace_root)
    result = inspect_calibration_dataset(path)
    assert result.dataset.content_hash == p["content_hash"]
    assert result.file_identities == frozenset(
        (member.stat().st_dev, member.stat().st_ino) for member in moved.iterdir()
    )
    assert (path / bundle_io.MANIFEST).read_bytes() == b"untrusted replacement"


def test_inventory_mutation_rejects_final_snapshot(tmp_path, monkeypatch):
    p, files = case()
    path = write(tmp_path, p, files)
    original = bundle_io.read_at

    def mutate(fd, name, maximum, **kwargs):
        raw = original(fd, name, maximum, **kwargs)
        if name == "response-a.json":
            (path / "new.json").write_bytes(b"{}")
        return raw

    monkeypatch.setattr(bundle_io, "read_at", mutate)
    invalid(path)


def test_aggregate_raw_budget_is_enforced_before_artifact_read(tmp_path, monkeypatch):
    p, files = case()
    path = write(tmp_path, p, files)
    maximum = len((path / bundle_io.MANIFEST).read_bytes()) + len(files["response-a.json"]) - 1
    monkeypatch.setattr(bundle_io, "AGGREGATE_BYTES", maximum)
    invalid(path)


def test_aggregate_decoded_budget_is_enforced(tmp_path, monkeypatch):
    p, files = case(controlled=True)
    path = write(tmp_path, p, files)
    # Raw gzip fits comfortably; its actual TAR expansion cannot fit this budget.
    raw_size = sum(f.stat().st_size for f in path.iterdir())
    assert len(gzip.decompress(files["experiment-a.tar.gz"])) > len(files["experiment-a.tar.gz"])
    monkeypatch.setattr(inspection, "AGGREGATE_BYTES", raw_size)
    invalid(path)


def test_json_limit_is_applied_to_manifest_before_parse(tmp_path, monkeypatch):
    p, files = case()
    path = write(tmp_path, p, files)
    monkeypatch.setattr(bundle_io, "JSON_BYTES", 10)
    invalid(path)


@pytest.mark.parametrize(
    "raw",
    [
        b"not gzip",
        gzip.compress(b"broken tar"),
        gzip.compress(archive([("../escape.json", b"{}")])),
    ],
)
def test_nested_archive_is_inspected_not_only_hashed(tmp_path, raw):
    p, files = case(controlled=True)
    files["experiment-a.tar.gz"] = raw
    invalid(write(tmp_path, p, files))


@pytest.mark.parametrize("maximum", [0, -1, True, 64 * 1024 * 1024 + 1, 1.5])
def test_nested_reader_rejects_invalid_budget_before_open(tmp_path, maximum):
    with pytest.raises(ValueError, match="expanded-byte budget"):
        read_members(tmp_path / "absent", max_expanded_bytes=maximum)


@pytest.mark.parametrize("container", ["gzip", "directory"])
def test_nested_reader_custom_budget_preserves_default(tmp_path, container):
    files = members()
    if container == "gzip":
        path = tmp_path / "bundle.tar.gz"
        raw = archive(files.items())
        path.write_bytes(gzip.compress(raw))
        budget = len(raw)
    else:
        path = tmp_path / "bundle"
        path.mkdir()
        for name, raw in files.items():
            (path / name).write_bytes(raw)
        budget = sum(map(len, files.values()))
    assert read_members(path) == files
    assert read_members(path, max_expanded_bytes=budget) == files
    with pytest.raises(ValueError):
        read_members(path, max_expanded_bytes=budget - 1)


def test_fdopen_failure_closes_both_descriptors(tmp_path, monkeypatch):
    p, files = case()
    path = write(tmp_path, p, files)
    opened = []
    original = os.open

    def capture(*args, **kwargs):
        fd = original(*args, **kwargs)
        opened.append(fd)
        return fd

    def fail(*args, **kwargs):
        raise OSError(errno.EIO, "private diagnostic")

    monkeypatch.setattr(bundle_io.os, "open", capture)
    monkeypatch.setattr(bundle_io.os, "fdopen", fail)
    invalid(path)
    assert len(opened) >= 2
    for fd in opened:
        with pytest.raises(OSError):
            os.fstat(fd)


def test_cli_write_failure_preserves_output_and_private_error(tmp_path, monkeypatch, capsys):
    from latency_fingerprinting.observability import output as output_module

    p, files = case()
    path = write(tmp_path / "input", p, files)
    output = tmp_path / "report.json"
    output.write_bytes(b"existing")

    def fail(*args, **kwargs):
        raise OSError(errno.EIO, "secret /private/path")

    monkeypatch.setattr(output_module.os, "replace", fail)
    assert main(["inspect-calibration", "--directory", str(path), "--output", str(output)]) == 1
    assert output.read_bytes() == b"existing"
    assert not list(tmp_path.glob(".*.tmp"))
    assert capsys.readouterr() == ("", "error: inspect-calibration: invalid_input_or_output\n")


def test_missing_nested_root_has_fixed_api_and_cli_error(tmp_path, capsys):
    p, files = case(controlled=True)
    files["experiment-a.tar.gz"] = gzip.compress(archive([("artifact-1.json", b"{}")]))
    path = write(tmp_path / "input", p, files)
    invalid(path)
    output = tmp_path / "report.json"
    output.write_bytes(b"previous")
    assert main(["inspect-calibration", "--directory", str(path), "--output", str(output)]) == 1
    assert output.read_bytes() == b"previous"
    assert capsys.readouterr() == ("", "error: inspect-calibration: invalid_input_or_output\n")


def test_growth_after_stat_is_bounded_and_rejected(tmp_path, monkeypatch):
    p, files = case()
    path = write(tmp_path, p, files)
    artifact = path / "response-a.json"
    identity = artifact.stat().st_ino
    original = os.fstat
    changed = False

    def grow(fd):
        nonlocal changed
        metadata = original(fd)
        if metadata.st_ino == identity and not changed:
            changed = True
            with artifact.open("ab") as stream:
                stream.write(b" ")
        return metadata

    monkeypatch.setattr(bundle_io.os, "fstat", grow)
    invalid(path)
    assert changed


def test_inventory_bound_is_exact_and_rejects_unsafe_names(tmp_path):
    for index in range(257):
        (tmp_path / f"member-{index}.json").write_bytes(b"{}")
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        assert len(bundle_io.inventory(fd)) == 257
        (tmp_path / "member-257.json").write_bytes(b"{}")
        with pytest.raises(ValueError):
            bundle_io.inventory(fd)
        (tmp_path / "member-257.json").unlink()
        (tmp_path / ".hidden.json").write_bytes(b"{}")
        with pytest.raises(ValueError):
            bundle_io.inventory(fd)
    finally:
        os.close(fd)


def test_file_root_and_missing_manifest_fail_privately(tmp_path):
    invalid(tmp_path)
    path = tmp_path / "root.json"
    path.write_bytes(b"{}")
    invalid(path)
