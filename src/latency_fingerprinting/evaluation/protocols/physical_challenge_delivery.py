"""Receiver path and native snapshot joins; browser clocks never align to Linux time."""

import hashlib
import re

from latency_fingerprinting.evaluation.protocols.physical_challenge_receipts import (
    _exact,
    _integer,
    _require,
)
from latency_fingerprinting.json_io import strict_json_loads

ERROR = "invalid_challenge_receiver_delivery"


def inspect_challenge_delivery(acquisition_bytes):
    """Reconcile recorded delivery stages and phase samples, without dose/scoring authority."""
    try:
        _require(type(acquisition_bytes) is bytes and 0 < len(acquisition_bytes) <= 4 * 1024 * 1024)
        a = strict_json_loads(acquisition_bytes.decode())
        _require(
            a["method"] == "n11-physical-challenge-acquisition-v1"
            and a["status"] == "passed"
            and a["live_authority"] is False
        )
        events = a["events"]

        def one(kind, phase=None):
            found = [
                e
                for e in events
                if e.get("kind") == kind and (phase is None or e.get("phase") == phase)
            ]
            _require(len(found) == 1)
            return found[0]

        context = one("n11_challenge_resource_context")["context"]
        origin_text = context["controller_origin_ns"]
        _require(
            type(origin_text) is str
            and origin_text.isascii()
            and origin_text.isdecimal()
            and len(origin_text) <= 19
        )
        origin = _integer(int(origin_text))
        delivery = one("n11_receiver_delivery")
        _require(
            delivery["live_authority"] is False
            and delivery["basis"] == "browser_elapsed_separate_from_linux_monotonic"
        )
        browser, bridge = a["receiver_delivery_browser"], delivery["bridge"]
        relay_event = one("n11_relay_receiver_delivery")
        _require(
            relay_event["basis"] == "relay_wall_clock_ms_separate_from_browser_and_camera_clocks"
        )
        relay = relay_event["rows"]
        _require(all(type(rows) is list for rows in (browser, bridge, relay)))
        _require(2 <= len(browser) == len(bridge) == len(relay) <= 256)
        previous = None
        local = {}
        for i, (b, c, r) in enumerate(zip(browser, bridge, relay, strict=True)):
            _require(
                all(type(row["sequence"]) is int and row["sequence"] == i for row in (b, c, r))
            )
            _require(c["accepted"] is True and r["decision"] == "forwarded")
            elapsed = _integer(b["elapsed_ns"])
            _require(elapsed == _integer(c["browser_elapsed_ns"]))
            received, checked = _integer(c["received_ns"]), _integer(c["checked_ns"])
            relay_at = _integer(r["received_ms"])
            frames, presented = _integer(b["frames_decoded"]), _integer(b["presented_frames"])
            _require(received <= checked)
            if previous is not None:
                pe, pr, pc, pt, pf, pp = previous
                _require(
                    elapsed > pe
                    and received > pr
                    and checked > pc
                    and relay_at >= pt
                    and frames >= pf
                    and presented >= pp
                )
            previous = elapsed, received, checked, relay_at, frames, presented
            seq = c["local_sequence"]
            if seq is not None:
                _integer(seq)
                _require(seq not in local)
                local[seq] = c
        owners, workers = delivery["owner"], delivery["worker"]
        _require(
            type(owners) is list
            and type(workers) is list
            and 2 <= len(owners) == len(workers) <= 256
        )
        # Worker and controller monotonic timestamps are compared only with a shared
        # recorded Linux time namespace, never against browser or relay timestamps.
        trace = one("n11_encoded_event_trace")
        namespace = trace["controller_time_namespace"]
        _require(
            type(namespace) is str
            and re.fullmatch(r"time:\[[0-9]{1,20}\]", namespace)
            and namespace == trace["trace"]["time_namespace"]
        )
        previous = (-1, -1, -1)
        worker_receipts = []
        for o, w in zip(owners, workers, strict=True):
            _exact(o, "sequence observed_ns queued_ns")
            _exact(w, "sequence observed_ns received_ns")
            seq = _integer(o["sequence"])
            _require(type(w["sequence"]) is int and seq == w["sequence"] and seq in local)
            c = local[seq]
            observed, queued, received = (
                _integer(o["observed_ns"]),
                _integer(o["queued_ns"]),
                _integer(w["received_ns"]),
            )
            _require(
                type(w["observed_ns"]) is int and w["observed_ns"] == observed == c["received_ns"]
            )
            _require(c["checked_ns"] <= queued <= received)
            _require(all(x > p for x, p in zip((seq, queued, received), previous, strict=True)))
            previous = seq, queued, received
            worker_receipts.append(received - origin)
        media_event = one("n11_worker_media_progress")
        _require(
            media_event["live_authority"] is False
            and media_event["basis"]
            == "worker_read_brackets_and_controller_receipt_separate_from_browser_clock"
        )
        media = media_event["rows"]
        _require(type(media) is list and 2 <= len(media) <= 128)
        by_sequence = {}
        for row in media:
            seq = _integer(row["sequence"])
            _require(seq not in by_sequence)
            by_sequence[seq] = row
        phase_reports = []
        for phase in ("healthy", "degraded", "relief", "recovery", "post"):
            reference = phase in ("healthy", "post")
            samples = (
                one("n11_challenge_reference", phase)["samples"]
                if reference
                else [
                    e
                    for e in events
                    if e.get("kind") == "n11_pair_native" and e.get("phase") == phase
                ]
            )
            _require(type(samples) is list and 4 <= len(samples) <= 64)
            if reference:
                lo, hi = (_integer(samples[i]["at_ns"]) for i in (0, -1))
            else:
                lo, hi = (
                    _integer(one(kind, phase)["at_ns"])
                    for kind in ("n11_pair_phase_started", "n11_pair_phase_completed")
                )
            _require(lo < hi)
            for row in samples:
                source = by_sequence.get(row["sequence"])
                _require(source is not None)
                _require(
                    _integer(source["controller_received_ns"]) - origin <= _integer(row["at_ns"])
                )
                _require(
                    all(
                        type(source[k]) is int and source[k] == row[k]
                        for k in (
                            "configured_fps",
                            "negotiated_fps",
                            "capture_buffers",
                            "encoded_buffers",
                        )
                    )
                )
                _require(
                    all(
                        type(source[k]) is int and source[k] == row["native_read"][k]
                        for k in ("read_start_ns", "read_end_ns")
                    )
                )
            selected = [i for i, c in enumerate(bridge) if lo <= c["received_ns"] - origin <= hi]
            _require(len(selected) >= 2)
            first, last = browser[selected[0]], browser[selected[-1]]
            _require(
                last["frames_decoded"] > first["frames_decoded"]
                and last["presented_frames"] > first["presented_frames"]
            )
            if phase == "relief":
                _require(sum(lo <= at <= hi for at in worker_receipts) >= 2)
            phase_reports.append(
                dict(
                    phase=phase,
                    linked_native_samples=len(samples),
                    linked_browser_reports=len(selected),
                )
            )
        return dict(
            method="n11-physical-challenge-delivery-links-v1",
            acquisition_sha256="sha256:" + hashlib.sha256(acquisition_bytes).hexdigest(),
            receiver_path_consistent=True,
            browser_reports=len(browser),
            worker_receipts=len(workers),
            phases=phase_reports,
            browser_clock_alignment_verified=False,
            source_media_verified=False,
            resource_dose_verified=False,
            n2_pair_admitted=False,
            empirical_acceptance=False,
            acquisition_authority=False,
        )
    except (ValueError, KeyError, TypeError, UnicodeError, OverflowError, AttributeError):
        raise ValueError(ERROR) from None
