"""Invented generic CPU read vectors only; never condition recognition evidence."""

from copy import deepcopy
from fractions import Fraction

import pytest

from latency_fingerprinting.evaluation import cpu_resource_response as method


def windows():
    result, sequence, cpu, throttle = {}, 0, 0, 0
    for i, phase in enumerate(method.PHASES):
        result[phase] = []
        cpu_step = 0 if phase in ("healthy", "post") else 500000
        throttle_step = 1000000 if phase == "degraded" else 0
        for j in range(7):
            start = i * 4_000_000_000 + j * 500_000_000
            counters = dict(
                usage_usec=cpu + j * cpu_step,
                user_usec=cpu + j * cpu_step,
                system_usec=0,
                nr_periods=sequence,
                nr_throttled=sequence,
                throttled_usec=throttle + j * throttle_step,
            )
            result[phase].append(
                dict(
                    **method.CONSTANTS,
                    clock_id="controller-monotonic-" + "a" * 64,
                    phase=phase,
                    sequence=sequence,
                    read_start_ns=start,
                    read_end_ns=start + 1000,
                    source_identity={
                        name: dict(device=1, inode=k + 1)
                        for k, name in enumerate(("cgroup", "cpu.stat", "cpu.max"))
                    },
                    quota=dict(quota_usec=200000, period_usec=100000),
                    counters=counters,
                    live_authority=False,
                )
            )
            sequence += 1
        cpu += 6 * cpu_step
        throttle += 6 * throttle_step
    return result


def f(value):
    return Fraction(value["numerator"], value["denominator"])


def test_exact_resource_rates_and_differences_support_zero_healthy_without_epsilon():
    result = method.cpu_resource_response(windows())
    assert result["state"] == "candidate_response_available" and len(result["features"]) == 6
    rate = result["windows"]["degraded"]["rate_intervals"]["cpu_quota_fraction"]
    assert f(rate["lower"]) == Fraction(2999999 * 1000, 3_000_001_000) / 2
    assert f(rate["upper"]) == Fraction(3000001 * 1000, 2_999_999_000) / 2
    difference = result["features"]["cpu_quota_fraction.degraded_minus_healthy"]["difference"]
    assert f(difference["lower"]) < Fraction(1, 2) < f(difference["upper"])
    assert (
        result["features"]["cpu_quota_fraction.post_minus_healthy"]["state"]
        == "candidate_interval_available"
    )
    assert result["confidence"] is None and result["diagnostic_label"] is None
    assert not result["empirical_acceptance"] and not result["acquisition_authority"]
    assert result["accepted_diagnostic_groups"] == result["independent_support_groups"] == 0


def test_throttling_rate_can_exceed_one_and_is_never_clipped_to_percentage():
    result = method.cpu_resource_response(windows())
    interval = result["windows"]["degraded"]["rate_intervals"]["throttled_seconds_per_wall_second"]
    assert f(interval["lower"]) > 1
    assert f(interval["lower"]) < 2 < f(interval["upper"])


def test_over_quota_reported_rate_not_silently_capped():
    data = windows()
    for rows in data.values():
        for row in rows:
            row["counters"]["usage_usec"] *= 10
    rate = method.cpu_resource_response(data)["windows"]["degraded"]["rate_intervals"][
        "cpu_quota_fraction"
    ]
    assert f(rate["lower"]) > 1


