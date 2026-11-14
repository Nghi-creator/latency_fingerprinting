#!/usr/bin/env python3
"""Explore event-span measurement feasibility on frozen fitting data."""

import argparse
import hashlib
import json
from fractions import Fraction
from pathlib import Path

from plan_shared_window_precision import (
    ELAPSED_ERROR,
    TICKS,
    _hulls,
    _point_box,
    _scenario,
    planned_rate_bounds,
)

from latency_fingerprinting.evaluation.fixture_conditions import CONDITIONS
from latency_fingerprinting.evaluation.shared_window_projection import project_shared_window_source
from latency_fingerprinting.evaluation.shared_window_separation import _interval
from latency_fingerprinting.json_io import strict_json_loads


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fit", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    raw = args.fit.read_bytes()
    digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    if digest != args.expected_sha256:
        raise ValueError("fitting artifact hash differs")
    training = strict_json_loads(raw.decode("utf-8"))["training"]
    if len(training) != 6 or any(set(slots) != set(CONDITIONS) for slots in training.values()):
        raise ValueError("six complete fitting blocks required")
    points = {}
    for block, slots in sorted(training.items()):
        for condition, slot in sorted(slots.items()):
            projected = project_shared_window_source(slot["source"])
            if projected["state"] != "shared_window_rates_available":
                raise ValueError("complete rate projection required")
            points[block, condition] = {
                group: {p: sum(_interval(box)) / 2 for p, box in phases.items()}
                for group, phases in projected["phase_rates"].items()
            }
    results = []
    scenarios = [
        (Fraction(t), ms, False) for t, ms in ((2, 1), (2, 5), (3, 1), (3, 5), (4, 5), (5, 5))
    ]
    scenarios += [(Fraction(31, 10), 5, True), (Fraction(4), 5, True)]
    for duration, error_ms, event_aligned in scenarios:
        error = Fraction(error_ms, 1000)
        # Use the next lower whole count and exact event-span length. CPU retains
        # its existing count guard and independent nearest-tick timing model.
        scenario = {}
        adjusted = {}
        for key, point in points.items():
            box = {}
            adjusted[key] = {}
            for group, phases in point.items():
                box[group] = {}
                adjusted[key][group] = {}
                for phase, rate in phases.items():
                    if group == "encoded":
                        count = int(rate * duration)
                        span = Fraction(count) / rate if event_aligned else duration
                        box[group][phase] = (count / (span + error), count / (span - error))
                        adjusted[key][group][phase] = Fraction(count) / span
                    else:
                        box[group][phase] = planned_rate_bounds(
                            rate, duration, TICKS[group], ELAPSED_ERROR[group], Fraction(1, 2)
                        )
                        adjusted[key][group][phase] = rate
            scenario[key] = box
        simulated_nominal = {
            key: {n: bounds[0] for n, bounds in _hulls(_point_box(point)).items()}
            for key, point in adjusted.items()
        }
        results.append(
            _scenario(
                scenario,
                simulated_nominal,
                dict(
                    nominal_span_seconds=str(duration),
                    encoded_elapsed_half_width_ms=error_ms,
                    count_model="floor_of_frozen_midpoint_rate_times_span",
                    elapsed_model="count_divided_by_reference_rate"
                    if event_aligned
                    else "fixed_nominal_span",
                ),
            )
        )
    if args.fit.read_bytes() != raw:
        raise ValueError("fitting artifact changed during planning")
    print(
        json.dumps(
            dict(
                fit_sha256=digest,
                original_midpoint_vectors=len(points),
                scenarios=results,
                query_cases_used=0,
                new_acquisitions=0,
                scope="hypothetical_event_span_precision_sensitivity",
                empirical_acceptance=False,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
