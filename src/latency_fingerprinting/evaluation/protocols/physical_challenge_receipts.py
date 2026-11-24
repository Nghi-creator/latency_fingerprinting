"""Strict lifecycle transcript reconstruction, explicitly without media/N2 admission."""

import hashlib
import json
import re

from latency_fingerprinting.evaluation.protocols.physical_challenges import (
    physical_challenge_recipe,
)
from latency_fingerprinting.json_io import strict_json_loads

ERROR = "invalid_challenge_transcript"
PEER = "n11-physical-challenge-peer-v1"
LIFECYCLE = "n11-physical-condition-lifecycle-v1"
OPS = (
    "start",
    "begin_degraded",
    "end_degraded",
    "prepare_relief",
    "dispatch_relief",
    "begin_relief",
    "end_relief",
    "begin_recovery",
    "end_recovery",
    "close",
)


def _require(condition):
    if not condition:
        raise ValueError(ERROR)


def _exact(value, keys):
    _require(type(value) is dict and set(value) == set(keys.split()))


def _integer(value):
    _require(type(value) is int and 0 <= value < 2**63)
    return value


def _wire(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _decode(text, limit):
    _require(type(text) is str and 0 < len(text.encode()) <= limit)
    result = strict_json_loads(text)
    _require(_wire(result) == text.encode())
    return result


def _states(recipe):
    controls = {
        "control_no_injected_fault": (0, 0),
        "control_owned_identity_delay": (34000, 0),
        "control_owned_cpu_pressure": (0, 2),
    }
    if recipe in controls:
        return controls[recipe], controls[recipe]
    value = physical_challenge_recipe(recipe)
    return tuple(value["stages"]["degraded"].values()), tuple(value["stages"]["relief"].values())


def inspect_challenge_transcript(raw):
    """Verify declared command/lifecycle consistency; never infer raw media or labels.

    Requires all ten normal commands and exact original canonical command/ack
    strings. A failed/partial prefix is not a completed transcript; callers must
    retain it as a failed/unavailable case. Clocks are checked within each domain.
    """
    try:
        _require(type(raw) is bytes and 0 < len(raw) <= 4 * 1024 * 1024)
        root = strict_json_loads(raw.decode())
        _exact(root, "schema_version recipe generation channel_id controller_clock records")
        _require(root["schema_version"] == "n11-challenge-command-transcript-v1")
        generation, recipe, channel = root["generation"], root["recipe"], root["channel_id"]
        _exact(generation, "owner pipeline peer")
        _require(
            all(
                type(v) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", v)
                for v in generation.values()
            )
        )
        _require(type(channel) is str and re.fullmatch(r"[a-f0-9]{64}", channel))
        _require(type(recipe) is str and root["controller_clock"] == "controller_monotonic_ns")
        before, after = _states(recipe)
        _require(type(root["records"]) is list and len(root["records"]) == 10)
        clock_id = "challenge-worker-monotonic-" + hashlib.sha256(_wire(generation)).hexdigest()
        state = dict(worker=0, ids=None, cpu=None, cgroup=None)

        def pressure(value, workers):
            _require(type(value) is dict)
            active = value.get("state") == "active"
            _exact(
                value,
                "state active_workers identities cpu_ns cgroup"
                if active
                else "state active_workers identities cpu_ns",
            )
            _require(type(value["active_workers"]) is int and value["active_workers"] == workers)
            ids = value["identities"]
            _require(type(ids) is list)
            if value["state"] in ("unused", "closed_unused"):
                _require(
                    workers == 0 and ids == [] and value["cpu_ns"] == [] and state["ids"] is None
                )
            else:
                _require(
                    len(ids) == len(set(ids)) == 2
                    and all(type(i) is str and re.fullmatch(r"[a-f0-9]{64}", i) for i in ids)
                )
                if state["ids"] is None:
                    state["ids"] = ids
                _require(ids == state["ids"])
                if active:
                    _require(
                        workers == 2 and type(value["cpu_ns"]) is list and len(value["cpu_ns"]) == 2
                    )
                    cpu = [_integer(i) for i in value["cpu_ns"]]
                    _require(
                        state["cpu"] is None
                        or all(a >= b for a, b in zip(cpu, state["cpu"], strict=True))
                    )
                    state["cpu"] = cpu
                    _exact(value["cgroup"], "nr_periods nr_throttled throttled_usec")
                    cg = {k: _integer(v) for k, v in value["cgroup"].items()}
                    _require(
                        state["cgroup"] is None or all(cg[k] >= state["cgroup"][k] for k in cg)
                    )
                    state["cgroup"] = cg
                else:
                    _require(
                        value["state"] == "reaped" and workers == 0 and value["cpu_ns"] is None
                    )

        def witness(value, dose):
            _exact(
                value,
                "method generation read_start_ns read_end_ns delay_us pressure "
                "clock live_authority",
            )
            _require(value["method"] == LIFECYCLE and value["generation"] == generation)
            _require(value["clock"] == "worker_monotonic_ns" and value["live_authority"] is False)
            start, end = _integer(value["read_start_ns"]), _integer(value["read_end_ns"])
            _require(state["worker"] <= start <= end)
            _require(type(value["delay_us"]) is int and value["delay_us"] == dose[0])
            pressure(value["pressure"], dose[1])
            state["worker"] = end
            return end

        previous, controller_end, current = [], 0, (0, 0)
        deadline = ready = dispatch = None
        starts = {}
        for index, (row, op) in enumerate(zip(root["records"], OPS, strict=True), 1):
            _exact(row, "command_json ack_json request_at_ns ack_at_ns")
            _require(controller_end <= _integer(row["request_at_ns"]) <= _integer(row["ack_at_ns"]))
            controller_end = row["ack_at_ns"]
            cmd, ack = _decode(row["command_json"], 4096), _decode(row["ack_json"], 256 * 1024)
            expected = dict(
                method=PEER,
                generation=generation,
                recipe=recipe,
                channel_id=channel,
                sequence=index,
                operation=op,
            )
            _require(_wire(cmd) == _wire(expected))
            _exact(
                ack,
                "method generation recipe channel_id command_sequence operation status "
                "command_sha256 snapshot events live_authority",
            )
            _require(
                ack["method"] == PEER
                and ack["generation"] == generation
                and ack["recipe"] == recipe
                and ack["channel_id"] == channel
            )
            _require(
                type(ack["command_sequence"]) is int
                and ack["command_sequence"] == index
                and ack["operation"] == op
            )
            _require(ack["status"] == "completed" and ack["live_authority"] is False)
            _require(
                ack["command_sha256"]
                == "sha256:" + hashlib.sha256(row["command_json"].encode()).hexdigest()
            )
            snap, events = ack["snapshot"], ack["events"]
            _exact(
                snap,
                "method generation recipe channel_id command_sequence observed_ns state "
                "failed expired condition_deadline_ns ready_not_before_ns witness "
                "cadence_application_verified clock clock_id snapshot_start_ns",
            )
            _require(
                snap["method"] == PEER
                and snap["generation"] == generation
                and snap["recipe"] == recipe
                and snap["channel_id"] == channel
            )
            _require(type(snap["command_sequence"]) is int and snap["command_sequence"] == index)
            _require(
                snap["failed"] is False
                and snap["expired"] is False
                and snap["cadence_application_verified"] is False
            )
            _require(snap["clock"] == "worker_monotonic_ns" and snap["clock_id"] == clock_id)
            _require(snap["state"] == ("closed" if op == "close" else "active"))
            if deadline is None:
                deadline = _integer(snap["condition_deadline_ns"])
            _require(
                _integer(snap["condition_deadline_ns"]) == deadline and deadline >= 20_000_000_000
            )
            _require(
                type(events) is list
                and len(events) <= 32
                and _wire(events[: len(previous)]) == _wire(previous)
            )
            added = events[len(previous) :]
            expected_kind = (
                "condition_applied"
                if op in ("start", "prepare_relief")
                else "phase_start"
                if op.startswith("begin_")
                else "phase_end"
                if op.startswith("end_")
                else "cadence_dispatch_boundary"
                if op == "dispatch_relief"
                else "cleanup"
            )
            count = 0 if op == "prepare_relief" and before == after else 1
            _require(len(added) == count)
            if count:
                e = added[0]
                _require(e.get("kind") == expected_kind)
                if expected_kind == "condition_applied":
                    _exact(e, "kind before after established_not_before_ns")
                    witness(e["before"], current)
                    current = before if op == "start" else after
                    ready = witness(e["after"], current) + 1_000_000_000
                    _require(_integer(e["established_not_before_ns"]) == ready)
                elif expected_kind in ("phase_start", "phase_end"):
                    _exact(e, "kind phase at_ns witness")
                    phase = op.split("_", 1)[1]
                    _require(e["phase"] == phase)
                    end = witness(e["witness"], before if phase == "degraded" else after)
                    at = _integer(e["at_ns"])
                    _require(end <= at)
                    if expected_kind == "phase_start":
                        _require(at >= ready)
                        starts[phase] = at
                        if phase == "relief":
                            _require(dispatch is not None and 0 <= at - dispatch <= 1_750_000_000)
                    else:
                        _require(3_200_000_000 <= at - starts[phase] <= 4_500_000_000)
                        if phase == "relief":
                            _require(at - dispatch < 5_000_000_000)
                    state["worker"] = at
                elif expected_kind == "cadence_dispatch_boundary":
                    _exact(e, "kind at_ns")
                    dispatch = _integer(e["at_ns"])
                    _require(dispatch >= max(ready, state["worker"]))
                    state["worker"] = dispatch
                else:
                    _exact(
                        e,
                        "kind delay_zero pressure_reaped confirmed read_start_ns read_end_ns "
                        "post_delay_us post_pressure generation failed expired live_authority",
                    )
                    _require(
                        all(e[k] is True for k in ("delay_zero", "pressure_reaped", "confirmed"))
                    )
                    _require(
                        all(e[k] is False for k in ("failed", "expired", "live_authority"))
                        and e["generation"] == generation
                    )
                    _require(
                        state["worker"]
                        <= _integer(e["read_start_ns"])
                        <= _integer(e["read_end_ns"])
                        < deadline
                    )
                    _require(type(e["post_delay_us"]) is int and e["post_delay_us"] == 0)
                    pressure(e["post_pressure"], 0)
                    state["worker"] = e["read_end_ns"]
                    current = (0, 0)
            _require(
                deadline - 20_000_000_000 <= state["worker"] <= _integer(snap["snapshot_start_ns"])
            )
            witness(snap["witness"], current)
            _require(state["worker"] <= _integer(snap["observed_ns"]) < deadline)
            _require(_integer(snap["ready_not_before_ns"]) == ready)
            state["worker"] = snap["observed_ns"]
            previous = events
        return dict(
            state="lifecycle_transcript_consistent_media_unverified",
            commands_verified=10,
            phases_verified=3,
            transcript_sha256="sha256:" + hashlib.sha256(raw).hexdigest(),
            recipe=recipe,
            source_media_verified=False,
            resource_dose_verified=False,
            n2_pair_admitted=False,
            admission_reason="changing_pair_not_stable"
            if before != after
            else "separate_source_projection_and_media_links_required",
            acquisition_authority=False,
            empirical_acceptance=False,
        )
    except (KeyError, TypeError, ValueError, UnicodeError, OverflowError):
        raise ValueError(ERROR) from None