@pytest.mark.parametrize(
    "kind,reason",
    [
        ("empty", "insufficient_samples"),
        ("short", "window_too_short"),
        ("wide", "read_span_too_wide"),
        ("gap", "sample_gap_too_wide"),
        ("between", "between_window_gap_too_wide"),
        ("long", "window_too_long"),
    ],
)
def test_well_formed_ineligible_source_retained_with_unavailable_vector(kind, reason):
    data = windows()
    if kind == "empty":
        data["post"] = []
    elif kind == "short":
        data["post"] = data["post"][:4]
    elif kind == "wide":
        data["post"][0]["read_end_ns"] += 50_000_000
    elif kind == "gap":
        for row in data["post"][3:]:
            row["read_start_ns"] += 1_200_000_000
            row["read_end_ns"] += 1_200_000_000
    elif kind == "between":
        for row in data["post"]:
            row["read_start_ns"] += 20_000_000_000
            row["read_end_ns"] += 20_000_000_000
    else:
        for j, row in enumerate(data["post"]):
            row["read_start_ns"] = 16_000_000_000 + j * 900_000_000
            row["read_end_ns"] = row["read_start_ns"] + 1000
    result = method.cpu_resource_response(data)
    assert result["state"] == "unavailable"
    assert reason in result["windows"]["post"]["reason_codes"]
    assert result["features"]["cpu_quota_fraction.post_minus_healthy"]["difference"] is None


@pytest.mark.parametrize(
    "kind",
    [
        "counter",
        "sequence",
        "clock",
        "identity",
        "quota",
        "bool_quota",
        "bool_counter",
        "negative",
        "reversed",
        "overlap",
        "label",
        "method",
        "units",
    ],
)
def test_reset_context_type_clock_or_label_change_invalidates(kind):
    data = windows()
    row = data["relief"][0]
    if kind == "counter":
        row["counters"]["usage_usec"] = 0
    elif kind == "sequence":
        row["sequence"] += 1
    elif kind == "clock":
        row["clock_id"] = "controller-monotonic-" + "b" * 64
    elif kind == "identity":
        row["source_identity"]["cpu.stat"]["inode"] += 1
    elif kind == "quota":
        row["quota"]["quota_usec"] = 400000
    elif kind == "bool_quota":
        row["quota"]["quota_usec"] = True
    elif kind == "bool_counter":
        row["counters"]["usage_usec"] = True
    elif kind == "negative":
        row["counters"]["usage_usec"] = -1
    elif kind == "reversed":
        row["read_end_ns"] = row["read_start_ns"] - 1
    elif kind == "overlap":
        row["read_start_ns"] = data["degraded"][-1]["read_end_ns"]
    elif kind == "label":
        row["condition"] = "owned_cpu_pressure"
    elif kind == "method":
        row["method"] = "different"
    else:
        row["counter_units"] = "percent"
    with pytest.raises(ValueError, match=method.ERROR):
        method.cpu_resource_response(data)


def test_recovery_still_required_even_though_not_a_difference_coordinate():
    data = windows()
    data["recovery"][-1]["read_end_ns"] += 50_000_000
    result = method.cpu_resource_response(data)
    assert result["state"] == "unavailable" and result["unavailable_windows"] == ["recovery"]
    assert all(r["state"] == "candidate_interval_available" for r in result["features"].values())


def test_limits_shape_and_no_truth_or_interval_subset_argument():
    for change in ("missing", "extra", "oversized"):
        data = windows()
        if change == "missing":
            del data["healthy"]
        elif change == "extra":
            data["condition"] = "no_injected_fault"
        else:
            data["post"] *= 10
        with pytest.raises(ValueError):
            method.cpu_resource_response(data)
    with pytest.raises(TypeError):
        method.cpu_resource_response(windows(), truth="condition")


def test_deterministic_detached_identity_binds_interior_samples():
    data = windows()
    before = deepcopy(data)
    original = method.cpu_resource_response(data)
    assert data == before and original == method.cpu_resource_response(data)
    data["degraded"][2]["counters"]["usage_usec"] += 1
    changed = method.cpu_resource_response(data)
    assert changed["features"] == original["features"]
    assert changed["response_id"] != original["response_id"]
    spec = method.cpu_resource_response_spec()
    spec["quota"]["quota_usec"] = 1
    spec["windows"].clear()
    assert method.cpu_resource_response_spec()["quota"]["quota_usec"] == 200000
    assert len(method.cpu_resource_response_spec()["windows"]) == 5
