"""Independent arithmetic on retained native and browser domains; no clock alignment."""

import math
import re

SAFE_MAX = 2**53 - 1
PHASES = ("baseline", "during", "restored")


class EvidenceGap(ValueError):
    """A fixed diagnostic code, never arbitrary producer text."""


def require(condition, code):
    if not condition:
        raise EvidenceGap(code)


def obj(value):
    require(type(value) is dict, "object_required")
    return value


def items(value, minimum, maximum):
    require(type(value) is list and minimum <= len(value) <= maximum, "collection_bounds")
    return value


def number(value, *, integral=False, maximum=SAFE_MAX):
    require(type(value) is int or (not integral and type(value) is float), "numeric_type")
    require(0 <= value <= maximum and math.isfinite(value), "numeric_bounds")
    return value


def digest(value, *, prefixed=False):
    pattern = r"sha256:[a-f0-9]{64}" if prefixed else r"[a-f0-9]{64}"
    require(type(value) is str and re.fullmatch(pattern, value) is not None, "hash_format")
    return value


def series(rows, field, *, integral=False):
    return [number(obj(row)[field], integral=integral) for row in rows]


def differences(values):
    return [b - a for a, b in zip(values, values[1:], strict=False)]


def delta(values):
    require(len(values) >= 2 and all(d >= 0 for d in differences(values)), "counter_reset")
    return values[-1] - values[0]


def advancing(values, maximum_gap):
    return len(values) >= 2 and all(0 < d <= maximum_gap for d in differences(values))


def frame_trace(data, *, continuous=False):
    data = obj(data)
    require(data["basis"] == "browser_performance_relative_ms", "browser_clock_basis")
    require(data["failure"] is None, "browser_measurement_failure")
    duration = number(data["duration_ms"])
    require(
        (10000 <= duration <= 26000) if continuous else (2000 <= duration <= 2500),
        "browser_window_duration",
    )
    frames = items(data["frames"], 200 if continuous else 2, 2048 if continuous else 300)
    stamps, pts, counts = (
        series(frames, field, integral=field == "presented")
        for field in ("at_ms", "pts_ms", "presented")
    )
    require(all(t <= duration for t in stamps), "frame_outside_window")
    presented = delta(counts)
    require(stamps[-1] > stamps[0], "frame_clock_reversed")
    dimensions = all(
        number(obj(f)["width"], integral=True) == 640 and number(f["height"], integral=True) == 480
        for f in frames
    )
    return {
        "met": advancing(stamps, 250)
        and advancing(pts, 250)
        and advancing(counts, 8)
        and stamps[0] <= 250
        and duration - stamps[-1] <= (500 if continuous else 250)
        and dimensions,
        "presented_fps": 1000 * presented / (stamps[-1] - stamps[0]),
        "maximum_callback_gap_ms": max(differences(stamps)),
        "maximum_media_gap_ms": max(differences(pts)),
    }


def browser_window(data, expected_fps):
    trace = frame_trace(data)
    duration = number(data["duration_ms"])
    stats = items(data["stats"], 2, 32)
    times = series(stats, "at_ms")
    require(
        advancing(times, 500)
        and times[0] <= 500
        and duration - times[-1] <= 500
        and all(t <= duration for t in times),
        "stats_clock_coverage",
    )
    decoded, dropped, freezes = (
        delta(series(stats, field, integral=True)) for field in ("decoded", "dropped", "freezes")
    )
    decode_fps = 1000 * decoded / (times[-1] - times[0])
    visuals = items(data["visuals"], 2, 16)
    visual_times = series(visuals, "at_ms")
    hashes = [number(obj(v)["hash"], integral=True, maximum=2**32 - 1) for v in visuals]
    bins = [number(v["color_bins"], integral=True, maximum=512) for v in visuals]
    require(
        advancing(visual_times, 750)
        and visual_times[0] <= 750
        and duration - visual_times[-1] <= 750
        and all(t <= duration for t in visual_times),
        "visual_clock_coverage",
    )
    met = (
        trace["met"]
        and data["connection_state"] == "connected"
        and all(
            0.9 * expected_fps <= rate <= 1.1 * expected_fps
            for rate in (trace["presented_fps"], decode_fps)
        )
        and dropped == freezes == 0
        and len(set(hashes)) >= 3
        and min(bins) >= 4
        and all(
            number(s["width"], integral=True) == 640 and number(s["height"], integral=True) == 480
            for s in stats
        )
    )
    return dict(trace, met=met, decoded_fps=decode_fps, new_dropped=dropped, new_freezes=freezes)


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
        return {
            "state": "observed",
            "cpu_percent": 100 * cpu * 10**9 / wall,
            "clock_basis": data["basis"],
        }
    except (ValueError, TypeError, KeyError, IndexError, OverflowError):
        return empty


