"""Reviewed N3 snapshots: expectations, drift, public reproduction and hygiene."""

import json
import shutil
from pathlib import Path

import pytest

from latency_fingerprinting.analytical.matching import verify_match_repository_v2
from latency_fingerprinting.analytical.repository import load_fingerprint_repository_v2
from latency_fingerprinting.cli import ROOT_MODELS, main
from latency_fingerprinting.json_io import load_json_file, load_model_file
from latency_fingerprinting.models import MatchResultV2

from . import check_reproduction as module
from .fixture_cases import (
    DEFAULT_FIXTURE_DIRECTORY,
    fixture_drift,
    fixture_records,
    rendered_fixture_files,
)
from .fixture_expectations import MATCH_EXPECTATIONS, check_expectations


@pytest.fixture(scope="module")
def records():
    return fixture_records()


def test_independent_expectations_and_pin_reproduction_are_read_only(records, capsys):
    root = DEFAULT_FIXTURE_DIRECTORY
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    check_expectations(records)
    assert len(rendered_fixture_files()) == 19
    assert fixture_drift() == {}
    assert module.check_reproduction()["fixtureSha256"] == module.EXPECTED_SHA256
    assert module.main() == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["status"] == "current" and captured.err == ""
    assert before == {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("relative", sorted(module.EXPECTED_SHA256))
def test_each_stored_snapshot_is_canonical_public_validated_json(relative, records, capsys):
    path = DEFAULT_FIXTURE_DIRECTORY / relative
    from latency_fingerprinting.pipeline import canonical_json

    assert path.read_bytes() == canonical_json(records[Path(relative)]).encode("utf-8")
    payload = load_json_file(path)
    validated = ROOT_MODELS[payload["schemaVersion"]].model_validate(payload)
    assert validated == records[Path(relative)]
    assert main(["validate", str(path)]) == 0
    captured = capsys.readouterr()
    assert captured.out.encode() == path.read_bytes() and captured.err == ""


@pytest.mark.parametrize("name", sorted(MATCH_EXPECTATIONS))
def test_cli_match_reproduces_every_snapshot_and_verifies_full_references(name, tmp_path, capsys):
    mapping = {
        "matched": ("complete", "matched"),
        "invalid_response": ("confounded", "matched"),
        "no_fingerprints": ("complete", None),
        "no_compatible_fingerprints": ("complete", "unreviewed"),
        "insufficient_features": ("insufficient", "matched"),
        "weak_match": ("complete", "weak"),
        "ambiguous_margin": ("complete", "ambiguous"),
        "conflicting_evidence": ("complete", "conflicting"),
    }
    response_name, reference_name = mapping[name]
    root = DEFAULT_FIXTURE_DIRECTORY
    repository = root / "references" / reference_name if reference_name else tmp_path
    assert (
        main(
            [
                "match-v2",
                "--response",
                str(root / "responses" / f"{response_name}.json"),
                "--policy",
                str(root / "policy.json"),
                "--fingerprints",
                str(repository),
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    expected_path = root / "matches" / f"{name}.json"
    assert captured.out.encode() == expected_path.read_bytes() and captured.err == ""
    verify_match_repository_v2(
        load_model_file(expected_path, MatchResultV2), load_fingerprint_repository_v2(repository)
    )


def test_public_response_and_fingerprint_creation_reproduce_snapshots(records, tmp_path, capsys):
    root = DEFAULT_FIXTURE_DIRECTORY
    assert (
        main(
            [
                "build-response-v2",
                "--observation",
                str(root / "inputs/observation.json"),
                "--policy",
                str(root / "policy.json"),
            ]
        )
        == 0
    )
    assert capsys.readouterr().out.encode() == (root / "responses/complete.json").read_bytes()
    reference = records[Path("references/matched/fingerprint.json")]
    path = tmp_path / "response.json"
    from latency_fingerprinting.pipeline import canonical_json

    path.write_text(canonical_json(reference.response))
    assert (
        main(
            [
                "build-fingerprint-v2",
                "--response",
                str(path),
                "--policy",
                str(root / "policy.json"),
                "--bottleneck-label",
                "synthetic_reference",
            ]
        )
        == 0
    )
    assert (
        capsys.readouterr().out.encode()
        == (root / "references/matched/fingerprint.json").read_bytes()
    )


@pytest.mark.parametrize("kind", ["missing", "changed", "unexpected", "link"])
def test_drift_checker_reports_changes_without_repair(kind, tmp_path):
    root = tmp_path / "snapshots"
    shutil.copytree(DEFAULT_FIXTURE_DIRECTORY, root)
    relative = Path("responses/complete.json")
    path = root / relative
    if kind == "missing":
        path.unlink()
    elif kind == "changed":
        path.write_text(path.read_text() + " ")
    elif kind == "unexpected":
        relative = Path("matches/unexpected.json")
        (root / relative).write_text("{}")
    else:
        path.unlink()
        path.symlink_to(DEFAULT_FIXTURE_DIRECTORY / relative)
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert fixture_drift(root) == {
        relative: {
            "missing": "missing",
            "changed": "changed",
            "unexpected": "unexpected",
            "link": "unsafe_link",
        }[kind]
    }
    assert before == {p: p.read_bytes() for p in before}


@pytest.mark.parametrize("failure", ["missing", "pin", "expectation"])
def test_reproduction_failure_has_no_partial_json_or_traceback(
    failure, tmp_path, monkeypatch, capsys
):
    if failure == "missing":
        monkeypatch.setattr(module, "DEFAULT_FIXTURE_DIRECTORY", tmp_path)
    elif failure == "pin":
        monkeypatch.setattr(module, "EXPECTED_SHA256", {})
    else:

        def fail_expectations(records):
            raise ValueError("independent numerical expectation failed")

        monkeypatch.setattr(module, "check_expectations", fail_expectations)
    assert module.main() == 1
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err.startswith("error: ")
    assert "Traceback" not in captured.err


def test_all_snapshots_remain_explicitly_synthetic_and_sanitized(records):
    for record in records.values():
        payload = record.model_dump(mode="json", by_alias=True)
        text = json.dumps(payload)
        assert "controlled_real" not in text and "organic_real" not in text
        assert '"validated"' not in text and '"executionStatus": "executed"' not in text
        assert "/Users/" not in text and "http://" not in text and "https://" not in text
        if "queryResponse" in payload:
            assert payload["noticeCode"] == "software_similarity_not_causal_confidence"
    assert len(records) == 19


def test_reproduction_does_not_create_missing_directories(tmp_path):
    missing = tmp_path / "not_created"
    assert len(fixture_drift(missing)) == 19
    assert not missing.exists()


def test_two_configured_ci_jobs_run_n3_reproduction():
    workflow = (Path(__file__).parents[2] / ".github/workflows/ci.yml").read_text()
    assert workflow.count("run: python -m tests.analytical.check_reproduction") == 2
    assert 'python-version: "3.11"' in workflow and 'python-version: "3.13"' in workflow
