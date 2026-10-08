"""Public v2 commands: API parity, bounded inputs and private fail-closed errors."""

import json
import os
import subprocess
import sys

import pytest

from latency_fingerprinting import cli_v2
from latency_fingerprinting.analytical.fingerprints import create_fingerprint_v2
from latency_fingerprinting.analytical.matching import match_response_v2
from latency_fingerprinting.analytical.repository import FingerprintRepositoryV2
from latency_fingerprinting.analytical.responses import derive_analytical_response
from latency_fingerprinting.cli import main
from latency_fingerprinting.models import AnalyticalResponseV2, FeaturePolicyV1, ObservationRecordV2
from latency_fingerprinting.pipeline import canonical_json

from .cases import fingerprint_payload, policy_payload, response_payload

COMMANDS = ["build-response-v2", "build-fingerprint-v2", "match-v2"]


@pytest.fixture
def inputs(tmp_path):
    payload = response_payload()
    paths = {}
    for name, data in [
        ("policy", policy_payload()),
        ("observation", payload["observation"]),
        ("response", payload),
    ]:
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(data))
        paths[name] = path
    repository = tmp_path / "references"
    repository.mkdir()
    (repository / "reference.json").write_text(json.dumps(fingerprint_payload()))
    paths["fingerprints"] = repository
    return paths


def args(command, paths):
    common = [command, "--policy", str(paths["policy"])]
    if command == "build-response-v2":
        return [*common, "--observation", str(paths["observation"])]
    common += ["--response", str(paths["response"])]
    if command == "build-fingerprint-v2":
        return [*common, "--bottleneck-label", "network_pressure"]
    return [*common, "--fingerprints", str(paths["fingerprints"])]


