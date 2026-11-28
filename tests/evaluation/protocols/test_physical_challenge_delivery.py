"""Invented delivery clocks and snapshot joins; no browser/native experiment."""

import json

import pytest

from latency_fingerprinting.evaluation.protocols.physical_challenge_delivery import (
    inspect_challenge_delivery,
)


def source():
    origin = 10**12
    browser = []
    bridge = []
    relay = []
    owner = []
    worker = []
    for i in range(115):
        at = origin + i * 200_000_000
        browser.append(
            dict(
                sequence=i, elapsed_ns=i * 210_000_000, frames_decoded=i * 6, presented_frames=i * 6
            )
        )
        bridge.append(
            dict(
                sequence=i,
                browser_elapsed_ns=i * 210_000_000,
                received_ns=at,
                checked_ns=at + 1,
                local_sequence=None if i == 0 else i - 1,
                accepted=True,
            )
        )
        relay.append(dict(sequence=i, received_ms=1700000000000 + i * 205, decision="forwarded"))
        if 35 <= i <= 60:
            owner.append(dict(sequence=i - 1, observed_ns=at, queued_ns=at + 2))
            worker.append(dict(sequence=i - 1, observed_ns=at, received_ns=at + 3))
    events = [
        dict(kind="n11_challenge_resource_context", context=dict(controller_origin_ns=str(origin))),
        dict(
            kind="n11_receiver_delivery",
            bridge=bridge,
            owner=owner,
            worker=worker,
            live_authority=False,
            basis="browser_elapsed_separate_from_linux_monotonic",
        ),
        dict(
            kind="n11_relay_receiver_delivery",
            rows=relay,
            basis="relay_wall_clock_ms_separate_from_browser_and_camera_clocks",
        ),
        dict(
            kind="n11_encoded_event_trace",
            controller_time_namespace="time:[123]",
            trace=dict(time_namespace="time:[123]"),
        ),
    ]
    media = []
    seq = 0
    for phase, start in [
        ("healthy", 200_000_000),
        ("degraded", 4_000_000_000),
        ("relief", 8_000_000_000),
        ("recovery", 14_000_000_000),
        ("post", 18_000_000_000),
    ]:
        rows = []
        for i in range(4):
            at = start + i * 1_100_000_000
            read = dict(read_start_ns=at, read_end_ns=at + 10)
            row = dict(
                at_ns=at,
                sequence=seq,
                configured_fps=24 if phase == "relief" else 30,
                negotiated_fps=24 if phase == "relief" else 30,
                capture_buffers=seq * 30,
                encoded_buffers=seq * 30,
                native_read=read,
            )
            rows.append(row)
            media.append(
                dict(
                    **{
                        k: row[k]
                        for k in (
                            "sequence",
                            "configured_fps",
                            "negotiated_fps",
                            "capture_buffers",
                            "encoded_buffers",
                        )
                    },
                    **read,
                    controller_received_ns=origin + at - 1,
                )
            )
            seq += 1
        if phase in ("healthy", "post"):
            events.append(dict(kind="n11_challenge_reference", phase=phase, samples=rows))
        else:
            events.extend(dict(kind="n11_pair_native", phase=phase, **row) for row in rows)
            for edge, i in [("started", 0), ("completed", -1)]:
                events.append(
                    dict(kind="n11_pair_phase_" + edge, phase=phase, at_ns=rows[i]["at_ns"])
                )
    events.append(
        dict(
            kind="n11_worker_media_progress",
            live_authority=False,
            basis="worker_read_brackets_and_controller_receipt_separate_from_browser_clock",
            rows=media,
        )
    )
    return dict(
        method="n11-physical-challenge-acquisition-v1",
        status="passed",
        live_authority=False,
        events=events,
        receiver_delivery_browser=browser,
    )


def inspect(a):
    return inspect_challenge_delivery(json.dumps(a).encode())


def test_browser_relay_bridge_owner_worker_and_five_phases_join_without_clock_alignment():
    result = inspect(source())
    assert result["receiver_path_consistent"] is True
    assert len(result["phases"]) == 5 and result["worker_receipts"] == 26
    assert not result["browser_clock_alignment_verified"] and not result["source_media_verified"]


@pytest.mark.parametrize(
    "change",
    [
        "sequence",
        "elapsed",
        "dropped",
        "bridge",
        "worker",
        "namespace",
        "native_counter",
        "native_bracket",
        "native_receipt",
        "phase_support",
    ],
)
def test_receiver_and_native_splicing_is_rejected(change):
    a = source()
    events = a["events"]
    d = next(e for e in events if e["kind"] == "n11_receiver_delivery")
    if change == "sequence":
        a["receiver_delivery_browser"][2]["sequence"] = 1
    elif change == "elapsed":
        d["bridge"][1]["browser_elapsed_ns"] += 1
    elif change == "dropped":
        next(e for e in events if e["kind"] == "n11_relay_receiver_delivery")["rows"][1][
            "decision"
        ] = "rejected"
    elif change == "bridge":
        d["owner"][0]["observed_ns"] += 1
    elif change == "worker":
        d["worker"][0]["received_ns"] = 0
    elif change == "namespace":
        next(e for e in events if e["kind"] == "n11_encoded_event_trace")["trace"][
            "time_namespace"
        ] = "time:[999]"
    elif change == "phase_support":
        a["receiver_delivery_browser"][40]["frames_decoded"] = 0
    else:
        row = next(e for e in events if e["kind"] == "n11_worker_media_progress")["rows"][4]
        if change == "native_counter":
            row["encoded_buffers"] += 1
        elif change == "native_bracket":
            row["read_end_ns"] += 1
        else:
            row["controller_received_ns"] += 10**12
    with pytest.raises(ValueError, match="invalid_challenge_receiver_delivery"):
        inspect(a)


def test_independent_browser_and_relay_clock_origins_do_not_change_joins():
    a = source()
    for row in a["receiver_delivery_browser"]:
        row["elapsed_ns"] += 10**14
    for e in a["events"]:
        if e["kind"] == "n11_receiver_delivery":
            for row in e["bridge"]:
                row["browser_elapsed_ns"] += 10**14
        elif e["kind"] == "n11_relay_receiver_delivery":
            for row in e["rows"]:
                row["received_ms"] += 10**9
    assert inspect(a)["receiver_path_consistent"] is True
