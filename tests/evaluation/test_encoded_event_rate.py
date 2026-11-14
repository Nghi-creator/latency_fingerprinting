"""Check exact counts and abstention for the event-span design."""

from fractions import Fraction

import pytest

from latency_fingerprinting.evaluation.encoded_event_rate import encoded_event_rate

START, END = 100_000_000, 3_400_000_000
CLOCK = "worker-monotonic-" + "a" * 64


def trace():
    return [
        dict(
            clock_id=CLOCK,
            read_start_ns=i * 40_000_000,
            read_end_ns=i * 40_000_000 + 200_000,
            event_ordinal=i,
        )
        for i in range(87)
    ]


def test_consecutive_events_give_exact_interval_count_and_rate_bounds():
    result = encoded_event_rate(trace(), phase_start_ns=START, phase_end_ns=END)
    assert result["state"] == "candidate_event_span_available"
    span = result["span"]
    assert span["first_ordinal"] == 3 and span["last_ordinal"] == 84
    assert span["completed_intervals"] == 81
    assert Fraction(**result["rate_fps"]["lower"]) == Fraction(81_000_000_000, 3_240_200_000)
    assert Fraction(**result["rate_fps"]["upper"]) == Fraction(81_000_000_000, 3_239_800_000)


@pytest.mark.parametrize("issue", ["dropped", "foreign", "overlap", "polled_counter"])
def test_damaged_sequence_rejected(issue):
    events = trace()
    if issue == "dropped":
        del events[20]
    elif issue == "foreign":
        events[20]["clock_id"] = "worker-monotonic-" + "b" * 64
    elif issue == "polled_counter":
        events[20]["counter"] = events[20].pop("event_ordinal")
    else:
        events[20]["read_end_ns"] = events[21]["read_start_ns"]
    with pytest.raises(ValueError):
        encoded_event_rate(events, phase_start_ns=START, phase_end_ns=END)


@pytest.mark.parametrize(
    "issue,reason",
    [
        ("missing_suffix", "phase_coverage_unavailable"),
        ("ambiguous_boundary", "phase_coverage_unavailable"),
        ("short", "event_span_outside_limits"),
        ("wide", "elapsed_uncertainty_exceeds_budget"),
    ],
)
def test_unresolved_trace_cannot_supply_a_rate(issue, reason):
    events, start, end = trace(), START, END
    if issue == "missing_suffix":
        events = events[:85]
    elif issue == "ambiguous_boundary":
        start = events[3]["read_start_ns"] + 1
    elif issue == "short":
        end = 2_000_000_000
    else:
        events[3]["read_end_ns"] += 11_000_000
    report = encoded_event_rate(events, phase_start_ns=start, phase_end_ns=end)
    assert report["reason"] == reason
    assert report["state"] == "unavailable" and report["rate_fps"] is None
