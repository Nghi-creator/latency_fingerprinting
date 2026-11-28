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


def with_start_receipts(recipe="mixed_delay_pressure"):
    """Invented receipts added in memory; frozen historical vectors stay untouched."""
    value = json.loads((ROOT / f"{recipe}.json").read_bytes())
    workers = [
        dict(pid=i, boot="00000000-0000-0000-0000-000000000001", start=i + 10) for i in (101, 102)
    ]
    ids = [hashlib.sha256(json.dumps(w, sort_keys=True).encode()).hexdigest() for w in workers]
    intent = json.dumps(
        dict(version="n11-private-pressure-v1", state="active", workers=workers), sort_keys=True
    )
    for row in value["records"]:
        ack = json.loads(row["ack_json"].replace("a" * 64, ids[0]).replace("b" * 64, ids[1]))
        # Channel is not a pressure identity.
        ack["channel_id"] = value["channel_id"]
        ack["snapshot"]["channel_id"] = value["channel_id"]
        for e in ack["events"]:
            if e["kind"] != "condition_applied":
                continue
            e["pressure_start"] = None
            if (
                e["before"]["pressure"]["active_workers"] == 0
                and e["after"]["pressure"]["active_workers"] == 2
            ):
                e["pressure_start"] = dict(
                    method="n11-physical-pressure-start-v1",
                    read_start_ns=e["before"]["read_end_ns"],
                    read_end_ns=e["after"]["read_start_ns"],
                    clock="worker_monotonic_ns",
                    live_authority=False,
                    intent_json=intent,
                    start_result=dict(
                        workers=2,
                        maximum_active_ns=20000000000,
                        child_failsafe_ns=40000000000,
                        allocation_cores=2,
                        identities=ids,
                        intent_sha256=hashlib.sha256(intent.encode()).hexdigest(),
                    ),
                )
        row["ack_json"] = json.dumps(ack, sort_keys=True, separators=(",", ":"))
    return value


@pytest.mark.parametrize("recipe", [p.stem for p in sorted(ROOT.glob("*.json"))])
def test_explicit_start_evidence_for_every_recipe(recipe):
    result = inspect_challenge_transcript(
        json.dumps(with_start_receipts(recipe)).encode(), require_pressure_start=True
    )
    assert result["pressure_start_receipts_verified"] is True
    assert result["pressure_starts_verified"] == (
        0 if recipe in ("control_no_injected_fault", "control_owned_identity_delay") else 1
    )
    assert result["resource_dose_verified"] is False


def test_historical_transcripts_remain_readable_but_do_not_supply_start_evidence():
    raw = (ROOT / "mixed_delay_pressure.json").read_bytes()
    assert inspect_challenge_transcript(raw)["pressure_start_receipts_verified"] is False
    with pytest.raises(ValueError):
        inspect_challenge_transcript(raw, require_pressure_start=True)


@pytest.mark.parametrize(
    "change",
    ["missing", "digest", "quota", "bool", "ids", "clock", "bracket", "registry", "pid_reuse"],
)
def test_resealed_start_receipt_lies_fail_even_under_legacy_entrypoint(change):
    value = with_start_receipts()
    # Change every cumulative copy so rejection is not merely an event-prefix mismatch.
    for row in value["records"]:
        ack = json.loads(row["ack_json"])
        e = ack["events"][0]
        r = e["pressure_start"]
        if change == "missing":
            e["pressure_start"] = None
        elif change == "digest":
            r["start_result"]["intent_sha256"] = "0" * 64
        elif change in ("quota", "bool"):
            r["start_result"]["allocation_cores"] = True if change == "bool" else 3
        elif change == "ids":
            r["start_result"]["identities"].reverse()
        elif change == "clock":
            r["clock"] = "controller_monotonic_ns"
        elif change == "bracket":
            r["read_end_ns"] = e["after"]["read_start_ns"] + 1
        elif change in ("registry", "pid_reuse"):
            intent = json.loads(r["intent_json"])
            if change == "registry":
                intent["state"] = "parked"
            else:
                intent["workers"][1]["pid"] = intent["workers"][0]["pid"]
            r["intent_json"] = json.dumps(intent, sort_keys=True)
            r["start_result"]["intent_sha256"] = hashlib.sha256(
                r["intent_json"].encode()
            ).hexdigest()
        row["ack_json"] = json.dumps(ack, sort_keys=True, separators=(",", ":"))
    with pytest.raises(ValueError, match="invalid_challenge_transcript"):
        inspect_challenge_transcript(json.dumps(value).encode())
