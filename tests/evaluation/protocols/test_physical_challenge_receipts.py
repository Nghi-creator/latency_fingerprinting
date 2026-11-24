"""Synthetic producer transcripts: lifecycle consistency never grants N2 admission."""

import hashlib
import json
from pathlib import Path

import pytest

from latency_fingerprinting.evaluation.protocols.physical_challenge_receipts import (
    inspect_challenge_transcript,
)

ROOT = Path("fixtures/physical-challenge-v1/transcripts")


@pytest.mark.parametrize("path", sorted(ROOT.glob("*.json")), ids=lambda p: p.stem)
def test_producer_roundtrip_keeps_lifecycle_and_media_acceptance_separate(path):
    result = inspect_challenge_transcript(path.read_bytes())
    assert result["commands_verified"] == 10
    assert result["phases_verified"] == 3
    assert result["source_media_verified"] is False
    assert result["n2_pair_admitted"] is False
    assert result["empirical_acceptance"] is False
    if "_to_" in path.stem:
        assert result["admission_reason"] == "changing_pair_not_stable"


@pytest.mark.parametrize(
    "change",
    [
        "suffix",
        "request_hash",
        "sequence",
        "generation",
        "expired",
        "cleanup",
        "dose",
        "clock",
        "controller_time",
        "extra",
    ],
)
def test_resealed_structural_or_timing_lies_are_rejected(change):
    value = json.loads((ROOT / "mixed_delay_pressure.json").read_bytes())
    row = value["records"][-1]
    ack = json.loads(row["ack_json"])
    if change == "suffix":
        value["records"].pop()
    elif change == "request_hash":
        ack["command_sha256"] = "sha256:" + "0" * 64
    elif change == "sequence":
        ack["command_sequence"] = True
    elif change == "generation":
        ack["generation"]["peer"] = "replacement"
    elif change == "expired":
        ack["snapshot"]["expired"] = True
    elif change == "cleanup":
        ack["events"][-1]["post_pressure"]["active_workers"] = 2
    elif change == "dose":
        ack["events"][0]["after"]["delay_us"] = 35000
    elif change == "clock":
        ack["snapshot"]["clock_id"] = "controller-monotonic-" + "a" * 64
    elif change == "controller_time":
        row["ack_at_ns"] = row["request_at_ns"] - 1
    else:
        value["approved"] = True
    row["ack_json"] = json.dumps(ack, sort_keys=True, separators=(",", ":"))
    with pytest.raises(ValueError, match="invalid_challenge_transcript"):
        inspect_challenge_transcript(json.dumps(value).encode())


def test_independent_controller_origin_never_changes_worker_durations():
    value = json.loads((ROOT / "delay_to_pressure.json").read_bytes())
    for row in value["records"]:
        row["request_at_ns"] += 10**12
        row["ack_at_ns"] += 10**12
    assert inspect_challenge_transcript(json.dumps(value).encode())["phases_verified"] == 3


def test_duplicate_keys_and_non_bytes_are_rejected():
    for raw in ("not bytes", b'{"recipe":"a","recipe":"b"}'):
        with pytest.raises(ValueError, match="invalid_challenge_transcript"):
            inspect_challenge_transcript(raw)


def test_prior_event_prefix_cannot_change_numeric_types_under_python_equality():
    value = json.loads((ROOT / "mixed_delay_pressure.json").read_bytes())
    ack = json.loads(value["records"][1]["ack_json"])
    ack["events"][0]["before"]["delay_us"] = False
    value["records"][1]["ack_json"] = json.dumps(ack, sort_keys=True, separators=(",", ":"))
    with pytest.raises(ValueError, match="invalid_challenge_transcript"):
        inspect_challenge_transcript(json.dumps(value).encode())


def test_synthetic_fixture_inventory_and_private_path_boundary():
    base = ROOT.parent
    inventory = json.loads((base / "inventory.json").read_bytes())
    assert inventory["synthetic"] is True
    assert inventory["empirical_acceptance"] is False
    assert len(inventory["files"]) == 6
    for name, digest in inventory["files"].items():
        raw = (base / name).read_bytes()
        assert "sha256:" + hashlib.sha256(raw).hexdigest() == digest
        assert b"/Users/" not in raw
