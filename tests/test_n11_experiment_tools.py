"""Custody and input-integrity regressions for reusable offline operator tools."""

import hashlib
import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest


def tool(name):
    path = Path(__file__).resolve().parents[1] / "experiments" / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_archive_preserves_prior_custody_and_refuses_overwrite(tmp_path):
    script = tool("archive_evidence")
    source = tmp_path / "evidence"
    source.mkdir()
    (source / "raw.json").write_bytes(b'{"original":true}')
    prior = tmp_path / "prior.tar.gz"
    prior.write_bytes(b"prior opaque archive")
    target = tmp_path / "sealed.tar.gz"
    receipt = script.create_archive(target, {"case": source}, prior=(prior, script.digest(prior)))
    assert receipt["verified_files"] == 2
    assert receipt["sha256"] == script.digest(target)
    assert target.stat().st_mode & 0o777 == 0o600
    assert script.verify_archive(target) == receipt
    assert (source / "raw.json").read_bytes() == b'{"original":true}'
    with pytest.raises(FileExistsError):
        script.create_archive(target, {"case": source})


def test_wrong_prior_hash_creates_no_archive(tmp_path):
    script = tool("archive_evidence")
    source = tmp_path / "raw"
    source.write_text("source")
    target = tmp_path / "sealed.tar.gz"
    with pytest.raises(ValueError, match="prior custody"):
        script.create_archive(target, {"raw": source}, prior=(source, "0" * 64))
    assert not target.exists()


@pytest.mark.parametrize("name", ["../escape", "/absolute", "x/../escape", "MANIFEST.json", "x\\y"])
def test_archive_paths_cannot_escape_or_replace_manifest(tmp_path, name):
    script = tool("archive_evidence")
    source = tmp_path / "raw"
    source.write_text("source")
    with pytest.raises(ValueError):
        script.create_archive(tmp_path / "sealed.tar.gz", {name: source})


def test_archive_rejects_symlink_and_recursive_destination(tmp_path):
    script = tool("archive_evidence")
    source = tmp_path / "raw"
    source.write_text("source")
    link = tmp_path / "link"
    link.symlink_to(source)
    with pytest.raises(ValueError, match="symlink"):
        script.create_archive(tmp_path / "sealed.tar.gz", {"raw": link})
    with pytest.raises(ValueError, match="outside"):
        script.create_archive(tmp_path / "sealed.tar.gz", {"directory": tmp_path})


def test_duplicate_prior_include_is_rejected(tmp_path):
    script = tool("archive_evidence")
    source = tmp_path / "raw"
    source.write_text("source")
    with pytest.raises(ValueError, match="duplicate prior"):
        script.create_archive(
            tmp_path / "sealed.tar.gz",
            {"prior-custody/raw": source},
            prior=(source, script.digest(source)),
        )


def add_member(archive, name, data):
    member = tarfile.TarInfo(name)
    member.size = len(data)
    archive.addfile(member, io.BytesIO(data))


def test_verification_detects_tampered_payload_and_duplicate_members(tmp_path):
    script = tool("archive_evidence")
    manifest = {"raw": {"size": 3, "sha256": hashlib.sha256(b"old").hexdigest()}}
    target = tmp_path / "tampered.tar.gz"
    with tarfile.open(target, "w:gz") as archive:
        add_member(archive, "MANIFEST.json", json.dumps(manifest).encode())
        add_member(archive, "raw", b"new")
    with pytest.raises(ValueError, match="digest"):
        script.verify_archive(target)
    with tarfile.open(target, "w:gz") as archive:
        add_member(archive, "MANIFEST.json", b"{}")
        add_member(archive, "MANIFEST.json", b"{}")
    with pytest.raises(ValueError, match="duplicate"):
        script.verify_archive(target)


def test_duplicate_phase_manifest_is_rejected(tmp_path):
    script = tool("verify_native_exports")
    target = tmp_path / "phase.tar"
    with tarfile.open(target, "w") as archive:
        add_member(archive, "bundle-manifest.json", b"{}")
        add_member(archive, "bundle-manifest.json", b"{}")
    with pytest.raises(ValueError, match="exactly one"):
        script.phase_manifest(target)


def test_source_manifest_cannot_read_outside_its_root(tmp_path):
    script = tool("verify_native_exports")
    root = tmp_path / "sources"
    root.mkdir()
    outside = tmp_path / "private"
    outside.write_text("private")
    (root / "link").symlink_to(outside)
    for relative in ["../private", str(outside), "link"]:
        with pytest.raises(ValueError):
            script.beneath(root, relative)


def test_changed_frozen_source_fails_before_running_any_inspector(tmp_path):
    script = tool("verify_native_exports")
    source = tmp_path / "sources"
    source.mkdir()
    (source / "worker.py").write_text("changed")
    (tmp_path / "plan.json").write_text(json.dumps({"source_sha256": {"worker.py": "0" * 64}}))
    (tmp_path / "control-receipt.json").write_text(
        json.dumps(
            {
                "result": {"restoration": "verified_by_port"},
                "ledger_state": "clean",
            }
        )
    )
    with pytest.raises(ValueError, match="frozen source changed"):
        script.verify_case(tmp_path, producer=tmp_path / "absent", policy=tmp_path / "absent.json")
