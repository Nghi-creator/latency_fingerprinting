"""Real bounded child processes, never native acquisitions or study-data retries."""

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "experiments/run_study_job.py"


def module():
    spec = importlib.util.spec_from_file_location("study_job", SCRIPT)
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


def launch(tmp_path, body, *, timeout=10):
    directory = tmp_path / "job"
    # This launching interpreter exits while the detached supervisor/command are active.
    result = subprocess.run(  # noqa: S603 -- fixed local helper/interpreter and synthetic command
        [
            sys.executable,
            str(SCRIPT),
            "start",
            "--job-directory",
            str(directory),
            "--cwd",
            str(tmp_path),
            "--timeout-seconds",
            str(timeout),
            "--",
            sys.executable,
            "-c",
            body,
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )
    assert json.loads(result.stdout)["state"] == "launched"
    return directory


def wait(directory, *, terminal=True):
    tool = module()
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        value = tool.status(directory)
        if (terminal and value["state"] in tool.TERMINAL) or (
            not terminal and value["state"] == "running"
        ):
            return value
        time.sleep(0.02)
    raise AssertionError("bounded synthetic supervisor did not reach expected state")


def test_job_survives_launcher_exit_in_its_own_process_session(tmp_path):
    directory = launch(
        tmp_path,
        "import pathlib,time\n"
        "while not pathlib.Path('release').exists(): time.sleep(.01)\n"
        "print('completed after caller exit')",
    )
    running = wait(directory, terminal=False)
    assert running["supervisor_session_id"] == running["supervisor_pid"]
    assert running["supervisor_session_id"] != os.getsid(0)
    (tmp_path / "release").write_text("release")
    result = wait(directory)
    assert result["state"] == "completed" and result["returncode"] == 0
    assert (directory / "command.log").read_text().strip() == "completed after caller exit"
    assert result["study_acceptance"] == "not_inferred_from_process_status"


def test_nonzero_exit_is_terminal_and_existing_job_directory_cannot_restart(tmp_path):
    directory = launch(tmp_path, "raise SystemExit(7)")
    result = wait(directory)
    assert result["state"] == "failed" and result["returncode"] == 7
    with pytest.raises(FileExistsError):
        module().start_job(directory, [sys.executable, "-c", "pass"], cwd=tmp_path)


def test_deadline_terminates_only_the_owned_command_group(tmp_path):
    directory = launch(tmp_path, "import time;time.sleep(60)", timeout=1)
    result = wait(directory)
    assert result["state"] == "timed_out" and result["returncode"] < 0
    assert result["elapsed_seconds"] < 10


def test_token_bound_stop_is_idempotent_and_records_terminal_status(tmp_path):
    directory = launch(tmp_path, "import time;time.sleep(60)")
    wait(directory, terminal=False)
    tool = module()
    assert tool.stop_job(directory)["state"] == "stop_requested"
    assert tool.stop_job(directory)["state"] in {"stop_requested", "stopped"}
    result = wait(directory)
    assert result["state"] == "stopped" and result["returncode"] < 0


def test_another_job_token_cannot_cancel_this_job(tmp_path):
    directory = launch(tmp_path, "import time;time.sleep(0.7)")
    (directory / "stop-request.json").write_text(json.dumps({"job_id": "another-job"}))
    result = wait(directory)
    assert result["state"] == "completed" and result["returncode"] == 0


def test_manifest_mutation_stops_owned_command_without_executing_changed_argv(tmp_path):
    directory = launch(tmp_path, "import time;time.sleep(60)")
    wait(directory, terminal=False)
    original = (directory / "job.json").read_bytes()
    manifest = json.loads(original)
    manifest["command"] = ["/unavailable/changed-command"]
    (directory / "job.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="manifest changed"):
        module().status(directory)
    deadline = time.monotonic() + 10
    while not (directory / "result.json").exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    result = json.loads((directory / "result.json").read_text())
    assert result["state"] == "failed" and result["reason"] == "manifest_changed"
    assert result["returncode"] < 0
    (directory / "job.json").write_bytes(original)
    assert module().status(directory)["state"] == "failed"


def test_changed_manifest_cannot_launch_a_supervisor_command(tmp_path):
    (tmp_path / "job.json").write_text("{}")
    with pytest.raises(ValueError, match="manifest changed"):
        module().supervise(tmp_path, manifest_sha256="0" * 64)
    assert not (tmp_path / "supervisor-claim.json").exists()
    assert not (tmp_path / "command.log").exists()


@pytest.mark.parametrize("timeout", [0, 7201, True])
def test_invalid_deadlines_create_no_job_or_process(tmp_path, timeout):
    directory = tmp_path / "job"
    with pytest.raises(ValueError):
        module().start_job(
            directory, [sys.executable, "-c", "pass"], cwd=tmp_path, timeout_seconds=timeout
        )
    assert not directory.exists()
