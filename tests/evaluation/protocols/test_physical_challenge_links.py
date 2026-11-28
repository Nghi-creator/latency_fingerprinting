"""Invented clock-separated ACK/reference joins, never native source qualification."""

import json
from copy import deepcopy

import pytest

from latency_fingerprinting.evaluation.protocols.physical_challenge_links import (
    inspect_challenge_links,
)
from tests.evaluation.protocols.test_physical_challenge_receipts import with_start_receipts


def source(recipe="mixed_delay_pressure"):
    t = with_start_receipts(recipe)
    events = []
    commands = {}
    acks = {}
    for row in t["records"]:
        row["request_at_ns"] += 4_000_000_000
        row["ack_at_ns"] += 4_000_000_000
        ack = json.loads(row["ack_json"])
        op = ack["operation"]
        acks[op] = ack
        event = dict(
            kind="n11_challenge_command",
            operation=op,
            read_start_ns=row["request_at_ns"],
            read_end_ns=row["ack_at_ns"],
            ack=ack,
            live_authority=False,
        )
        commands[op] = event
        events.append(event)
    identity = dict(first="a" * 64)
    for phase in ("degraded", "relief", "recovery"):
        for edge, op in (("started", "begin_"), ("completed", "end_")):
            events.append(
                dict(
                    kind="n11_pair_phase_" + edge,
                    phase=phase,
                    at_ns=commands[op + phase][
                        "read_end_ns" if edge == "started" else "read_start_ns"
                    ],
                    worker_identities=identity,
                )
            )
    context = dict(
        method="n11-physical-challenge-observation-v1",
        generation=t["generation"],
        controller_origin_ns="0",
    )
    events.extend(
        [
            dict(kind="n11_challenge_resource_context", context=context),
            dict(kind="n11_challenge_command_transcript", transcript=t, live_authority=False),
            dict(
                kind="n11_pair_dispatched",
                at_ns=commands["dispatch_relief"]["read_start_ns"],
                request=dict(generation=t["generation"]),
            ),
        ]
    )
    for phase in ("healthy", "post"):
        healthy = phase == "healthy"
        state = deepcopy(acks["start" if healthy else "close"]["snapshot"])
        state["command_sequence"] = 0 if healthy else 10
        state["state"] = "fresh" if healthy else "closed"
        if healthy:
            state["condition_deadline_ns"] = state["ready_not_before_ns"] = None
            state["witness"] = deepcopy(acks["start"]["events"][0]["before"])
        rows = []
        for i in range(4):
            s = deepcopy(state)
            at = (
                100 + i * 100
                if healthy
                else acks["close"]["snapshot"]["observed_ns"] + 100 + i * 100
            )
            s["snapshot_start_ns"] = s["witness"]["read_start_ns"] = at
            s["witness"]["read_end_ns"] = s["observed_ns"] = at + 1
            controller = (
                0 if healthy else commands["close"]["read_end_ns"] + 100_000_000
            ) + i * 1_100_000_000
            rows.append(
                dict(
                    at_ns=controller,
                    configured_fps=30,
                    negotiated_fps=30,
                    condition_state=s,
                    container_cpu_read=dict(read_start_ns=controller, read_end_ns=controller + 100),
                )
            )
        events.append(
            dict(
                kind="n11_challenge_reference",
                phase=phase,
                samples=rows,
                worker_identities=identity,
                live_authority=False,
            )
        )
    return dict(
        method="n11-physical-challenge-acquisition-v1",
        role="engineering_challenge_raw_phases_no_pair_or_diagnostic_label",
        status="passed",
        live_authority=False,
        challenge_recipe=recipe,
        mode="engineering-n11-physical-challenge-" + recipe,
        events=events,
    )


def inspect(value):
    return inspect_challenge_links(json.dumps(value).encode())


@pytest.mark.parametrize(
    "recipe",
    [
        "mixed_delay_pressure",
        "delay_to_pressure",
        "pressure_to_delay",
        "control_no_injected_fault",
        "control_owned_identity_delay",
        "control_owned_cpu_pressure",
    ],
)
def test_six_recipes_join_original_commands_and_references(recipe):
    result = inspect(source(recipe))
    assert result["command_phase_links_verified"] is True
    assert len(result["references"]) == 2
    assert not result["source_media_verified"] and not result["n2_pair_admitted"]


@pytest.mark.parametrize(
    "change",
    [
        "ack",
        "origin",
        "phase",
        "dispatch",
        "generation",
        "reference_identity",
        "foreign_delay",
        "stale_state",
        "post_before_cleanup",
        "missing_command",
    ],
)
def test_resealed_source_links_reject_cross_case_or_out_of_phase_evidence(change):
    a = source()
    events = a["events"]
    command = next(e for e in events if e["kind"] == "n11_challenge_command")
    ref = next(e for e in events if e["kind"] == "n11_challenge_reference" and e["phase"] == "post")
    if change == "ack":
        command["ack"]["snapshot"]["recipe"] = "foreign"
    elif change == "origin":
        next(e for e in events if e["kind"] == "n11_challenge_resource_context")["context"][
            "controller_origin_ns"
        ] = "100"
    elif change == "phase":
        next(e for e in events if e["kind"] == "n11_pair_phase_started")["at_ns"] = 0
    elif change == "dispatch":
        next(e for e in events if e["kind"] == "n11_pair_dispatched")["at_ns"] = 0
    elif change == "generation":
        next(e for e in events if e["kind"] == "n11_pair_dispatched")["request"]["generation"] = {
            "owner": "foreign",
            "pipeline": "foreign",
            "peer": "foreign",
        }
    elif change == "reference_identity":
        ref["worker_identities"] = {"first": "b" * 64}
    elif change == "foreign_delay":
        ref["samples"][0]["condition_state"]["witness"]["delay_us"] = 34000
    elif change == "stale_state":
        ref["samples"][1]["condition_state"] = deepcopy(ref["samples"][0]["condition_state"])
    elif change == "post_before_cleanup":
        ref["samples"][0]["container_cpu_read"]["read_start_ns"] = 0
    else:
        events.remove(command)
    with pytest.raises(ValueError, match="invalid_challenge_source_links"):
        inspect(a)
