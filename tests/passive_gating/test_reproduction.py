"""Frozen full-result parity and hostile reader, command and post-execution drift."""

import copy
import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest

from . import check_reproduction as module
from .cases import canonical

RELEASE, PAYLOADS = module.load_release()


def corpus(tmp_path):
    root = tmp_path / "passive"
    shutil.copytree(module.FIXTURES, root)
    return root


def test_release_is_read_only_and_explicit_about_provenance(capsys):
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in module.FIXTURES.iterdir()}
    assert module.main() == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out) == dict(
        status="current",
        fixtureRelease="1.0.0",
        cases=len(RELEASE["cases"]),
        provenance="synthetic_and_model_only",
        producerIntegration="not_run",
        releaseSha256=module.RELEASE_SHA256,
    )
    assert before == {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in module.FIXTURES.iterdir()
    }


@pytest.mark.parametrize("name", sorted(RELEASE["cases"]))
def test_every_frozen_case_matches_full_api_and_cli(name, tmp_path, capsys):
    module.check_case(RELEASE["cases"][name], PAYLOADS, tmp_path / "out.json", release=RELEASE)
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("name", sorted(RELEASE["sha256"]))
def test_every_operand_and_original_source_byte_is_pinned(name, tmp_path):
    root = corpus(tmp_path)
    p = root / name
    p.write_bytes(p.read_bytes() + b" ")
    with pytest.raises(ValueError, match="fixture release pin mismatch"):
        module.load_release(root)


@pytest.mark.parametrize(
    "kind",
    [
        "missing",
        "extra",
        "directory",
        "symlink",
        "fifo",
        "release",
        "release-fifo",
        "release-directory",
        "flood",
        "root-symlink",
    ],
)
def test_inventory_and_release_integrity(kind, tmp_path):
    root = corpus(tmp_path)
    path = root / "policy.json"
    if kind == "missing":
        path.unlink()
    elif kind == "extra":
        (root / "extra.json").write_bytes(b"{}")
    elif kind in {"directory", "symlink", "fifo"}:
        path.unlink()
        if kind == "directory":
            path.mkdir()
        elif kind == "symlink":
            path.symlink_to(module.FIXTURES / path.name)
        else:
            os.mkfifo(path)
    elif kind.startswith("release"):
        path = root / "release.json"
        if kind == "release":
            path.write_bytes(path.read_bytes() + b" ")
        else:
            path.unlink()
            if kind == "release-fifo":
                os.mkfifo(path)
            else:
                path.mkdir()
    elif kind == "root-symlink":
        alias = tmp_path / "alias"
        alias.symlink_to(root, target_is_directory=True)
        root = alias
    else:
        for index in range(module.MAX_FILES + 1):
            (root / f"extra-{index}.json").write_bytes(b"{}")
    with pytest.raises((OSError, ValueError)):
        module.load_release(root)


@pytest.mark.parametrize("name", ["release.json", "policy.json"])
@pytest.mark.parametrize("kind", ["fifo", "symlink", "growth"])
def test_post_inventory_replacement_is_bounded(name, kind, tmp_path, monkeypatch):
    root = corpus(tmp_path)
    original = module.read_at

    def replace(parent, leaf, maximum):
        if leaf == name:
            path = root / leaf
            if kind == "growth":
                with path.open("ab") as target:
                    target.truncate(maximum + 1)
            else:
                path.unlink()
                if kind == "fifo":
                    os.mkfifo(path)
                else:
                    path.symlink_to(module.FIXTURES / name)
        return original(parent, leaf, maximum)

    monkeypatch.setattr(module, "read_at", replace)
    with pytest.raises((OSError, ValueError)):
        module.load_release(root)


def test_inventory_mutation_closes_descriptor(tmp_path, monkeypatch):
    root = corpus(tmp_path)
    original = module.read_at
    descriptors = set()

    def mutate(parent, name, maximum):
        descriptors.add(parent)
        if name == "policy.json":
            (root / "extra.json").write_bytes(b"{}")
        return original(parent, name, maximum)

    monkeypatch.setattr(module, "read_at", mutate)
    with pytest.raises(ValueError, match="inventory changed"):
        module.load_release(root)
    for fd in descriptors:
        with pytest.raises(OSError):
            os.fstat(fd)


@pytest.mark.parametrize("maximum", [1, 1000000])
def test_aggregate_byte_limit(maximum, monkeypatch):
    monkeypatch.setattr(module, "MAX_TOTAL_BYTES", maximum)
    with pytest.raises(ValueError):
        module.load_release()


@pytest.mark.parametrize(
    "field",
    [
        "n6_release_sha256",
        "n7_release_sha256",
        "n8_release_sha256",
        "policy_content_hash",
        "design_vectors_sha256",
    ],
)
def test_dependency_pins_checked_even_with_faulty_release_pin(field, tmp_path, monkeypatch):
    root = corpus(tmp_path)
    release = copy.deepcopy(RELEASE)
    release[field] = "0" * 64
    raw = canonical(release)
    (root / "release.json").write_bytes(raw)
    monkeypatch.setattr(module, "RELEASE_SHA256", hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError, match="dependency pin mismatch"):
        module.load_release(root)


