"""Native counter contradictions stay unavailable even when aggregate CPU rises."""

import hashlib
import json

import pytest

from latency_fingerprinting.live_probes.browser_cpu import browser_cpu

from .integrated_reconstruction_cases import browser_resources


def snapshot(at, ticks):
    rows = [
        dict(
            identity_hash=identity * 64,
            cpu_ticks_decimal=str(value),
            seconds_numerator=1,
            seconds_denominator=10000,
            cpu_seconds=value / 10000,
        )
        for identity, value in zip("ab", ticks, strict=True)
    ]
    inventory = json.dumps([row["identity_hash"] for row in rows], separators=(",", ":"))
    return dict(
        host_at_ns=at,
        cpu_seconds=sum(row["cpu_seconds"] for row in rows),
        process_count=2,
        inventory_hash=hashlib.sha256(inventory.encode()).hexdigest(),
        sampling_method="linux_proc_stat_ticks_v1",
        process_counters=rows,
        native_read_duration_ns=100,
        host_read_duration_ns=1000,
    )


def resources():
    return dict(
        basis="host_hrtime_browser_owned_process_cpu_separate_clock",
        before=snapshot(0, (10000, 20000)),
        after=snapshot(2 * 10**9, (12000, 23000)),
    )


def test_reconstructs_native_cpu_and_keeps_legacy_aggregate_snapshots():
    darwin = resources()
    for sample in (darwin["before"], darwin["after"]):
        sample["sampling_method"] = "darwin_proc_pid_rusage_v0_mach_timebase_v1"
        for row in sample["process_counters"]:
            row.update(
                cpu_ticks_decimal=str(int(row["cpu_ticks_decimal"]) * 2400),
                seconds_numerator=125,
                seconds_denominator=3000000000,
            )
    for data in (resources(), darwin, browser_resources(0)):
        result = browser_cpu(data)
        assert result["state"] == "observed"
        assert result["cpu_percent"] == pytest.approx(25)


@pytest.mark.parametrize(
    "mutation",
    [
        "hidden_reset",
        "total",
        "conversion",
        "identity",
        "duplicate",
        "partial",
        "method",
        "timebase",
        "native_bracket",
        "host_bracket",
        "impossible_bracket",
        "tick_overflow",
        "bool_tick",
        "bool_timebase",
    ],
)
def test_native_contradictions_are_unavailable_without_zero_filling(mutation):
    data = resources()
    after = data["after"]
    row = after["process_counters"][0]
    if mutation == "hidden_reset":
        data["after"] = snapshot(2 * 10**9, (16000, 19000))
    elif mutation == "total":
        after["cpu_seconds"] += 1
    elif mutation == "conversion":
        row["cpu_ticks_decimal"] = "12001"
    elif mutation == "identity":
        after["inventory_hash"] = "c" * 64
    elif mutation == "duplicate":
        after["process_counters"][1]["identity_hash"] = row["identity_hash"]
    elif mutation == "partial":
        del after["sampling_method"]
    elif mutation == "method":
        after["sampling_method"] = "unknown"
    elif mutation == "timebase":
        # Keep conversion and aggregate unchanged; changing clock units is still invalid.
        row["seconds_numerator"] = 2
        row["seconds_denominator"] = 20000
    elif mutation == "native_bracket":
        after["native_read_duration_ns"] = 50000001
    elif mutation == "host_bracket":
        after["host_read_duration_ns"] = 1000000001
    elif mutation == "impossible_bracket":
        after["host_read_duration_ns"] = 99
    elif mutation == "tick_overflow":
        row["cpu_ticks_decimal"] = str(2**64)
    elif mutation == "bool_tick":
        row["cpu_ticks_decimal"] = True
    else:
        row["seconds_numerator"] = True
    assert browser_cpu(data) == {"state": "unavailable", "cpu_percent": None}
