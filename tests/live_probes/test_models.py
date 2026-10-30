"""Independent N10 sealing, chronology and conservative counter reconstruction."""

import copy
import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

from latency_fingerprinting.cli import main
from latency_fingerprinting.live_probes import (
    LiveProbeEvidence,
    create_live_probe_evidence,
    inspect_live_probe_evidence,
)
from latency_fingerprinting.schemas import render_schema

from .cases import canonical, payload, seal


def test_literal_seal_factory_roundtrip_and_immutable_inspection():
    raw = payload()
    root = LiveProbeEvidence.model_validate(raw)
    fields = {
        key: value
        for key, value in raw.items()
        if key
        not in {
            "schema_version",
            "method_release",
            "assurance",
            "evidence_id",
            "content_hash",
        }
    }
    assert create_live_probe_evidence(**fields) == root
    assert root.model_dump(mode="json") == raw
    assert LiveProbeEvidence.model_validate_json(canonical(raw)) == root
    result = inspect_live_probe_evidence(root)
    assert result.application_attempted
    assert result.budget_consumption == "reservation_required_not_verified"
    assert result.restoration == "setting_and_local_progress_only"
    assert result.receiver_continuity == "unverified"
    assert result.capability == "unavailable_unqualified"
    assert result.live_authority is False
    assert result.missing_phases == result.late_receipt_phases == ()
    assert all(row.reason_codes == () and row.duration_ns == 70 for row in result.windows)
    assert all(
        row.encoded_bytes_delta == 60000 and row.decoded_frames_delta == 10
        for row in result.windows
    )
    raw["windows"][0]["samples"].clear()
    assert len(root.windows[0].samples) == 2
    with pytest.raises(ValueError):
        root.windows[0].samples[0].bitrate = 1
    with pytest.raises(ValueError):
        result.restoration = "verified"


@pytest.mark.parametrize(
    "key,value",
    [
        ("live_authority", True),
        ("live_authority", 0),
        ("capability", "qualified"),
        ("receiver_continuity", "verified"),
        ("quality", "measured"),
        ("reason_codes", []),
        ("reason_codes", ["capability_unqualified"] * 2),
        ("method_release", "n10-live-evidence-v2"),
        ("windows", [None] * 4),
        ("receipts", [None] * 4),
    ],
)
def test_no_promotion_and_closed_root(key, value):
    raw = payload()
    raw[key] = value
    with pytest.raises(ValueError):
        LiveProbeEvidence.model_validate(seal(raw))


@pytest.mark.parametrize(
    "field,value",
    [
        ("read_start_ns", True),
        ("read_end_ns", 1.0),
        ("encoded_bytes", -1),
        ("encoded_frames", 2**53),
        ("decoded_frames", "1"),
        ("bitrate", 0),
        ("bitrate", 2**31),
        ("counter_generation", "../private"),
    ],
)
def test_strict_counter_read_types(field, value):
    raw = payload()
    raw["windows"][0]["samples"][0][field] = value
    with pytest.raises(ValueError):
        LiveProbeEvidence.model_validate(seal(raw))


@pytest.mark.parametrize(
    "change",
    [
        "window_order",
        "duplicate_phase",
        "window_overlap",
        "setter_crossing",
        "within_settling",
        "restoration_without_attempt",
        "baseline_after_application",
        "wrong_requested_value",
        "returned_without_end",
        "setter_reversed",
        "read_reversed",
        "sample_outside",
        "read_overlap",
        "deadline_order",
        "wrong_provenance",
    ],
)
def test_invalid_chronology_and_scope_cannot_be_resealed(change):
    raw = payload()
    if change == "window_order":
        raw["windows"].reverse()
    elif change == "duplicate_phase":
        raw["windows"][1]["phase"] = "baseline"
    elif change == "window_overlap":
        raw["windows"][0]["end_ns"] = 260
    elif change == "setter_crossing":
        raw["windows"][1]["start_ns"] = 205
    elif change == "within_settling":
        raw["windows"][1]["start_ns"] = 215
    elif change == "restoration_without_attempt":
        raw["receipts"].pop(0)
    elif change == "baseline_after_application":
        raw["receipts"][0].update(call_start_ns=150, call_end_ns=160)
        raw["windows"][0].update(start_ns=170, end_ns=180, samples=[])
    elif change == "wrong_requested_value":
        raw["receipts"][0]["requested_value"] = 1
    elif change == "returned_without_end":
        raw["receipts"][0]["call_end_ns"] = None
    elif change == "setter_reversed":
        raw["receipts"][0]["call_end_ns"] = 199
    elif change == "read_reversed":
        raw["windows"][0]["samples"][0]["read_end_ns"] = 9
    elif change == "sample_outside":
        raw["windows"][0]["samples"][1]["read_end_ns"] = 100
    elif change == "read_overlap":
        raw["windows"][0]["samples"][1]["read_start_ns"] = 11
    elif change == "deadline_order":
        raw["intent"]["application_deadline_ns"] = 650
    elif change == "wrong_provenance":
        raw["scope"]["peer_generation"] = "peer-1"
    with pytest.raises(ValueError):
        LiveProbeEvidence.model_validate(seal(raw))


