"""Invented hashed identity/journal arithmetic; no native or private PID data."""

import copy
import hashlib
import json

from .integrated_reconstruction_cases import cohort as base_cohort


def hashed(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def cohort():
    runs = base_cohort()
    for index, run in enumerate(runs[1:], 1):
        req = next(e["request"] for e in run["events"] if e["kind"] == "game_failure_dispatched")
        result = next(e["result"] for e in run["events"] if e["kind"] == "game_failure_result")
        rows = []
        for stage, phase in enumerate(("active_target", "replacement_ready", "issuer_restarted")):
            start = 100000000000 * index + stage * 5000000000
            peers = {}
            for name in ("first", "second") if stage == 0 else ("replacement", "second"):
                identity = "4" if name == "first" else "5" if name == "second" else "6"
                fps = 24 if name == "first" else 30
                peers[name] = dict(
                    process=dict(identity_hash=identity * 64, cpu_ticks=stage * 10),
                    generation=copy.deepcopy(req["generation"])
                    if name == "first"
                    else dict(
                        owner=name + "-owner", pipeline=name + "-pipeline", peer=name + "-peer"
                    ),
                    token_hash=identity * 64,
                    offer_hash="7" * 64,
                    native_sequence=1 + stage * 10,
                    native_received_ns=start - 1000000,
                    native=dict(
                        read_start_ns=stage * 10**9,
                        read_end_ns=stage * 10**9 + 1000,
                        configured_fps=fps,
                        negotiated_fps=fps,
                        width=640,
                        height=480,
                        target_bitrate=1500000,
                        cpu_used=6,
                        max_quantizer=48,
                        connection_state="connected",
                        ice_connection_state="connected",
                        capture_buffers=100 + stage * 100,
                        encoded_buffers=100 + stage * 100,
                    ),
                )
            state = "active" if stage == 0 else "clean" if index == 1 else "dirty"
            p = dict(
                version="n10-cadence-journal-v1",
                policy_hash="8" * 64,
                boot_hash="9" * 64,
                state=state,
                actions=1,
                reserved_ns=4000000000,
                cooldown_until_ns_decimal="0",
                active=None if state == "clean" else req["request_id"],
                history=[
                    dict(
                        request=copy.deepcopy(req),
                        request_hash=hashed(req),
                        prior=dict(
                            generation=copy.deepcopy(req["generation"]),
                            healthy=True,
                            configured_fps=30,
                            negotiated_fps=30,
                            settings_hash="a" * 64,
                        ),
                        process_hash="4" * 64,
                        reserved_ns=4000000000,
                        result=result if state == "clean" else None,
                        failure=result if state == "dirty" else None,
                    )
                ],
            )
            calls = (
                {} if stage == 0 else dict(retired_draft="rejected", retired_receiver="rejected")
            )
            if stage == 2:
                calls.update(
                    old_issuer="rejected_capability",
                    new_request="read_only_draft" if index == 1 else "rejected_dirty_ledger",
                )
            rows.append(
                dict(
                    kind="failure_lifetime",
                    method="n10-contained-game-lifetime-observations-v1",
                    phase=phase,
                    case=run["case"],
                    basis="camera_linux_monotonic_relative_brackets_child_stamps_unaligned",
                    read_start_ns=start,
                    read_end_ns=start + 1000000,
                    issuer_epoch=2 if stage == 2 else 1,
                    capture_hash="c" * 64,
                    processes={
                        name: dict(identity_hash=str(i + 1) * 64, cpu_ticks=100 + stage * 100)
                        for i, name in enumerate(("camera", "game", "display"))
                    },
                    peers=peers,
                    journal=dict(
                        directory_hash="b" * 64,
                        private_content_hash=("d" if stage == 0 else "e") * 64,
                        projection_hash=hashed(p),
                        projection=p,
                    ),
                    old_process=None
                    if stage == 0
                    else dict(
                        identity_hash="4" * 64,
                        returncode=0 if index == 1 else -9,
                        supervisor_exit_code=0 if index == 1 else -9,
                    ),
                    admission_outcomes=calls,
                    live_authority=False,
                )
            )
        dispatch_index = next(
            i for i, e in enumerate(run["events"]) if e["kind"] == "game_failure_dispatched"
        )
        run["events"].insert(dispatch_index + 1, rows[0])
        verified_index = next(
            i for i, e in enumerate(run["events"]) if e["kind"] == "game_failure_verified"
        )
        run["events"][verified_index:verified_index] = rows[1:]
    return runs
