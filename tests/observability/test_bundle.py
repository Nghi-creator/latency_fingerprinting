"""Independent bundle layout, adversarial I/O and atomic-output regressions."""

import gzip
import hashlib
import io
import json
import os
import tarfile

import pytest

from latency_fingerprinting.cli import main
from latency_fingerprinting.observability import StageTraceRecord, bundle, output
from latency_fingerprinting.pipeline import canonical_json
from tests.observability.test_contracts import record


def files():
    payload = canonical_json(StageTraceRecord.model_validate(record())).encode()
    manifest = {
        "schema_version": 1,
        "bundle_type": "pixelated_stage_trace",
        "trace_schema_version": "stage-trace-record-v1",
        "trace_bytes": len(payload),
        "trace_sha256": hashlib.sha256(payload).hexdigest(),
    }
    return {"trace-record.json": payload, "trace-manifest.json": json.dumps(manifest).encode()}


def directory(tmp_path, members):
    path = tmp_path / "bundle"
    path.mkdir()
    for name, data in members.items():
        (path / name).write_bytes(data)
    return path


def tar_bytes(members, *, member_type=None, format=tarfile.USTAR_FORMAT):
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=format) as archive:
        for name, data in members:
            member = tarfile.TarInfo(name)
            member.size = len(data)
            if member_type:
                member.type = member_type
                member.linkname = "trace-record.json"
            archive.addfile(member, io.BytesIO(data) if member.isfile() else None)
    return raw.getvalue()


def archive(tmp_path, raw):
    path = tmp_path / "trace.tar.gz"
    path.write_bytes(gzip.compress(raw))
    return path


@pytest.mark.parametrize("container", ["directory", "gzip"])
def test_adoption_and_cli_equal_original(tmp_path, capsys, container):
    members = files()
    path = (
        directory(tmp_path, members)
        if container == "directory"
        else archive(tmp_path, tar_bytes(members.items()))
    )
    adopted = bundle.ingest_trace_bundle(path)
    assert canonical_json(adopted).encode() == members["trace-record.json"]
    target = tmp_path / "adopted.json"
    assert main(["ingest-trace", "--bundle", str(path), "--output", str(target)]) == 0
    assert target.read_bytes() == members["trace-record.json"]
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema_version", 2),
        ("schema_version", True),
        ("schema_version", 1.0),
        ("schema_version", "1"),
        ("bundle_type", "pixelated_research"),
        ("trace_schema_version", "stage-trace-record-v2"),
        ("trace_bytes", True),
        ("trace_bytes", 0),
        ("trace_bytes", "1"),
        ("trace_sha256", "A" * 64),
        ("trace_sha256", "0" * 64),
        ("private_token", "secret-marker"),
    ],
)
def test_manifest_rejections(tmp_path, key, value):
    members = files()
    manifest = json.loads(members["trace-manifest.json"])
    manifest[key] = value
    members["trace-manifest.json"] = json.dumps(manifest).encode()
    with pytest.raises(ValueError, match="^invalid_trace_bundle$"):
        bundle.ingest_trace_bundle(directory(tmp_path, members))


@pytest.mark.parametrize(
    "case", ["duplicate", "invalid_utf8", "deep", "noncanonical", "private", "wrong_version"]
)
def test_json_rejections_even_with_matching_hash(tmp_path, case):
    members = files()
    payload = members["trace-record.json"]
    if case == "duplicate":
        payload = payload.replace(
            b'"trace_id": "trace-1"', b'"trace_id": "trace-1", "trace_id": "trace-2"'
        )
    elif case == "invalid_utf8":
        payload = b"\xff"
    elif case == "deep":
        payload = b"[" * 33 + b"0" + b"]" * 33
    else:
        value = json.loads(payload)
        if case == "private":
            value["private_field"] = "secret-marker"
        if case == "wrong_version":
            value["schema_version"] = "stage-trace-record-v2"
        payload = json.dumps(value).encode()
    manifest = json.loads(members["trace-manifest.json"])
    manifest.update(trace_bytes=len(payload), trace_sha256=hashlib.sha256(payload).hexdigest())
    members.update(
        {"trace-record.json": payload, "trace-manifest.json": json.dumps(manifest).encode()}
    )
    with pytest.raises(ValueError, match="^invalid_trace_bundle$"):
        bundle.ingest_trace_bundle(directory(tmp_path, members))


@pytest.mark.parametrize(
    "name",
    [
        "extra.json",
        "summary.json",
        "../trace-record.json",
        "/trace-record.json",
        "./trace-record.json",
        "nested/trace-record.json",
    ],
)
def test_tar_names_and_extra_members(tmp_path, name):
    members = list(files().items()) + [(name, b"{}")]
    with pytest.raises(ValueError):
        bundle.ingest_trace_bundle(archive(tmp_path, tar_bytes(members)))


@pytest.mark.parametrize(
    "kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.DIRTYPE, tarfile.FIFOTYPE, tarfile.CHRTYPE]
)
def test_tar_nonregular(tmp_path, kind):
    with pytest.raises(ValueError):
        bundle.ingest_trace_bundle(archive(tmp_path, tar_bytes(files().items(), member_type=kind)))


