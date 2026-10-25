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
        from tests.passive_gating.check_reproduction import FIXTURES as PASSIVE_FIXTURES
        from tests.passive_gating.check_reproduction import check_reproduction as check_passive

        passive_corpus = directory / "passive-gating"
        shutil.copytree(PASSIVE_FIXTURES, passive_corpus)
        passive_release = check_passive(
            passive_corpus,
            n6_directory=corpus,
            n7_directory=profile_corpus,
            n8_directory=match_corpus,
            invoke=invoke_installed,
        )
        from tests.packaging.passive_check import SCRIPT, stage

        passive_operands, passive_result = stage(directory)
        run(
            [str(python), "-I", "-c", SCRIPT, str(passive_operands), str(passive_result)],
            directory=directory,
        )
        for payload in ("policy", "baseline", "replay"):
            passive_input = directory / f"n9-{payload}.json"
            passive_input.write_text(json.dumps(json.loads(passive_operands.read_bytes())[payload]))
            code, stdout, stderr = invoke_installed(["validate", passive_input])
            if code or not stdout or stderr:
                raise ValueError("installed N9 standalone validation drift")
        code, stdout, stderr = invoke_installed(["validate", passive_result])
        if code or not stdout or stderr:
            raise ValueError("installed N9 result validation drift")
        passive_data = json.loads(passive_operands.read_bytes())
        for command, extra, expected in (
            ("build-passive-baseline", [], passive_data["baseline"]),
            (
                "replay-passive-gate",
                [
                    "--baseline",
                    directory / "n9-baseline.json",
                    "--replay",
                    directory / "n9-replay.json",
                ],
                json.loads(passive_result.read_bytes()),
            ),
        ):
            output = directory / f"{command}.json"
            arguments = [
                command,
                "--directory",
                passive_data["source_directory"],
                "--policy",
                directory / "n9-policy.json",
                *extra,
                "--expected-dataset-content-hash",
                passive_data["evidence"]["dataset"]["content_hash"],
                "--output",
                output,
            ]
            code, stdout, stderr = invoke_installed(arguments)
            if code or stdout or stderr or json.loads(output.read_bytes()) != expected:
                raise ValueError("installed N9 linked command drift")
            protected = directory / ("n9-policy.json" if not extra else "n9-baseline.json")
            retained = protected.read_bytes()
            arguments[-1] = protected
            code, stdout, stderr = invoke_installed(arguments)
            if (
                code != 1
                or stdout
                or stderr != f"error: {command}: invalid_input_or_output\n".encode()
                or protected.read_bytes() != retained
            ):
                raise ValueError("installed N9 input/output protection drift")
        from tests.live_probes.cases import payload as live_payload

        live_input = directory / "live-evidence.json"
        live_input.write_text(json.dumps(live_payload()))
        code, stdout, stderr = invoke_installed(["validate", live_input])
        if code or stderr or json.loads(stdout) != live_payload():
            raise ValueError("installed N10 evidence validation drift")
        run(
            [
                str(python),
                "-I",
                "-c",
                (
                    "import json,sys; "
                    "from latency_fingerprinting.live_probes import "
                    "LiveProbeEvidence,inspect_live_probe_evidence; "
                    "e=LiveProbeEvidence.model_validate_json(open(sys.argv[1]).read()); "
                    "r=inspect_live_probe_evidence(e); "
                    "assert r.live_authority is False; "
                    "assert r.receiver_continuity == 'unverified'; "
                    "assert r.restoration == 'setting_and_local_progress_only'; "
                    "assert all(not w.reason_codes and w.decoded_frames_delta == 10 "
                    "for w in r.windows)"
                ),
                str(live_input),
            ],
            directory=directory,
        )
        from tests.live_probes.cadence_cases import META as cadence_meta
        from tests.live_probes.cadence_cases import evidence as cadence_evidence
        from tests.live_probes.cadence_cases import report as cadence_report

        cadence_input = directory / "cadence-report.json"
        cadence_output = directory / "cadence-evidence.json"
        cadence_input.write_text(json.dumps(cadence_report()))
        arguments = ["import-cadence-report", "--report", cadence_input, "--output", cadence_output]
        for key, value in cadence_meta.items():
            arguments += ["--" + key.replace("_", "-"), value]
        code, stdout, stderr = invoke_installed(arguments)
        expected_cadence = cadence_evidence().model_dump(mode="json")
        if code or stdout or stderr or json.loads(cadence_output.read_bytes()) != expected_cadence:
            raise ValueError("installed cadence import drift")
        code, stdout, stderr = invoke_installed(["validate", cadence_output])
        if code or stderr or json.loads(stdout) != expected_cadence:
            raise ValueError("installed cadence validation drift")
        run(
            [
                str(python),
                "-I",
                "-c",
                (
                    "import sys; from latency_fingerprinting.live_probes import "
                    "CadenceProbeEvidence,inspect_cadence_probe_evidence; "
                    "e=CadenceProbeEvidence.model_validate_json(open(sys.argv[1]).read()); "
                    "r=inspect_cadence_probe_evidence(e); "
                    "assert r.local_screen == 'met' and r.declared_restoration_supported; "
                    "assert r.live_authority is False and r.quality == 'not_evaluated'"
                ),
                str(cadence_output),
            ],
            directory=directory,
        )
        from tests.live_probes.game_browser_cases import META as game_meta
        from tests.live_probes.game_browser_cases import acquisition as game_acquisition
        from tests.live_probes.game_browser_cases import evidence as game_evidence

        game_input = directory / "game-browser-acquisition.json"
        game_output = directory / "game-browser-evidence.json"
        game_input.write_text(json.dumps(game_acquisition()))
        arguments = ["import-game-browser-report", "--report", game_input, "--output", game_output]
        for key, value in game_meta.items():
            arguments += ["--" + key.replace("_", "-"), value]
        code, stdout, stderr = invoke_installed(arguments)
        expected_game = game_evidence().model_dump(mode="json")
        if code or stdout or stderr or json.loads(game_output.read_bytes()) != expected_game:
            raise ValueError("installed game/browser import drift")
        code, stdout, stderr = invoke_installed(["validate", game_output])
        if code or stderr or json.loads(stdout) != expected_game:
            raise ValueError("installed game/browser validation drift")
        run(
            [
                str(python),
                "-I",
                "-c",
                (
                    "import sys; from latency_fingerprinting.live_probes import "
                    "GameBrowserProbeEvidence,inspect_game_browser_evidence; "
                    "e=GameBrowserProbeEvidence.model_validate_json(open(sys.argv[1]).read()); "
                    "r=inspect_game_browser_evidence(e); "
                    "assert r.engineering_screen == 'met' and r.declared_restoration_supported; "
                    "assert abs(r.worker_during_to_baseline_cpu_ratio - .8) < 1e-9; "
                    "assert r.live_authority is False and r.perceptual_quality == 'not_evaluated'"
                ),
                str(game_output),
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
            f"{match_release['cases']} N8 and {passive_release['cases']} N9 cases, "
            "N9 models/pure/linked APIs, N10 bitrate/cadence/game-browser evidence, "
            "inspection and protected import CLI, entry point "
            f"and all {len(actual)} schemas verified."
        )


if __name__ == "__main__":
    main()
