"""N7 CLI parity, private failure contracts, and pinned output boundaries."""

import os
import shutil
import stat

import pytest

from latency_fingerprinting.cli import main
from latency_fingerprinting.profiles import ProfileSnapshot, commands
from tests.calibration.check_reproduction import FIXTURES

from .cases import canonical, draft, excluded, policy, reviewed, supported
from .test_operations import VALID_CASES, replacement, review


def put(directory, name, payload):
    path = directory / name
    path.write_bytes(canonical(payload))
    return path


def invoke(arguments, capsys, *, invalid=False):
    assert main([str(a) for a in arguments]) == int(invalid)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (f"error: {arguments[0]}: invalid_input_or_output\n" if invalid else "")


def test_create_is_canonical_private_and_allows_explicit_unrelated_overwrite(tmp_path, capsys):
    source = put(tmp_path, "policy.json", policy())
    output = tmp_path / "out.json"
    output.write_bytes(b"old unrelated output")
    arguments = ["create-profile-snapshot", "--policy", source, "--output", output]
    invoke(arguments, capsys)
    assert output.read_bytes() == canonical(draft())
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    invoke(arguments, capsys)
    assert output.read_bytes() == canonical(draft())


@pytest.mark.parametrize("case", VALID_CASES)
def test_build_actual_linked_corpus_matches_independent_expectation(case, tmp_path, capsys):
    source = put(tmp_path, "policy.json", policy())
    output = tmp_path / "out.json"
    expected = excluded(case)
    invoke(
        [
            "build-profiles",
            "--directory",
            FIXTURES / case,
            "--policy",
            source,
            "--expected-split-id",
            expected["source_report"]["split_id"],
            "--expected-dataset-content-hash",
            expected["source_report"]["dataset_content_hash"],
            "--output",
            output,
        ],
        capsys,
    )
    assert output.read_bytes() == canonical(expected)
    assert stat.S_IMODE(output.stat().st_mode) == 0o600


@pytest.mark.parametrize("operation", ["mark_stale", "reject", "supersede"])
def test_transition_parity_and_protected_operands(operation, tmp_path, capsys):
    parent = ProfileSnapshot.model_validate(supported())
    target = replacement() if operation == "supersede" else None
    declaration = review(parent, operation, target=target)
    snapshot = put(tmp_path, "snapshot.json", parent.model_dump(mode="json"))
    evidence = put(tmp_path, "review.json", declaration)
    output = tmp_path / "out.json"
    arguments = [
        "transition-profile-snapshot",
        "--snapshot",
        snapshot,
        "--operation",
        operation,
        "--reason",
        declaration["reason_code"],
        "--review",
        evidence,
    ]
    operands = [snapshot, evidence]
    if target is not None:
        other = put(tmp_path, "replacement.json", target.model_dump(mode="json"))
        arguments += ["--replacement", other]
        operands.append(other)
    before = {p: p.read_bytes() for p in operands}
    invoke([*arguments, "--output", output], capsys)
    assert output.read_bytes() == canonical(
        reviewed(
            supported(),
            operation,
            declaration["reason_code"],
            target.snapshot_id if target is not None else None,
        )
    )
    for operand in operands:
        invoke([*arguments, "--output", operand], capsys, invalid=True)
        alias = tmp_path / "alias.json"
        os.link(operand, alias)
        invoke([*arguments, "--output", alias], capsys, invalid=True)
        alias.unlink()
    assert {p: p.read_bytes() for p in operands} == before


def test_build_parent_is_a_revision_and_cannot_be_overwritten(tmp_path, capsys):
    source = put(tmp_path, "policy.json", policy())
    parent = put(tmp_path, "parent.json", draft())
    arguments = [
        "build-profiles",
        "--directory",
        FIXTURES / "declared",
        "--policy",
        source,
        "--parent",
        parent,
    ]
    output = tmp_path / "out.json"
    invoke([*arguments, "--output", output], capsys)
    result = ProfileSnapshot.model_validate_json(output.read_bytes())
    assert result.lifecycle.parent_snapshot_id == draft()["snapshot_id"]
    for operand in (source, parent):
        before = operand.read_bytes()
        invoke([*arguments, "--output", operand], capsys, invalid=True)
        assert operand.read_bytes() == before


@pytest.mark.parametrize("operation,extra", [("supersede", []), ("reject", ["--replacement", "x"])])
def test_conditional_replacement_is_an_argument_error(operation, extra, capsys):
    with pytest.raises(SystemExit) as error:
        main(
            [
                "transition-profile-snapshot",
                "--snapshot",
                "x",
                "--operation",
                operation,
                "--reason",
                "x",
                "--review",
                "x",
                "--output",
                "x",
                *extra,
            ]
        )
    assert error.value.code == 2
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "kind",
    [
        "bad_json",
        "duplicate",
        "deep",
        "oversize",
        "symlink",
        "fifo",
        "directory",
        "ancestor_symlink",
        "missing",
    ],
)
def test_private_bounded_input_failures_preserve_output(kind, tmp_path, capsys, monkeypatch):
    source = put(tmp_path, "policy.json", policy())
    output = tmp_path / "out.json"
    output.write_bytes(b"retained")
    if kind == "bad_json":
        source.write_text("private invalid content")
    elif kind == "duplicate":
        source.write_text('{"schema_version":1,"schema_version":2}')
    elif kind == "deep":
        source.write_text("[" * 40 + "0" + "]" * 40)
    elif kind == "oversize":
        monkeypatch.setattr(commands, "MAX_CONTRACT_JSON_BYTES", 10)
    elif kind in {"symlink", "fifo", "directory", "missing"}:
        source.unlink()
        if kind == "symlink":
            source.symlink_to(output)
        elif kind == "fifo":
            os.mkfifo(source)
        elif kind == "directory":
            source.mkdir()
    elif kind == "ancestor_symlink":
        alias = tmp_path / "alias"
        alias.symlink_to(tmp_path, target_is_directory=True)
        source = alias / source.name
    invoke(
        ["create-profile-snapshot", "--policy", source, "--output", output], capsys, invalid=True
    )
    assert output.read_bytes() == b"retained"
    assert not list(tmp_path.glob(".n4-*.tmp"))


