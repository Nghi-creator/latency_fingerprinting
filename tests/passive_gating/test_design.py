"""Independent synthetic N9 design examples; no N9 production implementation."""

import copy
import hashlib
import json
import math
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs/passive_gating"
POLICY_HASH = "sha256:07beb342e6ae7387a6edb2235ba0b26a5122fb3fffb5f83b7da2e7109f48a5ca"
VECTOR_HASH = "3c024642afbfe43aa9fded4cbd0202b11ec23afb7aed7fe2d7e5799bcf1e8660"
POLICY = json.loads((DOCS / "N9_PASSIVE_POLICY_SPEC.json").read_bytes())
VECTORS = json.loads((DOCS / "N9_DESIGN_VECTORS.json").read_bytes())


def canonical(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode()


def operand(value):
    if type(value) is not float or not math.isfinite(value) or value < 0:
        raise ValueError("invalid_design_arithmetic")
    return Decimal.from_float(value)


def rounded(value):
    result = float(value)
    if not math.isfinite(result) or (value != 0 and result == 0):
        raise ValueError("invalid_design_arithmetic")
    return 0.0 if result == 0 else result


def median(values):
    if not 1 <= len(values) <= 256:
        raise ValueError("invalid_design_arithmetic")
    with localcontext() as context:
        context.prec = 2200
        ordered = sorted(operand(value) for value in values)
        half = len(ordered) // 2
        return rounded(
            ordered[half] if len(ordered) % 2 else (ordered[half - 1] + ordered[half]) / 2
        )


def ratio(value, center):
    with localcontext() as context:
        context.prec = 2200
        numerator, denominator = operand(value), operand(center)
        if denominator <= 0:
            raise ValueError("invalid_design_arithmetic")
        return rounded(numerator / denominator)


def classify(value, center):
    # Integer cross-products on exact Decimal representations, never rounded ratios.
    with localcontext() as context:
        context.prec = 2200
        value, center = operand(value), operand(center)
        if center <= 0:
            raise ValueError("invalid_design_arithmetic")
        if 5 * value <= 4 * center:
            return "low"
        return "recovered" if 10 * value >= 9 * center else "band"


def fit(groups):
    values = [median(group) for group in groups if group]
    center = median(values) if values else None
    with localcontext() as context:
        context.prec = 2200
        spread = (
            median([rounded(abs(operand(value) - operand(center))) for value in values])
            if values
            else None
        )
    reasons = []
    if len(groups) < 5:
        reasons.append("insufficient_training_groups")
    if len(values) < 5:
        reasons.append("insufficient_metric_groups")
    if not groups or 5 * len(values) < 4 * len(groups):
        reasons.append("insufficient_availability")
    if center is None or center <= 0:
        reasons.append("baseline_center_not_positive")
    return center, spread, reasons


def elapsed(value):
    if type(value) is not int or not 0 <= value <= 9007199254740991:
        raise ValueError("invalid_design_time")
    return value


def replay(case):
    """Test-only oracle on prevalidated abstract operands, not a public API.

    Literal tables supply expectations. This deliberately has no N6 reader,
    production model, production arithmetic or replay implementation dependency.
    """
    if not 0 <= len(case["events"]) <= 256:
        raise ValueError("invalid_design_event_limit")
    watermark = barrier = elapsed(case["start_ms"])
    last_end = last_valid = last_proposal = None
    status, latch, invalidated = "unknown", False, False
    bad = good = bad_ms = good_ms = proposals = 0
    seen, rows = set(), []

    def clear():
        nonlocal status, latch, last_valid, bad, good, bad_ms, good_ms
        status, latch, last_valid = "unknown", False, None
        bad = good = bad_ms = good_ms = 0

    for event in case["events"]:
        at = elapsed(event["at_ms"])
        kind = event["kind"]
        if kind not in {"window", "tick", "reset"}:
            raise ValueError("invalid_design_event")
        if kind == "window":
            start = elapsed(event["start_ms"])
            if start >= at:
                raise ValueError("invalid_design_time")
        action, reasons = "no_action", []
        if invalidated:
            reasons = ["stream_invalidated"]
        elif kind == "reset":
            watermark = barrier = max(watermark, at)
            invalidated = True
            clear()
            reasons = ["stream_reset"]
        elif kind == "tick":
            if at < watermark:
                invalidated = True
                clear()
                reasons = ["clock_reversed"]
            else:
                watermark = at
                if last_valid is not None and at - last_valid >= 5000:
                    clear()
                    barrier = at
                    reasons = ["stale"]
                else:
                    reasons = ["tick_only"]
        elif event.get("unavailable") in {"missing_measurements", "not_passive_window"}:
            watermark = barrier = max(watermark, at)
            clear()
            reasons = [event["unavailable"]]
        elif event.get("clock_changed"):
            invalidated = True
            clear()
            reasons = ["clock_scope_changed"]
        elif event.get("alias") or event["key"] in seen:
            reasons = ["duplicate_window"]
        else:
            seen.add(event["key"])
            if at < watermark or (last_end is not None and at <= last_end):
                reasons = ["out_of_order"]
            elif event.get("scope_changed"):
                watermark = barrier = at
                invalidated = True
                clear()
                reasons = ["scope_changed"]
            elif (last_end is not None and start < last_end) or start < barrier:
                reasons = [
                    "overlapping_window"
                    if last_end is not None and start < last_end
                    else "pre_barrier_window"
                ]
                watermark = last_end = barrier = at
                clear()
            else:
                if last_end is not None and start > last_end:
                    clear()
                    barrier = start
                    reasons.append("gap_reset")
                watermark = last_end = at
                if event.get("unavailable"):
                    clear()
                    barrier = at
                    reasons.append(event["unavailable"])
                else:
                    if not 1000 <= at - start <= 10000:
                        raise ValueError("invalid_design_window")
                    last_valid = at
                    ratio(event["fps"], case["center"])
                    category = classify(event["fps"], case["center"])
                    if category == "low":
                        good = good_ms = 0
                        bad, bad_ms = bad + 1, bad_ms + at - start
                        if bad < 3 or bad_ms < 6000:
                            status = "degraded" if latch else "pending_degradation"
                            action, reason = "observe", "entry_pending"
                        else:
                            status, latch = "degraded", True
                            if proposals >= 3:
                                reason = "proposal_budget_exhausted"
                            elif last_proposal is not None and at - last_proposal < 30000:
                                action, reason = "cooldown", "cooldown_active"
                            else:
                                proposals += 1
                                last_proposal = at
                                action, reason = "probe", "persistent_degradation"
                    elif category == "recovered":
                        bad = bad_ms = 0
                        good, good_ms = good + 1, good_ms + at - start
                        if good >= 2 and good_ms >= 4000:
                            status, latch, reason = "healthy", False, "healthy"
                        else:
                            status = "recovering" if latch else "pending_recovery"
                            action, reason = "observe", "recovery_pending"
                    else:
                        bad = good = bad_ms = good_ms = 0
                        status = "degraded" if latch else "unknown"
                        action, reason = "observe", "hysteresis_band"
                    reasons.append(reason)
        rows.append(
            dict(
                status=status,
                recommendation=action,
                reasons=reasons,
                bad_windows=bad,
                good_windows=good,
                proposals=proposals,
                degraded_latched=latch,
            )
        )
        assert bad_ms >= bad * 1000 and good_ms >= good * 1000
        assert bad_ms <= bad * 10000 and good_ms <= good * 10000
        assert 0 <= proposals <= 3
    return rows


def test_policy_pin_and_registry_meaning():
    assert (DOCS / "N9_PASSIVE_POLICY_SPEC.json").read_bytes() == canonical(POLICY)
    content = {k: v for k, v in POLICY.items() if k not in {"content_hash", "policy_id"}}
    assert "sha256:" + hashlib.sha256(canonical(content)).hexdigest() == POLICY_HASH
    assert POLICY["content_hash"] == POLICY_HASH
    assert POLICY["policy_id"] == "passive-gate-policy-" + POLICY_HASH[7:]
    registry_raw = (ROOT / "schemas/metric-registry-v1.json").read_bytes()
    # Registry content identity is defined by its existing model, not its file SHA.
    registry = json.loads(registry_raw)
    metric = next(d for d in registry["definitions"] if d["name"] == POLICY["metric"]["name"])
    aliases = {
        "semantic_version": "semanticVersion",
        "raw_fields": "rawFields",
        "canonical_unit": "canonicalUnit",
        "primary_aggregation": "primaryAggregation",
        "clock_basis": "clockBasis",
    }
    for key, value in POLICY["metric"].items():
        assert metric[aliases.get(key, key)] == value
    n7 = json.loads((ROOT / "docs/profiles/N7_PROFILE_POLICY_SPEC.json").read_bytes())
    assert POLICY["registry"] == n7["registry"]
    assert POLICY["calibration_method_release"] == n7["calibration_method_release"]


def test_design_release_pin_and_no_unsupported_authority():
    raw = (DOCS / "N9_DESIGN_VECTORS.json").read_bytes()
    assert raw == canonical(VECTORS)
    assert hashlib.sha256(raw).hexdigest() == VECTOR_HASH
    assert VECTORS["policy_content_hash"] == POLICY_HASH
    assert VECTORS["provenance"] == "synthetic_design_only"
    assert VECTORS["operand_contract"] == "abstract_prevalidated_events_not_n6_roots"
    assert not any(POLICY["evaluation"].values())
    assert POLICY["quality"]["imputation"] is None
    assert POLICY["query"]["profile_hypotheses"] == "unavailable"
    assert POLICY["query"]["cause_label"] is None
    assert POLICY["clock"]["monotonic_guarantee"] is False
    assert POLICY["query"]["ignored_n6_reasons"] == ["label_unverified"]


@pytest.mark.parametrize("case", VECTORS["baseline_cases"], ids=lambda c: c["case_id"])
def test_group_weighting_and_support(case):
    assert fit(case["groups"]) == (case["center"], case["raw_mad"], case["reasons"])


@pytest.mark.parametrize("case", VECTORS["query_support_cases"], ids=lambda c: c["case_id"])
def test_heldout_unlabelled_query_support(case):
    # Duplicate handling precedes this evidence gate; it cannot be an accepted query.
    assert "duplicate_evidence" not in case["n6_reasons"]
    reasons = []
    if case["role"] != case["mode"]:
        reasons.append("not_requested_role")
    if set(case["n6_reasons"]) - {"label_unverified"}:
        reasons.append("n6_excluded")
    assert reasons == case["reasons"]


@pytest.mark.parametrize("case", VECTORS["quality_cases"], ids=lambda c: c["case_id"])
def test_metric_support_sample_and_duration_gates(case):
    reasons = []
    if case["support"] != "supported" or case["role"] != "analytical_candidate":
        reasons.append("unsupported_metric")
    if case["status"] != "complete" or case["median"] is None:
        reasons.append("incomplete_metric")
    if case["rejected"]:
        reasons.append("rejected_samples")
    if case["samples"] < 2:
        reasons.append("insufficient_samples")
    if not 1000 <= case["duration_ms"] <= 10000:
        reasons.append("unsupported_window_duration")
    assert reasons == case["reasons"]


@pytest.mark.parametrize("case", VECTORS["classification_cases"], ids=lambda c: c["case_id"])
def test_exact_threshold_boundaries(case):
    assert classify(case["fps"], case["center"]) == case["classification"]


@pytest.mark.parametrize("case", VECTORS["numeric_cases"], ids=lambda c: c["case_id"])
def test_arithmetic(case):
    def evaluate():
        return median(case["values"]) if case["operation"] == "median" else ratio(*case["values"])

    if case.get("error"):
        with pytest.raises(ValueError, match="^invalid_design_arithmetic$"):
            evaluate()
    else:
        actual = evaluate()
        assert actual == case["expected"]
        if actual == 0:
            assert math.copysign(1, actual) == 1


@pytest.mark.parametrize("case", VECTORS["replay_cases"], ids=lambda c: c["case_id"])
def test_literal_replay_rows(case):
    before = copy.deepcopy(case)
    actual = replay(case)
    assert actual == case["expected"]
    assert replay(case) == actual
    assert case == before
    assert actual[-1]["proposals"] == sum(row["recommendation"] == "probe" for row in actual)


@pytest.mark.parametrize("value", [True, False, 0.0, 1.5, -1, 9007199254740992, "2000", None])
def test_clock_interface_does_not_quantize_or_coerce(value):
    with pytest.raises(ValueError, match="^invalid_design_time$"):
        elapsed(value)


@pytest.mark.parametrize("value", [0, 9007199254740991])
def test_clock_interface_inclusive_bounds(value):
    assert elapsed(value) == value


@pytest.mark.parametrize("value", [-1.0, float("inf"), float("nan"), True, 1, "1.0"])
def test_invalid_numeric_operands(value):
    with pytest.raises(ValueError, match="^invalid_design_arithmetic$"):
        classify(value, 60.0)


def test_rounded_display_ratio_does_not_choose_class():
    assert ratio(0.8, 1.0) == 0.8
    assert classify(0.8, 1.0) == "band"
    assert math.nextafter(0.8, -math.inf) < 0.8


def test_event_limit_has_no_truncation():
    event = {"kind": "tick", "at_ms": 0}
    assert len(replay({"start_ms": 0, "events": [event] * 256})) == 256
    with pytest.raises(ValueError, match="^invalid_design_event_limit$"):
        replay({"start_ms": 0, "events": [event] * 257})


def test_malformed_events_fail_even_after_invalidation():
    case = {
        "start_ms": 0,
        "events": [{"kind": "reset", "at_ms": 0}, {"kind": "tick", "at_ms": True}],
    }
    with pytest.raises(ValueError, match="^invalid_design_time$"):
        replay(case)
