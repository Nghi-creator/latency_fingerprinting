#!/usr/bin/env python3
"""Budget precision from frozen fitting inputs and explicit hypothetical rate boxes."""

import argparse
import hashlib
import json
from fractions import Fraction
from pathlib import Path
from statistics import median

from latency_fingerprinting.evaluation.fixture_conditions import CONDITIONS
from latency_fingerprinting.evaluation.shared_window_projection import project_shared_window_source
from latency_fingerprinting.evaluation.shared_window_separation import (
    FEATURES,
    GROUPS,
    _contrast,
    _hull,
    _interval,
    _ratio,
    compare_shared_window_centers,
)
from latency_fingerprinting.json_io import strict_json_loads

RELEASE = "n11-shared-window-precision-planning-v1"
NOMINAL_FLOOR = Fraction(12, 1000)
UNCERTAINTY_BUDGET = Fraction(9, 1000)
RESIDUAL_TARGET = NOMINAL_FLOOR - UNCERTAINTY_BUDGET
TICKS = {
    "encoded": Fraction(1),
    "cpu_quota_fraction": Fraction(1, 2_000_000),
    "throttled_seconds_per_wall_second": Fraction(1, 1_000_000),
}
ELAPSED_ERROR = {g: Fraction(1 if g == "encoded" else 5, 1000) for g in GROUPS}


def planned_rate_bounds(rate, duration, tick, elapsed_error, rounding):
    """Enclose the guarded rate for nearest-tick rounding and bounded elapsed error."""
    count = rate * duration
    allowance = tick * (1 + rounding)
    return (
        max(Fraction(), count - allowance) / (duration + elapsed_error),
        (count + allowance) / (duration - elapsed_error),
    )


def _hulls(box):
    return {
        name: _hull(box[group][a], box[group][b], group == "encoded")
        for group, terms in GROUPS.items()
        for name, (a, b) in terms.items()
    }


def _point_box(point):
    return {g: {p: (x, x) for p, x in phases.items()} for g, phases in point.items()}


def _interval_report(bounds):
    return dict(lower=_ratio(bounds[0]), upper=_ratio(bounds[1]))


def _scenario(boxes, nominal, label):
    hulls = {key: _hulls(box) for key, box in boxes.items()}
    records = []
    certificates = 0
    for (block, condition), features in nominal.items():
        peers = {c: [(b, c) for b, cc in boxes if b != block and cc == c] for c in CONDITIONS}
        centers = {
            c: {
                name: tuple(median(hulls[key][name][i] for key in keys) for i in (0, 1))
                for name in FEATURES
            }
            for c, keys in peers.items()
        }
        reference_centers = {
            c: {name: median(nominal[key][name] for key in keys) for name in FEATURES}
            for c, keys in peers.items()
        }
        excursions = {
            name: max(abs(x - v) for v in hulls[block, condition][name])
            for name, x in features.items()
        }
        query_penalty = 2 * sum(excursions.values()) / len(FEATURES)
        certificate = compare_shared_window_centers(
            {
                g: {p: _interval_report(x) for p, x in rows.items()}
                for g, rows in boxes[block, condition].items()
            },
            {
                c: {name: _interval_report(x) for name, x in rows.items()}
                for c, rows in centers.items()
            },
        )
        certificates += certificate["separated_condition"] == condition
        for rival in CONDITIONS:
            if rival == condition:
                continue
            nominal_margin = sum(
                abs(x - reference_centers[rival][name])
                - abs(x - reference_centers[condition][name])
                for name, x in features.items()
            ) / len(FEATURES)
            midpoint_margin = sum(
                _contrast(x, centers[condition][name], centers[rival][name])
                for name, x in features.items()
            ) / len(FEATURES)
            center_penalty = nominal_margin - midpoint_margin
            records.append(
                dict(
                    block=block,
                    condition=condition,
                    rival=rival,
                    nominal_margin=nominal_margin,
                    center_penalty=center_penalty,
                    query_penalty=query_penalty,
                    combined_penalty=center_penalty + query_penalty,
                    sufficient_lower=midpoint_margin - query_penalty,
                )
            )
    meets = sum(
        row["nominal_margin"] >= NOMINAL_FLOOR and row["combined_penalty"] <= UNCERTAINTY_BUDGET
        for row in records
    )
    return dict(
        scenario=label,
        pair_count=len(records),
        pairs_meeting_budget=meets,
        fitting_truth_certificates=certificates,
        minimum_nominal_margin=_ratio(min(row["nominal_margin"] for row in records)),
        maximum_combined_penalty=_ratio(max(row["combined_penalty"] for row in records)),
        minimum_sufficient_lower=_ratio(min(row["sufficient_lower"] for row in records)),
        comparisons=[
            {k: _ratio(v) if isinstance(v, Fraction) else v for k, v in row.items()}
            for row in records
        ],
    )


def plan(fit_path, expected_sha256):
    raw = fit_path.read_bytes()
    digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise ValueError("fitting artifact hash differs")
    training = strict_json_loads(raw.decode("utf-8"))["training"]
    if len(training) != 6 or any(set(rows) != set(CONDITIONS) for rows in training.values()):
        raise ValueError("six complete fitting blocks required")
    boxes = {}
    for block, rows in sorted(training.items()):
        for condition in CONDITIONS:
            projection = project_shared_window_source(rows[condition]["source"])
            if projection["state"] != "shared_window_rates_available":
                raise ValueError("complete rate projection required")
            boxes[block, condition] = {
                g: {p: _interval(v) for p, v in phases.items()}
                for g, phases in projection["phase_rates"].items()
            }
    points = {
        key: {g: {p: sum(x) / 2 for p, x in phases.items()} for g, phases in box.items()}
        for key, box in boxes.items()
    }
    nominal = {
        key: {n: x[0] for n, x in _hulls(_point_box(v)).items()} for key, v in points.items()
    }
    scenarios = [_scenario(boxes, nominal, {"kind": "recorded_guarded_rates"})]
    for duration, rounding, elapsed_error in (
        (5, Fraction(), dict.fromkeys(GROUPS, Fraction())),
        *((t, Fraction(1, 2), ELAPSED_ERROR) for t in (5, 12, 16, 20, 24)),
    ):
        planned = {
            key: {
                g: {
                    p: planned_rate_bounds(x, duration, TICKS[g], elapsed_error[g], rounding)
                    for p, x in phases.items()
                }
                for g, phases in point.items()
            }
            for key, point in points.items()
        }
        scenarios.append(
            _scenario(
                planned,
                nominal,
                dict(
                    kind="hypothetical_constant_rate_windows",
                    duration_seconds=duration,
                    nearest_tick_rounding_allowance=_ratio(rounding),
                    elapsed_error_seconds={g: _ratio(e) for g, e in elapsed_error.items()},
                ),
            )
        )
    if fit_path.read_bytes() != raw:
        raise ValueError("fitting artifact changed during planning")
    return dict(
        release=RELEASE,
        input_fit_sha256=digest,
        fitting_cases=18,
        nominal_margin_floor=_ratio(NOMINAL_FLOOR),
        combined_uncertainty_budget=_ratio(UNCERTAINTY_BUDGET),
        sufficient_residual_target=_ratio(RESIDUAL_TARGET),
        scenarios=scenarios,
        query_cases_used=0,
        empirical_acceptance=False,
        acquisition_authority=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fit", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(plan(args.fit, args.expected_sha256), indent=2))


if __name__ == "__main__":
    main()
