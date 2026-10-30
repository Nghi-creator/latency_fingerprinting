"""Custody is lossless and bounded; arbitrary producer claims cannot qualify a family."""

import hashlib
import json
import os
from pathlib import Path

import jsonschema
import pytest

from latency_fingerprinting.cli import main
from latency_fingerprinting.live_probes import (
    IntegratedGameRecord,
    import_integrated_game_cohort,
    inspect_integrated_game_record,
)
from latency_fingerprinting.live_probes.integrated_game import MAX_REPORT_BYTES, MODES
from latency_fingerprinting.schemas import render_schema

from .integrated_game_cases import META, cohort


def seal(rows=None):
    return import_integrated_game_cohort(
        json.dumps(cohort() if rows is None else rows).encode(), **META
    )


def test_lossless_utf8_custody_and_declarations_are_never_verification():
    rows = cohort()
    rows[0]["unmodeled"] = {"browser_clock": 1.25, "text": "Tiếng Việt", "host_clock": 99}
    raw = (json.dumps(rows, ensure_ascii=False, indent=2) + "\r\n").encode()
    record = import_integrated_game_cohort(raw, **META)
    assert record.raw_report.encode() == raw
    assert record.raw_report_hash == "sha256:" + hashlib.sha256(raw).hexdigest()
    assert IntegratedGameRecord.model_validate_json(record.model_dump_json()) == record
    report = inspect_integrated_game_record(record)
    assert report["cohort_completeness"] == "complete"
    assert report["missing_modes"] == []
    assert report["engineering_screen"] == "unavailable_independent_reconstruction_required"
    assert report["clock_alignment"] == "none"
    assert report["live_authority"] is False
    assert [r["outcome_declared"]["restoration"] for r in report["cases"]] == [
        "verified_by_port",
        "verified_by_port",
        "unknown",
        "unknown",
        "unknown",
    ]
    assert all(not r["restoration_independently_verified"] for r in report["cases"])
    jsonschema.validate(
        record.model_dump(mode="json"), json.loads(render_schema(IntegratedGameRecord))
    )


def test_partial_failed_checkpoint_and_nested_failure_payload_retained():
    rows = cohort()[:2]
    rows[1] = dict(
        mode=MODES[1],
        status="failed",
        live_authority=False,
        failure="cleanup unconfirmed",
        acquisition={"partial": [1, None]},
    )
    record = seal(rows)
    report = inspect_integrated_game_record(record)
    assert json.loads(record.raw_report) == rows
    assert report["missing_modes"] == list(MODES[2:])
    assert report["cohort_completeness"] == "partial"
    assert report["cases"][1]["acquisition_status_declared"] == "failed"
    assert report["cases"][1]["outcome_declared"] is None


@pytest.mark.parametrize(
    "change,state",
    [
        ("missing", "unavailable_missing_result"),
        ("null", "unavailable_no_result"),
        ("duplicate", "unavailable_ambiguous_result"),
        ("invalid", "unavailable_invalid_result"),
        ("missing_field", "unavailable_missing_result"),
    ],
)
def test_uncertainty_is_not_restoration(change, state):
    rows = cohort()
    events = rows[2]["events"]
    if change == "missing":
        events.clear()
    elif change == "null":
        events[0]["result"] = None
    elif change == "duplicate":
        events.append(events[0].copy())
    elif change == "invalid":
        events[0]["result"]["live_authority"] = True
    else:
        del events[0]["result"]
    row = inspect_integrated_game_record(seal(rows))["cases"][2]
    assert row["result_state"] == state
    assert row["outcome_declared"] is None
    assert row["restoration_independently_verified"] is False


@pytest.mark.parametrize(
    "raw",
    [
        b"[]",
        b"{}",
        b"[null]",
        b"\xff",
        b"\xef\xbb\xbf[]",
        b"[" * 129 + b"0" + b"]" * 129,
        b'[{"mode":"x","mode":"x"}]',
        b"[NaN]",
        b"[1e999]",
        b'[{"a":"\\ud800"}]',
        b" " * (MAX_REPORT_BYTES + 1),
    ],
)
def test_invalid_or_ambiguous_raw_input_rejected(raw):
    with pytest.raises(ValueError):
        import_integrated_game_cohort(raw, **META)


