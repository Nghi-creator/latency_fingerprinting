"""N9 private command output, exact API parity and protected file/directory identities."""

import os
import stat

import pytest

from latency_fingerprinting.cli import main
from latency_fingerprinting.passive_gating import (
    build_passive_baseline,
    commands,
    replay_passive_gate,
)

from .cases import POLICY, canonical
from .linked_cases import source_case, write_source

COMMANDS = ("build-passive-baseline", "replay-passive-gate")


def arguments(tmp_path, command):
    ev, windows = source_case()
    directory = tmp_path / "source"
    ev, b, r = write_source(directory, ev, windows)
    policy = tmp_path / "policy.json"
    policy.write_bytes(canonical(POLICY))
    baseline = tmp_path / "baseline.json"
    baseline.write_bytes(canonical(b))
    replay = tmp_path / "replay.json"
    replay.write_bytes(canonical(r))
    args = [command, "--directory", directory, "--policy", policy]
    if command == "replay-passive-gate":
        args += ["--baseline", baseline, "--replay", replay]
    return args, ev, b, r


def invoke(args, capsys, invalid=False):
    assert main(list(map(str, args))) == int(invalid)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (f"error: {args[0]}: invalid_input_or_output\n" if invalid else "")


@pytest.mark.parametrize("command", COMMANDS)
def test_api_parity_private_atomic_mode_and_repeatability(tmp_path, capsys, command):
    args, ev, b, r = arguments(tmp_path, command)
    directory = args[args.index("--directory") + 1]
    if command == "build-passive-baseline":
        expected = build_passive_baseline(directory, POLICY)
        assert expected.model_dump(mode="json") == b
    else:
        expected = replay_passive_gate(directory, b, r, POLICY)
    output = tmp_path / "out.json"
    output.write_bytes(b"old output")
    anchors = [
        "--expected-split-id",
        ev["dataset"]["split"]["split_id"],
        "--expected-dataset-content-hash",
        ev["dataset"]["content_hash"],
    ]
    for _ in range(2):
        invoke([*args, *anchors, "--output", output], capsys)
        assert output.read_bytes() == canonical(expected.model_dump(mode="json"))
        assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert not list(tmp_path.rglob(".n4-*.tmp"))


@pytest.mark.parametrize("command", COMMANDS)
def test_every_consumed_operand_and_source_member_is_protected_including_hardlinks(
    tmp_path, capsys, command
):
    args, _, _, _ = arguments(tmp_path, command)
    directory = args[args.index("--directory") + 1]
    protected = [
        args[args.index("--" + flag) + 1]
        for flag in ("policy", "baseline", "replay")
        if "--" + flag in args
    ]
    protected += list(directory.iterdir())
    original = {path: path.read_bytes() for path in protected}
    for path in protected:
        invoke([*args, "--output", path], capsys, True)
        alias = tmp_path / "hardlink.json"
        os.link(path, alias)
        invoke([*args, "--output", alias], capsys, True)
        alias.unlink()
    invoke([*args, "--output", directory / "new.json"], capsys, True)
    assert not (directory / "new.json").exists()
    assert {path: path.read_bytes() for path in protected} == original
    assert not list(tmp_path.rglob(".n4-*.tmp"))


@pytest.mark.parametrize(
    "command,operand",
    [
        ("build-passive-baseline", "policy"),
        ("build-passive-baseline", "directory"),
        ("replay-passive-gate", "policy"),
        ("replay-passive-gate", "directory"),
        ("replay-passive-gate", "baseline"),
        ("replay-passive-gate", "replay"),
    ],
)
def test_operand_symlinks_are_rejected(tmp_path, capsys, command, operand):
    args, _, _, _ = arguments(tmp_path, command)
    index = args.index("--" + operand) + 1
    link = tmp_path / "link"
    link.symlink_to(args[index], target_is_directory=operand == "directory")
    args[index] = link
    output = tmp_path / "out.json"
    output.write_bytes(b"preserved")
    invoke([*args, "--output", output], capsys, True)
    assert output.read_bytes() == b"preserved"


