"""Regression tests for reusable controlled-experiment tooling."""

from __future__ import annotations

import importlib.util
import io
import json
import tarfile
from pathlib import Path
from types import ModuleType

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str) -> ModuleType:
    path = PROJECT_ROOT / "experiments" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"experiment_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_bundle(path: Path, *, case_id: str, phase: str, run_id: str) -> None:
    payload = json.dumps(
        {
            "schemaVersion": 2,
            "comparisonCaseId": case_id,
            "phase": phase,
            "runId": run_id,
            "createdAt": "2026-08-13T00:00:00Z",
        }
    ).encode()
    info = tarfile.TarInfo("bundle-manifest.json")
    info.size = len(payload)
    with tarfile.open(path, "w") as archive:
        archive.addfile(info, io.BytesIO(payload))


def test_checksum_manifest_is_generic_and_deterministic(tmp_path: Path) -> None:
    script = load_script("record_bundle_checksums")
    experiment = tmp_path / "controlled-run-003"
    raw = experiment / "raw" / "full_data"
    raw.mkdir(parents=True)
    for phase in script.PHASES:
        write_bundle(
            raw / f"{phase}.tar",
            case_id=experiment.name,
            phase=phase,
            run_id="independent-run-id",
        )

    first = script.build_manifest(experiment)
    second = script.build_manifest(experiment)

    assert first == second
    assert first["comparisonCaseId"] == experiment.name
    assert first["runId"] == "independent-run-id"
    assert [artifact["phase"] for artifact in first["artifacts"]] == list(script.PHASES)
    assert all(len(artifact["sha256"]) == 64 for artifact in first["artifacts"])


def test_checksum_manifest_rejects_cross_case_bundle(tmp_path: Path) -> None:
    script = load_script("record_bundle_checksums")
    experiment = tmp_path / "controlled-run-003"
    raw = experiment / "raw" / "full_data"
    raw.mkdir(parents=True)
    for phase in script.PHASES:
        write_bundle(
            raw / f"{phase}.tar",
            case_id="wrong-case",
            phase=phase,
            run_id="independent-run-id",
        )

    with pytest.raises(ValueError, match="comparisonCaseId"):
        script.build_manifest(experiment)


def test_checksum_manifest_rejects_oversized_embedded_manifest(tmp_path: Path) -> None:
    script = load_script("record_bundle_checksums")
    bundle = tmp_path / "bundle.tar"
    info = tarfile.TarInfo("bundle-manifest.json")
    info.size = script.MAX_EMBEDDED_MANIFEST_BYTES + 1
    with tarfile.open(bundle, "w") as archive:
        archive.addfile(info, io.BytesIO(b" " * info.size))

    with pytest.raises(ValueError, match="safety limit"):
        script.embedded_manifest(bundle)


class FakeProcess:
    instances: list[FakeProcess] = []
    fail_start_at: int | None = None

    def __init__(self, **_: object) -> None:
        self.index = len(self.instances)
        self.alive = False
        self.terminated = False
        self.instances.append(self)

    def start(self) -> None:
        if self.index == self.fail_start_at:
            raise RuntimeError("start failed")
        self.alive = True

    def join(self) -> None:
        self.alive = False

    def is_alive(self) -> bool:
        return self.alive

    def terminate(self) -> None:
        self.terminated = True
        self.alive = False


def install_fake_process(monkeypatch: pytest.MonkeyPatch, script: ModuleType) -> None:
    FakeProcess.instances = []
    FakeProcess.fail_start_at = None
    monkeypatch.setattr(script.multiprocessing, "Process", FakeProcess)


def test_pressure_reports_started_only_after_all_workers_start(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = load_script("bounded_cpu_pressure")
    install_fake_process(monkeypatch, script)

    code = script.main(["--duration-s", "30", "--workers", "2", "--confirm-experiment-only"])
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]

    assert code == 0
    assert events == [
        {"durationS": 30, "event": "pressure_started", "workers": 2},
        {"event": "pressure_stopped", "restored": True},
    ]


def test_pressure_cleans_up_partial_start_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = load_script("bounded_cpu_pressure")
    install_fake_process(monkeypatch, script)
    FakeProcess.fail_start_at = 1

    code = script.main(["--duration-s", "30", "--workers", "2", "--confirm-experiment-only"])
    captured = capsys.readouterr()
    events = [json.loads(line) for line in captured.out.splitlines()]

    assert code == 1
    assert events == [{"errorType": "RuntimeError", "event": "pressure_stopped", "restored": True}]
    assert FakeProcess.instances[0].terminated
    assert "start failed" in captured.err
