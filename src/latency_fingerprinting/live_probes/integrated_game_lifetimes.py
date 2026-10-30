"""Compare supplied hashed lifetimes and projected journals; never authenticate execution."""

import hashlib
import json
import re

from .cadence import CadenceOutcome
from .integrated_game import MODES, IntegratedGameRecord, decode_cohort
from .integrated_game_measurements import EvidenceGap, digest, items, number, obj, require
from .integrated_game_reconstruction import one, reconstruct_integrated_game_record

METHOD = "n10-contained-game-lifetime-observations-v1"
PHASES = ("active_target", "replacement_ready", "issuer_restarted")


def observation_hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def process(row):
    row = obj(row)
    require(set(row) == {"identity_hash", "cpu_ticks"}, "process_projection_shape")
    digest(row["identity_hash"])
    number(row["cpu_ticks"], integral=True)
    return row


def peer(row, expected_fps, end):
    row = obj(row)
    process(row["process"])
    for field in ("token_hash", "offer_hash"):
        digest(row[field])
    generation = obj(row["generation"])
    require(
        set(generation) == {"owner", "pipeline", "peer"}
        and all(
            type(v) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", v) is not None
            for v in generation.values()
        ),
        "peer_generation_shape",
    )
    stamp = number(row["native_received_ns"], integral=True)
    require(
        0 <= end - stamp <= 1500000000 and number(row["native_sequence"], integral=True) > 0,
        "native_receipt_stale",
    )
    native = obj(row["native"])
    require(
        number(native["read_end_ns"], integral=True)
        >= number(native["read_start_ns"], integral=True),
        "child_read_bracket",
    )
    for field in ("capture_buffers", "encoded_buffers"):
        number(native[field], integral=True)
    expected = dict(
        configured_fps=expected_fps,
        negotiated_fps=expected_fps,
        width=640,
        height=480,
        target_bitrate=1500000,
        cpu_used=6,
        max_quantizer=48,
    )
    require(
        all(type(native[k]) is int and native[k] == v for k, v in expected.items()),
        "lifetime_native_settings",
    )
    require(
        native["connection_state"] == "connected"
        and native["ice_connection_state"] in ("connected", "completed"),
        "lifetime_native_connection",
    )
    return row


def journal(row, request, old_process, state, outcome):
    row = obj(row)
    for field in ("directory_hash", "private_content_hash", "projection_hash"):
        digest(row[field])
    p = obj(row["projection"])
    require(row["projection_hash"] == observation_hash(p), "journal_projection_hash")
    require(
        set(p)
        == {
            "version",
            "policy_hash",
            "boot_hash",
            "state",
            "actions",
            "reserved_ns",
            "cooldown_until_ns_decimal",
            "active",
            "history",
        },
        "journal_projection_shape",
    )
    require(
        p["version"] == "n10-cadence-journal-v1"
        and p["state"] == state
        and number(p["actions"], integral=True) == 1
        and number(p["reserved_ns"], integral=True) == 4000000000,
        "lifetime_journal_budget",
    )
    digest(p["policy_hash"])
    digest(p["boot_hash"])
    require(
        type(p["cooldown_until_ns_decimal"]) is str
        and re.fullmatch(r"[0-9]{1,19}", p["cooldown_until_ns_decimal"]) is not None
        and int(p["cooldown_until_ns_decimal"]) <= 2**63 - 1,
        "journal_cooldown_decimal",
    )
    require(
        p["active"] == (None if state == "clean" else request["request_id"]),
        "journal_active_request",
    )
    history = items(p["history"], 1, 1)[0]
    require(
        set(obj(history))
        == {"request", "request_hash", "prior", "process_hash", "reserved_ns", "result", "failure"},
        "journal_history_shape",
    )
    require(
        history["request"] == request
        and history["request_hash"] == observation_hash(request)
        and history["process_hash"] == old_process
        and number(history["reserved_ns"], integral=True) == p["reserved_ns"],
        "journal_request_binding",
    )
    prior = obj(history["prior"])
    require(
        set(prior)
        == {"generation", "healthy", "configured_fps", "negotiated_fps", "settings_hash"},
        "journal_preimage_shape",
    )
    require(
        prior["generation"] == request["generation"]
        and prior["healthy"] is True
        and number(prior["configured_fps"], integral=True) == 30
        and number(prior["negotiated_fps"], integral=True) == 30,
        "journal_preimage",
    )
    digest(prior["settings_hash"])
    if state == "active":
        require(history["result"] is None and history["failure"] is None, "active_journal_outcome")
    elif state == "clean":
        require(
            history["result"] == outcome and history["failure"] is None, "clean_journal_outcome"
        )
    else:
        require(history["result"] is None, "dirty_journal_completed")
        if history["failure"] is not None:
            failure = CadenceOutcome.model_validate(history["failure"])
            require(
                failure.request_id == request["request_id"] and failure.restoration == "unknown",
                "dirty_journal_failure",
            )
        require(outcome is None or history["failure"] == outcome, "retained_failure_mismatch")
    return row


