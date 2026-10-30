"""Frozen N6 software-evidence release: exact pins, decisions, CLI and read-only checks."""

import copy
import hashlib
import json
import shutil

import pytest

from . import check_reproduction as module


def test_complete_release_reproduces_read_only_and_silent(capsys):
    before = {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in module.FIXTURES.rglob("*")
        if p.is_file()
    }
    result = module.check_reproduction()
    assert result["cases"] == 14
    assert result["provenance"] == "synthetic"
    assert result["producerIntegration"] == "not_run"
    assert module.main() == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out) == result
    after = {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in module.FIXTURES.rglob("*")
        if p.is_file()
    }
    assert before == after


@pytest.mark.parametrize("name", module.CASES)
def test_every_case_matches_independent_expected_decisions_and_cli(name, tmp_path, capsys):
    expected = module.load_release()["cases"][name]
    module.check_case(module.FIXTURES / name, expected, tmp_path / "report.json")
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("relative", sorted(module.load_release()["sha256"]))
def test_each_artifact_pin_detects_drift(tmp_path, relative):
    root = tmp_path / "corpus"
    shutil.copytree(module.FIXTURES, root)
    path = root / relative
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="release pin mismatch"):
        module.load_release(root)


@pytest.mark.parametrize(
    "change", ["missing", "extra", "empty_directory", "symlink", "release", "flood", "special"]
)
def test_exact_corpus_inventory_and_oracle_pin(tmp_path, change):
    import os

    root = tmp_path / "corpus"
    shutil.copytree(module.FIXTURES, root)
    target = root / "baseline/response-a.json"
    if change == "missing":
        target.unlink()
    elif change == "extra":
        (root / "extra.json").write_bytes(b"{}")
    elif change == "empty_directory":
        (root / "empty").mkdir()
    elif change == "symlink":
        target.unlink()
        target.symlink_to(module.FIXTURES / "baseline/response-a.json")
    elif change == "release":
        p = root / "release.json"
        p.write_bytes(p.read_bytes() + b" ")
    elif change == "special":
        target.unlink()
        os.mkfifo(target)
    else:
        for index in range(65):
            (root / f"extra-{index}.json").write_bytes(b"{}")
    with pytest.raises(ValueError, match="N6 (fixture inventory|release pin) mismatch"):
        module.load_release(root)


def test_wrong_expected_decisions_fail_even_with_correct_pins(tmp_path):
    release = module.load_release()
    expected = copy.deepcopy(release["cases"]["baseline"])
    expected["entries"][0]["reason_codes"] = []
    with pytest.raises(ValueError, match="independent eligibility expectation mismatch"):
        module.check_case(module.FIXTURES / "baseline", expected, tmp_path / "report.json")


def test_synthetic_corpus_never_qualifies_real_calibration():
    release = module.load_release()
    for expected in release["cases"].values():
        if "error" in expected:
            continue
        assert expected["counts"]["eligible_entries"] == 0
        for entry in expected["entries"]:
            assert not entry["eligible"]
            assert "synthetic_only" in entry["reason_codes"] or entry["input_kind"] == "missing"


def test_main_error_is_fixed_and_does_not_echo_path(monkeypatch, capsys):
    def fail():
        raise ValueError("private path")

    monkeypatch.setattr(module, "check_reproduction", fail)
    assert module.main() == 1
    assert capsys.readouterr() == ("", "error: N6 reproduction failed\n")


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_valid_case_rejects_unexpected_cli_output(tmp_path, monkeypatch, stream):
    import sys

    original = module.cli_main

    def noisy(args):
        code = original(args)
        print("unexpected diagnostic", file=getattr(sys, stream))
        return code

    monkeypatch.setattr(module, "cli_main", noisy)
    expected = module.load_release()["cases"]["baseline"]
    with pytest.raises(ValueError, match="CLI status/privacy drift"):
        module.check_case(module.FIXTURES / "baseline", expected, tmp_path / "report.json")


@pytest.mark.parametrize("kind", ["fifo", "directory"])
def test_release_root_rejects_special_files_before_read(tmp_path, kind):
    import os

    root = tmp_path / "corpus"
    shutil.copytree(module.FIXTURES, root)
    path = root / "release.json"
    path.unlink()
    if kind == "fifo":
        os.mkfifo(path)
    else:
        path.mkdir()
    with pytest.raises((ValueError, OSError)):
        module.load_release(root)


@pytest.mark.parametrize("kind", ["fifo", "symlink", "growth"])
def test_fixture_replacement_after_inventory_is_bounded(tmp_path, monkeypatch, kind):
    import os

    root = tmp_path / "corpus"
    shutil.copytree(module.FIXTURES, root)
    original = module.read_at
    changed = False

    def replace(parent, name, maximum):
        nonlocal changed
        if name == "release.json" and not changed:
            changed = True
            path = root / name
            if kind == "growth":
                with path.open("ab") as output:
                    output.truncate(maximum + 1)
            else:
                path.unlink()
                if kind == "fifo":
                    os.mkfifo(path)
                else:
                    path.symlink_to(module.FIXTURES / name)
        return original(parent, name, maximum)

    monkeypatch.setattr(module, "read_at", replace)
    with pytest.raises((ValueError, OSError)):
        module.load_release(root)
    assert changed
