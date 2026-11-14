"""Conditional event-to-event rate from a complete same-worker encoded trace."""

from collections.abc import Mapping
from fractions import Fraction
from itertools import pairwise

from ..analytical.policy_release import payload_hash
from .contrast_bounds import MAX_INT, _read

RELEASE = "n11-encoded-event-span-rate-prototype-v1"
ERROR = "invalid_encoded_event_rate_input"
MAX_EVENTS = 512
MIN_SPAN_NS = 3_000_000_000
MAX_SPAN_NS = 5_000_000_000
MAX_ELAPSED_HALF_WIDTH_NS = 5_000_000
EVENT_KEYS = {"clock_id", "read_start_ns", "read_end_ns", "event_ordinal"}


def encoded_event_rate(events, *, phase_start_ns, phase_end_ns):
    """Bound event-span rate when read brackets enclose actual counted buffer events.

    The caller supplies one complete trace with strictly consecutive worker event
    ordinals. Boundary events must establish coverage of the whole phase. This
    numerical check cannot establish that the producer observed every buffer.
    """
    if (
        type(events) not in (tuple, list)
        or not 4 <= len(events) <= MAX_EVENTS
        or any(type(v) is not int for v in (phase_start_ns, phase_end_ns))
        or not 0 <= phase_start_ns < phase_end_ns <= MAX_INT
        or phase_end_ns - phase_start_ns > MAX_SPAN_NS
    ):
        raise ValueError(ERROR)
    if any(not isinstance(event, Mapping) or event.keys() != EVENT_KEYS for event in events):
        raise ValueError(ERROR)
    try:
        parsed = [
            _read(
                {k: v for k, v in event.items() if k != "event_ordinal"}
                | {"counter": event["event_ordinal"]}
            )
            for event in events
        ]
    except ValueError:
        raise ValueError(ERROR) from None
    clock = parsed[0][0]
    if any(event[0] != clock for event in parsed) or any(
        a[2] >= b[1] or a[3] + 1 != b[3] for a, b in pairwise(parsed)
    ):
        raise ValueError(ERROR)
    inside = [e for e in parsed if phase_start_ns <= e[1] and e[2] < phase_end_ns]
    outside = [e for e in parsed if e[2] < phase_start_ns or phase_end_ns <= e[1]]
    if (
        len(inside) < 2
        or len(inside) + len(outside) != len(parsed)
        or parsed[0][2] >= phase_start_ns
        or parsed[-1][1] < phase_end_ns
    ):
        return _report(events, phase_start_ns, phase_end_ns, "phase_coverage_unavailable")
    first, last = inside[0], inside[-1]
    inner, outer = last[1] - first[2], last[2] - first[1]
    if not MIN_SPAN_NS <= inner <= outer <= MAX_SPAN_NS:
        return _report(events, phase_start_ns, phase_end_ns, "event_span_outside_limits")
    if outer - inner > 2 * MAX_ELAPSED_HALF_WIDTH_NS:
        return _report(events, phase_start_ns, phase_end_ns, "elapsed_uncertainty_exceeds_budget")
    count = last[3] - first[3]
    return _report(
        events,
        phase_start_ns,
        phase_end_ns,
        None,
        span=dict(
            first_ordinal=first[3],
            last_ordinal=last[3],
            elapsed_lower_ns=inner,
            elapsed_upper_ns=outer,
            completed_intervals=count,
        ),
        rate=dict(
            lower=_ratio(Fraction(count * 1_000_000_000, outer)),
            upper=_ratio(Fraction(count * 1_000_000_000, inner)),
        ),
    )


def _ratio(value):
    return dict(numerator=value.numerator, denominator=value.denominator)


def _report(events, start, end, reason, *, span=None, rate=None):
    return dict(
        release=RELEASE,
        input_content_hash=payload_hash(
            dict(events=[dict(e) for e in events], phase_start_ns=start, phase_end_ns=end)
        ),
        state="candidate_event_span_available" if reason is None else "unavailable",
        reason=reason,
        span=span,
        rate_fps=rate,
        scope="encoded_buffer_event_span_conditional_on_complete_trace",
        empirical_acceptance=False,
        acquisition_authority=False,
    )
