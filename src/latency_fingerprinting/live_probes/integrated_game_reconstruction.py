"""Reconstruct supplied observations; process/ownership assertions stay declarations."""

import re

from .browser_cpu import browser_cpu
from .cadence import CadenceOutcome
from .integrated_game import MODES, IntegratedGameRecord, decode_cohort
from .integrated_game_measurements import (
    PHASES,
    EvidenceGap,
    browser_window,
    delta,
    digest,
    frame_trace,
    items,
    native_windows,
    number,
    obj,
    require,
    series,
)

CONTROL = "n10-contained-game-control-disturbance-v1"
FAILURE = "n10-contained-game-failure-v1"


def one(events, kind):
    found = [e for e in events if e["kind"] == kind]
    require(len(found) == 1, "event_cardinality")
    return found[0]


def request(event, duration):
    body = obj(event["request"])
    require(set(body) == {"request_id", "generation", "target_fps", "duration_ns"}, "request_shape")
    generation = obj(body["generation"])
    require(set(generation) == {"owner", "pipeline", "peer"}, "request_generation")
    require(
        all(
            type(v) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", v)
            for v in (body["request_id"], *generation.values())
        ),
        "request_alias",
    )
    require(
        number(body["target_fps"], integral=True) == 24
        and number(body["duration_ns"], integral=True) == duration
        and event["live_authority"] is False,
        "request_protocol",
    )
    return body


def journal(event, clean, reservation):
    require(
        event["ledger_state"] == ("clean" if clean else "dirty")
        and number(event["actions"], integral=True) == 1
        and number(event["reserved_ns"], integral=True) == reservation,
        "ledger_budget_mismatch",
    )


def context(run):
    data = obj(run["context"])
    require(set(data) == {"image", "software_hash", "host_platform", "host_arch"}, "context_shape")
    digest(data["image"], prefixed=True)
    digest(data["software_hash"])
    require(
        all(
            type(v) is str and 0 < len(v) <= 128
            for v in (data["host_platform"], data["host_arch"], run["browser"])
        ),
        "context_identity",
    )
    return data, run["browser"]


def acquisition(run, method):
    require(run["status"] == "passed" and run["live_authority"] is False, "acquisition_incomplete")
    require(run["method"] == method, "method_mismatch")
    events = items(run["events"], 1, 128)
    require(
        all(
            type(e) is dict and type(e.get("kind")) is str and len(e["kind"]) <= 64 for e in events
        ),
        "event_shape",
    )
    ready, bound, complete = (
        one(events, k) for k in ("camera_ready", "control_capture_bound", "complete")
    )
    require(ready["mode"] == run["mode"] and ready["source"] == "isolated_game", "capture_source")
    profile = obj(ready["profile"])
    require(
        profile["id"] == "balanced"
        and number(profile["fps"], integral=True) == 30
        and number(profile["bitrate_kbps"], integral=True) == 1500,
        "declared_profile",
    )
    require(
        bound["method"] == method
        and bound["scope"] == "owned_x99_game_display"
        and bound["live_authority"] is False,
        "capture_binding",
    )
    digest(bound["binding_hash"])
    require(
        complete["live_authority"] is False
        and complete["worker_cleanup"] is True
        and complete["game_alive"] is True,
        "cleanup_declarations",
    )
    require(
        events.index(ready) < events.index(bound) < events.index(complete), "capture_event_order"
    )
    stages = [e["stage"] for e in events if e["kind"] == "host_shutdown"]
    require(
        stages
        == [
            "camera_loop_returned",
            "disconnect_thread_joined",
            "socket_closed",
            "scene_close_start",
            "scene_closed",
            "scope_closed",
        ],
        "host_cleanup_sequence",
    )
    exit_event = one(events, "camera_process_exit")
    require(
        number(exit_event["code"], integral=True) == 0 and exit_event["signal"] is None,
        "camera_exit_declaration",
    )
    exit_index = events.index(exit_event)
    require(
        all(
            events.index(complete) < i < exit_index
            for i, e in enumerate(events)
            if e["kind"] == "host_shutdown"
        ),
        "host_cleanup_order",
    )
    relay = [(i, e["stage"]) for i, e in enumerate(events) if e["kind"] == "relay_shutdown"]
    require(
        [stage for _, stage in relay] == ["close_start", "closed"] and relay[0][0] > exit_index,
        "relay_cleanup_sequence",
    )
    return events


