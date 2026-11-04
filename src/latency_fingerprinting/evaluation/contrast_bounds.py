"""Read-only conditional models and guarded same-clock counter windows; no diagnosis."""

import hashlib
import json
import re
from collections.abc import Mapping
from fractions import Fraction

ERROR = "invalid_contrast_bounds"
MAX_INT = 2**63 - 1
READ_KEYS = {"clock_id", "read_start_ns", "read_end_ns", "counter"}


def _integer(value, low=0, high=MAX_INT):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(ERROR)
    return value


def _ratio(value):
    return dict(numerator=value.numerator, denominator=value.denominator)


def _cadence(prior, target, delay):
    for value in (prior, target, delay):
        _integer(value)
    if not 24 <= target < prior <= 60 or not 1 <= delay <= 1_000_000:
        raise ValueError(ERROR)
    if 100 * (prior - target) > 20 * prior:
        raise ValueError(ERROR)


def pacing_contrast_bounds(
    *, prior_fps, target_fps, delay_us, extra_period_us=None, bounds_declaration_sha256=None
):
    """Condition an envelope on explicit extra-period bounds, never fit them.

    A declaration hash is provenance, not authentication or calibration. Unknown
    processing/scheduling/wait bounds cannot silently become zero. This pure model
    does not estimate component latency or grant acquisition authority.
    """
    _cadence(prior_fps, target_fps, delay_us)
    result = dict(
        method_release="n11-pacing-contrast-envelope-v2",
        prior_fps=prior_fps,
        target_fps=target_fps,
        delay_us=delay_us,
        nominal_ceiling_fps=_ratio(Fraction(1_000_000, delay_us)),
        extra_period_bounds_us=None,
        bounds_declaration_sha256=None,
        bounds_assurance="unavailable",
        modeled_rate_bounds_fps=None,
        bounded_modeled_crossing=None,
        state="unavailable",
        reason_codes=["extra_period_bounds_unavailable"],
        measured_contrast="unavailable",
        diagnostic_utility="unavailable",
        acquisition_authority=False,
    )
    if extra_period_us is None:
        if bounds_declaration_sha256 is not None:
            raise ValueError(ERROR)
        return result
    if not isinstance(extra_period_us, (tuple, list)) or len(extra_period_us) != 2:
        raise ValueError(ERROR)
    low, high = (_integer(v, high=1_000_000) for v in extra_period_us)
    if (
        low > high
        or type(bounds_declaration_sha256) is not str
        or re.fullmatch(r"sha256:[a-f0-9]{64}", bounds_declaration_sha256) is None
    ):
        raise ValueError(ERROR)
    lower, upper = Fraction(1_000_000, delay_us + high), Fraction(1_000_000, delay_us + low)
    crossing = target_fps < lower and upper < prior_fps
    return {
        **result,
        "state": "conditional_model",
        "reason_codes": [] if crossing else ["no_strict_bounded_crossing"],
        "extra_period_bounds_us": dict(lower=low, upper=high),
        "bounds_declaration_sha256": bounds_declaration_sha256,
        "bounds_assurance": "unverified_declaration_not_calibration",
        "modeled_rate_bounds_fps": dict(lower=_ratio(lower), upper=_ratio(upper)),
        "bounded_modeled_crossing": crossing,
    }


def _read(value):
    if not isinstance(value, Mapping) or set(value) != READ_KEYS:
        raise ValueError(ERROR)
    clock = value["clock_id"]
    if type(clock) is not str or re.fullmatch(r"worker-monotonic-[a-f0-9]{64}", clock) is None:
        raise ValueError(ERROR)
    start, end, counter = (_integer(value[k]) for k in ("read_start_ns", "read_end_ns", "counter"))
    if start > end:
        raise ValueError(ERROR)
    return clock, start, end, counter


def _window(first, last):
    a, b = _read(first), _read(last)
    if a[0] != b[0] or a[2] >= b[1] or a[3] > b[3]:
        raise ValueError(ERROR)
    delta, minimum, maximum = b[3] - a[3], b[1] - a[2], b[2] - a[1]
    # A fixed one-buffer sensitivity guard is explicit. This is not a confidence
    # interval or an upper bound on arbitrary bursts, source lag or future rates.
    lower = Fraction(max(0, delta - 1) * 1_000_000_000, maximum)
    upper = Fraction((delta + 1) * 1_000_000_000, minimum)
    return (
        dict(
            method_release="n11-guarded-counter-window-v1",
            scope="same_clock_read_calls_with_one_buffer_sensitivity_not_confidence",
            clock_id=a[0],
            first_read=dict(first),
            last_read=dict(last),
            observed_counter_delta=delta,
            boundary_guard_buffers=1,
            minimum_elapsed_ns=minimum,
            maximum_elapsed_ns=maximum,
            guarded_rate_fps=dict(lower=_ratio(lower), upper=_ratio(upper)),
            underlying_counter_freshness="not_authenticated_by_read_brackets",
            transferable_rate_bound=False,
        ),
        lower,
        upper,
    )


def counter_rate_bounds(first, last):
    """Bound finite-window sensitivity using one declared worker clock only."""
    return _window(first, last)[0]