@pytest.mark.parametrize(
    "case",
    ["missing", "duplicate", "hidden_trailing", "no_terminator", "pax", "uncompressed", "bad_gzip"],
)
def test_archive_layout(tmp_path, case):
    members = list(files().items())
    if case == "missing":
        members.pop()
    if case == "duplicate":
        members.append(members[0])
    if case == "pax":
        members[0] = ("x" * 120, members[0][1])
    raw = tar_bytes(members, format=tarfile.PAX_FORMAT if case == "pax" else tarfile.USTAR_FORMAT)
    if case == "hidden_trailing":
        raw += b"secret-marker"
    if case == "no_terminator":
        raw = raw.rstrip(b"\0")
    path = archive(tmp_path, raw)
    if case == "uncompressed":
        path.write_bytes(raw)
    if case == "bad_gzip":
        path.write_bytes(b"\x1f\x8bgarbage")
    with pytest.raises(ValueError, match="^invalid_trace_bundle$"):
        bundle.ingest_trace_bundle(path)


@pytest.mark.parametrize(
    "case", ["missing", "extra", "symlink", "ancestor", "fifo", "subdirectory", "leaf_symlink"]
)
def test_directory_safety(tmp_path, case):
    path = directory(tmp_path, files())
    trace = path / "trace-record.json"
    if case == "missing":
        trace.unlink()
    if case == "extra":
        (path / "secret-marker").write_text("secret")
    if case == "subdirectory":
        trace.unlink()
        trace.mkdir()
    if case == "fifo":
        trace.unlink()
        os.mkfifo(trace)
    if case == "symlink":
        content = trace.read_bytes()
        trace.unlink()
        (tmp_path / "outside").write_bytes(content)
        trace.symlink_to(tmp_path / "outside")
    if case == "ancestor":
        link = tmp_path / "alias"
        link.symlink_to(tmp_path, target_is_directory=True)
        path = link / "bundle"
    if case == "leaf_symlink":
        link = tmp_path / "alias"
        link.symlink_to(path, target_is_directory=True)
        path = link
    with pytest.raises(ValueError):
        bundle.ingest_trace_bundle(path)


@pytest.mark.parametrize("case", ["json", "compressed", "expanded"])
def test_resource_caps(tmp_path, monkeypatch, case):
    if case == "json":
        monkeypatch.setattr(bundle, "MAX_CONTRACT_JSON_BYTES", 100)
        path = directory(tmp_path, files())
    elif case == "compressed":
        monkeypatch.setattr(bundle, "MAX_BUNDLE_BYTES", 10)
        path = archive(tmp_path, tar_bytes(files().items()))
    else:
        monkeypatch.setattr(bundle, "MAX_BUNDLE_BYTES", 4096)
        path = archive(tmp_path, b"\0" * 10000)
    with pytest.raises(ValueError):
        bundle.ingest_trace_bundle(path)


@pytest.mark.parametrize(
    "case",
    ["symlink", "ancestor", "directory", "fifo", "replace_failure", "sync_failure", "oversize"],
)
def test_atomic_output_failure_leaves_target_and_no_temp(tmp_path, monkeypatch, case):
    target = tmp_path / "output.json"
    target.write_bytes(b"original")
    payload = b"new"
    if case == "symlink":
        outside = tmp_path / "outside"
        outside.write_bytes(b"original")
        target.unlink()
        target.symlink_to(outside)
    if case == "ancestor":
        alias = tmp_path / "alias"
        alias.symlink_to(tmp_path, target_is_directory=True)
        target = alias / "output.json"
    if case == "directory":
        target.unlink()
        target.mkdir()
    if case == "fifo":
        target.unlink()
        os.mkfifo(target)
    if case in {"replace_failure", "sync_failure"}:

        def fail(*args, **kwargs):
            raise OSError("secret-marker")

        monkeypatch.setattr(output.os, "replace" if case == "replace_failure" else "fsync", fail)
    if case == "oversize":
        monkeypatch.setattr(output, "MAX_CONTRACT_JSON_BYTES", 1)
    with pytest.raises((OSError, ValueError)):
        output.write_trace_output(target, payload)
    assert not list(tmp_path.glob(".n4-*.tmp"))
    if case not in {"directory", "fifo"}:
        assert target.read_bytes() == b"original"


def test_cli_failure_no_echo_no_partial_output(tmp_path, capsys):
    path = directory(tmp_path, {"secret-marker": b"secret"})
    target = tmp_path / "output.json"
    target.write_bytes(b"original")
    assert main(["ingest-trace", "--bundle", str(path), "--output", str(target)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error: ingest-trace: invalid_input_or_output\n"
    assert target.read_bytes() == b"original"


def test_cli_output_error_is_private_and_preserves_existing(tmp_path, capsys):
    path = directory(tmp_path, files())
    outside = tmp_path / "existing.json"
    outside.write_bytes(b"original")
    target = tmp_path / "secret-marker"
    target.symlink_to(outside)
    assert main(["ingest-trace", "--bundle", str(path), "--output", str(target)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error: ingest-trace: invalid_input_or_output\n"
    assert outside.read_bytes() == b"original"
    assert not list(tmp_path.glob(".n4-*.tmp"))


def test_long_tar_extension_chain_fails_before_recursive_parsing(tmp_path):
    raw = tar_bytes(
        [("trace-manifest.json", b"")] * 2000,
        member_type=tarfile.XHDTYPE,
    )
    with pytest.raises(ValueError, match="^invalid_trace_bundle$"):
        bundle.ingest_trace_bundle(archive(tmp_path, raw))