@pytest.mark.parametrize("mutation", ["order", "duplicate", "extra", "true", "zero", "status"])
def test_fixed_prefix_wrapper(mutation):
    rows = cohort()
    if mutation == "order":
        rows.reverse()
    elif mutation == "duplicate":
        rows[1] = rows[0]
    elif mutation == "extra":
        rows.append(rows[0])
    elif mutation in ("true", "zero"):
        rows[0]["live_authority"] = True if mutation == "true" else 0
    else:
        rows[0]["status"] = "met"
    with pytest.raises(ValueError):
        seal(rows)


@pytest.mark.parametrize(
    "field,value",
    [
        ("raw_report", "[]"),
        ("raw_report_hash", "sha256:" + "0" * 64),
        ("content_hash", "sha256:" + "0" * 64),
        ("producer_revision", "b" * 40),
        ("capability", "available"),
        ("live_authority", 0),
        ("unknown", "extra"),
    ],
)
def test_sealed_record_rejects_tampering(field, value):
    record = seal().model_dump(mode="json")
    record[field] = value
    with pytest.raises(ValueError):
        IntegratedGameRecord.model_validate(record)


def test_same_object_revalidated_and_source_whitespace_changes_identity():
    record = seal()
    other = import_integrated_game_cohort(record.raw_report.encode() + b"\n", **META)
    assert other.raw_report_hash != record.raw_report_hash
    assert other.content_hash != record.content_hash
    unsafe = record.model_copy(update={"raw_report": "[]"})
    with pytest.raises(ValueError):
        inspect_integrated_game_record(unsafe)


def test_cli_import_validate_inspect_and_protected_aliases(tmp_path, capsys):
    source, output = tmp_path / "source.json", tmp_path / "record.json"
    source.write_bytes(json.dumps(cohort()).encode() + b"\n")
    args = [
        "import-integrated-game-cohort",
        "--report",
        str(source),
        "--output",
        str(output),
        "--acquisition-id",
        META["acquisition_id"],
        "--producer-revision",
        META["producer_revision"],
    ]
    assert main(args) == 0
    assert capsys.readouterr().out == ""
    record = IntegratedGameRecord.model_validate_json(output.read_bytes())
    assert record.raw_report.encode() == source.read_bytes()
    assert main(["validate", str(output)]) == 0
    assert json.loads(capsys.readouterr().out) == record.model_dump(mode="json")
    assert main(["inspect-integrated-game-record", str(output)]) == 0
    assert json.loads(capsys.readouterr().out) == inspect_integrated_game_record(record)
    for alias in (source, tmp_path / "hardlink", tmp_path / "symlink"):
        if alias.name == "hardlink":
            os.link(source, alias)
        elif alias.name == "symlink":
            alias.symlink_to(source)
        args[args.index("--output") + 1] = str(alias)
        retained = source.read_bytes()
        assert main(args) == 1
        assert source.read_bytes() == retained
        assert "invalid_input_or_output" in capsys.readouterr().err
    args[args.index("--report") + 1] = str(tmp_path / "symlink")
    args[args.index("--output") + 1] = str(output)
    retained = output.read_bytes()
    assert main(args) == 1
    assert output.read_bytes() == retained


def test_all_previous_39_schema_bytes_preserved():
    previous = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in Path("schemas").glob("*.schema.json")
        if p.name != "integrated-game-cohort-record-v1.schema.json"
    }
    assert len(previous) == 39
    # Independently pinned before this root was added.
    assert (
        hashlib.sha256(json.dumps(previous, sort_keys=True).encode()).hexdigest()
        == "ba38ee2630d7cb437b175d3be5c43fe761eda7d35c3a8028d8b82b37b796aece"
    )