def viewers(run, *, fault=None):
    rows = items(run["viewers"], 2, 2)
    for index, row in enumerate(rows):
        row = obj(row)
        expected = 1 if index == 0 and fault in ("receiver-loss", "source-loss") else 0
        require(
            number(row["failures"], integral=True) == expected
            and number(row["unbound"], integral=True) == 1
            and number(row["bindings"], integral=True)
            == (1 if fault is None else 3 if index == 0 else 2),
            "viewer_lifecycle_counts",
        )
        require(
            row["epochs"]
            == (
                ["first", "replacement"]
                if index == 0 and fault is not None
                else ["first"]
                if index == 0
                else ["second"]
            ),
            "viewer_epochs",
        )


def failure_case(run):
    case = run["mode"].removeprefix("engineering-game-")
    require(
        run["role"] == "contained_game_failure_not_qualification" and run["case"] == case,
        "failure_role",
    )
    events = acquisition(run, FAILURE)
    dispatched, fault, result, verified = (
        one(events, k)
        for k in (
            "game_failure_dispatched",
            "game_failure_fault",
            "game_failure_result",
            "game_failure_verified",
        )
    )
    allowed = {
        "control_capture_bound",
        "game_failure_dispatched",
        "game_failure_fault",
        "game_failure_result",
        "game_failure_verified",
    }
    if case in ("cancel", "reconnect"):
        reconnect = one(events, "game_failure_reconnect")
        require(
            events.index(result) < events.index(reconnect) < events.index(verified)
            if case == "cancel"
            else events.index(dispatched) < events.index(reconnect) < events.index(fault),
            "reconnect_order",
        )
        allowed.add("game_failure_reconnect")
    if case == "source-loss":
        restored = one(events, "game_failure_source_restored")
        require(
            events.index(fault) < events.index(restored) < events.index(verified),
            "source_restore_order",
        )
        allowed.add("game_failure_source_restored")
    scoped = [e for e in events if e["kind"].startswith(("control_", "game_failure_"))]
    require(
        all(
            e["kind"] in allowed
            and e["method"] == FAILURE
            and (e["kind"] == "control_capture_bound" or e["case"] == case)
            for e in scoped
        ),
        "failure_event_scope",
    )
    require(
        events.index(one(events, "control_capture_bound"))
        < events.index(dispatched)
        < events.index(fault)
        < events.index(result)
        < events.index(verified)
        < events.index(one(events, "complete"))
        and fault["target_observed"] is True,
        "fault_order",
    )
    req = request(dispatched, 2000000000)
    clean = case == "cancel"
    for event in (result, verified):
        journal(event, clean, 4000000000)
    body = result["result"]
    if body is None:
        require(case in ("receiver-loss", "reconnect"), "explicit_result_required")
    else:
        outcome = CadenceOutcome.model_validate(body)
        require(outcome.request_id == req["request_id"], "result_request_mismatch")
        require(
            (outcome.outcome, outcome.reason, outcome.restoration)
            == ("aborted", "cancelled", "verified_by_port")
            if clean
            else outcome.outcome != "completed" and outcome.restoration == "unknown",
            "unexpected_failure_outcome",
        )
    for field in (
        "old_reaped",
        "stale_handles_rejected",
        "owner_restarted",
        "old_owner_rejected",
        "game_progress",
        "sibling_progress",
        "sibling_identity_retained",
    ):
        require(verified[field] is True, "lifetime_declaration_inconsistent")
    require(
        verified["live_authority"] is False
        and verified["dirty_blocked"] is (not clean)
        and verified["clean_draft_allowed"] is clean
        and verified["source_restored"] is (case == "source-loss"),
        "restart_declaration_inconsistent",
    )
    require(
        type(verified["old_exit"]) is int and verified["old_exit"] == (0 if clean else -9),
        "worker_exit_declaration",
    )
    viewers(run, fault=case)
    quality = browser_window(run["sibling_quality"], 30)
    return {
        "state": "met" if quality["met"] else "not_met",
        "sibling_temporal": quality,
        "lifecycle_declarations": "consistent",
        "restoration": "unavailable_no_result"
        if body is None
        else "declared_port_result_only"
        if clean
        else "unknown",
        "process_lifetime_verification": "unavailable_raw_lifetimes_not_retained",
    }


