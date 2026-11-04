"""Invented hand vectors; never native evidence or accepted diagnostic sources."""

import copy

import pytest

from latency_fingerprinting.evaluation.capacity_calibration import (
    ERROR,
    GRID,
    METHOD,
    inspect_capacity_confirmation,
    select_capacity_calibration,
)
from latency_fingerprinting.evaluation.contrast_bounds import native_worker_clock_id


def case(index, *, initial=27, confirmation=False):
    role = "confirmation" if confirmation else "calibration"
    identity = f"slot{index}" + ("confirmation" if confirmation else "")
    generation = dict(owner=identity, pipeline="pipeline", peer="peer")
    clock = native_worker_clock_id(generation)
    method = "n11-contained-pacing-capacity-" + role + "-v1"
    events = [dict(kind="n11_pair_dispatched", request=dict(generation=generation, target_fps=24))]
    sequence = 0
    for phase, offset, base, rate in [
        ("healthy", 1, 0, 30),
        ("degraded", 5, 200, initial),
        ("relief", 9, 400, 24),
        ("recovery", 13, 600, initial),
        ("post", 17, 800, 30),
    ]:
        rows = []
        for second in range(4):
            sequence += 1
            time = (offset + second) * 10**9
            rows.append(
                dict(
                    kind="n11_pair_native",
                    phase=phase,
                    sequence=sequence,
                    at_ns=time,
                    configured_fps=24 if phase == "relief" else 30,
                    negotiated_fps=24 if phase == "relief" else 30,
                    encoded_buffers=base + second * rate,
                    native_read=dict(
                        method="native-counter-read-brackets-v1",
                        clock_id=clock,
                        basis="worker_elapsed_monotonic_ns",
                        read_start_ns=time,
                        read_end_ns=time,
                    ),
                )
            )
        if phase in ("healthy", "post"):
            events.append(dict(kind="n11_pacing_reference", phase=phase, samples=rows))
        else:
            events.extend(rows)
    return dict(
        plan=dict(
            schema_version="n11-contained-pacing-capacity-" + role + "-plan-v1",
            mode=f"engineering-n11-capacity-{role}-{index}",
            retry_allowed=False,
            observations=1,
            phases=["degraded", "relief", "recovery"],
            target_fps=[30, 24, 30],
            action_duration_ms=5000,
            labels="unavailable",
            capacity=dict(
                method=METHOD,
                role=role,
                grid_index=index,
                grid_delay_us=list(GRID),
                selection_sha256="sha256:" + "f" * 64 if confirmation else None,
                native_reference_reads_required=True,
                native_counter_read_method="native-counter-read-brackets-v1",
            ),
            fault=dict(
                method="n11-owned-pacing-capacity-" + role + "-v1",
                delay_us=GRID[index],
                maximum_active_ms=20000,
                native_reference_ms=2000,
                establishment_ms=1000,
            ),
            image="sha256:" + "a" * 64,
            source_manifest_hash="sha256:" + "b" * 64,
            producer_revision="c" * 40,
            core_revision="d" * 40,
            acquisition_id="n11-raw-" + identity,
        ),
        acquisition=dict(
            status="passed",
            method=method,
            live_authority=False,
            events=events,
            role="engineering_capacity_" + role + "_label_unavailable",
        ),
        control=dict(
            method=method,
            restoration="verified_by_port",
            ledger_state="clean",
            reserved_ns=7_000_000_000,
            live_authority=False,
            accepted_diagnostic_groups=0,
            diagnostic_label=None,
            capacity=dict(grid_index=index, delay_us=GRID[index], role=role),
            native_counter_reads=dict(state="complete", reference_reads=True),
        ),
    )


def cases():
    return [case(i) for i in range(8)]


def test_complete_grid_selects_lower_median_with_exact_guarded_capacity_bounds():
    result = select_capacity_calibration(cases())
    assert result["selected_grid_index"] == 3 and result["selected_delay_us"] == 34000
    row = result["rows"][0]
    assert row["initial"]["guarded_rate_fps"]["lower"] == dict(numerator=80, denominator=3)
    assert row["initial"]["guarded_rate_fps"]["upper"] == dict(numerator=82, denominator=3)
    assert all(row["conditions"].values())
    assert result["diagnostic_label"] is None and result["accepted_diagnostic_groups"] == 0
    assert result["acquisition_authority"] is False


