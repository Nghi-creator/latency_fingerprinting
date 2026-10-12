"""Frozen assignment/source ledger and each retained trial are independently checked."""

import gzip
import hashlib
import json

import pytest

from latency_fingerprinting.cli import main
from latency_fingerprinting.scenarios.campaign import CampaignPlan, inspect_campaign
from tests.scenarios.test_bundle import archive, encoded, members


def plan(trials=None):
    return dict(
        schema_version="n5-campaign-plan-v1",
        campaign_id="campaign-1",
        core_version="a" * 40,
        producer_version="a" * 40,
        node_id="node-1",
        workload_id="workload-1",
        node_version="26.4.0",
        host_workers=1,
        seed=7,
        trials=trials
        or [
            dict(
                run_id="run-1",
                source_id="c" * 32,
                scenario="host_contention",
                assignment="reference",
                repeat_index=1,
            )
        ],
    )


def campaign(directory, available=True):
    directory.mkdir()
    declaration = plan()
    raw = encoded(declaration)
    (directory / "campaign-plan.json").write_bytes(raw)
    row = dict(
        run_id="run-1",
        source_id="c" * 32,
        status="unavailable",
        reason="runtime_unavailable",
        file_name=None,
        bytes=0,
        sha256=None,
        acquisition_started_ns=None,
        acquisition_ended_ns=None,
    )
    if available:
        # Hand-authored producer-capture declarations exercise validation, not real capture.
        files = members()
        m = json.loads(files["experiment-manifest.json"])
        m.update(provenance="producer_capture", assignment="reference")
        m["runtime"]["kind"] = "linux_x11"
        files["experiment-manifest.json"] = encoded(m)
        digest = hashlib.sha256(files["experiment-manifest.json"]).hexdigest()
        result = json.loads(files["experiment-result.json"])
        result["manifest_sha256"] = digest
        for ref in result["artifacts"]:
            root = json.loads(files[ref["file_name"]])
            if ref["role"] == "phase_evidence":
                root["manifest_sha256"] = digest
            else:
                root["provenance"] = "producer_capture"
            payload = encoded(root)
            files[ref["file_name"]] = payload
            ref.update(bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
        files["experiment-result.json"] = encoded(result)
        payload = gzip.compress(archive(files.items()), mtime=0)
        (directory / "run-1.tar.gz").write_bytes(payload)
        row.update(
            status="exported",
            reason=None,
            file_name="run-1.tar.gz",
            bytes=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
            acquisition_started_ns=1,
            acquisition_ended_ns=200_000_000_000,
        )
    index = dict(
        schema_version="n5-campaign-index-v1",
        campaign_id="campaign-1",
        plan_sha256=hashlib.sha256(raw).hexdigest(),
        state="finished" if available else "trial_failed",
        trials=[row],
    )
    (directory / "campaign-index.json").write_bytes(encoded(index))
    return directory


@pytest.mark.parametrize("available", [True, False])
def test_detached_campaign_and_cli_keep_acceptance_separate(tmp_path, capsys, available):
    path = campaign(tmp_path / "campaign", available)
    report = inspect_campaign(path)
    assert report["trials"][0]["state"] == ("verified" if available else "unavailable")
    assert report["phase_1_acceptance"] == "pending"
    assert report["repeated_effect_criteria_passed"] is False
    output = tmp_path / "report.json"
    assert main(["inspect-campaign", "--directory", str(path), "--output", str(output)]) == 0
    assert json.loads(output.read_bytes()) == report
    assert main(["validate", str(output)]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out) == report


@pytest.mark.parametrize(
    "drift", ["plan", "source", "length", "hash", "extra", "alias", "finished_missing"]
)
def test_campaign_drift_rejects_and_preserves_output(tmp_path, capsys, drift):
    path = campaign(tmp_path / "campaign")
    index = json.loads((path / "campaign-index.json").read_bytes())
    if drift == "plan":
        index["plan_sha256"] = "0" * 64
    elif drift == "source":
        index["trials"][0]["source_id"] = "d" * 32
    elif drift == "length":
        index["trials"][0]["bytes"] += 1
    elif drift == "hash":
        index["trials"][0]["sha256"] = "0" * 64
    elif drift == "extra":
        (path / "private-secret.txt").write_bytes(b"private")
    elif drift == "alias":
        source = path / "run-1.tar.gz"
        source.rename(tmp_path / "original.gz")
        source.symlink_to(tmp_path / "original.gz")
    else:
        index["trials"] = []
    (path / "campaign-index.json").write_bytes(encoded(index))
    out = tmp_path / "report.json"
    out.write_bytes(b"previous")
    assert main(["inspect-campaign", "--directory", str(path), "--output", str(out)]) == 1
    assert out.read_bytes() == b"previous"
    assert capsys.readouterr() == ("", "error: inspect-campaign: invalid_input_or_output\n")


@pytest.mark.parametrize("drift", ["source", "repeat", "bool"])
def test_predeclared_source_and_repeat_identity_is_strict(drift):
    value = plan()
    if drift == "bool":
        value["host_workers"] = True
    else:
        other = dict(value["trials"][0], run_id="run-2", source_id="d" * 32)
        if drift == "source":
            other.update(repeat_index=2, source_id="c" * 32)
        value["trials"].append(other)
    with pytest.raises(ValueError):
        CampaignPlan.model_validate(value)
