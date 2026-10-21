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
        from tests.profiles.cases import (
            canonical,
            draft,
            excluded,
            policy,
            reviewed,
            seal,
            supported,
        )

        for name, payload in (
            ("profile-policy", policy()),
            ("profile-draft", draft()),
            ("profile-supported", supported()),
        ):
            source = directory / (name + ".json")
            source.write_bytes(canonical(payload))
            # Validate independent model-only examples with the installed entry point.
            completed = subprocess.run(  # noqa: S603
                [str(executable), "validate", str(source)],
                cwd=directory,
                capture_output=True,
                check=False,
                timeout=30,
                env={k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "PYTHONHOME"}},
            )
            if (
                completed.returncode != 0
                or completed.stderr
                or completed.stdout != source.read_bytes()
            ):
                raise ValueError("installed N7 standalone validation drift")

        # All new commands execute outside the checkout against the installed wheel.
        def profile_command(command, arguments, expected=None):
            output = directory / "profile-output.json"
            output.write_bytes(b"retained output\n")
            completed = subprocess.run(  # noqa: S603
                [str(executable), command, *map(str, arguments), "--output", str(output)],
                cwd=directory,
                capture_output=True,
                check=False,
                timeout=30,
                env={k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "PYTHONHOME"}},
            )
            invalid = expected is None
            if (
                completed.returncode != int(invalid)
                or completed.stdout
                or completed.stderr
                != (f"error: {command}: invalid_input_or_output\n".encode() if invalid else b"")
                or output.read_bytes() != (b"retained output\n" if invalid else canonical(expected))
            ):
                raise ValueError("installed N7 command parity/privacy drift")

        policy_path = directory / "profile-policy.json"
        profile_command("create-profile-snapshot", ["--policy", policy_path], draft())
        for name, expected_case in release["cases"].items():
            profile_command(
                "build-profiles",
                ["--directory", corpus / name, "--policy", policy_path],
                None if "error" in expected_case else excluded(name),
            )
        parent = supported()  # Artificial model-only lifecycle checks, not linked evidence.
        target = supported()
        target["lifecycle"]["parent_snapshot_id"] = draft()["snapshot_id"]
        seal(target)
        target_path = directory / "replacement.json"
        target_path.write_bytes(canonical(target))
        for operation, reason in (
            ("mark_stale", "external_review"),
            ("reject", "operator_rejected"),
            ("supersede", "replacement_selected"),
        ):
            target_id = target["snapshot_id"] if operation == "supersede" else None
            declaration = dict(
                actor_id="operator",
                subject_snapshot_id=parent["snapshot_id"],
                replacement_snapshot_id=target_id,
                reason_code=reason,
                evidence_sha256="sha256:" + "a" * 64,
            )
            review_path = directory / "review.json"
            review_path.write_bytes(canonical(declaration))
            arguments = [
                "--snapshot",
                directory / "profile-supported.json",
                "--operation",
                operation,
                "--reason",
                reason,
                "--review",
                review_path,
            ]
            if target_id is not None:
                arguments += ["--replacement", target_path]
            expected = reviewed(parent, operation, reason, target_id)
            # The independent helper uses the same declared review digest.
            assert expected["lifecycle"]["review"] == declaration
            profile_command("transition-profile-snapshot", arguments, expected)
        load_release(corpus)
        run(
            [
                str(python),
                "-I",
                "-c",
                "from latency_fingerprinting.models import ProfilePolicy, ProfileSnapshot",
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
            f"Installed wheel imports, all 14 N6/N7 cases, N7 lifecycle commands, entry point "
            f"and all {len(actual)} schemas verified."
        )


if __name__ == "__main__":
    main()
