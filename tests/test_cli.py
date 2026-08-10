"""Command-line boundary tests for the offline P0 workflow."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from latency_fingerprinting.cli import main
from latency_fingerprinting.models import (
    MatchDecision,
    MatchResult,
    ObservationRecord,
    ObservationWindow,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = PROJECT_ROOT / "fixtures"
QUERY_CASES = FIXTURES / "query_cases"
REFERENCES = FIXTURES / "reference_cases"
SCHEMAS = PROJECT_ROOT / "schemas"
PIXELATED = PROJECT_ROOT / "tests" / "data" / "pixelated_bundle"


def invoke(args: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    exit_code = main(args)
    captured = capsys.readouterr()
    return exit_code, captured.out, captured.err


@pytest.mark.parametrize(
    ("path", "schema_version"),
    [
        (QUERY_CASES / "similar_network" / "observation.json", "observation-v1"),
        (REFERENCES / "network_pressure" / "fingerprint.json", "fingerprint-v1"),
        (QUERY_CASES / "similar_network" / "expected-match-result.json", "match-result-v1"),
    ],
)
def test_validate_accepts_each_root_record(
    path: Path,
    schema_version: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code, stdout, stderr = invoke(["validate", str(path)], capsys)

    assert exit_code == 0
    assert json.loads(stdout)["schemaVersion"] == schema_version
    assert stderr == ""


def test_validate_rejects_unknown_schema_version(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "unknown.json"
    path.write_text('{"schemaVersion": "future-v2"}\n', encoding="utf-8")

    exit_code, stdout, stderr = invoke(["validate", str(path)], capsys)

    assert exit_code == 1
    assert stdout == ""
    assert "unsupported schemaVersion" in stderr


def test_export_schemas_writes_then_checks_current_files(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "schemas"
    export_code, export_stdout, export_stderr = invoke(
        ["export-schemas", "--output", str(output)], capsys
    )
    check_code, check_stdout, check_stderr = invoke(
        ["export-schemas", "--output", str(output), "--check"], capsys
    )

    assert export_code == 0
    assert json.loads(export_stdout)["status"] == "written"
    assert export_stderr == ""
    assert check_code == 0
    assert json.loads(check_stdout)["status"] == "current"
    assert check_stderr == ""
    assert {path.name for path in output.iterdir()} == {path.name for path in SCHEMAS.iterdir()}


def test_export_schema_check_reports_drift_without_rewriting(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "schemas"
    invoke(["export-schemas", "--output", str(output)], capsys)
    changed = output / "observation-v1.schema.json"
    changed.write_text("modified by test\n", encoding="utf-8")

    exit_code, stdout, stderr = invoke(
        ["export-schemas", "--output", str(output), "--check"], capsys
    )

    assert exit_code == 1
    assert stdout == ""
    assert "schema drift detected" in stderr
    assert changed.read_text(encoding="utf-8") == "modified by test\n"


def test_build_response_emits_the_expected_observation(
    capsys: pytest.CaptureFixture[str],
) -> None:
    case = QUERY_CASES / "similar_network"
    exit_code, stdout, stderr = invoke(
        [
            "build-response",
            "--degraded",
            str(case / "degraded.json"),
            "--relief",
            str(case / "relief.json"),
            "--probe",
            str(case / "probe.json"),
        ],
        capsys,
    )

    expected = ObservationRecord.model_validate_json(
        (case / "observation.json").read_text(encoding="utf-8")
    )
    assert exit_code == 0
    assert ObservationRecord.model_validate_json(stdout) == expected
    assert stderr == ""


def test_build_response_reports_missing_input(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    case = QUERY_CASES / "similar_network"
    exit_code, stdout, stderr = invoke(
        [
            "build-response",
            "--degraded",
            str(tmp_path / "missing.json"),
            "--relief",
            str(case / "relief.json"),
            "--probe",
            str(case / "probe.json"),
        ],
        capsys,
    )

    assert exit_code == 1
    assert stdout == ""
    assert "error:" in stderr


def test_ingest_pixelated_emits_a_core_window(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code, stdout, stderr = invoke(
        [
            "ingest-pixelated",
            str(PIXELATED / "valid"),
            "--phase",
            "degraded",
            "--comparison-case-id",
            "controlled-case-001",
            "--context",
            str(PIXELATED / "context.json"),
        ],
        capsys,
    )

    window = ObservationWindow.model_validate_json(stdout)
    assert exit_code == 0
    assert window.phase.value == "degraded"
    assert window.comparison_case_id == "controlled-case-001"
    assert stderr == ""


def test_ingest_pixelated_v2_emits_compute_metrics(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code, stdout, stderr = invoke(
        [
            "ingest-pixelated",
            str(PIXELATED / "valid-v2"),
            "--phase",
            "degraded",
            "--comparison-case-id",
            "controlled-case-001",
            "--context",
            str(PIXELATED / "context-v2.json"),
        ],
        capsys,
    )

    window = ObservationWindow.model_validate_json(stdout)
    assert exit_code == 0
    assert "host.game_cpu_percent" in window.metrics
    assert "encoder.frames_dropped_delta" in window.metrics
    assert stderr == ""


def test_ingest_pixelated_reports_invalid_bundle(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code, stdout, stderr = invoke(
        [
            "ingest-pixelated",
            str(tmp_path / "missing-bundle"),
            "--phase",
            "relief",
            "--comparison-case-id",
            "controlled-case-001",
            "--context",
            str(PIXELATED / "context.json"),
        ],
        capsys,
    )

    assert exit_code == 1
    assert stdout == ""
    assert "bundle path does not exist" in stderr


def test_match_emits_a_schema_valid_result(
    capsys: pytest.CaptureFixture[str],
) -> None:
    observation = QUERY_CASES / "similar_network" / "observation.json"
    exit_code, stdout, stderr = invoke(
        ["match", str(observation), "--fingerprints", str(REFERENCES)], capsys
    )

    result = MatchResult.model_validate_json(stdout)
    schema = json.loads((SCHEMAS / "match-result-v1.schema.json").read_text(encoding="utf-8"))
    payload = json.loads(stdout)
    assert exit_code == 0
    assert result.decision is MatchDecision.MATCHED
    assert result.accepted_label == "network_pressure"
    assert set(schema["required"]).issubset(payload)
    assert set(payload).issubset(schema["properties"])
    assert stderr == ""


def test_match_unknown_is_successful_output(capsys: pytest.CaptureFixture[str]) -> None:
    observation = QUERY_CASES / "ambiguous" / "observation.json"
    exit_code, stdout, stderr = invoke(
        ["match", str(observation), "--fingerprints", str(REFERENCES)], capsys
    )

    result = MatchResult.model_validate_json(stdout)
    assert exit_code == 0
    assert result.decision is MatchDecision.UNKNOWN
    assert stderr == ""


def test_match_rejects_a_dirty_repository_by_default(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = tmp_path / "fingerprints"
    good = repository / "good"
    bad = repository / "bad"
    good.mkdir(parents=True)
    bad.mkdir(parents=True)
    shutil.copyfile(REFERENCES / "network_pressure" / "fingerprint.json", good / "fingerprint.json")
    (bad / "fingerprint.json").write_text("not JSON\n", encoding="utf-8")
    observation = QUERY_CASES / "similar_network" / "observation.json"

    exit_code, stdout, stderr = invoke(
        ["match", str(observation), "--fingerprints", str(repository)], capsys
    )

    assert exit_code == 1
    assert stdout == ""
    assert "repository contains rejected files" in stderr


def test_match_can_explicitly_ignore_rejected_fingerprints(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = tmp_path / "fingerprints"
    good = repository / "good"
    bad = repository / "bad"
    good.mkdir(parents=True)
    bad.mkdir(parents=True)
    shutil.copyfile(REFERENCES / "network_pressure" / "fingerprint.json", good / "fingerprint.json")
    (bad / "fingerprint.json").write_text("not JSON\n", encoding="utf-8")
    observation = QUERY_CASES / "similar_network" / "observation.json"

    exit_code, stdout, stderr = invoke(
        [
            "match",
            str(observation),
            "--fingerprints",
            str(repository),
            "--allow-rejected-fingerprints",
        ],
        capsys,
    )

    assert exit_code == 0
    assert MatchResult.model_validate_json(stdout).decision is MatchDecision.MATCHED
    assert "warning: ignored 1 rejected fingerprint file" in stderr


def test_match_reports_invalid_observation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "observation.json"
    path.write_text("{}\n", encoding="utf-8")

    exit_code, stdout, stderr = invoke(
        ["match", str(path), "--fingerprints", str(REFERENCES)], capsys
    )

    assert exit_code == 1
    assert stdout == ""
    assert "validation error" in stderr
