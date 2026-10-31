"""Consistency of supplied OS browser counters; never authenticate process ownership."""

import hashlib
import json
import re

from .integrated_game_measurements import delta, digest, items, number, obj, require

METHODS = {"darwin_proc_pid_rusage_v0_mach_timebase_v1", "linux_proc_stat_ticks_v1"}
NATIVE_FIELDS = {
    "sampling_method",
    "process_counters",
    "native_read_duration_ns",
    "host_read_duration_ns",
}


def native_counters(snapshot):
    require(snapshot["sampling_method"] in METHODS, "browser_sampling_method")
    native_duration = number(snapshot["native_read_duration_ns"], integral=True, maximum=50000000)
    host_duration = number(snapshot["host_read_duration_ns"], integral=True, maximum=1000000000)
    require(native_duration <= host_duration, "browser_read_bracket")
    rows = items(snapshot["process_counters"], 1, 128)
    require(len(rows) == snapshot["process_count"], "browser_counter_inventory")
    counters = {}
    for row in rows:
        row = obj(row)
        identity = digest(row["identity_hash"])
        require(identity not in counters, "browser_duplicate_process")
        text = row["cpu_ticks_decimal"]
        require(type(text) is str and re.fullmatch(r"[0-9]{1,20}", text), "browser_tick_text")
        ticks = int(text)
        require(ticks < 2**64, "browser_tick_bounds")
        numerator = number(row["seconds_numerator"], integral=True, maximum=2**32)
        denominator = number(row["seconds_denominator"], integral=True, maximum=2**63 - 1)
        require(numerator > 0 and denominator > 0, "browser_timebase")
        seconds = number(row["cpu_seconds"])
        require(
            abs(seconds - ticks * numerator / denominator) <= 1e-9,
            "browser_tick_conversion",
        )
        counters[identity] = (ticks, numerator, denominator, seconds)
    identities = list(counters)
    require(identities == sorted(identities), "browser_counter_order")
    payload = json.dumps(identities, separators=(",", ":")).encode()
    require(
        hashlib.sha256(payload).hexdigest() == snapshot["inventory_hash"],
        "browser_counter_inventory_hash",
    )
    require(
        abs(sum(row[3] for row in counters.values()) - snapshot["cpu_seconds"]) <= 1e-9,
        "browser_counter_total",
    )
    return counters


def validate_native_pair(before, after):
    """Old snapshots retain aggregate-only meaning; partial native metadata is invalid."""
    if not any(NATIVE_FIELDS.intersection(snapshot) for snapshot in (before, after)):
        return
    a, b = native_counters(before), native_counters(after)
    require(before["sampling_method"] == after["sampling_method"], "browser_sampling_changed")
    require(a.keys() == b.keys(), "browser_process_lifetime_changed")
    require(
        all(b[key][0] >= a[key][0] and b[key][1:3] == a[key][1:3] for key in a),
        "browser_process_counter_or_timebase_changed",
    )


def browser_cpu(data):
    """Missing/changing inventories stay unavailable, separate from the video screen."""
    empty = {"state": "unavailable", "cpu_percent": None}
    try:
        data = obj(data)
        require(
            data["basis"] == "host_hrtime_browser_owned_process_cpu_separate_clock",
            "browser_resource_basis",
        )
        a, b = obj(data["before"]), obj(data["after"])
        require(
            digest(a["inventory_hash"]) == digest(b["inventory_hash"]), "browser_inventory_changed"
        )
        count = number(a["process_count"], integral=True, maximum=128)
        require(
            count > 0 and count == number(b["process_count"], integral=True, maximum=128),
            "browser_inventory_changed",
        )
        wall = number(b["host_at_ns"], integral=True) - number(a["host_at_ns"], integral=True)
        require(1500000000 <= wall <= 3000000000, "browser_resource_duration")
        cpu = delta([number(a["cpu_seconds"]), number(b["cpu_seconds"])])
        validate_native_pair(a, b)
        return {
            "state": "observed",
            "cpu_percent": 100 * cpu * 10**9 / wall,
            "clock_basis": data["basis"],
        }
    except (ValueError, TypeError, KeyError, IndexError, OverflowError):
        return empty
