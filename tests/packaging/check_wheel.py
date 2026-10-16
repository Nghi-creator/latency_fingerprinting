"""Build and exercise a wheel in a clean venv, outside the checkout."""

from __future__ import annotations

import os
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
            f"Installed wheel imports, console entry point and all {len(actual)} schemas verified."
        )


if __name__ == "__main__":
    main()