@pytest.mark.parametrize("command", COMMANDS)
@pytest.mark.parametrize(
    "kind", ["symlink", "directory", "fifo", "missing_parent", "symlink_parent"]
)
def test_bad_outputs_are_rejected_without_changing_existing_files(tmp_path, capsys, command, kind):
    args, _, _, _ = arguments(tmp_path, command)
    output = tmp_path / "out.json"
    retained = tmp_path / "retained"
    retained.write_bytes(b"preserved")
    if kind == "symlink":
        output.symlink_to(retained)
    elif kind == "directory":
        output.mkdir()
    elif kind == "fifo":
        os.mkfifo(output)
    elif kind == "missing_parent":
        output = tmp_path / "absent" / "out.json"
    else:
        alias = tmp_path / "alias"
        alias.symlink_to(tmp_path, target_is_directory=True)
        output = alias / "out.json"
    invoke([*args, "--output", output], capsys, True)
    assert retained.read_bytes() == b"preserved"
    assert not list(tmp_path.rglob(".n4-*.tmp"))


@pytest.mark.parametrize("command", COMMANDS)
@pytest.mark.parametrize(
    "problem",
    [
        "malformed",
        "duplicate",
        "nonfinite",
        "utf8",
        "oversized",
        "anchor",
        "source_change",
        "extra_member",
    ],
)
def test_operational_errors_are_fixed_private_and_preserve_output(
    tmp_path, capsys, command, problem
):
    args, _, _, _ = arguments(tmp_path, command)
    operand = tmp_path / ("replay.json" if command == "replay-passive-gate" else "policy.json")
    raw = {
        "malformed": b"not JSON /private/secret",
        "duplicate": b'{"schema_version":1,"schema_version":2}',
        "nonfinite": b'{"value":NaN}',
        "utf8": b"\xff",
        "oversized": b" " * (10485760 + 1),
    }
    if problem in raw:
        operand.write_bytes(raw[problem])
    elif problem == "anchor":
        args += ["--expected-dataset-content-hash", "sha256:" + "0" * 64]
    else:
        directory = args[args.index("--directory") + 1]
        target = directory / (
            "extra.json" if problem == "extra_member" else "artifact-query-000.json"
        )
        target.write_bytes(b"private changed source /private/secret")
    output = tmp_path / "out.json"
    output.write_bytes(b"preserved")
    invoke([*args, "--output", output], capsys, True)
    assert output.read_bytes() == b"preserved"
    assert not list(tmp_path.rglob(".n4-*.tmp"))


@pytest.mark.parametrize("command", COMMANDS)
def test_pinned_source_directory_is_protected_after_rename(tmp_path, capsys, monkeypatch, command):
    args, _, _, _ = arguments(tmp_path, command)
    directory = args[args.index("--directory") + 1]
    moved = tmp_path / "moved"
    operation = (
        "_build_passive_baseline" if command == "build-passive-baseline" else "_replay_passive_gate"
    )
    original = getattr(commands, operation)

    def rename(*args, **kwargs):
        result = original(*args, **kwargs)
        directory.rename(moved)
        directory.mkdir()
        return result

    monkeypatch.setattr(commands, operation, rename)
    invoke([*args, "--output", moved / "out.json"], capsys, True)
    assert not (moved / "out.json").exists()


@pytest.mark.parametrize("command", COMMANDS)
def test_atomic_writer_failure_leaves_old_output_and_no_temp(
    tmp_path, capsys, monkeypatch, command
):
    import latency_fingerprinting.observability.output as output_io

    args, _, _, _ = arguments(tmp_path, command)
    output = tmp_path / "out.json"
    output.write_bytes(b"preserved")

    def fail(*args, **kwargs):
        raise OSError("private filesystem message")

    monkeypatch.setattr(output_io.os, "replace", fail)
    invoke([*args, "--output", output], capsys, True)
    assert output.read_bytes() == b"preserved"
    assert not list(tmp_path.rglob(".n4-*.tmp"))


@pytest.mark.parametrize(
    "args",
    [
        ["build-passive-baseline"],
        ["replay-passive-gate"],
        ["replay-passive-gate", "--directory", "x", "--policy", "x", "--output", "x"],
    ],
)
def test_required_arguments_are_syntax_errors(args, capsys):
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2
    assert capsys.readouterr().out == ""
