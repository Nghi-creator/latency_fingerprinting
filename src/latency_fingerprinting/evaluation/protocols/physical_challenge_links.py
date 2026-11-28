"""Join original challenge ACKs, controller phases and fresh absence references."""

import hashlib
import re

from latency_fingerprinting.evaluation.protocols.physical_challenge_receipts import (
    LIFECYCLE,
    OPS,
    PEER,
    _decode,
    _exact,
    _integer,
    _require,
    _wire,
    inspect_challenge_transcript,
)
from latency_fingerprinting.json_io import strict_json_loads

ERROR = "invalid_challenge_source_links"


def inspect_challenge_links(acquisition_bytes):
    """Check supplied source links; no clock alignment, dose, or scoring authority."""
    try:
        _require(type(acquisition_bytes) is bytes and 0 < len(acquisition_bytes) <= 4 * 1024 * 1024)
        a = strict_json_loads(acquisition_bytes.decode())
        _require(
            a["method"] == "n11-physical-challenge-acquisition-v1"
            and a["status"] == "passed"
            and a["live_authority"] is False
        )
        _require(a["role"] == "engineering_challenge_raw_phases_no_pair_or_diagnostic_label")
        events = a["events"]
        _require(type(events) is list and all(type(e) is dict for e in events))

        def one(kind, phase=None):
            found = [
                e
                for e in events
                if e.get("kind") == kind and (phase is None or e.get("phase") == phase)
            ]
            _require(len(found) == 1)
            return found[0]

        t = one("n11_challenge_command_transcript")
        _require(t["live_authority"] is False)
        transcript = t["transcript"]
        lifecycle = inspect_challenge_transcript(_wire(transcript), require_pressure_start=True)
        recipe, generation = transcript["recipe"], transcript["generation"]
        _require(
            a["challenge_recipe"] == recipe
            and a["mode"] == "engineering-n11-physical-challenge-" + recipe
        )
        context = one("n11_challenge_resource_context")["context"]
        _require(
            context["method"] == "n11-physical-challenge-observation-v1"
            and context["generation"] == generation
        )
        origin = context["controller_origin_ns"]
        _require(type(origin) is str and re.fullmatch(r"[0-9]{1,19}", origin))
        origin = _integer(int(origin))
        _require(one("n11_pair_dispatched")["request"]["generation"] == generation)
        command_events = [e for e in events if e.get("kind") == "n11_challenge_command"]
        _require(len(command_events) == 10)
        commands, acknowledgments = {}, {}
        for op, row, event in zip(OPS, transcript["records"], command_events, strict=True):
            _require(event["operation"] == op and event["live_authority"] is False)
            ack = _decode(row["ack_json"], 256 * 1024)
            _require(_wire(event["ack"]) == _wire(ack))
            start, end = _integer(event["read_start_ns"]), _integer(event["read_end_ns"])
            _require(start <= row["request_at_ns"] - origin <= row["ack_at_ns"] - origin <= end)
            commands[op], acknowledgments[op] = (start, end), ack
        identity = None
        bounds = {}
        previous = commands["start"][1]
        for phase in ("degraded", "relief", "recovery"):
            start, end = (
                one("n11_pair_phase_started", phase),
                one("n11_pair_phase_completed", phase),
            )
            lo, hi = _integer(start["at_ns"]), _integer(end["at_ns"])
            current = start["worker_identities"]
            _exact(current, "first")
            _require(
                type(current["first"]) is str and re.fullmatch(r"[a-f0-9]{64}", current["first"])
            )
            _require(identity is None or _wire(current) == _wire(identity))
            identity = current
            _require(
                previous
                <= commands["begin_" + phase][0]
                <= commands["begin_" + phase][1]
                <= lo
                < hi
                <= commands["end_" + phase][0]
            )
            _require(3_200_000_000 <= hi - lo <= 4_500_000_000)
            bounds[phase] = (lo, hi)
            previous = commands["end_" + phase][1]
        dispatch = _integer(one("n11_pair_dispatched")["at_ns"])
        _require(
            commands["end_degraded"][1]
            <= commands["prepare_relief"][0]
            <= commands["prepare_relief"][1]
            <= dispatch
            <= commands["dispatch_relief"][0]
            <= commands["dispatch_relief"][1]
            <= commands["begin_relief"][0]
        )
        _require(commands["end_recovery"][1] <= commands["close"][0])
        clock = "challenge-worker-monotonic-" + hashlib.sha256(_wire(generation)).hexdigest()
        first_worker = acknowledgments["start"]["events"][0]["before"]["read_start_ns"]
        last_worker = acknowledgments["close"]["snapshot"]["observed_ns"]
        terminal_pressure = acknowledgments["close"]["snapshot"]["witness"]["pressure"]
        reference_reports = []
        for phase, sequence in (("healthy", 0), ("post", 10)):
            e = one("n11_challenge_reference", phase)
            _require(
                e["live_authority"] is False and _wire(e["worker_identities"]) == _wire(identity)
            )
            rows = e["samples"]
            _require(type(rows) is list and 4 <= len(rows) <= 64)
            prior = observed = -1
            for row in rows:
                at = _integer(row["at_ns"])
                _require(at > prior and row["configured_fps"] == row["negotiated_fps"] == 30)
                state = row["condition_state"]
                _exact(
                    state,
                    "method channel_id generation recipe command_sequence observed_ns "
                    "state failed expired "
                    "condition_deadline_ns ready_not_before_ns witness "
                    "cadence_application_verified "
                    "clock clock_id snapshot_start_ns",
                )
                _require(
                    state["method"] == PEER
                    and state["generation"] == generation
                    and state["recipe"] == recipe
                    and state["channel_id"] == transcript["channel_id"]
                )
                _require(
                    type(state["command_sequence"]) is int
                    and state["command_sequence"] == sequence
                    and state["state"] == ("fresh" if phase == "healthy" else "closed")
                )
                _require(
                    state["failed"]
                    is state["expired"]
                    is state["cadence_application_verified"]
                    is False
                    and state["clock"] == "worker_monotonic_ns"
                    and state["clock_id"] == clock
                )
                w = state["witness"]
                _exact(
                    w,
                    "method generation read_start_ns read_end_ns delay_us pressure "
                    "clock live_authority",
                )
                _require(
                    w["method"] == LIFECYCLE
                    and w["generation"] == generation
                    and w["clock"] == "worker_monotonic_ns"
                    and w["live_authority"] is False
                    and type(w["delay_us"]) is int
                    and w["delay_us"] == 0
                )
                _require(
                    observed
                    < _integer(state["snapshot_start_ns"])
                    <= _integer(w["read_start_ns"])
                    <= _integer(w["read_end_ns"])
                    <= _integer(state["observed_ns"])
                )
                observed, prior = state["observed_ns"], at
                if phase == "healthy":
                    _require(
                        observed <= first_worker
                        and state["condition_deadline_ns"] is None
                        and state["ready_not_before_ns"] is None
                    )
                    _require(
                        _wire(w["pressure"])
                        == _wire(dict(state="unused", active_workers=0, identities=[], cpu_ns=[]))
                    )
                    _require(
                        _integer(row["container_cpu_read"]["read_end_ns"]) < commands["start"][0]
                    )
                else:
                    _require(
                        state["snapshot_start_ns"] >= last_worker
                        and _wire(w["pressure"]) == _wire(terminal_pressure)
                    )
                    _require(
                        state["condition_deadline_ns"]
                        == acknowledgments["close"]["snapshot"]["condition_deadline_ns"]
                        and state["ready_not_before_ns"]
                        == acknowledgments["close"]["snapshot"]["ready_not_before_ns"]
                    )
                    _require(
                        _integer(row["container_cpu_read"]["read_start_ns"]) > commands["close"][1]
                    )
            _require(rows[-1]["at_ns"] - rows[0]["at_ns"] >= 3_200_000_000)
            reference_reports.append(
                dict(phase=phase, samples=len(rows), owned_absence_consistent=True)
            )
        return dict(
            method="n11-physical-challenge-source-links-v1",
            acquisition_sha256="sha256:" + hashlib.sha256(acquisition_bytes).hexdigest(),
            command_phase_links_verified=True,
            references=reference_reports,
            lifecycle=lifecycle,
            source_media_verified=False,
            receiver_delivery_verified=False,
            resource_dose_verified=False,
            n2_pair_admitted=False,
            empirical_acceptance=False,
            acquisition_authority=False,
        )
    except (ValueError, KeyError, TypeError, UnicodeError, OverflowError, AttributeError):
        raise ValueError(ERROR) from None
