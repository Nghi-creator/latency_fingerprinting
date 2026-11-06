"""Synthetic on-disk combined study I/O; no native sources or independent validation."""

import importlib.util
import json
from pathlib import Path

import pytest

from tests.evaluation.test_combined_interval_candidate import source
from tests.evaluation.test_combined_study_protocol import draft, reseal


def processor():
    file = Path(__file__).resolve().parents[1] / "experiments/combined_resource_study.py"
    spec = importlib.util.spec_from_file_location("combined_study_processor", file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def allocation(tmp_path):
    module = processor()
    p = draft()
    p["image_sha256"] = "sha256:" + "a" * 64
    p["tool_hashes"]["processor"] = module.sha(Path(module.__file__))
    p["review"].update(
        state="confirmed", reviewer_id="synthetic", evidence_sha256="sha256:" + "d" * 64
    )
    reseal(p)
    write(tmp_path / "protocol.json", p)
    sessions = []
    for block in p["blocks"]:
        slots = []
        for condition in block["condition_order"]:
            identifier = block["acquisition_ids"][condition]
            directory = tmp_path / identifier
            plan = dict(
                acquisition_id=identifier,
                schema_version="n11-contained-resource-condition-plan-v1",
                condition=dict(name=condition),
                source_manifest_hash=p["source_manifest_hash"],
                image=p["image_sha256"],
            )
            if block["role"] == "training":
                directory.mkdir()
                raw = source(identifier, list(block["acquisition_ids"]).index(condition))
                (directory / "acquisition.json").write_text(raw["acquisition_json"])
                write(directory / "resource-observation.json", raw["resource_artifact"])
                write(directory / "plan.json", plan)
                write(
                    directory / "control-receipt.json",
                    dict(
                        condition=condition,
                        condition_integrity="verified_declared_internal_evidence",
                        resource_integrity="verified_declared_internal_evidence",
                        synthetic_id=identifier,
                    ),
                )
                write(
                    directory / "verification-command.stdout",
                    dict(
                        acquisition_id=identifier,
                        sdk_cli_equal_phases=3,
                        source_manifest=p["source_manifest_hash"],
                        native_sha256=module.sha(directory / "acquisition.json"),
                    ),
                )
            slots.append(
                dict(
                    condition=condition,
                    acquisition_id=identifier,
                    output=str(directory),
                    plan_sha256=module.sha(directory / "plan.json")
                    if block["role"] == "training"
                    else "sha256:" + "f" * 64,
                )
            )
        sessions.append({**block, "slots": slots})
    value = dict(
        protocol_id=p["protocol_id"],
        protocol_file_sha256=module.sha(tmp_path / "protocol.json"),
        sessions=sessions,
    )
    write(tmp_path / "allocation.json", value)
    return module, tmp_path / "allocation.json", value, p


def test_fitting_never_opens_nonexistent_query_paths(tmp_path):
    module, path, value, _ = allocation(tmp_path)
    result = module.fit_allocation(path)
    assert result["calibration"]["state"] == "candidate_calibration_available"
    assert len(result["training"]) == 6 and result["calibration"]["independent_support_groups"] == 0
    assert all(
        not Path(slot["output"]).exists()
        for block in value["sessions"][6:]
        for slot in block["slots"]
    )


@pytest.mark.parametrize(
    "kind",
    [
        "condition",
        "source_hash",
        "raw_hash",
        "failure",
        "plan",
        "slots",
        "processor",
        "pending",
        "source_image",
    ],
)
def test_training_truth_source_plan_or_review_mismatch_rejected(kind, tmp_path):
    module, path, value, p = allocation(tmp_path)
    slot = value["sessions"][0]["slots"][0]
    directory = Path(slot["output"])
    if kind == "failure":
        (directory / "failure.json").write_text("{}")
    elif kind in ("processor", "pending"):
        if kind == "processor":
            p["tool_hashes"]["processor"] = "sha256:" + "f" * 64
        else:
            p["review"].update(state="pending", reviewer_id=None, evidence_sha256=None)
        reseal(p)
        write(tmp_path / "protocol.json", p)
        value.update(
            protocol_id=p["protocol_id"],
            protocol_file_sha256=module.sha(tmp_path / "protocol.json"),
        )
        write(path, value)
    elif kind == "slots":
        value["sessions"][0]["slots"].reverse()
        write(path, value)
    elif kind == "plan":
        plan = json.loads((directory / "plan.json").read_text())
        plan["image"] = "sha256:" + "c" * 64
        write(directory / "plan.json", plan)
    elif kind == "source_image":
        # Even consistently re-hashed metadata cannot override measured image.
        p["image_sha256"] = "sha256:" + "e" * 64
        reseal(p)
        write(tmp_path / "protocol.json", p)
        value.update(
            protocol_id=p["protocol_id"],
            protocol_file_sha256=module.sha(tmp_path / "protocol.json"),
        )
        for block in value["sessions"][:6]:
            for s in block["slots"]:
                d = Path(s["output"])
                plan = json.loads((d / "plan.json").read_text())
                plan["image"] = p["image_sha256"]
                write(d / "plan.json", plan)
                s["plan_sha256"] = module.sha(d / "plan.json")
        write(path, value)
    else:
        file = directory / (
            "control-receipt.json" if kind == "condition" else "verification-command.stdout"
        )
        data = json.loads(file.read_text())
        data[
            {
                "condition": "condition",
                "source_hash": "source_manifest",
                "raw_hash": "native_sha256",
            }[kind]
        ] = "bad"
        write(file, data)
    with pytest.raises(ValueError):
        module.fit_allocation(path)


def test_query_score_reads_only_measurements_and_rejects_changed_calibration(tmp_path):
    module, path, _, _ = allocation(tmp_path)
    fitted = module.fit_allocation(path)
    query = tmp_path / "query"
    query.mkdir()
    raw = source("fresh-query")
    (query / "acquisition.json").write_text(raw["acquisition_json"])
    write(query / "resource-observation.json", raw["resource_artifact"])
    # Invalid truth-bearing files must not be read by this API.
    (query / "plan.json").write_text("invalid truth")
    (query / "control-receipt.json").write_text("invalid truth")
    result = module.score_case(fitted, query, block_id="new", session_id=fitted["session_id"])
    assert (
        result["state"] == "candidate_condition_prediction"
        and result["predicted_condition"] == "no_injected_fault"
    )
    fitted["calibration"]["thresholds"]["minimum_gap"] = {"numerator": 0, "denominator": 1}
    with pytest.raises(ValueError, match="changed calibration"):
        module.score_case(fitted, query, block_id="new", session_id=fitted["session_id"])
