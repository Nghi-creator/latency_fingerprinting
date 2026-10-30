"""Independent counterexamples; producer flags never substitute for measurements."""

import json

import pytest

from latency_fingerprinting.cli import main
from latency_fingerprinting.live_probes import (
    import_integrated_game_cohort,
    inspect_integrated_game_record,
    reconstruct_integrated_game_record,
)

from .integrated_game_cases import META
from .integrated_reconstruction_cases import cohort


def record(runs):
    return import_integrated_game_cohort(json.dumps(runs).encode(), **META)


def reconstruct(runs):
    return reconstruct_integrated_game_record(record(runs))


def event(run, kind):
    return next(e for e in run["events"] if e["kind"] == kind)


def test_reconstructs_arithmetic_without_qualifying_declarations():
    original = record(cohort())
    before = original.model_dump_json()
    report = reconstruct_integrated_game_record(original)
    assert report["supplied_observation_screen"] == "met"
    assert [row["state"] for row in report["cases"]] == ["met"] * 5
    assert report["process_lifetime_verification"] == "unavailable_retained_declarations_only"
    assert report["independent_execution_verification"] == "unavailable"
    assert report["clock_alignment"] == "none"
    assert report["capability"] == "unavailable_unqualified"
    assert report["live_authority"] is False
    assert all(
        report[key] == "not_evaluated"
        for key in ("audio_quality", "perceptual_quality", "desktop_acceptance")
    )
    for index, window in enumerate(report["cases"][0]["windows"]):
        assert window["source_rates"]["first"]["encoded_buffers"] == (24 if index == 1 else 30)
        assert window["viewers"][0]["presented_fps"] == (24 if index == 1 else 30)
        assert window["native_resources"]["first"]["cpu_percent"] == 8
        assert window["native_resources"]["game"]["sampled_peak_rss_bytes"] == 2048
        assert window["browser_resources"]["cpu_percent"] == 25
    assert original.model_dump_json() == before
    assert (
        inspect_integrated_game_record(original)["engineering_screen"]
        == "unavailable_independent_reconstruction_required"
    )


@pytest.mark.parametrize(
    "index,kind,field,value",
    [
        (1, "game_failure_dispatched", "live_authority", 0),
        (1, "game_failure_fault", "target_observed", 1),
        (2, "game_failure_result", "ledger_state", "clean"),
        (3, "game_failure_verified", "reserved_ns", 0),
        (4, "game_failure_verified", "actions", True),
        (1, "game_failure_verified", "old_exit", False),
        (2, "game_failure_verified", "old_exit", 0),
        (3, "game_failure_verified", "stale_handles_rejected", 1),
        (3, "game_failure_verified", "old_owner_rejected", False),
        (2, "game_failure_verified", "dirty_blocked", False),
        (1, "game_failure_verified", "clean_draft_allowed", False),
        (3, "game_failure_verified", "source_restored", False),
        (2, "game_failure_verified", "source_restored", True),
        (4, "game_failure_verified", "sibling_identity_retained", False),
        (1, "control_capture_bound", "binding_hash", "bad"),
        (0, "control_result", "reserved_ns", 5000000000),
        (0, "control_native", "worker_identities", {"first": "d" * 64, "second": "d" * 64}),
        (0, "camera_ready", "source", "production"),
        (1, "camera_process_exit", "code", False),
        (2, "complete", "worker_cleanup", False),
    ],
)
def test_lifecycle_misuse_cannot_pass(index, kind, field, value):
    runs = cohort()
    event(runs[index], kind)[field] = value
    result = reconstruct(runs)
    assert result["supplied_observation_screen"] != "met"
    assert result["cases"][index]["state"] == "unavailable"
    assert result["cases"][(index + 1) % 5]["state"] == "met"


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate",
        "reorder",
        "wrong_scope",
        "wrong_request",
        "false_restore",
        "completed_fault",
        "contradictory_teardown",
        "extra_action",
        "late_reconnect",
        "missing_source_restore",
        "request_generation_extra",
        "request_bool_duration",
        "wrong_viewer",
        "wrong_epoch",
        "relay_closed_early",
    ],
)
def test_failure_event_boundaries(mutation):
    runs = cohort()
    run = runs[3]
    if mutation == "duplicate":
        run["events"].append(event(run, "game_failure_result").copy())
    elif mutation == "reorder":
        e = event(run, "game_failure_fault")
        run["events"].remove(e)
        run["events"].insert(1, e)
    elif mutation == "wrong_scope":
        event(run, "game_failure_verified")["case"] = "reconnect"
    elif mutation == "wrong_request":
        event(run, "game_failure_result")["result"]["request_id"] = "foreign"
    elif mutation == "false_restore":
        event(run, "game_failure_result")["result"]["restoration"] = "verified_by_port"
    elif mutation == "completed_fault":
        event(run, "game_failure_result")["result"]["outcome"] = "completed"
    elif mutation == "contradictory_teardown":
        event(run, "game_failure_result")["result"].update(
            outcome="interrupted_teardown", reason="worker_terminated"
        )
    elif mutation == "extra_action":
        run["events"].append(dict(kind="control_dispatched", method=run["method"]))
    elif mutation == "late_reconnect":
        run = runs[1]
        e = event(run, "game_failure_reconnect")
        run["events"].remove(e)
        run["events"].append(e)
    elif mutation == "missing_source_restore":
        run["events"].remove(event(run, "game_failure_source_restored"))
    elif mutation == "request_generation_extra":
        event(run, "game_failure_dispatched")["request"]["generation"]["foreign"] = True
    elif mutation == "request_bool_duration":
        event(run, "game_failure_dispatched")["request"]["duration_ns"] = True
    elif mutation == "wrong_viewer":
        run["viewers"][1]["bindings"] = 3
    elif mutation == "wrong_epoch":
        run["viewers"][0]["epochs"] = ["first"]
    else:
        e = next(
            e for e in run["events"] if e["kind"] == "relay_shutdown" and e["stage"] == "closed"
        )
        run["events"].remove(e)
        run["events"].insert(0, e)
    index = 1 if mutation == "late_reconnect" else 3
    assert reconstruct(runs)["cases"][index]["state"] == "unavailable"


