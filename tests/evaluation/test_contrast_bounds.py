"""Hand-calculated interval and provenance adversaries; all examples are synthetic."""

import copy

import pytest

from latency_fingerprinting.evaluation.contrast_bounds import (
    ERROR,
    compare_counter_rate_bounds,
    counter_rate_bounds,
    inspect_native_counter_reads,
    native_worker_clock_id,
    pacing_contrast_bounds,
)

GEN = {"owner": "owner", "peer": "peer", "pipeline": "pipeline"}
CLOCK = native_worker_clock_id(GEN)
DECLARATION = "sha256:" + "a" * 64


def read(time, counter, end=None, clock=CLOCK):
    return dict(
        clock_id=clock,
        read_start_ns=time,
        read_end_ns=time if end is None else end,
        counter=counter,
    )


def model(**updates):
    return pacing_contrast_bounds(prior_fps=30, target_fps=24, delay_us=37500, **updates)


def acquisition():
    events = [dict(kind="n11_pair_dispatched", request=dict(generation=GEN, target_fps=24))]
    for i, (phase, offset, base, frames) in enumerate(
        [
            ("degraded", 0, 0, 54),
            ("relief", 3_000_000_000, 60, 48),
            ("recovery", 6_000_000_000, 120, 54),
        ]
    ):
        for j, (time, counter) in enumerate(
            [(offset, base), (offset + 2_000_000_000, base + frames)]
        ):
            events.append(
                dict(
                    kind="n11_pair_native",
                    phase=phase,
                    sequence=i * 2 + j + 1,
                    at_ns=999999999999,
                    configured_fps=24 if phase == "relief" else 30,
                    negotiated_fps=24 if phase == "relief" else 30,
                    encoded_buffers=counter,
                    native_read=dict(
                        method="native-counter-read-brackets-v1",
                        clock_id=CLOCK,
                        basis="worker_elapsed_monotonic_ns",
                        read_start_ns=time,
                        read_end_ns=time,
                    ),
                )
            )
    return dict(
        status="passed",
        method="n11-contained-pacing-contrast-v1",
        live_authority=False,
        events=events,
    )


def test_unknown_extra_period_is_unavailable_and_never_defaults_to_zero():
    result = model()
    assert result["nominal_ceiling_fps"] == dict(numerator=80, denominator=3)
    assert result["state"] == "unavailable" and result["bounded_modeled_crossing"] is None
    assert result["modeled_rate_bounds_fps"] is None
    assert result["acquisition_authority"] is False


def test_explicit_ranges_are_conditional_and_can_erase_the_nominal_crossing():
    result = model(extra_period_us=(0, 5000), bounds_declaration_sha256=DECLARATION)
    assert result["modeled_rate_bounds_fps"] == dict(
        lower=dict(numerator=400, denominator=17), upper=dict(numerator=80, denominator=3)
    )
    assert result["bounded_modeled_crossing"] is False
    tighter = model(extra_period_us=(2000, 3000), bounds_declaration_sha256=DECLARATION)
    assert tighter["modeled_rate_bounds_fps"] == dict(
        lower=dict(numerator=2000, denominator=81), upper=dict(numerator=2000, denominator=79)
    )
    assert tighter["bounded_modeled_crossing"] is True
    assert tighter["state"] == "conditional_model"
    assert tighter["bounds_assurance"] == "unverified_declaration_not_calibration"
    assert tighter["measured_contrast"] == tighter["diagnostic_utility"] == "unavailable"
    assert tighter["acquisition_authority"] is False


def test_exact_boundary_is_not_a_crossing():
    result = pacing_contrast_bounds(
        prior_fps=30,
        target_fps=25,
        delay_us=37500,
        extra_period_us=(2500, 2500),
        bounds_declaration_sha256=DECLARATION,
    )
    assert result["modeled_rate_bounds_fps"]["lower"] == dict(numerator=25, denominator=1)
    assert result["bounded_modeled_crossing"] is False


@pytest.mark.parametrize(
    "updates",
    [
        dict(extra_period_us=(-1, 0), bounds_declaration_sha256=DECLARATION),
        dict(extra_period_us=(1, 0), bounds_declaration_sha256=DECLARATION),
        dict(extra_period_us=(True, 1), bounds_declaration_sha256=DECLARATION),
        dict(extra_period_us=(0, 1)),
        dict(bounds_declaration_sha256=DECLARATION),
        dict(extra_period_us=(0, 1), bounds_declaration_sha256="path"),
    ],
)
def test_invalid_or_unattributed_bounds_fail(updates):
    with pytest.raises(ValueError, match=ERROR):
        model(**updates)


