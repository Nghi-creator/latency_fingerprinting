#!/usr/bin/env python3
"""Launch one bounded, supervised POSIX job independently of the calling terminal."""

from __future__ import annotations

import argparse
import contextlib
import datetime
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

TERMINAL = {"completed", "failed", "timed_out", "stopped", "launch_failed"}


def now():
    return datetime.datetime.now(datetime.UTC).isoformat()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def publish(path, value, *, exclusive=False):
    temporary = path.parent / (".job-" + uuid.uuid4().hex + ".tmp")
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
        if exclusive:
            os.link(temporary, path)
        else:
            os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def start_job(directory, command, *, cwd, timeout_seconds=3600):
    """No shell, scheduling, retry or resume. The command is explicitly trusted caller input."""
    if os.name != "posix":
        raise ValueError("POSIX process sessions required")
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 7200:
        raise ValueError("timeout must be an integer from 1 to 7200 seconds")
    if not command or any(type(v) is not str or not v for v in command):
        raise ValueError("explicit command argument vector required")
    executable = shutil.which(command[0])
    if executable is None:
        raise ValueError("command executable unavailable")
    cwd, directory = Path(cwd).resolve(), Path(directory).resolve()
    if not cwd.is_dir():
        raise ValueError("working directory unavailable")
    script = Path(__file__).resolve()
    directory.mkdir(mode=0o700)  # Exclusive directory also prevents accidental retry.
    manifest = dict(
        schema_version="bounded-study-job-v1",
        job_id=uuid.uuid4().hex,
        command=[executable, *command[1:]],
        cwd=str(cwd),
        timeout_seconds=timeout_seconds,
        created_at_utc=now(),
        launcher_pid=os.getpid(),
        supervisor_sha256=sha(script),
    )
    publish(directory / "job.json", manifest, exclusive=True)
    manifest_digest = sha(directory / "job.json")
    try:
        with (directory / "supervisor.log").open("xb") as output:
            # Trusted local interpreter/script/argv; detached I/O never holds a caller pipe open.
            worker = subprocess.Popen(  # noqa: S603
                [
                    sys.executable,
                    str(script),
                    "_supervise",
                    str(directory),
                    "--manifest-sha256",
                    manifest_digest,
                ],
                cwd=directory,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )
        publish(
            directory / "launch.json",
            dict(
                job_id=manifest["job_id"],
                supervisor_pid=worker.pid,
                manifest_sha256=manifest_digest,
            ),
            exclusive=True,
        )
    except OSError:
        publish(
            directory / "result.json",
            dict(job_id=manifest["job_id"], state="launch_failed", ended_at_utc=now()),
            exclusive=True,
        )
        raise
    return dict(
        job_id=manifest["job_id"],
        directory=str(directory),
        state="launched",
        supervisor_pid=worker.pid,
    )


def bound_manifest(directory):
    raw = (directory / "job.json").read_bytes()
    manifest = json.loads(raw)
    confirmed = False
    for name in ("launch.json", "supervisor-claim.json"):
        path = directory / name
        if path.exists():
            anchor = read(path)
            if (
                anchor.get("job_id") != manifest["job_id"]
                or anchor.get("manifest_sha256") != hashlib.sha256(raw).hexdigest()
            ):
                raise ValueError("job manifest changed")
            confirmed = True
    return manifest, confirmed


def status(directory):
    directory = Path(directory).resolve()
    manifest, confirmed = bound_manifest(directory)
    if not confirmed:
        result = directory / "result.json"
        if result.exists():
            value = read(result)
            if value.get("job_id") == manifest["job_id"] and value.get("state") == "launch_failed":
                return value
        return dict(job_id=manifest["job_id"], state="launch_unconfirmed")
    result = directory / "result.json"
    if result.exists():
        value = read(result)
        if value.get("job_id") != manifest["job_id"] or value.get("state") not in TERMINAL:
            raise ValueError("invalid job result")
        return value
    heartbeat = directory / "heartbeat.json"
    if not heartbeat.exists():
        return dict(job_id=manifest["job_id"], state="launch_unconfirmed")
    value = read(heartbeat)
    if value.get("job_id") != manifest["job_id"]:
        raise ValueError("invalid job heartbeat")
    age = (
        datetime.datetime.now(datetime.UTC)
        - datetime.datetime.fromisoformat(value["observed_at_utc"])
    ).total_seconds()
    if not 0 <= age <= 5:
        value["state"] = "supervision_unconfirmed"
    return value


