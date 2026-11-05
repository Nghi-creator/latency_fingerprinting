"""Synthetic read brackets and counters; no native execution or scientific acceptance."""

from copy import deepcopy
from fractions import Fraction

import pytest

from latency_fingerprinting.evaluation import temporal_rate_response as candidate

CLOCK = "worker-monotonic-" + "a" * 64


def windows(rates=(30, 20, 16, 30)):
    result, counter, sequence = {}, 0, 0
    for index, (phase, rate) in enumerate(zip(candidate.PHASES, rates, strict=True)):
        rows = []
        for i in range(7):
            start = index * 4_000_000_000 + i * 500_000_000
            rows.append(
                dict(
                    clock_id=CLOCK,
                    read_start_ns=start,
                    read_end_ns=start + 100_000,
                    counter=counter + i * rate // 2,
                    sequence=sequence + i,
                )
            )
        counter, sequence = rows[-1]["counter"] + 10, rows[-1]["sequence"] + 1
        result[phase] = rows
    return result


def value(ratio):
    return Fraction(ratio["numerator"], ratio["denominator"])


def test_exact_guarded_intervals_retain_reference_and_decline_authority():
    data = windows()
    result = candidate.temporal_rate_response(data)
    assert result["state"] == "candidate_response_available"
    healthy = result["windows"]["healthy"]["rate"]["guarded_rate_fps"]
    assert value(healthy["lower"]) == Fraction(89 * 10**9, 3_000_100_000)
    assert value(healthy["upper"]) == Fraction(91 * 10**9, 2_999_900_000)
    for name, exact in [
        ("degraded_vs_healthy", Fraction(-1, 3)),
        ("relief_vs_degraded", Fraction(-1, 5)),
        ("post_vs_healthy", 0),
    ]:
        interval = result["features"][name]["ratio_minus_one"]
        assert value(interval["lower"]) < exact < value(interval["upper"])
    assert result["confidence"] is None and result["diagnostic_label"] is None
    assert not result["empirical_acceptance"] and not result["acquisition_authority"]
    assert result["independent_support_groups"] == result["accepted_diagnostic_groups"] == 0
    assert result["underlying_counter_freshness"] == "not_authenticated_by_read_brackets"


def test_healthy_reference_retains_effect_cancelled_by_relief_only_ratio():
    # Proportional degraded/relief rates have the same scalar relative response.
    assert Fraction(24 - 30, 30) == Fraction(16 - 20, 20)
    normal = candidate.temporal_rate_response(windows((30, 30, 24, 30)))
    persistent = candidate.temporal_rate_response(windows((30, 20, 16, 30)))
    a = normal["features"]["degraded_vs_healthy"]["ratio_minus_one"]
    b = persistent["features"]["degraded_vs_healthy"]["ratio_minus_one"]
    assert value(b["upper"]) < value(a["lower"])
    # This only demonstrates algebraic observability on invented inputs.
    assert not persistent["empirical_acceptance"]


def test_zero_denominator_unavailable_without_epsilon_or_partial_vector_acceptance():
    result = candidate.temporal_rate_response(windows((30, 0, 0, 30)))
    assert result["state"] == "unavailable"
    row = result["features"]["relief_vs_degraded"]
    assert row["reason_codes"] == ["denominator_interval_includes_zero"]
    assert row["ratio_minus_one"] is None
    assert result["features"]["post_vs_healthy"]["state"] == "candidate_interval_available"
    assert result["reason_codes"] == ["incomplete_response_vector"]