def test_read_brackets_and_explicit_buffer_guard_have_exact_fraction_bounds():
    result = counter_rate_bounds(
        read(0, 0, end=10_000_000), read(1_000_000_000, 30, end=1_010_000_000)
    )
    assert result["guarded_rate_fps"] == dict(
        lower=dict(numerator=2900, denominator=101), upper=dict(numerator=3100, denominator=99)
    )
    assert result["minimum_elapsed_ns"] == 990_000_000
    assert result["maximum_elapsed_ns"] == 1_010_000_000
    assert result["boundary_guard_buffers"] == 1
    assert result["transferable_rate_bound"] is False


def test_zero_progress_remains_observed_zero_with_explicit_sensitivity():
    result = counter_rate_bounds(read(0, 7), read(2_000_000_000, 7))
    assert result["observed_counter_delta"] == 0
    assert result["guarded_rate_fps"] == dict(
        lower=dict(numerator=0, denominator=1), upper=dict(numerator=1, denominator=2)
    )


@pytest.mark.parametrize(
    "a,b",
    [
        (read(0, 5), read(1_000_000_000, 4)),
        (read(0, 0, end=1_000_000_000), read(1_000_000_000, 5)),
        (read(10, 0, end=0), read(1_000_000_000, 5)),
        (read(0, 0), read(1_000_000_000, 5, clock="worker-monotonic-" + "f" * 64)),
        ({**read(0, 0), "counter": True}, read(1_000_000_000, 5)),
        ({"at_ns": 0, "counter": 0}, read(1_000_000_000, 5)),
        ({**read(0, 0), "extra": "field"}, read(1_000_000_000, 5)),
    ],
)
def test_cross_clock_reversal_reset_and_unbracketed_reads_fail(a, b):
    with pytest.raises(ValueError, match=ERROR):
        counter_rate_bounds(a, b)


def test_guarded_separation_and_borderline_intervals_do_not_create_diagnoses():
    args = [read(0, 0), read(2_000_000_000, 54), read(3_000_000_000, 60), read(5_000_000_000, 108)]
    result = compare_counter_rate_bounds(*args, target_fps=24)
    assert result["state"] == "guarded_window_separation"
    assert result["diagnostic_label"] is None and result["acquisition_authority"] is False
    args[1] = read(2_000_000_000, 49)
    result = compare_counter_rate_bounds(*args, target_fps=24)
    assert result["guarded_separation"] is False
    assert result["reason_codes"] == [
        "initial_guarded_rate_not_above_target",
        "guarded_windows_not_separated",
    ]
    with pytest.raises(ValueError):
        compare_counter_rate_bounds(*args, target_fps=True)
    args[2] = read(1_000_000_000, 60)
    with pytest.raises(ValueError):
        compare_counter_rate_bounds(*args, target_fps=24)


def test_parser_uses_worker_clock_and_preserves_legacy_unavailability():
    original = acquisition()
    result = inspect_native_counter_reads(original)
    assert (
        result["state"] == "available" and result["guarded_contrast"]["guarded_separation"] is True
    )
    changed = copy.deepcopy(original)
    for row in changed["events"][1:]:
        row["at_ns"] = 0
    assert inspect_native_counter_reads(changed) == result
    for row in changed["events"][1:]:
        del row["native_read"]
    old = inspect_native_counter_reads(changed)
    assert old["state"] == "unavailable" and old["reason_codes"] == [
        "native_worker_read_brackets_missing"
    ]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda a: a["events"][2].pop("native_read"),
        lambda a: a["events"][2]["native_read"].update(clock_id="worker-monotonic-" + "f" * 64),
        lambda a: a["events"][2]["native_read"].update(basis="parent_elapsed_ns"),
        lambda a: a["events"][2].update(sequence=1),
        lambda a: a["events"][4].update(encoded_buffers=0),
        lambda a: a["events"][2].update(configured_fps=24),
        lambda a: a["events"][0]["request"].update(target_fps=True),
        lambda a: a.update(status="failed"),
    ],
)
def test_partial_foreign_replayed_or_changed_counter_evidence_fails(mutate):
    data = acquisition()
    mutate(data)
    with pytest.raises(ValueError, match=ERROR):
        inspect_native_counter_reads(data)


def test_generation_clock_identity_is_key_order_independent_and_closed():
    assert native_worker_clock_id(dict(reversed(list(GEN.items())))) == CLOCK
    for bad in ({**GEN, "extra": "x"}, {**GEN, "peer": True}, None):
        with pytest.raises(ValueError, match=ERROR):
            native_worker_clock_id(bad)