@pytest.mark.parametrize(
    "change,reason",
    [
        ("reset", "counter_reset"),
        ("generation", "counter_generation_changed"),
        ("missing_generation", "missing_counter_generation"),
        ("encode_stall", "no_encoded_progress"),
        ("missing", "missing_counter"),
        ("setting", "setting_mismatch"),
        ("missing_setting", "missing_setting"),
        ("unrelated", "unrelated_settings_changed"),
        ("missing_settings", "missing_unrelated_settings"),
        ("stall", "no_decoded_progress"),
        ("empty", "insufficient_samples"),
    ],
)
def test_failed_measurements_remain_evidence_with_explicit_diagnostics(change, reason):
    raw = payload()
    row = raw["windows"][2]["samples"][-1]
    if change == "reset":
        row["encoded_bytes"] = 0
    elif change == "generation":
        row["counter_generation"] = "new-counters"
    elif change == "missing_generation":
        row["counter_generation"] = None
    elif change == "encode_stall":
        row["encoded_frames"] = 20
    elif change == "missing":
        row["encoded_bytes"] = None
    elif change == "setting":
        row["bitrate"] = 500000
    elif change == "missing_setting":
        row["bitrate"] = None
    elif change == "unrelated":
        row["settings"]["cpu_used"] = 6
    elif change == "missing_settings":
        row["settings"] = None
    elif change == "stall":
        row["decoded_frames"] = 20
    elif change == "empty":
        raw["windows"][2]["samples"] = []
    result = inspect_live_probe_evidence(seal(raw))
    assert reason in result.windows[-1].reason_codes
    assert result.restoration == "unknown"
    assert result.live_authority is False
    if change in {"reset", "generation", "missing_generation", "missing", "empty"}:
        assert result.windows[-1].encoded_bytes_delta is None


def test_partial_setter_unknown_return_and_late_restoration_are_retained():
    raw = payload()
    raw["receipts"][0].update(outcome="raised", call_end_ns=None)
    raw["intent"]["restoration_deadline_ns"] = 350
    result = inspect_live_probe_evidence(seal(raw))
    assert result.application_attempted
    assert result.late_receipt_phases == ("restoration", "cleanup")
    assert result.unknown_completion_phases == ("application",)
    assert result.budget_consumption == "reservation_required_not_verified"
    assert result.restoration != "verified"


def test_unattempted_and_missing_phases_are_not_fabricated():
    raw = payload()
    raw["receipts"] = []
    raw["windows"] = raw["windows"][:1]
    result = inspect_live_probe_evidence(seal(raw))
    assert not result.application_attempted
    assert result.budget_consumption == "not_attempted"
    assert result.restoration == "not_needed"
    assert result.missing_phases == ("during", "restoration")


def test_typed_unchecked_copy_hash_and_nested_corruption_are_revalidated():
    root = LiveProbeEvidence.model_validate(payload())
    for broken in (
        root.model_copy(update={"live_authority": True}),
        root.model_copy(update={"content_hash": "sha256:" + "0" * 64}),
        root.model_copy(
            update={"windows": (root.windows[0].model_copy(update={"samples": (None,)}),)}
        ),
    ):
        with pytest.raises(ValueError):
            inspect_live_probe_evidence(broken)
    raw = payload()
    raw["windows"][0]["samples"][0]["encoded_bytes"] = 1
    with pytest.raises(ValueError):
        LiveProbeEvidence.model_validate(raw)


def test_generic_cli_schema_and_duplicate_safe_json(tmp_path, capsys):
    raw = payload()
    schema = json.loads(render_schema(LiveProbeEvidence))
    jsonschema.validate(raw, schema)
    path = tmp_path / "evidence.json"
    path.write_bytes(canonical(raw))
    assert main(["validate", str(path)]) == 0
    assert capsys.readouterr().out == canonical(raw).decode()
    for invalid in (
        b'{"schema_version":"live-probe-evidence-v1","schema_version":"x"}',
        b'{"x":NaN}',
        b"\xff",
        b"[" * 33 + b"0" + b"]" * 33,
        b" " * (10 * 1024 * 1024 + 1),
    ):
        with pytest.raises(ValueError):
            LiveProbeEvidence.model_validate_json(invalid)
    assert Path("schemas/live-probe-evidence-v1.schema.json").read_text() == render_schema(
        LiveProbeEvidence
    )


def test_factory_rejects_reserved_fields_and_unsafe_nested_data_before_hashing():
    with pytest.raises(ValueError):
        create_live_probe_evidence(schema_version="custom")
    fields = payload()
    for key in ("schema_version", "method_release", "assurance", "evidence_id", "content_hash"):
        fields.pop(key)
    bad = copy.deepcopy(fields)
    bad["windows"][0]["samples"] = [None] * 65
    with pytest.raises(ValueError):
        create_live_probe_evidence(**bad)


def test_one_additive_schema_preserves_previous_36_schema_bytes():
    previous = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in Path("schemas").glob("*.schema.json")
        if path.name
        not in {
            "live-probe-evidence-v1.schema.json",
            "cadence-probe-evidence-v1.schema.json",
            "game-browser-probe-evidence-v1.schema.json",
            "integrated-game-cohort-record-v1.schema.json",
        }
    }
    assert len(previous) == 36
    assert (
        hashlib.sha256(json.dumps(previous, sort_keys=True).encode()).hexdigest()
        == "4dbc0085a9e9e04aa520cd6213daaac7b7ed4137dfdb75ba1a4e228e48b10786"
    )