@pytest.mark.parametrize(
    "kind,reason",
    [
        ("missing", "insufficient_samples"),
        ("short", "window_too_short"),
        ("long", "window_too_long"),
        ("span", "read_span_too_wide"),
        ("gap", "sample_gap_too_wide"),
        ("between", "between_window_gap_too_wide"),
    ],
)
def test_well_formed_but_ineligible_windows_retained_without_trimming(kind, reason):
    data = windows()
    if kind == "missing":
        data["healthy"] = []
    elif kind == "short":
        data["healthy"] = data["healthy"][:4]
    elif kind == "long":
        for i, row in enumerate(data["post"]):
            row["read_start_ns"] = 12_000_000_000 + i * 900_000_000
            row["read_end_ns"] = row["read_start_ns"] + 100_000
    elif kind == "span":
        data["healthy"][0]["read_end_ns"] = 100_000_001
    elif kind == "gap":
        data["healthy"] = [data["healthy"][i] for i in (0, 1, 2, 6)]
    else:
        for row in data["post"]:
            row["read_start_ns"] += 20_000_000_000
            row["read_end_ns"] += 20_000_000_000
    phase = "post" if kind in ("long", "between") else "healthy"
    result = candidate.temporal_rate_response(data)
    assert result["state"] == "unavailable"
    assert reason in result["windows"][phase]["reason_codes"]
    assert result["windows"][phase]["rate"] is None
    assert result["windows"][phase]["sample_count"] == len(data[phase])


@pytest.mark.parametrize(
    "kind",
    [
        "clock",
        "counter",
        "sequence",
        "overlap",
        "reverse",
        "bool",
        "negative",
        "oversized",
        "label",
        "missing_key",
    ],
)
def test_invalid_source_order_types_or_label_bearing_inputs_rejected(kind):
    data = windows()
    row = data["relief"][0]
    if kind == "clock":
        row["clock_id"] = "worker-monotonic-" + "b" * 64
    elif kind == "counter":
        row["counter"] = 0
    elif kind == "sequence":
        row["sequence"] = 0
    elif kind == "overlap":
        row["read_start_ns"] = data["degraded"][-1]["read_end_ns"]
    elif kind == "reverse":
        row["read_end_ns"] = row["read_start_ns"] - 1
    elif kind == "bool":
        row["counter"] = True
    elif kind == "negative":
        row["read_start_ns"] = -1
    elif kind == "oversized":
        row["sequence"] = 2**63
    elif kind == "label":
        row["condition"] = "owned_identity_delay"
    else:
        del row["counter"]
    with pytest.raises(ValueError, match=candidate.ERROR):
        candidate.temporal_rate_response(data)


def test_exact_window_names_bounded_input_and_no_truth_argument():
    data = windows()
    del data["post"]
    with pytest.raises(ValueError):
        candidate.temporal_rate_response(data)
    data = windows()
    data["condition"] = "owned_cpu_pressure"
    with pytest.raises(ValueError):
        candidate.temporal_rate_response(data)
    data = windows()
    data["healthy"] *= 10
    with pytest.raises(ValueError):
        candidate.temporal_rate_response(data)
    with pytest.raises(TypeError):
        candidate.temporal_rate_response(windows(), truth="condition")


def test_deterministic_identity_binds_all_samples_not_only_endpoints():
    data = windows()
    before = deepcopy(data)
    result = candidate.temporal_rate_response(data)
    assert data == before and result == candidate.temporal_rate_response(data)
    data["healthy"][2]["counter"] += 1
    changed = candidate.temporal_rate_response(data)
    assert changed["features"] == result["features"]
    assert changed["input_content_hash"] != result["input_content_hash"]
    assert changed["response_id"] != result["response_id"]


def test_spec_returns_detached_nested_objects():
    spec = candidate.temporal_rate_response_spec()
    spec["window_order"].reverse()
    spec["features"]["post_vs_healthy"]["denominator"] = "relief"
    original = candidate.temporal_rate_response_spec()
    assert original["window_order"] == list(candidate.PHASES)
    assert original["features"]["post_vs_healthy"]["denominator"] == "healthy"


def test_one_buffer_increment_still_has_zero_lower_denominator_bound():
    data = windows()
    base = data["degraded"][0]["counter"]
    for row in data["degraded"]:
        row["counter"] = base
    data["degraded"][-1]["counter"] += 1
    result = candidate.temporal_rate_response(data)
    assert result["windows"]["degraded"]["state"] == "candidate_window_available"
    assert result["features"]["relief_vs_degraded"]["reason_codes"] == [
        "denominator_interval_includes_zero"
    ]


