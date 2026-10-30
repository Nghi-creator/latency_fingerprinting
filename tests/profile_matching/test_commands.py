"""N8 command parity, private errors and protected no-follow output boundaries."""

import os
import shutil
import stat

import pytest

from latency_fingerprinting.cli import main
from latency_fingerprinting.profile_matching import (
    commands,
    evaluate_profile_snapshot,
    match_profile_snapshot,
)
from tests.calibration.check_reproduction import FIXTURES

from .cases import canonical, policy
from .test_synthetic_inputs import source


def arguments(tmp_path, command, case="reviewed-roles"):
    ev, _ = source(case)
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_bytes(canonical(ev["snapshot"]))
    policy_file = tmp_path / "policy.json"
    policy_file.write_bytes(canonical(policy()))
    args = [
        command,
        "--directory",
        FIXTURES / case,
        "--snapshot",
        snapshot,
        "--policy",
        policy_file,
    ]
    if command == "match-profiles":
        args += ["--query-entry-id", ev["report"]["entries"][0]["entry_id"]]
    else:
        args += ["--mode", "leave_training_group_out"]
    return args, ev


def invoke(args, capsys, invalid=False):
    assert main(list(map(str, args))) == int(invalid)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (f"error: {args[0]}: invalid_input_or_output\n" if invalid else "")


@pytest.mark.parametrize("command", ["match-profiles", "evaluate-profiles"])
def test_canonical_private_output_api_parity_and_explicit_overwrite(command, tmp_path, capsys):
    args, ev = arguments(tmp_path, command)
    output = tmp_path / "out.json"
    output.write_bytes(b"previous output")
    invoke([*args, "--output", output], capsys)
    if command == "match-profiles":
        expected = match_profile_snapshot(
            FIXTURES / "reviewed-roles",
            ev["snapshot"],
            policy(),
            query_entry_id=ev["report"]["entries"][0]["entry_id"],
        )
    else:
        expected = evaluate_profile_snapshot(
            FIXTURES / "reviewed-roles", ev["snapshot"], policy(), mode="leave_training_group_out"
        )
    assert output.read_bytes() == canonical(expected.model_dump(mode="json"))
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    invoke([*args, "--output", output], capsys)
    assert not list(tmp_path.glob(".n4-*.tmp"))


@pytest.mark.parametrize("command", ["match-profiles", "evaluate-profiles"])
def test_every_operand_and_source_member_is_protected_including_hardlinks(
    command, tmp_path, capsys
):
    args, _ = arguments(tmp_path, command)
    corpus = tmp_path / "corpus"
    shutil.copytree(FIXTURES / "reviewed-roles", corpus)
    args[args.index("--directory") + 1] = corpus
    protected = [tmp_path / "snapshot.json", tmp_path / "policy.json", *corpus.iterdir()]
    originals = {p: p.read_bytes() for p in protected}
    for path in protected:
        invoke([*args, "--output", path], capsys, True)
        alias = tmp_path / "hardlink.json"
        os.link(path, alias)
        invoke([*args, "--output", alias], capsys, True)
        alias.unlink()
    invoke([*args, "--output", corpus / "new.json"], capsys, True)
    assert {p: p.read_bytes() for p in protected} == originals
    assert not (corpus / "new.json").exists()
    assert not list(tmp_path.rglob(".n4-*.tmp"))


@pytest.mark.parametrize("command", ["match-profiles", "evaluate-profiles"])
@pytest.mark.parametrize("operand", ["directory", "snapshot", "policy"])
def test_input_symlinks_are_rejected(command, operand, tmp_path, capsys):
    args, _ = arguments(tmp_path, command)
    index = args.index("--" + operand) + 1
    path = tmp_path / "link"
    path.symlink_to(args[index], target_is_directory=operand == "directory")
    args[index] = path
    output = tmp_path / "out.json"
    output.write_bytes(b"preserved")
    invoke([*args, "--output", output], capsys, True)
    assert output.read_bytes() == b"preserved"


@pytest.mark.parametrize("command", ["match-profiles", "evaluate-profiles"])
@pytest.mark.parametrize(
    "kind", ["symlink", "directory", "fifo", "missing_parent", "symlink_parent"]
)
def test_bad_output_is_rejected_without_replacing_existing_data(command, kind, tmp_path, capsys):
    args, _ = arguments(tmp_path, command)
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
        alias = tmp_path / "parent"
        alias.symlink_to(tmp_path, target_is_directory=True)
        output = alias / "out.json"
    invoke([*args, "--output", output], capsys, True)
    assert retained.read_bytes() == b"preserved"
    assert not list(tmp_path.glob(".n4-*.tmp"))


@pytest.mark.parametrize("command", ["match-profiles", "evaluate-profiles"])
@pytest.mark.parametrize(
    "problem", ["malformed", "duplicate", "unknown_query_or_mode", "anchor", "changed_artifact"]
)
def test_invalid_request_preserves_output_and_fixed_private_error(
    command, problem, tmp_path, capsys
):
    args, _ = arguments(tmp_path, command)
    if problem == "malformed":
        (tmp_path / "snapshot.json").write_bytes(b"not json /private/path")
    elif problem == "duplicate":
        (tmp_path / "policy.json").write_bytes(b'{"schema_version": 1, "schema_version": 2}')
    elif problem == "unknown_query_or_mode":
        if command == "match-profiles":
            args[-1] = "absent"
        else:
            args[args.index("--snapshot") + 1] = tmp_path / "absent"
    elif problem == "anchor":
        args += ["--expected-dataset-content-hash", "sha256:" + "0" * 64]
    else:
        corpus = tmp_path / "corpus"
        shutil.copytree(FIXTURES / "reviewed-roles", corpus)
        args[args.index("--directory") + 1] = corpus
        artifact = next(p for p in corpus.iterdir() if p.name != "calibration-dataset.json")
        artifact.write_bytes(artifact.read_bytes() + b" ")
    output = tmp_path / "out.json"
    output.write_bytes(b"preserved")
    invoke([*args, "--output", output], capsys, True)
    assert output.read_bytes() == b"preserved"


@pytest.mark.parametrize("command", ["match-profiles", "evaluate-profiles"])
def test_pinned_source_directory_is_protected_after_path_rename(
    command, tmp_path, capsys, monkeypatch
):
    args, _ = arguments(tmp_path, command)
    corpus = tmp_path / "corpus"
    shutil.copytree(FIXTURES / "reviewed-roles", corpus)
    args[args.index("--directory") + 1] = corpus
    moved = tmp_path / "moved"
    operation_name = (
        "_match_profile_snapshot" if command == "match-profiles" else "_evaluate_profile_snapshot"
    )
    original = getattr(commands, operation_name)

    def rename(*a, **kw):
        result = original(*a, **kw)
        corpus.rename(moved)
        corpus.mkdir()
        return result

    monkeypatch.setattr(commands, operation_name, rename)
    invoke([*args, "--output", moved / "out.json"], capsys, True)
    assert not (moved / "out.json").exists()


@pytest.mark.parametrize(
    "args",
    [
        ["match-profiles"],
        ["evaluate-profiles"],
        [
            "evaluate-profiles",
            "--directory",
            "x",
            "--snapshot",
            "x",
            "--policy",
            "x",
            "--output",
            "x",
            "--mode",
            "training",
        ],
    ],
)
def test_missing_or_invalid_required_arguments_are_syntax_errors(args, capsys):
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2
    assert capsys.readouterr().out == ""