def test_no_candidate_never_interpolates_or_allocates_confirmation():
    data = [case(i, initial=24) for i in range(8)]
    result = select_capacity_calibration(data)
    assert result["selection_state"] == "no_candidate"
    assert result["selected_grid_index"] is result["selected_delay_us"] is None
    assert all(not row["conditions"]["initial_lower_above_24"] for row in result["rows"])
    with pytest.raises(ValueError, match=ERROR):
        inspect_capacity_confirmation(data, result, case(0, confirmation=True))


def test_selection_uses_capacity_only_and_never_relief_diagnostic_separation():
    data = cases()
    for item in data:
        relief = [e for e in item["acquisition"]["events"] if e.get("phase") == "relief"]
        for i, row in enumerate(relief):
            row["encoded_buffers"] = 400 + i * 30  # valid continuity; contrast is erased
        item["acquisition"]["n3_predictions"] = "arbitrary ignored declaration"
    result = select_capacity_calibration(data)
    assert result["selected_grid_index"] == 3
    assert all(row["qualifies"] for row in result["rows"])


def test_only_qualifying_points_enter_median_and_extremes_are_retained():
    data = [case(i, initial=27 if i in (2, 4, 5, 7) else 30) for i in range(8)]
    result = select_capacity_calibration(data)
    assert len(result["rows"]) == 8 and result["selected_grid_index"] == 4
    assert result["rows"][0]["conditions"]["initial_upper_at_most_95pct_healthy_lower"] is False


@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: c.pop(),
        lambda c: c.reverse(),
        lambda c: c.__setitem__(1, copy.deepcopy(c[0])),
        lambda c: c[0]["plan"].update(source_manifest_hash="sha256:" + "f" * 64),
        lambda c: c[0]["plan"]["fault"].update(delay_us=1),
        lambda c: c[0]["plan"]["capacity"].update(grid_index=False),
        lambda c: c[0]["plan"]["capacity"].update(grid_delay_us=[False, *GRID[1:]]),
        lambda c: c[0]["acquisition"].update(status="failed"),
        lambda c: c[0]["control"].update(restoration="unverified"),
        lambda c: c[0]["control"]["native_counter_reads"].update(reference_reads=False),
        lambda c: c[0]["acquisition"]["events"][1]["samples"][1].pop("native_read"),
        lambda c: c[0]["acquisition"]["events"][1]["samples"][1].update(encoded_buffers=-1),
        lambda c: c[0]["acquisition"]["events"][1]["samples"][1].update(sequence=1),
        lambda c: c[0]["acquisition"]["events"][1]["samples"][1]["native_read"].update(
            read_start_ns=10**9
        ),
        lambda c: c[0]["acquisition"]["events"][1]["samples"][1]["native_read"].update(
            clock_id="worker-monotonic-" + "f" * 64
        ),
    ],
)
def test_missing_foreign_reused_or_partial_evidence_fails_closed(mutate):
    data = cases()
    mutate(data)
    with pytest.raises(ValueError):
        select_capacity_calibration(data)


def test_fresh_confirmation_recomputes_selection_without_accepting_n3_or_labels():
    data = cases()
    selection = select_capacity_calibration(data)
    result = inspect_capacity_confirmation(data, selection, case(3, confirmation=True))
    assert result["guarded_contrast"]["guarded_separation"] is True
    assert result["combined_contrast"] == "unavailable"
    assert result["accepted_diagnostic_groups"] == 0
    selection["selected_grid_index"] = 4
    with pytest.raises(ValueError, match=ERROR):
        inspect_capacity_confirmation(data, selection, case(4, confirmation=True))


@pytest.mark.parametrize("mutation", ["index", "source", "reused", "selection_hash"])
def test_confirmation_cannot_change_source_or_reuse_calibration(mutation):
    data = cases()
    selection = select_capacity_calibration(data)
    new = case(3, confirmation=True)
    if mutation == "index":
        new = case(4, confirmation=True)
    elif mutation == "source":
        new["plan"]["image"] = "sha256:" + "f" * 64
    elif mutation == "reused":
        new["plan"]["acquisition_id"] = data[3]["plan"]["acquisition_id"]
    else:
        new["plan"]["capacity"]["selection_sha256"] = None
    with pytest.raises(ValueError):
        inspect_capacity_confirmation(data, selection, new)