@pytest.mark.parametrize("command", COMMANDS)
def test_success_is_exact_api_json_repeatable_and_read_only(command, inputs, capsys):
    payload = response_payload()
    response = AnalyticalResponseV2.model_validate(payload)
    policy = FeaturePolicyV1.model_validate(policy_payload())
    fingerprint = create_fingerprint_v2(response, bottleneck_label="network_pressure")
    expected = {
        "build-response-v2": derive_analytical_response(
            ObservationRecordV2.model_validate(payload["observation"]), policy
        ),
        "build-fingerprint-v2": fingerprint,
        "match-v2": match_response_v2(response, policy, FingerprintRepositoryV2((fingerprint,))),
    }[command]
    root = inputs["policy"].parent
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    for _ in range(2):
        assert main(args(command, inputs)) == 0
        captured = capsys.readouterr()
        assert captured.out == canonical_json(expected) and captured.err == ""
    assert before == {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_end_to_end_python_module_commands(tmp_path):
    paths = {"observation": tmp_path / "observation.json", "policy": tmp_path / "policy.json"}
    paths["observation"].write_text(json.dumps(response_payload()["observation"]))
    paths["policy"].write_text(json.dumps(policy_payload()))

    def run(arguments):
        completed = subprocess.run(  # noqa: S603
            [sys.executable, "-m", "latency_fingerprinting", *arguments],
            capture_output=True,
            check=True,
        )
        assert completed.stderr == b""
        return completed.stdout

    response_bytes = run(args("build-response-v2", paths))
    paths["response"] = tmp_path / "response.json"
    paths["response"].write_bytes(response_bytes)
    fingerprint_bytes = run(args("build-fingerprint-v2", paths))
    paths["fingerprints"] = tmp_path / "references"
    paths["fingerprints"].mkdir()
    (paths["fingerprints"] / "fingerprint.json").write_bytes(fingerprint_bytes)
    result_bytes = run(args("match-v2", paths))
    result = json.loads(result_bytes)
    assert result["decision"] == "matched" and result["acceptedLabel"] == "network_pressure"
    assert run(args("match-v2", paths)) == result_bytes


@pytest.mark.parametrize("status", ["unreviewed", "rejected", "software_checked"])
def test_explicit_validation_status_is_preserved(status, inputs, capsys):
    assert main([*args("build-fingerprint-v2", inputs), "--validation-status", status]) == 0
    assert json.loads(capsys.readouterr().out)["validationStatus"] == status


def test_analytical_unknown_and_invalid_response_are_successful_json(inputs, capsys):
    for path in inputs["fingerprints"].iterdir():
        path.unlink()
    assert main(args("match-v2", inputs)) == 0
    assert json.loads(capsys.readouterr().out)["unknownReason"] == "no_fingerprints"
    payload = response_payload(confounder="intervention")
    inputs["observation"].write_text(json.dumps(payload["observation"]))
    assert main(args("build-response-v2", inputs)) == 0
    assert json.loads(capsys.readouterr().out) == payload
    inputs["response"].write_text(json.dumps(payload))
    assert main(args("match-v2", inputs)) == 0
    assert json.loads(capsys.readouterr().out)["unknownReason"] == "invalid_response"
    assert main(args("build-fingerprint-v2", inputs)) == 1
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("command", COMMANDS)
@pytest.mark.parametrize(
    "kind",
    [
        "duplicate",
        "depth",
        "non_finite",
        "invalid_utf8",
        "wrong_root",
        "missing",
        "altered_policy",
        "rehash_policy",
    ],
)
def test_malformed_input_or_policy_fails_privately_without_partial_output(
    command, kind, inputs, capsys
):
    path = inputs["observation" if command == "build-response-v2" else "response"]
    if kind == "duplicate":
        path.write_text('{"secret_source":"one","secret_source":"two"}')
    elif kind == "depth":
        path.write_text("[" * 129 + "0" + "]" * 129)
    elif kind == "non_finite":
        path.write_text('{"secret_source":NaN}')
    elif kind == "invalid_utf8":
        path.write_bytes(b"\xff")
    elif kind == "wrong_root":
        path.write_text('{"schemaVersion":"observation-v1","secret_source":"private"}')
    elif kind == "missing":
        path.unlink()
    else:
        from latency_fingerprinting.analytical.policy_release import payload_hash

        payload = policy_payload()
        payload["features"]["transport.jitter_ms"]["epsilon"] = 2
        if kind == "rehash_policy":
            payload["contentHash"] = payload_hash(
                {k: v for k, v in payload.items() if k != "contentHash"}
            )
        inputs["policy"].write_text(json.dumps(payload))
    for _ in range(2):
        assert main(args(command, inputs)) == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == f"error: {command}: invalid_input_or_result\n"
        assert "secret_source" not in captured.err and "Traceback" not in captured.err
        assert str(path) not in captured.err


@pytest.mark.parametrize("kind", ["wrong_root", "duplicate", "symlink", "resource"])
def test_repository_errors_fail_privately_without_partial_output(kind, inputs, capsys, monkeypatch):
    repository = inputs["fingerprints"]
    if kind == "wrong_root":
        (repository / "bad.json").write_text(json.dumps(response_payload()))
    elif kind == "duplicate":
        (repository / "duplicate.json").write_bytes((repository / "reference.json").read_bytes())
    elif kind == "symlink":
        (repository / "private.json").symlink_to(inputs["response"])
    else:
        from latency_fingerprinting.analytical import repository as module

        monkeypatch.setattr(module, "MAX_FINGERPRINT_FILES_V2", 0)
    assert main(args("match-v2", inputs)) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == "error: match-v2: invalid_input_or_result\n"


@pytest.mark.parametrize("kind", ["file_link", "ancestor_link", "fifo", "directory"])
def test_unsafe_or_non_regular_direct_input_is_rejected(kind, inputs, capsys):
    original = inputs["response"]
    if kind == "file_link":
        link = original.parent / "link.json"
        link.symlink_to(original)
        inputs["response"] = link
    elif kind == "ancestor_link":
        link = original.parent / "link"
        link.symlink_to(original.parent, target_is_directory=True)
        inputs["response"] = link / original.name
    elif kind == "fifo":
        original.unlink()
        os.mkfifo(original)
    else:
        inputs["response"] = original.parent
    assert main(args("build-fingerprint-v2", inputs)) == 1
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("command", COMMANDS)
def test_oversized_output_fails_before_stdout(command, inputs, capsys, monkeypatch):
    input_path = inputs["observation" if command == "build-response-v2" else "response"]
    monkeypatch.setattr(cli_v2, "MAX_CONTRACT_JSON_BYTES", input_path.stat().st_size)
    assert main(args(command, inputs)) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and "invalid_input_or_result" in captured.err


def test_direct_input_byte_limit_before_and_after_read(inputs, capsys, monkeypatch):
    path = inputs["response"]
    monkeypatch.setattr(cli_v2, "MAX_CONTRACT_JSON_BYTES", path.stat().st_size - 1)
    assert main(args("build-fingerprint-v2", inputs)) == 1
    assert capsys.readouterr().out == ""
    from types import SimpleNamespace

    real_fstat = os.fstat

    def stale_stat(fd):
        metadata = real_fstat(fd)
        return SimpleNamespace(st_mode=metadata.st_mode, st_size=0)

    monkeypatch.setattr(os, "fstat", stale_stat)
    assert main(args("build-fingerprint-v2", inputs)) == 1
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("command", COMMANDS)
def test_explicit_paths_are_required(command, capsys):
    with pytest.raises(SystemExit) as caught:
        main([command])
    assert caught.value.code == 2
    assert capsys.readouterr().out == ""


def test_invalid_status_label_and_no_v1_skip_option(inputs, capsys):
    with pytest.raises(SystemExit):
        main([*args("build-fingerprint-v2", inputs), "--validation-status", "validated"])
    assert capsys.readouterr().out == ""
    command_args = args("build-fingerprint-v2", inputs)
    command_args[-1] = "/private/secret_label"
    assert main(command_args) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and "secret_label" not in captured.err
    with pytest.raises(SystemExit):
        main([*args("match-v2", inputs), "--allow-rejected-fingerprints"])
    assert capsys.readouterr().out == ""


def test_v1_command_rejects_v2_inputs(inputs, capsys):
    assert (
        main(["match", str(inputs["response"]), "--fingerprints", str(inputs["fingerprints"])]) == 1
    )
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("command", COMMANDS)
def test_output_exact_byte_boundary_is_accepted(command, inputs, capsys, monkeypatch):
    assert main(args(command, inputs)) == 0
    expected = capsys.readouterr().out
    monkeypatch.setattr(cli_v2, "MAX_CONTRACT_JSON_BYTES", len(expected.encode("utf-8")))
    assert main(args(command, inputs)) == 0
    captured = capsys.readouterr()
    assert captured.out == expected and captured.err == ""
