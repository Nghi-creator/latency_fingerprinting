"""Opt-in, fixed-grid engineering capacity selection; no diagnostic acceptance.

Inputs are declarations. Callers must independently validate source custody and
the raw controller/property/cleanup evidence with the bound producer inspector.
Hashes bind content, not authenticity. No relief rate participates in selection.
"""

import hashlib
import json
import re
from collections.abc import Mapping
from fractions import Fraction

from .contrast_bounds import _inspect_native_counter_reads, _integer, _read, _window

GRID = (0, 30000, 32000, 34000, 36000, 37500, 40000, 50000)
METHOD = "n11-capacity-calibration-v1"
ERROR = "invalid_capacity_calibration"


def _require(condition):
    if not condition:
        raise ValueError(ERROR)


def _hash(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _one(events, kind, phase=None):
    rows = [
        e for e in events if e.get("kind") == kind and (phase is None or e.get("phase") == phase)
    ]
    _require(len(rows) == 1)
    return rows[0]


def _case(case, index, *, confirmation=False):
    _require(isinstance(case, Mapping) and set(case) == {"plan", "acquisition", "control"})
    plan, run, control = (case[k] for k in ("plan", "acquisition", "control"))
    _require(all(isinstance(v, Mapping) for v in (plan, run, control)))
    role = "confirmation" if confirmation else "calibration"
    method = "n11-contained-pacing-capacity-" + role + "-v1"
    capacity = plan.get("capacity", {})
    _require(isinstance(capacity, Mapping) and isinstance(plan.get("fault"), Mapping))
    _require(
        plan.get("schema_version") == "n11-contained-pacing-capacity-" + role + "-plan-v1"
        and plan.get("mode") == f"engineering-n11-capacity-{role}-{index}"
        and plan.get("retry_allowed") is False
        and plan.get("observations") == 1
        and plan.get("phases") == ["degraded", "relief", "recovery"]
        and plan.get("target_fps") == [30, 24, 30]
        and plan.get("action_duration_ms") == 5000
        and plan.get("labels") == "unavailable"
        and capacity.get("method") == METHOD
        and capacity.get("role") == role
        and type(capacity.get("grid_index")) is int
        and capacity["grid_index"] == index
        and capacity.get("grid_delay_us") == list(GRID)
        and all(type(v) is int for v in capacity["grid_delay_us"])
        and type(plan["fault"].get("delay_us")) is int
        and capacity.get("native_reference_reads_required") is True
        and capacity.get("native_counter_read_method") == "native-counter-read-brackets-v1"
        and plan.get("fault")
        == dict(
            method="n11-owned-pacing-capacity-" + role + "-v1",
            delay_us=GRID[index],
            maximum_active_ms=20000,
            native_reference_ms=2000,
            establishment_ms=1000,
        )
    )
    context = {
        k: plan.get(k)
        for k in ("image", "source_manifest_hash", "producer_revision", "core_revision")
    }
    for key, value in context.items():
        pattern = (
            r"sha256:[a-f0-9]{64}" if key in ("image", "source_manifest_hash") else r"[a-f0-9]{40}"
        )
        _require(type(value) is str and re.fullmatch(pattern, value) is not None)
    _require(
        type(plan.get("acquisition_id")) is str
        and re.fullmatch(r"n11-raw-[a-z0-9-]{1,40}", plan["acquisition_id"]) is not None
    )
    _require(run.get("role") == "engineering_capacity_" + role + "_label_unavailable")
    # These declarations are cross-checked, not substituted for raw producer validation.
    _require(
        control.get("method") == method
        and control.get("restoration") == "verified_by_port"
        and control.get("ledger_state") == "clean"
        and control.get("reserved_ns") == 7_000_000_000
        and control.get("live_authority") is False
        and control.get("accepted_diagnostic_groups") == 0
        and control.get("diagnostic_label") is None
        and control.get("capacity") == dict(grid_index=index, delay_us=GRID[index], role=role)
        and control.get("native_counter_reads", {}).get("state") == "complete"
        and control["native_counter_reads"].get("reference_reads") is True
    )
    inspection = _inspect_native_counter_reads(run, method)
    _require(inspection["state"] == "available")
    events = run["events"]
    native = [e for e in events if e.get("kind") == "n11_pair_native"]
    references = {
        p: _one(events, "n11_pacing_reference", p).get("samples") for p in ("healthy", "post")
    }
    _require(
        all(isinstance(rows, list) and 4 <= len(rows) <= 10000 for rows in references.values())
    )
    previous = (-1, -1, -1)
    reads = {p: [] for p in ("healthy", "degraded", "relief", "recovery", "post")}
    for phase, rows in (
        ("healthy", references["healthy"]),
        (None, native),
        ("post", references["post"]),
    ):
        for row in rows:
            _require(isinstance(row, Mapping))
            evidence = row.get("native_read", {})
            _require(
                set(evidence) == {"method", "clock_id", "basis", "read_start_ns", "read_end_ns"}
                and evidence.get("method") == "native-counter-read-brackets-v1"
                and evidence.get("basis") == "worker_elapsed_monotonic_ns"
                and evidence.get("clock_id") == inspection["clock_id"]
            )
            read = dict(
                clock_id=evidence["clock_id"],
                read_start_ns=evidence["read_start_ns"],
                read_end_ns=evidence["read_end_ns"],
                counter=row.get("encoded_buffers"),
            )
            _, start, end, counter = _read(read)
            sequence = _integer(row.get("sequence"))
            _require(sequence > previous[0] and start > previous[1] and counter >= previous[2])
            previous = sequence, end, counter
            if phase:
                _require(
                    type(row.get("configured_fps")) is int
                    and row["configured_fps"] == 30
                    and type(row.get("negotiated_fps")) is int
                    and row["negotiated_fps"] == 30
                )
            reads[phase or row["phase"]].append(read)
    windows = {p: _window(rows[0], rows[-1]) for p, rows in reads.items()}
    healthy, initial, post = (windows[p] for p in ("healthy", "degraded", "post"))
    # The producer requires >=2 s references in its parent clock. Guarded rates
    # use the actual worker brackets; do not impose a rounded cross-clock duration.
    for reference in references.values():
        _require(
            _integer(reference[-1].get("at_ns")) - _integer(reference[0].get("at_ns"))
            >= 2_000_000_000
        )
    conditions = dict(
        healthy_lower_at_least_27=healthy[1] >= 27,
        initial_lower_above_24=initial[1] > 24,
        initial_upper_at_most_95pct_healthy_lower=initial[2] <= Fraction(95, 100) * healthy[1],
        post_lower_at_least_95pct_healthy_upper=post[1] >= Fraction(95, 100) * healthy[2],
    )
    return (
        dict(
            grid_index=index,
            delay_us=GRID[index],
            acquisition_id=plan["acquisition_id"],
            case_sha256=_hash(case),
            generation_clock_id=inspection["clock_id"],
            healthy=healthy[0],
            initial=initial[0],
            post=post[0],
            conditions=conditions,
            qualifies=all(conditions.values()),
        ),
        context,
        inspection,
    )


def select_capacity_calibration(cases):
    """Select the lower median qualifying index after the complete eight-slot grid.

    Failed/missing slots raise; they never silently become zero or drop out. The
    caller retains the failed prefix and unstarted suffix rather than retrying.
    """
    _require(isinstance(cases, (list, tuple)) and len(cases) == len(GRID))
    rows, contexts = [], []
    for index, case in enumerate(cases):
        row, context, _ = _case(case, index)
        _require(case["plan"]["capacity"].get("selection_sha256") is None)
        rows.append(row)
        contexts.append(context)
    _require(all(c == contexts[0] for c in contexts))
    for key in ("acquisition_id", "case_sha256", "generation_clock_id"):
        _require(len({row[key] for row in rows}) == len(GRID))
    candidates = [row["grid_index"] for row in rows if row["qualifies"]]
    selected = candidates[(len(candidates) - 1) // 2] if candidates else None
    return dict(
        method_release=METHOD,
        **contexts[0],
        selection_state="candidate_for_confirmation" if candidates else "no_candidate",
        selected_grid_index=selected,
        selected_delay_us=None if selected is None else GRID[selected],
        selection_rule="complete_fixed_grid_capacity_only_lower_median_v1",
        grid_delay_us=list(GRID),
        rows=rows,
        input_assurance="internal_consistency_only_requires_independent_source_and_producer_validation",
        scope="engineering_capacity_not_held_out_evaluation_or_transferable_latency_bounds",
        diagnostic_label=None,
        accepted_diagnostic_groups=0,
        acquisition_authority=False,
    )


def inspect_capacity_confirmation(cases, selection, confirmation):
    """Recompute selection, exclude calibration identities and inspect one new run.

    The caller separately binds the original selection-file bytes to the plan and
    checks independent N3. This result alone cannot establish combined contrast.
    """
    expected = select_capacity_calibration(cases)
    _require(selection == expected and expected["selection_state"] == "candidate_for_confirmation")
    index = expected["selected_grid_index"]
    row, context, inspection = _case(confirmation, index, confirmation=True)
    _require(all(context[k] == expected[k] for k in context))
    _require(
        type(confirmation["plan"]["capacity"].get("selection_sha256")) is str
        and re.fullmatch(
            r"sha256:[a-f0-9]{64}", confirmation["plan"]["capacity"]["selection_sha256"]
        )
        is not None
    )
    for key in ("acquisition_id", "case_sha256", "generation_clock_id"):
        _require(row[key] not in {r[key] for r in expected["rows"]})
    return dict(
        method_release="n11-capacity-confirmation-v1",
        calibration_selection_sha256=_hash(expected),
        selected_grid_index=index,
        selected_delay_us=GRID[index],
        confirmation=row,
        guarded_contrast=inspection["guarded_contrast"],
        independent_n3_check="required_separately_unavailable_here",
        combined_contrast="unavailable",
        diagnostic_label=None,
        accepted_diagnostic_groups=0,
        acquisition_authority=False,
    )