def stop_job(directory):
    """Request cancellation by job token; never signal a PID read from a file."""
    directory = Path(directory).resolve()
    manifest, _ = bound_manifest(directory)
    if (directory / "result.json").exists():
        return status(directory)
    request = directory / "stop-request.json"
    if request.exists():
        if read(request).get("job_id") != manifest["job_id"]:
            raise ValueError("stop request belongs to another job")
        return dict(job_id=manifest["job_id"], state="stop_requested")
    publish(request, dict(job_id=manifest["job_id"], requested_at_utc=now()), exclusive=True)
    return dict(job_id=manifest["job_id"], state="stop_requested")


def supervise(directory, *, manifest_sha256):
    directory = Path(directory).resolve()
    raw = (directory / "job.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest_sha256:
        raise ValueError("job manifest changed before supervisor start")
    manifest = json.loads(raw)
    if manifest["supervisor_sha256"] != sha(Path(__file__).resolve()):
        raise ValueError("supervisor source changed")
    publish(
        directory / "supervisor-claim.json",
        dict(
            job_id=manifest["job_id"],
            pid=os.getpid(),
            session_id=os.getsid(0),
            manifest_sha256=manifest_sha256,
        ),
        exclusive=True,
    )
    interrupted = []
    for kind in (signal.SIGTERM, signal.SIGINT):
        signal.signal(kind, lambda signum, frame: interrupted.append(signum))
    started = time.monotonic()
    child = None
    state, reason, code = "failed", "supervisor_error", None
    try:
        with (directory / "command.log").open("xb") as output:
            child = subprocess.Popen(  # noqa: S603 -- frozen explicitly supplied argv, no shell
                manifest["command"],
                cwd=manifest["cwd"],
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )
            while child.poll() is None:
                if sha(directory / "job.json") != manifest_sha256:
                    state, reason = "failed", "manifest_changed"
                    break
                request = directory / "stop-request.json"
                if interrupted or (
                    request.exists() and read(request).get("job_id") == manifest["job_id"]
                ):
                    state, reason = "stopped", "explicit_stop_or_supervisor_signal"
                    break
                if time.monotonic() - started >= manifest["timeout_seconds"]:
                    state, reason = "timed_out", "whole_job_deadline"
                    break
                publish(
                    directory / "heartbeat.json",
                    dict(
                        job_id=manifest["job_id"],
                        state="running",
                        supervisor_pid=os.getpid(),
                        supervisor_session_id=os.getsid(0),
                        command_pid=child.pid,
                        observed_at_utc=now(),
                        elapsed_seconds=round(time.monotonic() - started, 3),
                    ),
                )
                time.sleep(0.25)
            else:
                code = child.returncode
                state, reason = (
                    ("completed", "exit_zero") if code == 0 else ("failed", "command_exit")
                )
    finally:
        if child is not None:
            if child.poll() is None:
                # The unreaped child is still alive: its group cannot have been recycled.
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=5)
            code = child.returncode
        publish(
            directory / "result.json",
            dict(
                job_id=manifest["job_id"],
                state=state,
                reason=reason,
                returncode=code,
                ended_at_utc=now(),
                elapsed_seconds=round(time.monotonic() - started, 3),
                study_acceptance="not_inferred_from_process_status",
            ),
            exclusive=True,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    start = modes.add_parser("start")
    start.add_argument("--job-directory", type=Path, required=True)
    start.add_argument("--cwd", type=Path, required=True)
    start.add_argument("--timeout-seconds", type=int, default=3600)
    start.add_argument("command", nargs=argparse.REMAINDER)
    for mode in ("status", "stop"):
        modes.add_parser(mode).add_argument("directory", type=Path)
    supervisor = modes.add_parser("_supervise")
    supervisor.add_argument("directory", type=Path)
    supervisor.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args()
    try:
        if args.mode == "start":
            command = args.command[1:] if args.command[:1] == ["--"] else args.command
            value = start_job(
                args.job_directory, command, cwd=args.cwd, timeout_seconds=args.timeout_seconds
            )
        elif args.mode == "status":
            value = status(args.directory)
        elif args.mode == "stop":
            value = stop_job(args.directory)
        else:
            supervise(args.directory, manifest_sha256=args.manifest_sha256)
            return 0
        print(json.dumps(value, indent=2))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"job operation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