@pytest.mark.parametrize("index", [2, 4])
def test_no_result_is_uncertainty_even_with_consistent_failure_declarations(index):
    runs = cohort()
    event(runs[index], "game_failure_result")["result"] = None
    result = reconstruct(runs)
    assert result["cases"][index]["restoration"] == "unavailable_no_result"
    assert result["cases"][index]["process_lifetime_verification"].startswith("unavailable")
    assert result["live_authority"] is False


def test_cancel_and_source_loss_require_explicit_results():
    runs = cohort()
    for index in (1, 3):
        event(runs[index], "game_failure_result")["result"] = None
    result = reconstruct(runs)
    assert [result["cases"][index]["state"] for index in (1, 3)] == ["unavailable"] * 2


@pytest.mark.parametrize(
    "outcome,reason",
    [
        ("unknown", "worker_terminated"),
        ("aborted", "generation_changed"),
        ("aborted", "restore_failed"),
    ],
)
def test_supported_uncertain_results_are_not_relabelled(outcome, reason):
    runs = cohort()
    body = event(runs[2], "game_failure_result")["result"]
    body.update(outcome=outcome, reason=reason)
    result = reconstruct(runs)
    assert result["cases"][2]["state"] == "met"
    assert result["cases"][2]["restoration"] == "unknown"
    assert json.loads(record(runs).raw_report)[2]["events"][4]["result"] == body


@pytest.mark.parametrize(
    "mutation",
    [
        "cpu_reset",
        "overlap",
        "read_width",
        "fractional_clock",
        "settings",
        "phase_lifetime",
        "script_reset",
        "fractional_ticks",
        "source_stall",
        "native_phase_order",
        "cross_phase_reset",
    ],
)
def test_native_counter_and_lifetime_boundaries(mutation):
    runs = cohort()
    reports = [e for e in runs[0]["events"] if e["kind"] == "control_native"]
    report = reports[1]
    s = report["samples"]
    if mutation == "cpu_reset":
        s[4]["workers"]["first"]["cpu_ticks"] = 999999
    elif mutation == "overlap":
        s[2]["read_end_ns"] = s[3]["read_start_ns"]
    elif mutation == "read_width":
        s[2]["read_end_ns"] += 50000000
    elif mutation == "fractional_clock":
        s[2]["read_start_ns"] += 0.5
    elif mutation == "settings":
        s[2]["workers"]["first"]["settings"]["target_bitrate"] = 1000000
    elif mutation == "phase_lifetime":
        report["worker_identities"]["first"] = "a" * 64
    elif mutation == "script_reset":
        s[4]["game_phase"]["script_actions"] = 999999
    elif mutation == "fractional_ticks":
        report["ticks_per_second"] = 100.0
    elif mutation == "source_stall":
        for sample in s:
            sample["workers"]["first"]["encoded_buffers"] = 500
    elif mutation == "native_phase_order":
        report["phase"] = "baseline"
    else:
        # Each phase is individually monotone; the boundary resets.
        for sample in s:
            sample["workers"]["first"]["cpu_ticks"] -= 100
    result = reconstruct(runs)
    assert result["cases"][0]["state"] != "met"
    assert result["cases"][1]["state"] == "met"