def compare_counter_rate_bounds(
    initial_first, initial_last, relief_first, relief_last, *, target_fps
):
    """Require separated guarded windows, without statistical or causal acceptance."""
    _integer(target_fps, 24, 60)
    initial, lower, _ = _window(initial_first, initial_last)
    relief, _, upper = _window(relief_first, relief_last)
    if (
        initial["clock_id"] != relief["clock_id"]
        or initial_last["read_end_ns"] >= relief_first["read_start_ns"]
    ):
        raise ValueError(ERROR)
    reasons = []
    if lower <= target_fps:
        reasons.append("initial_guarded_rate_not_above_target")
    if lower <= upper:
        reasons.append("guarded_windows_not_separated")
    return dict(
        method_release="n11-guarded-counter-contrast-v1",
        state="not_established" if reasons else "guarded_window_separation",
        reason_codes=reasons,
        initial=initial,
        relief=relief,
        target_fps=target_fps,
        guarded_separation=not reasons,
        diagnostic_utility="unavailable",
        diagnostic_label=None,
        acquisition_authority=False,
    )


def native_worker_clock_id(generation):
    """Bind a declared worker elapsed clock to the exact three-part generation."""
    if not isinstance(generation, Mapping) or set(generation) != {"owner", "pipeline", "peer"}:
        raise ValueError(ERROR)
    if any(
        type(v) is not str or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", v) is None
        for v in generation.values()
    ):
        raise ValueError(ERROR)
    raw = json.dumps(
        dict(generation), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return "worker-monotonic-" + hashlib.sha256(raw).hexdigest()


def inspect_native_counter_reads(acquisition):
    """Extract only versioned worker read evidence, never substitute parent times.

    This checks declared internal consistency, not authenticity of raw execution,
    controller qualification, underlying counter update times, or N9 latency.
    """
    if (
        not isinstance(acquisition, Mapping)
        or acquisition.get("status") != "passed"
        or acquisition.get("method") != "n11-contained-pacing-contrast-v1"
        or acquisition.get("live_authority") is not False
    ):
        raise ValueError(ERROR)
    events = acquisition.get("events")
    if (
        not isinstance(events, (list, tuple))
        or not 1 <= len(events) <= 10000
        or any(not isinstance(e, Mapping) for e in events)
    ):
        raise ValueError(ERROR)
    dispatches = [e for e in events if e.get("kind") == "n11_pair_dispatched"]
    if len(dispatches) != 1 or not isinstance(dispatches[0].get("request"), Mapping):
        raise ValueError(ERROR)
    request = dispatches[0]["request"]
    if type(request.get("target_fps")) is not int or request["target_fps"] != 24:
        raise ValueError(ERROR)
    clock = native_worker_clock_id(request.get("generation"))
    native = [e for e in events if e.get("kind") == "n11_pair_native"]
    if not native:
        raise ValueError(ERROR)
    if not any("native_read" in row for row in native):
        return dict(
            method_release="n11-native-counter-read-inspection-v1",
            state="unavailable",
            reason_codes=["native_worker_read_brackets_missing"],
            acquisition_authority=False,
            diagnostic_utility="unavailable",
        )
    phases = {name: [] for name in ("degraded", "relief", "recovery")}
    previous_sequence, previous_end, previous_counter = -1, -1, -1
    previous_phase = -1
    for row in native:
        phase = row.get("phase")
        if phase not in phases or list(phases).index(phase) < previous_phase:
            raise ValueError(ERROR)
        previous_phase = list(phases).index(phase)
        evidence = row.get("native_read")
        if (
            not isinstance(evidence, Mapping)
            or set(evidence) != {"method", "clock_id", "basis", "read_start_ns", "read_end_ns"}
            or evidence["method"] != "native-counter-read-brackets-v1"
            or evidence["basis"] != "worker_elapsed_monotonic_ns"
            or evidence["clock_id"] != clock
        ):
            raise ValueError(ERROR)
        read = dict(
            clock_id=clock,
            read_start_ns=evidence["read_start_ns"],
            read_end_ns=evidence["read_end_ns"],
            counter=row.get("encoded_buffers"),
        )
        _, start, end, counter = _read(read)
        sequence = _integer(row.get("sequence"))
        target = 24 if phase == "relief" else 30
        if (
            sequence <= previous_sequence
            or start <= previous_end
            or counter < previous_counter
            or type(row.get("configured_fps")) is not int
            or type(row.get("negotiated_fps")) is not int
            or row["configured_fps"] != target
            or row["negotiated_fps"] != target
        ):
            raise ValueError(ERROR)
        previous_sequence, previous_end, previous_counter = sequence, end, counter
        phases[phase].append(read)
    if any(len(rows) < 2 for rows in phases.values()):
        raise ValueError(ERROR)
    contrast = compare_counter_rate_bounds(
        phases["degraded"][0],
        phases["degraded"][-1],
        phases["relief"][0],
        phases["relief"][-1],
        target_fps=24,
    )
    return dict(
        method_release="n11-native-counter-read-inspection-v1",
        state="available",
        reason_codes=[],
        clock_id=clock,
        phase_windows={p: counter_rate_bounds(rows[0], rows[-1]) for p, rows in phases.items()},
        guarded_contrast=contrast,
        acquisition_authority=False,
        diagnostic_utility="unavailable",
    )