def native_windows(reports):
    """Same declared workers across all phases; never merge replacement lifetimes."""
    require(len(reports) == 3, "native_phase_count")
    all_samples, identities, hz, rows = [], None, None, []
    for phase, report in zip(PHASES, reports, strict=True):
        report = obj(report)
        require(
            report["phase"] == phase
            and report["basis"] == "linux_monotonic_brackets_exact_owned_process_ticks",
            "native_phase_or_basis",
        )
        ids = obj(report["worker_identities"])
        require(set(ids) == {"first", "second"}, "worker_inventory")
        values = [digest(ids[k]) for k in ("first", "second")]
        require(
            values[0] != values[1] and (identities is None or identities == ids),
            "worker_lifetime_changed",
        )
        identities = ids
        ticks = number(report["ticks_per_second"], integral=True, maximum=1000000)
        require(ticks > 0 and (hz is None or ticks == hz), "native_tick_frequency")
        hz = ticks
        samples = items(report["samples"], 10, 14)
        starts, ends = (
            series(samples, "read_start_ns", integral=True),
            series(samples, "read_end_ns", integral=True),
        )
        require(
            advancing(starts, 500000000)
            and all(0 <= b - a <= 50000000 for a, b in zip(starts, ends, strict=True))
            and all(b > a for a, b in zip(ends, starts[1:], strict=False)),
            "native_read_brackets",
        )
        wall = starts[-1] - starts[0]
        require(2500000000 <= wall <= 3000000000, "native_window_duration")
        if all_samples:
            require(starts[0] > all_samples[-1]["read_end_ns"], "native_phase_overlap")
        actors = {name: [obj(s[name]) for s in samples] for name in ("parent", "relay", "game")}
        source_rates, source_met = {}, True
        for peer in ("first", "second"):
            workers = []
            fps = 24 if phase == "during" and peer == "first" else 30
            expected = dict(
                configured_fps=fps,
                negotiated_fps=fps,
                width=640,
                height=480,
                target_bitrate=1500000,
                cpu_used=6,
                max_quantizer=48,
            )
            for sample in samples:
                require(set(obj(sample["workers"])) == {"first", "second"}, "native_worker_scope")
                worker = obj(sample["workers"][peer])
                settings = obj(worker["settings"])
                require(
                    set(settings) == set(expected)
                    and all(type(v) is int for v in settings.values())
                    and settings == expected,
                    "native_settings_changed",
                )
                workers.append(worker)
            actors[peer] = workers
            rates = {
                key: delta(series(workers, key, integral=True)) * 10**9 / wall
                for key in ("capture_buffers", "encoded_buffers")
            }
            source_rates[peer] = rates
            source_met = source_met and all(0.9 * fps <= v <= 1.1 * fps for v in rates.values())
        resource_rows = {}
        for name, samples_for_actor in actors.items():
            cpu = delta(series(samples_for_actor, "cpu_ticks", integral=True))
            resource_rows[name] = {
                "cpu_percent": 100 * cpu * 10**9 / (ticks * wall),
                "sampled_peak_rss_bytes": max(
                    series(samples_for_actor, "rss_bytes", integral=True)
                ),
            }
            if name == "game":
                require(cpu > 0, "game_progress_missing")
        for key in ("game_age_ns", "script_age_ns", "script_actions"):
            require(
                delta(series([obj(s["game_phase"]) for s in samples], key, integral=True)) > 0,
                "game_script_progress_missing",
            )
        rows.append(
            {
                "phase": phase,
                "met": source_met,
                "source_rates": source_rates,
                "native_resources": resource_rows,
                "duration_ns": wall,
            }
        )
        all_samples.extend(samples)
    # Endpoint-valid windows cannot conceal a reset between phases.
    for name in ("parent", "relay", "game"):
        delta(series([s[name] for s in all_samples], "cpu_ticks", integral=True))
    for peer in ("first", "second"):
        for key in ("cpu_ticks", "capture_buffers", "encoded_buffers"):
            delta(series([s["workers"][peer] for s in all_samples], key, integral=True))
    for key in ("game_age_ns", "script_age_ns", "script_actions"):
        delta(series([s["game_phase"] for s in all_samples], key, integral=True))
    return rows