@pytest.mark.parametrize(
    "mutation",
    [
        "counter_reset",
        "stats_gap",
        "visual_order",
        "visual_outside",
        "bool_counter",
        "short_window",
        "dropped",
        "freeze",
        "blank",
        "static",
        "pts_gap",
        "rate",
        "dimensions",
    ],
)
def test_sibling_measurements_are_recomputed(mutation):
    runs = cohort()
    q = runs[2]["sibling_quality"]
    if mutation == "counter_reset":
        q["stats"][4]["decoded"] = 999999
    elif mutation == "stats_gap":
        q["stats"] = q["stats"][::4]
    elif mutation == "visual_order":
        q["visuals"].reverse()
    elif mutation == "visual_outside":
        q["visuals"][-1]["at_ms"] = 3000
    elif mutation == "bool_counter":
        q["stats"][4]["decoded"] = True
    elif mutation == "short_window":
        q["duration_ms"] = 1000
    elif mutation == "dropped":
        q["stats"][-1]["dropped"] = 1
    elif mutation == "freeze":
        q["stats"][-1]["freezes"] = 1
    elif mutation == "blank":
        q["visuals"][1]["color_bins"] = 0
    elif mutation == "static":
        for visual in q["visuals"]:
            visual["hash"] = 1
    elif mutation == "pts_gap":
        q["frames"][4]["pts_ms"] += 500
    elif mutation == "rate":
        for f in q["frames"]:
            f["presented"] *= 2
    else:
        q["stats"][0]["width"] = 320
    result = reconstruct(runs)
    assert result["cases"][2]["state"] != "met"
    assert result["cases"][3]["state"] == "met"


@pytest.mark.parametrize(
    "mutation",
    [
        "spliced_trace",
        "transition_reset",
        "transition_drop",
        "long_gap",
        "window_order",
        "reused_window",
        "fake_producer_flags",
    ],
)
def test_control_transitions_cannot_be_hidden(mutation):
    runs = cohort()
    run = runs[0]
    if mutation == "spliced_trace":
        for frame in run["continuity"][0]["frames"]:
            frame["pts_ms"] += 1
    elif mutation == "transition_reset":
        for stat in run["control_windows"][1]["quality"][0]["stats"]:
            stat["decoded"] -= 200
    elif mutation == "transition_drop":
        for window in run["control_windows"][1:]:
            for stat in window["quality"][0]["stats"]:
                stat["dropped"] = 1
    elif mutation == "long_gap":
        run["continuity"][0]["frames"][20]["at_ms"] += 400
    elif mutation == "window_order":
        run["control_windows"].reverse()
    elif mutation == "reused_window":
        run["control_windows"][2]["quality"] = json.loads(
            json.dumps(run["control_windows"][0]["quality"])
        )
        for quality in run["control_windows"][2]["quality"]:
            for stat in quality["stats"]:
                stat["decoded"] += 1000
    else:
        run.update(control_screen="met", assessment={"met": True})
        run["control_windows"][1]["quality"][0]["frames"] = []
    assert reconstruct(runs)["cases"][0]["state"] != "met"


@pytest.mark.parametrize("mutation", ["missing", "inventory", "reset", "clock", "bool_count"])
def test_browser_resource_missingness_never_becomes_zero(mutation):
    runs = cohort()
    w = runs[0]["control_windows"][0]
    r = w["browser_resources"]
    if mutation == "missing":
        del w["browser_resources"]
    elif mutation == "inventory":
        r["after"]["inventory_hash"] = "a" * 64
    elif mutation == "reset":
        r["before"]["cpu_seconds"] = 2
    elif mutation == "clock":
        r["after"]["host_at_ns"] = 0
    else:
        r["before"]["process_count"] = True
    result = reconstruct(runs)["cases"][0]
    assert result["state"] == "met"
    assert result["windows"][0]["browser_resources"] == {
        "state": "unavailable",
        "cpu_percent": None,
    }


def test_failed_partial_changed_context_and_later_cases_remain_visible():
    runs = cohort()[:4]
    runs[1]["status"] = "failed"
    runs[2]["context"]["software_hash"] = "c" * 64
    result = reconstruct(runs)
    assert [r["state"] for r in result["cases"]] == [
        "met",
        "unavailable",
        "unavailable",
        "met",
        "unavailable",
    ]
    assert result["cases"][4]["reason"] == "missing_acquisition"
    assert result["supplied_observation_screen"] == "unavailable"


@pytest.mark.parametrize(
    "field,value",
    [
        ("events", None),
        ("events", [None]),
        ("events", [{"kind": []}]),
        ("viewers", None),
        ("sibling_quality", []),
        ("context", {"image": []}),
    ],
)
def test_opaque_malformed_observations_cannot_crash_reconstruction(field, value):
    runs = cohort()
    runs[2][field] = value
    result = reconstruct(runs)
    assert result["cases"][2]["state"] == "unavailable"
    assert result["cases"][3]["state"] == "met"


def test_cli_and_typed_instance_revalidation(tmp_path, capsys):
    source = tmp_path / "record.json"
    original = record(cohort())
    source.write_text(original.model_dump_json())
    assert main(["reconstruct-integrated-game-record", str(source)]) == 0
    assert json.loads(capsys.readouterr().out) == reconstruct_integrated_game_record(original)
    with pytest.raises(ValueError):
        reconstruct_integrated_game_record(original.model_copy(update={"raw_report": "[]"}))