def compare_peer(a, b):
    require(
        all(a[k] == b[k] for k in ("generation", "token_hash", "offer_hash"))
        and a["process"]["identity_hash"] == b["process"]["identity_hash"],
        "peer_lifetime_changed",
    )
    require(
        b["process"]["cpu_ticks"] >= a["process"]["cpu_ticks"]
        and b["native_sequence"] > a["native_sequence"]
        and b["native_received_ns"] > a["native_received_ns"]
        and b["native"]["read_start_ns"] > a["native"]["read_end_ns"]
        and all(b["native"][k] > a["native"][k] for k in ("capture_buffers", "encoded_buffers")),
        "peer_progress_or_clock_reset",
    )


def reconstruct_case(run):
    events = run["events"]
    rows = [e for e in events if e["kind"] == "failure_lifetime"]
    require(len(rows) == 3 and tuple(e["phase"] for e in rows) == PHASES, "lifetime_phase_order")
    dispatch, fault, verified = (
        one(events, k)
        for k in ("game_failure_dispatched", "game_failure_fault", "game_failure_verified")
    )
    result = one(events, "game_failure_result")["result"]
    require(
        events.index(dispatch)
        < events.index(rows[0])
        < events.index(fault)
        < events.index(rows[1])
        < events.index(rows[2])
        < events.index(verified),
        "lifetime_event_order",
    )
    if run["case"] == "source-loss":
        require(
            events.index(one(events, "game_failure_source_restored")) < events.index(rows[1]),
            "lifetime_source_not_restored",
        )
    req = dispatch["request"]
    old_hash = rows[0]["peers"]["first"]["process"]["identity_hash"]
    capture = one(events, "control_capture_bound")["binding_hash"]
    previous_end = -1
    for index, row in enumerate(rows):
        require(
            row["method"] == METHOD
            and row["case"] == run["case"]
            and row["live_authority"] is False
            and row["basis"] == "camera_linux_monotonic_relative_brackets_child_stamps_unaligned",
            "lifetime_scope",
        )
        start, end = (number(row[k], integral=True) for k in ("read_start_ns", "read_end_ns"))
        require(start > previous_end and 0 <= end - start <= 50000000, "lifetime_read_bracket")
        previous_end = end
        require(
            row["capture_hash"] == capture
            and number(row["issuer_epoch"], integral=True) == (2 if index == 2 else 1),
            "capture_or_issuer_changed",
        )
        require(
            set(obj(row["processes"])) == {"camera", "game", "display"}, "source_process_inventory"
        )
        for value in row["processes"].values():
            process(value)
        names = {"first", "second"} if index == 0 else {"replacement", "second"}
        require(set(obj(row["peers"])) == names, "peer_checkpoint_inventory")
        for name, value in row["peers"].items():
            peer(value, 24 if index == 0 and name == "first" else 30, end)
        identities = [v["identity_hash"] for v in row["processes"].values()]
        identities += [v["process"]["identity_hash"] for v in row["peers"].values()]
        require(len(set(identities)) == 5, "process_identity_collision")
        state = "active" if index == 0 else "clean" if run["case"] == "cancel" else "dirty"
        journal(row["journal"], req, old_hash, state, result)
        if index == 0:
            require(
                row["old_process"] is None and row["admission_outcomes"] == {},
                "active_checkpoint_state",
            )
            require(
                row["peers"]["first"]["generation"] == req["generation"], "active_peer_generation"
            )
        else:
            old = obj(row["old_process"])
            expected = 0 if run["case"] == "cancel" else -9
            require(
                old["identity_hash"] == old_hash
                and type(old["returncode"]) is int
                and type(old["supervisor_exit_code"]) is int
                and old["returncode"] == old["supervisor_exit_code"] == expected,
                "old_exit_observation",
            )
            expected_calls = dict(retired_draft="rejected", retired_receiver="rejected")
            if index == 2:
                expected_calls.update(
                    old_issuer="rejected_capability",
                    new_request="read_only_draft"
                    if run["case"] == "cancel"
                    else "rejected_dirty_ledger",
                )
            require(row["admission_outcomes"] == expected_calls, "admission_outcome_records")
        if index:
            previous = rows[index - 1]
            for name in row["processes"]:
                a, b = previous["processes"][name], row["processes"][name]
                require(
                    a["identity_hash"] == b["identity_hash"] and b["cpu_ticks"] >= a["cpu_ticks"],
                    "source_process_lifetime_changed",
                )
                if name == "game":
                    require(b["cpu_ticks"] > a["cpu_ticks"], "game_checkpoint_progress")
            compare_peer(previous["peers"]["second"], row["peers"]["second"])
            for key in ("directory_hash",):
                require(
                    previous["journal"][key] == row["journal"][key], "journal_directory_changed"
                )
            for key in ("boot_hash", "policy_hash"):
                require(
                    previous["journal"]["projection"][key] == row["journal"]["projection"][key],
                    "journal_scope_changed",
                )
    require(
        rows[2]["read_start_ns"] - rows[1]["read_end_ns"] >= 2500000000,
        "post_restart_interval_short",
    )
    a, b = rows[0]["peers"]["first"], rows[1]["peers"]["replacement"]
    require(
        a["process"]["identity_hash"] != b["process"]["identity_hash"]
        and a["generation"] != b["generation"]
        and a["token_hash"] != b["token_hash"],
        "replacement_reused_lifetime",
    )
    compare_peer(rows[1]["peers"]["replacement"], rows[2]["peers"]["replacement"])
    require(rows[1]["journal"] == rows[2]["journal"], "issuer_restart_changed_journal")
    return {
        "state": "met",
        "lifetime_identity_comparisons": "consistent",
        "journal_projection_comparisons": "consistent",
        "issuer_restart": "same_camera_new_logical_issuer",
        "old_exit": 0 if run["case"] == "cancel" else -9,
        "live_authority": False,
    }


def reconstruct_integrated_game_lifetimes(record):
    record = IntegratedGameRecord.model_validate(record)
    result = reconstruct_integrated_game_record(record)
    runs = decode_cohort(record.raw_report)
    rows = []
    for index, mode in enumerate(MODES[1:], 1):
        row = {"mode": mode, "state": "unavailable", "reason": "missing_lifetime_observations"}
        try:
            require(result["cases"][index]["state"] == "met", "base_observations_not_met")
            row = {"mode": mode, **reconstruct_case(runs[index])}
        except EvidenceGap as error:
            row["reason"] = str(error)
        except (ValueError, KeyError, TypeError, IndexError, OverflowError):
            row["reason"] = "invalid_or_missing_lifetime_observations"
        rows.append(row)
    result.update(
        method_release="n10-integrated-game-reconstruction-v2",
        lifetime_cases=rows,
        supplied_lifetime_screen="met" if all(r["state"] == "met" for r in rows) else "unavailable",
    )
    if result["supplied_lifetime_screen"] == "met":
        result["process_lifetime_verification"] = "failure_case_hashed_lifetime_comparisons_only"
    # These are still supplied observations, not authenticated execution or live authorization.
    return result