@pytest.mark.parametrize("leaf", ["", ".", "..", "../escape", "nested/file", "nested\\file"])
def test_source_staging_never_escapes_directory(leaf, tmp_path):
    release = copy.deepcopy(RELEASE)
    release["sources"]["recovery-band"][leaf] = next(
        iter(RELEASE["sources"]["recovery-band"].values())
    )
    with pytest.raises(ValueError, match="inventory mismatch"):
        module.check_case(
            RELEASE["cases"]["recovery-band-build"],
            PAYLOADS,
            tmp_path / "out.json",
            release=release,
        )


@pytest.mark.parametrize("kind", ["result", "stdout", "stderr", "code", "output", "source"])
def test_wrong_results_and_cli_or_source_mutation_cannot_pass(kind, tmp_path):
    case = RELEASE["cases"]["recovery-band-replay"]
    payloads = copy.deepcopy(PAYLOADS)
    if kind == "result":
        payloads[case["expected_file"]]["rows"][-1]["recommendation"] = "probe"

    def invoke(arguments):
        code, stdout, stderr = module.invoke_local(arguments)
        if kind == "stdout":
            stdout += b"private detail"
        elif kind == "stderr":
            stderr += b"private detail"
        elif kind == "code":
            code = 1
        elif kind == "output":
            (tmp_path / "out.json").write_bytes(b"wrong")
        elif kind == "source":
            source = Path(arguments[arguments.index("--directory") + 1])
            (source / "calibration-dataset.json").write_bytes(b"{}")
        return code, stdout, stderr

    with pytest.raises(ValueError, match="expectation mismatch|CLI .* drift|source bytes changed"):
        module.check_case(case, payloads, tmp_path / "out.json", release=RELEASE, invoke=invoke)


def test_invalid_case_must_preserve_output(tmp_path):
    def invoke(arguments):
        result = module.invoke_local(arguments)
        (tmp_path / "out.json").write_bytes(b"lost output")
        return result

    with pytest.raises(ValueError, match="output/preservation drift"):
        module.check_case(
            RELEASE["cases"]["build-wrong-expected_split_id"],
            PAYLOADS,
            tmp_path / "out.json",
            release=RELEASE,
            invoke=invoke,
        )


@pytest.mark.parametrize("fault", ["accept", "wrong_error"])
def test_faulty_api_errors_cannot_pass(fault, tmp_path, monkeypatch):
    def broken(*args, **kwargs):
        if fault == "wrong_error":
            raise ValueError("private failure")
        return None

    monkeypatch.setattr(module, "build_passive_baseline", broken)
    with pytest.raises(ValueError, match="N9 (invalid case accepted|API error drift)"):
        module.check_case(
            RELEASE["cases"]["build-wrong-expected_split_id"],
            PAYLOADS,
            tmp_path / "out.json",
            release=RELEASE,
        )


def test_main_failure_is_private(monkeypatch, capsys):
    def fail():
        raise ValueError("private path")

    monkeypatch.setattr(module, "check_reproduction", fail)
    assert module.main() == 1
    assert capsys.readouterr() == ("", "error: N9 reproduction failed\n")


@pytest.mark.parametrize("family", ["n9", "n8", "n7", "n6"])
def test_post_execution_dependency_mutation_is_detected(family, tmp_path, monkeypatch):
    roots = {"n9": corpus(tmp_path)}
    for name, fixtures in (
        ("n6", module.N6_FIXTURES),
        ("n7", module.N7_FIXTURES),
        ("n8", module.N8_FIXTURES),
    ):
        roots[name] = tmp_path / name
        shutil.copytree(fixtures, roots[name])
    load = module.load_release

    def one_case(directory=module.FIXTURES):
        release, payloads = load(directory)
        return {**release, "cases": {"linked": release["cases"]["recovery-band-build"]}}, payloads

    monkeypatch.setattr(module, "load_release", one_case)
    calls = 0

    def invoke(arguments):
        nonlocal calls
        result = module.invoke_local(arguments)
        calls += 1
        target = roots[family] / ("baseline/response-a.json" if family == "n6" else "policy.json")
        target.write_bytes(target.read_bytes() + b" ")
        return result

    with pytest.raises(ValueError, match="release pin mismatch"):
        module.check_reproduction(
            roots["n9"],
            n6_directory=roots["n6"],
            n7_directory=roots["n7"],
            n8_directory=roots["n8"],
            invoke=invoke,
        )
    assert calls == 1


def test_literal_milestones_are_explicit_and_signed_zero_is_retained():
    result = PAYLOADS["cooldown-budget-result.json"]
    assert [
        r["state"]["last_proposal_ms"] for r in result["rows"] if r["recommendation"] == "probe"
    ] == [6000, 36000, 66000]
    assert result["rows"][-1]["reason_codes"] == ["proposal_budget_exhausted"]
    threshold = PAYLOADS["binary64-threshold-result.json"]
    assert [r["classification"] for r in threshold["rows"]] == ["band", "recovered", "low"]
    assert threshold["rows"][-1]["observed_fps"].hex().startswith("-0x0")
    assert threshold["rows"][-1]["relative_fps"].hex().startswith("0x0")
