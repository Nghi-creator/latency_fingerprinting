"""N9 production behavior against preimplementation literals and hostile retained roots."""

import copy
import math

import pytest

from latency_fingerprinting.passive_gating import (
    PassiveBaseline,
    PassiveGatePolicy,
    PassiveGateResult,
    arithmetic,
    create_passive_replay,
    evaluate_passive_replay,
    fit_passive_baseline,
)
from latency_fingerprinting.passive_gating.policy_release import approved_policy_payload

from .cases import POLICY, baseline, canonical, evidence, replay_payload, seal, window
from .test_design import VECTORS


@pytest.mark.parametrize("case", VECTORS["numeric_cases"], ids=lambda c: c["case_id"])
def test_production_fraction_arithmetic_against_decimal_literals(case):
    operation = arithmetic.median if case["operation"] == "median" else arithmetic.ratio
    args = [case["values"]] if case["operation"] == "median" else case["values"]
    if case.get("error"):
        with pytest.raises(ValueError, match="^invalid_passive_arithmetic$"):
            operation(*args)
    else:
        assert operation(*args).hex() == case["expected"].hex()


@pytest.mark.parametrize("case", VECTORS["baseline_cases"], ids=lambda c: c["case_id"])
def test_production_baseline_arithmetic_against_independent_literals(case):
    actual = arithmetic.statistics(case["groups"])
    assert actual == dict(
        center=case["center"],
        raw_mad=case["raw_mad"],
        reason_codes=case["reasons"],
        state="rejected" if case["reasons"] else "provisional",
    )


@pytest.mark.parametrize("case", VECTORS["classification_cases"], ids=lambda c: c["case_id"])
def test_production_exact_classification(case):
    assert arithmetic.classify(case["fps"], case["center"]) == case["classification"]


def test_literal_root_and_pure_factory_parity(roots):
    ev, windows, b, r = roots
    actual = fit_passive_baseline(
        ev, {k: v for k, v in windows.items() if k.startswith("train")}, POLICY
    )
    assert actual.model_dump(mode="json") == b
    supplied = PassiveBaseline.model_validate_json(canonical(b))
    assert supplied == actual
    generated = create_passive_replay(
        supplied,
        mode="validation",
        stream={k: v for k, v in r["stream"].items() if k != "stream_id"},
        start_ms=0,
        windows=r["windows"],
        events=r["events"],
    )
    assert generated.model_dump(mode="json") == r
    result = evaluate_passive_replay(supplied, generated, POLICY)
    assert result.final_state.status == "degraded"
    assert result.final_state.bad_duration_ms == 6000
    assert result.final_state.last_proposal_ms == 6000
    assert result.counts.proposals == 1
    assert [row.observed_fps for row in result.rows] == [40.0] * 3
    assert [row.effect_hypothesis for row in result.rows] == [
        None,
        None,
        "received_fps_degradation",
    ]
    assert all(
        row.cause_label is None and row.profile_hypotheses == "unavailable" for row in result.rows
    )
    assert PassiveGateResult.model_validate_json(result.model_dump_json(by_alias=True)) == result
    assert PassiveGateResult.model_validate(result) == result
    ev["dataset"]["entries"].clear()
    b["inputs"].clear()
    r["events"].clear()
    assert result.baseline.inputs and result.replay.events
    with pytest.raises(ValueError):
        result.final_state.proposals = 0
    with pytest.raises(TypeError):
        result.baseline.strata[0].scope.context["versions"]["another"] = "version"


def literal_history(case):
    originals = {}
    for event in case["events"]:
        if event["kind"] != "window" or event.get("alias"):
            continue
        key = event["key"]
        w = window(
            "literal-" + key,
            start=event["start_ms"],
            end=event["at_ms"],
            fps=event["fps"],
            query=True,
        )
        if event.get("clock_changed"):
            w["clock"]["domain_id"] = "changed-domain"
        if event.get("scope_changed"):
            w["effective_settings"]["targetFps"] = 90
        originals[key] = w
    keys = list(originals)
    supplied = list(originals.values())
    alias_indices = {}
    for event in case["events"]:
        if event.get("alias"):
            alias_indices[event["key"]] = len(supplied)
            supplied.append(copy.deepcopy(originals[event["key"]]))
    ev, windows = evidence(supplied)
    b = baseline(ev, windows)
    events = []
    for e in case["events"]:
        identifier = None
        if e["kind"] == "window":
            idx = alias_indices[e["key"]] if e.get("alias") else keys.index(e["key"])
            identifier = f"query-{idx:03d}"
        events.append(
            dict(
                kind=e["kind"],
                at_ms=e["at_ms"],
                entry_id=identifier,
                reset_reason=e.get("reset_reason"),
            )
        )
    return b, replay_payload(b, windows, events)


@pytest.mark.parametrize(
    "case",
    [c for c in VECTORS["replay_cases"] if not any(e.get("unavailable") for e in c["events"])],
    ids=lambda c: c["case_id"],
)
def test_full_typed_replay_against_frozen_literal_histories(case):
    b, r = literal_history(case)
    result = evaluate_passive_replay(b, r, POLICY)
    actual = [
        dict(
            status=row.state.status,
            recommendation=row.recommendation,
            reasons=list(row.reason_codes),
            bad_windows=row.state.bad_windows,
            good_windows=row.state.good_windows,
            proposals=row.state.proposals,
            degraded_latched=row.state.degraded_latched,
        )
        for row in result.rows
    ]
    assert actual == case["expected"]
    assert evaluate_passive_replay(b, r, POLICY) == result
    c = result.counts
    assert c.window_events + c.tick_events + c.reset_events == c.total_events
    assert (
        c.accepted_windows
        + c.ignored_duplicate_windows
        + c.ignored_out_of_order_windows
        + c.unavailable_windows
        == c.window_events
    )


