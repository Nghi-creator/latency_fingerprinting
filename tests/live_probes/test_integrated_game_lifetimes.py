"""Lifetimes/journals must agree beyond the old pass flags; missingness stays explicit."""

import json

import pytest

from latency_fingerprinting.cli import main
from latency_fingerprinting.live_probes import (
    import_integrated_game_cohort,
    reconstruct_integrated_game_lifetimes,
    reconstruct_integrated_game_record,
)

from .integrated_game_cases import META
from .integrated_lifetime_cases import cohort, hashed
from .integrated_reconstruction_cases import cohort as old_cohort


def record(runs):
    return import_integrated_game_cohort(json.dumps(runs).encode(), **META)


def test_hashed_observations_reconstruct_without_authentication_or_schema_promotion():
    source = record(cohort())
    original = source.model_dump_json()
    result = reconstruct_integrated_game_lifetimes(source)
    assert result["supplied_lifetime_screen"] == "met"
    assert [r["state"] for r in result["lifetime_cases"]] == ["met"] * 4
    assert result["independent_execution_verification"] == "unavailable"
    assert result["live_authority"] is False
    assert result["capability"] == "unavailable_unqualified"
    assert result["issuer_restart_scope"] == "logical_local_owner_not_camera_process_reboot"
    assert source.model_dump_json() == original
    assert reconstruct_integrated_game_record(source)["supplied_observation_screen"] == "met"


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "duplicate",
        "order",
        "receipt_stale",
        "sequence_reset",
        "child_clock_reset",
        "source_reset",
        "sibling_changed",
        "replacement_reused",
        "restarted_replacement_changed",
        "reboot",
        "capture",
        "issuer",
        "bool_exit",
        "wrong_exit",
        "reservation",
        "journal_hash",
        "directory",
        "journal_process",
        "journal_request",
        "journal_outcome",
        "journal_changed_on_restart",
        "dirty_bypass",
        "private_history_extra",
        "source_cpu_reset",
        "read_overlap",
        "bool_clock",
        "post_restart_too_short",
        "cooldown_precision",
    ],
)
def test_wrong_lifetime_or_journal_cannot_be_hidden_by_pass_flags(mutation):
    runs = cohort()
    run = runs[2]
    rows = [e for e in run["events"] if e["kind"] == "failure_lifetime"]
    a, b, c = rows
    if mutation == "missing":
        run["events"].remove(b)
    elif mutation == "duplicate":
        run["events"].append(b)
    elif mutation == "order":
        a["phase"], b["phase"] = b["phase"], a["phase"]
    elif mutation == "receipt_stale":
        b["peers"]["second"]["native_received_ns"] -= 2000000000
    elif mutation == "sequence_reset":
        c["peers"]["second"]["native_sequence"] = 1
    elif mutation == "child_clock_reset":
        c["peers"]["replacement"]["native"]["read_start_ns"] = 0
    elif mutation == "source_reset":
        c["peers"]["second"]["native"]["encoded_buffers"] = 0
    elif mutation == "sibling_changed":
        b["peers"]["second"]["process"]["identity_hash"] = "0" * 64
    elif mutation == "replacement_reused":
        b["peers"]["replacement"] = a["peers"]["first"]
    elif mutation == "restarted_replacement_changed":
        c["peers"]["replacement"]["generation"]["owner"] = "new-owner"
    elif mutation == "reboot":
        c["processes"]["camera"]["identity_hash"] = "0" * 64
    elif mutation == "capture":
        c["capture_hash"] = "0" * 64
    elif mutation == "issuer":
        c["issuer_epoch"] = 1
    elif mutation == "bool_exit":
        b["old_process"]["returncode"] = False
    elif mutation == "wrong_exit":
        b["old_process"]["supervisor_exit_code"] = 0
    elif mutation == "reservation":
        b["journal"]["projection"]["reserved_ns"] = 0
    elif mutation == "journal_hash":
        b["journal"]["projection_hash"] = "0" * 64
    elif mutation == "directory":
        c["journal"]["directory_hash"] = "0" * 64
    elif mutation == "journal_process":
        b["journal"]["projection"]["history"][0]["process_hash"] = "0" * 64
    elif mutation == "journal_request":
        b["journal"]["projection"]["history"][0]["request"]["generation"]["owner"] = "foreign"
    elif mutation == "journal_outcome":
        b["journal"]["projection"]["history"][0]["result"] = {"restoration": "verified_by_port"}
    elif mutation == "journal_changed_on_restart":
        c["journal"]["private_content_hash"] = "0" * 64
    elif mutation == "dirty_bypass":
        c["admission_outcomes"]["new_request"] = "read_only_draft"
    elif mutation == "private_history_extra":
        b["journal"]["projection"]["history"][0]["process"] = {"pid": 123}
    elif mutation == "source_cpu_reset":
        c["processes"]["game"]["cpu_ticks"] = 0
    elif mutation == "read_overlap":
        c["read_start_ns"] = b["read_end_ns"]
    elif mutation == "post_restart_too_short":
        c["read_start_ns"] = b["read_end_ns"] + 1000
        c["read_end_ns"] = c["read_start_ns"] + 1000
    elif mutation == "cooldown_precision":
        c["journal"]["projection"]["cooldown_until_ns_decimal"] = 1.5
    else:
        c["read_start_ns"] = True
    if mutation != "journal_hash":
        for row in rows:
            row["journal"]["projection_hash"] = hashed(row["journal"]["projection"])
    result = reconstruct_integrated_game_lifetimes(record(runs))
    assert result["supplied_lifetime_screen"] == "unavailable"
    assert result["lifetime_cases"][1]["state"] == "unavailable"
    assert result["lifetime_cases"][2]["state"] == "met"


def test_older_reports_and_partial_cohorts_are_not_backfilled():
    for runs in (old_cohort(), cohort()[:2]):
        result = reconstruct_integrated_game_lifetimes(record(runs))
        assert result["supplied_lifetime_screen"] == "unavailable"
        assert len(result["lifetime_cases"]) == 4
        assert result["independent_execution_verification"] == "unavailable"


def test_cli_opt_in_preserves_original_v1_view(tmp_path, capsys):
    source = tmp_path / "record.json"
    r = record(cohort())
    source.write_text(r.model_dump_json())
    assert main(["reconstruct-integrated-game-record", str(source), "--lifetimes"]) == 0
    assert json.loads(capsys.readouterr().out) == reconstruct_integrated_game_lifetimes(r)
    assert main(["reconstruct-integrated-game-record", str(source)]) == 0
    assert json.loads(capsys.readouterr().out) == reconstruct_integrated_game_record(r)