def test_minimum_inner_duration_boundary_is_inclusive():
    data = windows()
    data["healthy"] = [data["healthy"][i] for i in (0, 1, 3, 6)]
    data["healthy"][-1]["read_start_ns"] = 2_000_100_000
    data["healthy"][-1]["read_end_ns"] = 2_000_200_000
    result = candidate.temporal_rate_response(data)
    assert result["windows"]["healthy"]["state"] == "candidate_window_available"
    data["healthy"][-1]["read_start_ns"] -= 1
    result = candidate.temporal_rate_response(data)
    assert result["windows"]["healthy"]["reason_codes"] == ["window_too_short"]


def acquisition():
    from latency_fingerprinting.evaluation.contrast_bounds import native_worker_clock_id

    generation = dict(owner="owner", pipeline="pipeline", peer="peer")
    clock = native_worker_clock_id(generation)
    data = windows()
    for row in data["post"]:
        row["sequence"] += 2
    last = data["relief"][-1]
    data["recovery"] = [
        dict(
            clock_id=clock,
            read_start_ns=11_200_000_000 + i * 500_000_000,
            read_end_ns=11_200_100_000 + i * 500_000_000,
            sequence=last["sequence"] + i + 1,
            counter=last["counter"] + i + 1,
        )
        for i in range(2)
    ]
    events = [dict(kind="n11_pair_dispatched", request=dict(target_fps=24, generation=generation))]
    for phase in ("healthy", "degraded", "relief", "recovery", "post"):
        samples = []
        for row in data[phase]:
            samples.append(
                dict(
                    sequence=row["sequence"],
                    encoded_buffers=row["counter"],
                    configured_fps=24 if phase == "relief" else 30,
                    negotiated_fps=24 if phase == "relief" else 30,
                    native_read=dict(
                        method="native-counter-read-brackets-v1",
                        basis="worker_elapsed_monotonic_ns",
                        clock_id=clock,
                        read_start_ns=row["read_start_ns"],
                        read_end_ns=row["read_end_ns"],
                    ),
                    condition_witness=dict(condition="owned_identity_delay", sleep_time_us=34000),
                )
            )
        if phase in ("healthy", "post"):
            events.append(dict(kind="n11_pacing_reference", phase=phase, samples=samples))
        else:
            events.extend(dict(kind="n11_pair_native", phase=phase, **row) for row in samples)
    return dict(
        status="passed",
        method="n11-contained-condition-witness-v1",
        live_authority=False,
        events=events,
    )


def test_projection_strips_labels_doses_and_observer_times_and_validates_recovery():
    data = acquisition()
    before = deepcopy(data)
    result = candidate.project_temporal_rate_response(data)
    assert result["response"]["state"] == "candidate_response_available"
    assert result["all_sample_counts"]["recovery"] == 2
    assert result["omitted_coordinate_phases"] == ["recovery"]
    assert data == before
    for event in data["events"]:
        for row in event.get("samples", [event]):
            row["condition_witness"] = dict(condition="different", sleep_time_us=999999)
            row["at_ns"] = -123456
    changed = candidate.project_temporal_rate_response(data)
    assert changed["response"] == result["response"]
    assert changed["source_payload_hash"] != result["source_payload_hash"]


@pytest.mark.parametrize(
    "kind",
    [
        "missing_reference",
        "duplicate_reference",
        "reference_clock",
        "recovery_counter",
        "post_sequence",
        "reference_target",
    ],
)
def test_projection_rejects_source_changes_even_outside_response_coordinates(kind):
    data = acquisition()
    reference = next(e for e in data["events"] if e.get("kind") == "n11_pacing_reference")
    if kind == "missing_reference":
        data["events"].remove(reference)
    elif kind == "duplicate_reference":
        data["events"].append(deepcopy(reference))
    elif kind == "reference_clock":
        reference["samples"][0]["native_read"]["clock_id"] = CLOCK
    elif kind == "reference_target":
        reference["samples"][0]["negotiated_fps"] = 24
    elif kind == "recovery_counter":
        next(e for e in data["events"] if e.get("phase") == "recovery")["encoded_buffers"] = 0
    else:
        post = next(e for e in data["events"] if e.get("phase") == "post")
        post["samples"][0]["sequence"] = 0
    with pytest.raises(ValueError, match=candidate.ERROR):
        candidate.project_temporal_rate_response(data)
