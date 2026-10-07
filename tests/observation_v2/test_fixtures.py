"""N2 snapshot reproduction, independent arithmetic and public root validation."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from latency_fingerprinting.cli import main
from latency_fingerprinting.json_io import load_json_file
from latency_fingerprinting.models import ObservationRecordV2, ObservationWindowV2
from latency_fingerprinting.pipeline import canonical_json

from . import check_reproduction as reproduction
from .fixture_cases import DEFAULT_FIXTURE_DIRECTORY, PROJECT_ROOT, fixture_drift

NAMES = tuple(reproduction.EXPECTED_SHA256)


@pytest.mark.parametrize("name", NAMES)
def test_checked_in_roots_validate_and_cli_retains_exact_bytes(name, capsys):
    path = DEFAULT_FIXTURE_DIRECTORY / name
    payload = load_json_file(path)
    schema = load_json_file(PROJECT_ROOT / f"schemas/{payload['schemaVersion']}.schema.json")
    Draft202012Validator(schema).validate(payload)
    model_type = ObservationRecordV2 if name == "synthetic-pair.json" else ObservationWindowV2
    model = model_type.model_validate(payload)
    assert canonical_json(model).encode() == path.read_bytes()
    assert main(["validate", str(path)]) == 0
    output = capsys.readouterr()
    assert output.out.encode() == path.read_bytes() and output.err == ""


def test_adopted_counter_evidence_matches_hand_calculated_expectation():
    payload = load_json_file(DEFAULT_FIXTURE_DIRECTORY / "adopted-engine-v2.json")
    rate = payload["measurements"]["client.frames_decoded_rate_fps"]["summary"]
    total = payload["measurements"]["client.frames_decoded_window_total"]["summary"]
    model = ObservationWindowV2.model_validate(payload)
    assert model.measurements["client.frames_decoded_rate_fps"].summary.value == 60
    assert model.measurements["client.frames_decoded_window_total"].summary.value == 600
    assert rate["coverage"] == total["coverage"] == 1
    assert rate["observedDurationMs"] == total["observedDurationMs"] == 10000
    assert rate["counterIntervals"] == total["counterIntervals"]
    assert [(i["durationMs"], i["delta"], i["rate"]) for i in rate["counterIntervals"]] == [
        (5000, 300, 60),
        (5000, 300, 60),
    ]
    proxy = payload["measurements"]["encoder.pipeline_delay_proxy_ms"]
    assert proxy["support"]["state"] == "unsupported"
    assert model.measurements["encoder.pipeline_delay_proxy_ms"].summary.value is None
    assert all(
        t["value"] is None and t["reasonCode"] == "not_instrumented"
        for t in payload["stageTimings"]
    )


def test_absent_source_and_synthetic_pair_do_not_claim_experimental_evidence():
    browser = load_json_file(DEFAULT_FIXTURE_DIRECTORY / "adopted-browser-v1.json")
    assert browser["sources"]["engine_runtime"]["state"] == "unavailable"
    summary = browser["measurements"]["encoder.frames_out_window_total"]["summary"]
    model = ObservationWindowV2.model_validate(browser)
    assert model.measurements["encoder.frames_out_window_total"].summary.value is None
    assert summary["usableSampleCount"] == 0
    assert [t["reasonCode"] for t in browser["stageTimings"][:2]] == ["source_unavailable"] * 2
    pair = load_json_file(DEFAULT_FIXTURE_DIRECTORY / "synthetic-pair.json")
    assert pair["intervention"]["applicationMethod"] == "simulated_pair"
    assert pair["intervention"]["executionStatus"] == "not_executed"
    for field in ("degradedWindow", "reliefWindow"):
        assert pair[field]["provenance"] == "synthetic"
        assert pair[field]["clock"]["provenance"] == "synthetic_elapsed"
        assert pair[field]["stageTimings"] == []
    assert "response" not in pair and "normalizedResponse" not in pair


@pytest.mark.parametrize(
    "field,value",
    [("registryVersion", "latency-metrics-v9.0.0"), ("contentHash", "sha256:" + "0" * 64)],
)
def test_fixture_cannot_be_rebound_to_incompatible_registry(field, value):
    payload = load_json_file(DEFAULT_FIXTURE_DIRECTORY / "adopted-engine-v2.json")
    payload["registry"][field] = value
    with pytest.raises(ValidationError):
        ObservationWindowV2.model_validate(payload)


def test_reproduction_and_drift_check_never_write(monkeypatch, capsys):
    before = {p.name: p.read_bytes() for p in DEFAULT_FIXTURE_DIRECTORY.glob("*.json")}

    def no_write(*args, **kwargs):
        pytest.fail("N2 CI reproduction must not write artifacts")

    monkeypatch.setattr(Path, "write_text", no_write)
    monkeypatch.setattr(Path, "write_bytes", no_write)
    monkeypatch.setattr(Path, "mkdir", no_write)
    assert fixture_drift() == {}
    assert reproduction.main() == 0
    output = capsys.readouterr()
    assert output.err == ""
    assert json.loads(output.out)["fixtureSha256"] == reproduction.EXPECTED_SHA256
    assert {p.name: p.read_bytes() for p in DEFAULT_FIXTURE_DIRECTORY.glob("*.json")} == before


@pytest.mark.parametrize("fault", ["missing", "changed", "unexpected", "pin"])
def test_reproduction_drift_fails_with_no_partial_json(tmp_path, monkeypatch, capsys, fault):
    for path in DEFAULT_FIXTURE_DIRECTORY.glob("*.json"):
        (tmp_path / path.name).write_bytes(path.read_bytes())
    monkeypatch.setattr(reproduction, "DEFAULT_FIXTURE_DIRECTORY", tmp_path)
    path = tmp_path / "adopted-engine-v2.json"
    if fault == "missing":
        path.unlink()
    elif fault == "changed":
        path.write_bytes(path.read_bytes() + b"\n")
    elif fault == "unexpected":
        (tmp_path / "unexpected.json").write_text("{}")
    else:
        monkeypatch.setattr(reproduction, "EXPECTED_SHA256", {})
    if fault != "pin":
        assert fault in fixture_drift(tmp_path).values()
    for _ in range(2):
        assert reproduction.main() == 1
        output = capsys.readouterr()
        assert output.out == "" and "error:" in output.err and "Traceback" not in output.err
