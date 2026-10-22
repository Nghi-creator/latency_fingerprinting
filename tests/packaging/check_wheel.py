"""Build and exercise a wheel in a clean venv, outside the checkout."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run(arguments: list[str], *, directory: Path) -> None:
    # Trusted interpreter/CLI and temporary paths; no shell or arbitrary command input.
    environment = {
        key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "PYTHONHOME"}
    }
    subprocess.run(arguments, cwd=directory, env=environment, check=True, timeout=180)  # noqa: S603


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="latency-wheel-") as temporary:
        directory = Path(temporary).resolve()
        wheels = directory / "wheels"
        run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                str(ROOT),
                "--wheel-dir",
                str(wheels),
            ],
            directory=directory,
        )
        (wheel,) = wheels.glob("latency_fingerprinting-*.whl")
        environment = directory / "installed"
        venv.EnvBuilder(with_pip=True).create(environment)
        scripts = environment / ("Scripts" if os.name == "nt" else "bin")
        python = scripts / ("python.exe" if os.name == "nt" else "python")
        run([str(python), "-m", "pip", "install", str(wheel)], directory=directory)
        run(
            [
                str(python),
                "-I",
                "-c",
                (
                    "import pathlib, sys, latency_fingerprinting; "
                    "location=pathlib.Path(latency_fingerprinting.__file__); "
                    "assert location.is_relative_to(sys.prefix); "
                    "import latency_fingerprinting.adapters.pixelated_archive"
                ),
            ],
            directory=directory,
        )
        executable = scripts / (
            "latency-fingerprint.exe" if os.name == "nt" else "latency-fingerprint"
        )
        run([str(executable), "--help"], directory=directory)
        # Frozen source data and independent expectations run against the installed CLI.
        from tests.calibration.check_reproduction import FIXTURES, load_release, report_projection

        release = load_release()
        corpus = directory / "calibration"
        shutil.copytree(FIXTURES, corpus)
        inspected = directory / "calibration-report.json"
        for name, expected_case in release["cases"].items():
            inspected.write_bytes(b"retained output\n")
            arguments = [
                str(executable),
                "inspect-calibration",
                "--directory",
                str(corpus / name),
                "--output",
                str(inspected),
            ]
            # Trusted installed executable and copied pinned data; no shell.
            completed = subprocess.run(  # noqa: S603
                arguments,
                cwd=directory,
                capture_output=True,
                check=False,
                timeout=30,
                env={k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "PYTHONHOME"}},
            )
            invalid = "error" in expected_case
            expected_error = (
                b"error: inspect-calibration: invalid_input_or_output\n" if invalid else b""
            )
            if (
                completed.returncode != int(invalid)
                or completed.stdout
                or completed.stderr != expected_error
            ):
                raise ValueError("installed N6 CLI status/privacy drift")
            if invalid:
                if inspected.read_bytes() != b"retained output\n":
                    raise ValueError("installed N6 CLI failed to preserve output")
            elif report_projection(json.loads(inspected.read_bytes())) != expected_case:
                raise ValueError("installed N6 independent expectation mismatch")
        load_release(corpus)
        from tests.profiles.check_reproduction import FIXTURES as PROFILE_FIXTURES
        from tests.profiles.check_reproduction import check_reproduction as check_profiles

        profile_corpus = directory / "profiles"
        shutil.copytree(PROFILE_FIXTURES, profile_corpus)

        def invoke_installed(arguments):
            # Trusted installed executable and pinned fixture operands, without a shell.
            completed = subprocess.run(  # noqa: S603
                [str(executable), *map(str, arguments)],
                cwd=directory,
                capture_output=True,
                check=False,
                timeout=30,
                env={k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "PYTHONHOME"}},
            )
            return completed.returncode, completed.stdout, completed.stderr

        profile_release = check_profiles(
            profile_corpus,
            n6_directory=corpus,
            invoke=invoke_installed,
        )
        run(
            [
                str(python),
                "-I",
                "-c",
                "from latency_fingerprinting.models import ProfilePolicy, ProfileSnapshot",
            ],
            directory=directory,
        )
        from tests.profile_matching.check_reproduction import FIXTURES as MATCH_FIXTURES
        from tests.profile_matching.check_reproduction import check_reproduction as check_matching

        match_corpus = directory / "profile-matching"
        shutil.copytree(MATCH_FIXTURES, match_corpus)
        match_release = check_matching(
            match_corpus,
            n6_directory=corpus,
            n7_directory=profile_corpus,
            invoke=invoke_installed,
        )
        protected = match_corpus / "snapshot-reviewed-roles.json"
        original = protected.read_bytes()
        for command, extra in (
            ("match-profiles", ["--query-entry-id", "entry-a"]),
            ("evaluate-profiles", ["--mode", "validation"]),
        ):
            code, stdout, stderr = invoke_installed(
                [
                    command,
                    "--directory",
                    corpus / "reviewed-roles",
                    "--snapshot",
                    protected,
                    "--policy",
                    match_corpus / "policy.json",
                    *extra,
                    "--output",
                    protected,
                ]
            )
            if (
                code != 1
                or stdout
                or stderr != f"error: {command}: invalid_input_or_output\n".encode()
                or protected.read_bytes() != original
            ):
                raise ValueError("installed N8 input/output protection drift")
        run(
            [
                str(python),
                "-I",
                "-c",
                "from latency_fingerprinting.models import "
                "ProfileMatchPolicy, ProfileMatchResult, ProfileEvaluationResult; "
                "from latency_fingerprinting.profile_matching import "
                "match_profile_snapshot, evaluate_profile_snapshot",
            ],
            directory=directory,
        )
        exported = directory / "schemas"
        run(
            [
                str(python),
                "-I",
                "-m",
                "latency_fingerprinting",
                "export-schemas",
                "--output",
                str(exported),
            ],
            directory=directory,
        )
        expected = {p.name: p.read_bytes() for p in (ROOT / "schemas").glob("*.schema.json")}
        actual = {p.name: p.read_bytes() for p in exported.glob("*.schema.json")}
        if not expected or expected != actual:
            raise ValueError("installed wheel schema exports differ from the frozen release")
        print(
            f"Installed wheel imports, 14 N6 and {profile_release['cases']} N7 cases, "
            f"{match_release['cases']} N8 cases, entry point "
            f"and all {len(actual)} schemas verified."
        )


if __name__ == "__main__":
    main()