@pytest.mark.parametrize(
    "change",
    [
        "center",
        "mad",
        "group_value",
        "group_entries",
        "selected",
        "reason",
        "scope",
        "counts",
        "state",
        "input_order",
        "missing_window",
        "source",
        "partition",
        "review",
        "extra",
        "hash",
        "copy",
    ],
)
def test_rehashed_false_baseline_never_validates(roots, change):
    _, _, b, _ = roots
    s = b["strata"][0]
    selected = next(i for i in b["inputs"] if i["selected"])
    if change == "center":
        s["center"] = 90.0
    elif change == "mad":
        s["raw_mad"] = 1.0
    elif change == "group_value":
        s["groups"][0]["value"] = 90.0
    elif change == "group_entries":
        s["groups"][0]["entry_ids"] = []
    elif change == "selected":
        selected["selected"] = False
    elif change == "reason":
        selected["reason_codes"] = ["not_training"]
    elif change == "scope":
        s["scope"]["effective_settings"]["targetFps"] = 30
    elif change == "counts":
        b["counts"]["selected_entries"] = 4
    elif change == "state":
        b["state"] = "rejected"
    elif change == "input_order":
        b["inputs"].reverse()
    elif change == "missing_window":
        selected["window"] = None
    elif change == "source":
        selected["window"]["run_id"] = "foreign"
    elif change == "partition":
        b["evidence"]["report"]["entries"][0]["partition_id"] = "partition-" + "f" * 64
    elif change == "review":
        b["evidence"]["dataset"]["reviews"][0]["outcome"] = "uncertain"
    elif change == "extra":
        b["trusted"] = True
    elif change == "hash":
        b["content_hash"] = "sha256:" + "0" * 64
    elif change == "copy":
        m = PassiveBaseline.model_validate(b)
        bad = m.strata[0].model_copy(update={"center": 90.0})
        with pytest.raises(ValueError):
            PassiveBaseline.model_validate(m.model_copy(update={"strata": (bad,)}))
        return
    if change != "hash":
        seal(b, "baseline_id", "passive-baseline-")
    with pytest.raises(ValueError):
        PassiveBaseline.model_validate(b)


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "healthy"),
        ("degraded_latched", False),
        ("watermark_ms", 0),
        ("last_window_end_ms", None),
        ("last_valid_end_ms", None),
        ("barrier_ms", 1),
        ("bad_windows", 0),
        ("bad_duration_ms", 1),
        ("good_windows", 1),
        ("good_duration_ms", 1),
        ("proposals", 0),
        ("last_proposal_ms", None),
        ("stream_invalidated", True),
    ],
)
def test_every_rehashed_state_field_reconstructs(roots, field, value):
    _, _, b, r = roots
    p = evaluate_passive_replay(b, r, POLICY).model_dump(mode="json")
    p["rows"][-1]["state"][field] = value
    p["final_state"][field] = value
    seal(p, "result_id", "passive-gate-")
    with pytest.raises(ValueError, match="does not reconstruct"):
        PassiveGateResult.model_validate(p)


@pytest.mark.parametrize(
    "field,value",
    [
        ("classification", "band"),
        ("observed_fps", 41.0),
        ("relative_fps", 0.9),
        ("recommendation", "no_action"),
        ("reason_codes", ["healthy"]),
        ("effect_hypothesis", None),
        ("cause_label", "host_contention"),
        ("profile_hypotheses", "verified"),
        ("novelty_key", "passive-window-" + "0" * 64),
        ("event_index", 0),
        ("event_id", "passive-event-" + "0" * 64),
        ("entry_id", "train-0"),
        ("window_artifact_id", "unknown"),
    ],
)
def test_every_rehashed_row_field_reconstructs(roots, field, value):
    _, _, b, r = roots
    p = evaluate_passive_replay(b, r, POLICY).model_dump(mode="json")
    p["rows"][-1][field] = value
    seal(p, "result_id", "passive-gate-")
    with pytest.raises(ValueError):
        PassiveGateResult.model_validate(p)


def test_approved_policy_copies_are_not_mutable_or_self_approvable():
    p = approved_policy_payload()
    m = PassiveGatePolicy.model_validate(p)
    assert m.model_dump(mode="json") == POLICY
    p["gates"]["minimum_bad_windows"] = 1
    seal(p, "policy_id", "passive-gate-policy-")
    with pytest.raises(ValueError):
        PassiveGatePolicy.model_validate(p)
    with pytest.raises(ValueError):
        PassiveGatePolicy.model_validate(
            m.model_copy(update={"gates": m.gates.model_copy(update={"minimum_bad_windows": 1})})
        )
    assert approved_policy_payload() == POLICY


@pytest.mark.parametrize("value", [True, "1", None, float("inf"), float("nan"), 10**1000, -1.0])
def test_arithmetic_domain_failures_are_fixed(value):
    with pytest.raises(ValueError, match="^invalid_passive_arithmetic$"):
        arithmetic.classify(value, 60.0)


def test_computed_ratio_zero_is_positive():
    assert math.copysign(1, arithmetic.ratio(-0.0, 60.0)) == 1