def control_case(run):
    require(run["role"] == "contained_game_control_disturbance_not_qualification", "control_role")
    events = acquisition(run, CONTROL)
    scoped = [e for e in events if e["kind"].startswith(("control_", "game_failure_"))]
    expected = [
        ("control_capture_bound", None),
        ("control_window_started", "baseline"),
        ("control_native", "baseline"),
        ("control_dispatched", None),
        ("control_window_started", "during"),
        ("control_native", "during"),
        ("control_result", None),
        ("control_window_started", "restored"),
        ("control_native", "restored"),
    ]
    require(
        [(e["kind"], e.get("phase")) for e in scoped] == expected
        and all(e["method"] == CONTROL for e in scoped),
        "control_event_order",
    )
    require(
        events.index(scoped[-1]) < events.index(one(events, "complete")), "control_cleanup_order"
    )
    dispatched, result = (one(events, k) for k in ("control_dispatched", "control_result"))
    req = request(dispatched, 5000000000)
    outcome = CadenceOutcome.model_validate(result["result"])
    require(
        (outcome.request_id, outcome.outcome, outcome.reason, outcome.restoration)
        == (req["request_id"], "completed", "duration_elapsed", "verified_by_port"),
        "control_outcome",
    )
    journal(result, True, 7000000000)
    viewers(run)
    native = native_windows([e for e in events if e["kind"] == "control_native"])
    windows = items(run["control_windows"], 3, 3)
    rows = []
    for phase, window, native_row in zip(PHASES, windows, native, strict=True):
        require(obj(window)["phase"] == phase, "browser_phase_order")
        quality = [
            browser_window(q, 24 if phase == "during" and i == 0 else 30)
            for i, q in enumerate(items(window["quality"], 2, 2))
        ]
        rows.append(
            {
                **native_row,
                "viewers": quality,
                "browser_resources": browser_cpu(window.get("browser_resources")),
            }
        )
    traces = items(run["continuity"], 2, 2)
    continuity = [frame_trace(t, continuous=True) for t in traces]
    for peer in (0, 1):
        stats = [s for w in windows for s in w["quality"][peer]["stats"]]
        require(
            delta(series(stats, "dropped", integral=True)) == 0
            and delta(series(stats, "freezes", integral=True)) == 0,
            "transition_drops_or_freezes",
        )
        delta(series(stats, "decoded", integral=True))
        frames = traces[peer]["frames"]
        by_count = {f["presented"]: f for f in frames}
        phase_frames = [f for w in windows for f in w["quality"][peer]["frames"]]
        delta(series(phase_frames, "presented", integral=True))
        require(
            all(
                a["quality"][peer]["frames"][-1]["presented"]
                < b["quality"][peer]["frames"][0]["presented"]
                for a, b in zip(windows, windows[1:], strict=False)
            ),
            "browser_phase_overlap",
        )
        require(
            all(
                f["presented"] in by_count and f["pts_ms"] == by_count[f["presented"]]["pts_ms"]
                for f in phase_frames
            ),
            "continuous_trace_coverage",
        )
    met = all(row["met"] and all(q["met"] for q in row["viewers"]) for row in rows) and all(
        t["met"] for t in continuity
    )
    return {
        "state": "met" if met else "not_met",
        "windows": rows,
        "continuity": continuity,
        "lifecycle_declarations": "consistent",
        "restoration": "port_result_and_temporal_samples_only",
        "process_lifetime_verification": "unavailable_opaque_worker_identity_declarations",
    }


def reconstruct_integrated_game_record(record):
    """Recompute arithmetic/consistency only; never authenticate or grant live capability."""
    record = IntegratedGameRecord.model_validate(record)
    runs = decode_cohort(record.raw_report)
    rows, reference = [], None
    for index, mode in enumerate(MODES):
        row = {"mode": mode, "state": "unavailable", "reason": "missing_acquisition"}
        if index < len(runs):
            run = runs[index]
            try:
                key = context(run)
                if reference is None:
                    reference = key
                require(key == reference, "cohort_context_changed")
                row = {"mode": mode, **(control_case(run) if index == 0 else failure_case(run))}
            except EvidenceGap as error:
                row["reason"] = str(error)
            except (ValueError, TypeError, KeyError, IndexError, OverflowError):
                row["reason"] = "invalid_or_missing_observations"
        rows.append(row)
    states = [row["state"] for row in rows]
    return {
        "method_release": "n10-integrated-game-reconstruction-v1",
        "record_hash": record.content_hash,
        "raw_report_hash": record.raw_report_hash,
        "cases": rows,
        "supplied_observation_screen": "unavailable"
        if "unavailable" in states
        else "met"
        if all(state == "met" for state in states)
        else "not_met",
        "process_lifetime_verification": "unavailable_retained_declarations_only",
        "independent_execution_verification": "unavailable",
        "resource_interpretation": "separate_clock_descriptive_cpu_no_causal_benefit",
        "clock_alignment": "none",
        "issuer_restart_scope": "logical_local_owner_not_camera_process_reboot",
        "perceptual_quality": "not_evaluated",
        "audio_quality": "not_evaluated",
        "desktop_acceptance": "not_evaluated",
        "diagnostic_value": "unverified",
        "capability": "unavailable_unqualified",
        "live_authority": False,
    }