@pytest.mark.parametrize("target", ["new.json", "dataset.json"])
def test_build_never_writes_any_member_of_inspected_directory(target, tmp_path, capsys):
    directory = tmp_path / "dataset"
    shutil.copytree(FIXTURES / "declared", directory)
    before = {p.name: p.read_bytes() for p in directory.iterdir()}
    source = put(tmp_path, "policy.json", policy())
    invoke(
        [
            "build-profiles",
            "--directory",
            directory,
            "--policy",
            source,
            "--output",
            directory / target,
        ],
        capsys,
        invalid=True,
    )
    assert {p.name: p.read_bytes() for p in directory.iterdir()} == before


def test_renamed_inspected_root_is_still_protected(tmp_path, capsys, monkeypatch):
    directory = tmp_path / "dataset"
    shutil.copytree(FIXTURES / "declared", directory)
    sink = tmp_path / "sink"
    sink.mkdir()
    source = put(tmp_path, "policy.json", policy())
    original = commands._build_profile_snapshot

    def rename_after_inspection(*args, **kwargs):
        result = original(*args, **kwargs)
        sink.rename(tmp_path / "old-sink")
        directory.rename(sink)
        return result

    monkeypatch.setattr(commands, "_build_profile_snapshot", rename_after_inspection)
    invoke(
        [
            "build-profiles",
            "--directory",
            directory,
            "--policy",
            source,
            "--output",
            sink / "new.json",
        ],
        capsys,
        invalid=True,
    )
    assert not (sink / "new.json").exists()
    assert not list(sink.glob(".n4-*.tmp"))


def test_renamed_operand_parent_is_still_protected(tmp_path, capsys, monkeypatch):
    directory = tmp_path / "inputs"
    directory.mkdir()
    source = put(directory, "policy.json", policy())
    sink = tmp_path / "sink"
    sink.mkdir()
    original = commands.create_profile_snapshot

    def rename_after_read(*args, **kwargs):
        result = original(*args, **kwargs)
        sink.rename(tmp_path / "old-sink")
        directory.rename(sink)
        return result

    monkeypatch.setattr(commands, "create_profile_snapshot", rename_after_read)
    invoke(
        ["create-profile-snapshot", "--policy", source, "--output", sink / "policy.json"],
        capsys,
        invalid=True,
    )
    assert (sink / "policy.json").read_bytes() == canonical(policy())


def test_write_failure_preserves_output_and_cleans_temporary(tmp_path, capsys, monkeypatch):
    from latency_fingerprinting.observability import output as writer

    source = put(tmp_path, "policy.json", policy())
    output = tmp_path / "out.json"
    output.write_bytes(b"retained")

    def fail(*args, **kwargs):
        raise OSError("private failure")

    monkeypatch.setattr(writer.os, "replace", fail)
    invoke(
        ["create-profile-snapshot", "--policy", source, "--output", output], capsys, invalid=True
    )
    assert output.read_bytes() == b"retained"
    assert not list(tmp_path.glob(".n4-*.tmp"))


def test_fdopen_failure_closes_all_pinned_descriptors(tmp_path, capsys, monkeypatch):
    source = put(tmp_path, "policy.json", policy())
    descriptors = []
    original = commands.os.open

    def opened(*args, **kwargs):
        descriptor = original(*args, **kwargs)
        descriptors.append(descriptor)
        return descriptor

    def fail(*args, **kwargs):
        raise OSError("private failure")

    monkeypatch.setattr(commands.os, "open", opened)
    monkeypatch.setattr(commands.os, "fdopen", fail)
    invoke(
        ["create-profile-snapshot", "--policy", source, "--output", tmp_path / "out"],
        capsys,
        invalid=True,
    )
    assert descriptors
    for descriptor in set(descriptors):
        with pytest.raises(OSError):
            os.fstat(descriptor)


@pytest.mark.parametrize("case", ["wrong-binding", "split-leakage", "release.json"])
def test_failed_build_preserves_existing_output(case, tmp_path, capsys):
    source = put(tmp_path, "policy.json", policy())
    output = tmp_path / "out.json"
    output.write_bytes(b"retained")
    invoke(
        ["build-profiles", "--directory", FIXTURES / case, "--policy", source, "--output", output],
        capsys,
        invalid=True,
    )
    assert output.read_bytes() == b"retained"
