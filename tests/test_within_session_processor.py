"""Synthetic on-disk processor checks; no native acquisition or measured labels."""

import importlib.util
import json
from pathlib import Path

import pytest

from latency_fingerprinting.evaluation import within_session_protocol as protocol
from tests.evaluation.test_fixture_conditions import slot
from tests.evaluation.test_within_session import draft


def processor():
    path = Path(__file__).resolve().parents[1] / "experiments/within_session_study.py"
    spec = importlib.util.spec_from_file_location("within_session_processor", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def allocation(tmp_path):
    p = draft()
    p["review"].update(
        state="confirmed", reviewer_id="synthetic-test", evidence_sha256="sha256:" + "c" * 64
    )
    p["content_hash"] = protocol._content(p)
    write(tmp_path / "protocol.json", p)
    sessions = []
    for block in p["blocks"]:
        slots = []
        for index, (condition, identifier) in enumerate(block["acquisition_ids"].items()):
            # Query paths intentionally do not exist: fitting must never open them.
            directory = tmp_path / identifier
            if block["role"] == "training":
                directory.mkdir()
                record = slot(
                    identifier, condition, relief=[(0, 60, 120), (0, 30, 60), (0, 0, 0)][index]
                )["response"]
                write(
                    directory / "plan.json",
                    dict(
                        acquisition_id=identifier,
                        condition=dict(name=condition),
                        source_manifest_hash=p["source_manifest_hash"],
                    ),
                )
                write(
                    directory / "control-receipt.json",
                    dict(
                        condition=condition,
                        acquisition_id=identifier,
                        condition_integrity="verified_declared_internal_evidence",
                    ),
                )
                write(directory / "acquisition.json", dict(synthetic=True, identifier=identifier))
                write(directory / "response.json", record.model_dump(mode="json", by_alias=True))
            slots.append(dict(condition=condition, output=str(directory)))
        sessions.append({**block, "slots": slots})
    a = dict(protocol_id=p["protocol_id"], sessions=sessions)
    write(tmp_path / "allocation.json", a)
    return tmp_path / "allocation.json", sessions


def test_processor_fits_only_training_paths_without_opening_query_files(tmp_path):
    path, _ = allocation(tmp_path)
    result = processor().fit_allocation(path)
    assert len(result["training"]) == 6
    assert result["calibration"]["state"] == "experimental_calibration_available"
    assert result["calibration"]["session_components"] == 1
    assert result["calibration"]["independent_support_groups"] == 0
    assert result["calibration"]["input_provenance_kinds"] == ["synthetic"]


def test_processor_rejects_misbound_condition_truth_before_fitting(tmp_path):
    path, sessions = allocation(tmp_path)
    directory = Path(sessions[0]["slots"][0]["output"])
    receipt = json.loads((directory / "control-receipt.json").read_text())
    receipt["condition"] = "owned_cpu_pressure"
    write(directory / "control-receipt.json", receipt)
    with pytest.raises(ValueError, match="invalid training witness"):
        processor().fit_allocation(path)
