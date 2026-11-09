#!/usr/bin/env python3
"""Explain frozen fitting-fold ambiguity; never fit a replacement or open query cases."""

import argparse
import hashlib
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path
from statistics import median

from latency_fingerprinting.analytical.policy_release import payload_hash
from latency_fingerprinting.evaluation.combined_interval_candidate import FEATURES
from latency_fingerprinting.evaluation.counter_specific_candidate import (
    counter_specific_candidate_spec,
    fit_counter_specific_candidate,
)
from latency_fingerprinting.evaluation.counter_specific_projection import (
    project_counter_specific_resource,
)
from latency_fingerprinting.evaluation.fixture_conditions import CONDITIONS
from latency_fingerprinting.json_io import strict_json_loads

RELEASE = "n11-counter-specific-calibration-diagnosis-v1"


def ratio(value):
    return {"numerator": value.numerator, "denominator": value.denominator}


def fraction(value):
    return Fraction(value["numerator"], value["denominator"])


def distance_terms(query, center):
    return (
        max(Fraction(), query[0] - center[1], center[0] - query[1]),
        max(abs(query[0] - center[1]), abs(query[1] - center[0])),
    )


def shared_query_gap_lower(query, own, rival):
    """Exact coordinate minimum with a shared query point, independent center boxes.

    The piecewise affine contrast is distance(x, rival box) minus maximum
    distance(x, own box). Its knots are rival endpoints and the own midpoint;
    a minimum over the query interval occurs at a knot or an interval endpoint.
    This diagnostic still treats different coordinates as independent. It is
    not a replacement classifier and does not model shared-baseline dependence.
    """
    candidates = {query[0], query[1]}
    for value in (rival[0], rival[1], (own[0] + own[1]) / 2):
        candidates.add(max(query[0], min(query[1], value)))
    return min(
        max(Fraction(), rival[0] - value, value - rival[1])
        - max(abs(value - own[0]), abs(value - own[1]))
        for value in candidates
    )


def diagnose_fit(fitted):
    if fitted["method_content_hash"] != counter_specific_candidate_spec()["content_hash"]:
        raise ValueError("wrong frozen method identity")
    rebuilt = fit_counter_specific_candidate(fitted["training"], session_id=fitted["session_id"])
    if payload_hash(rebuilt) != payload_hash(fitted["calibration"]):
        raise ValueError("frozen calibration does not replay")
    if len(rebuilt["folds"]) != 6 or rebuilt["calibration_query_count"] != 18:
        raise ValueError("complete six-block fitting folds required")
    projected = {}
    for block, slots in fitted["training"].items():
        projected[block] = {}
        for condition, slot in slots.items():
            response = project_counter_specific_resource(slot["source"])
            if response["state"] != "candidate_combined_response_available":
                raise ValueError("complete response required for distance diagnosis")
            projected[block][condition] = {
                name: (fraction(row["lower"]), fraction(row["upper"]))
                for name, row in response["features"].items()
            }
    summaries = {
        c: {"responses": 0, "robust_correct": 0, "ambiguous": 0, "robust_wrong": 0}
        for c in CONDITIONS
    }
    cases, drivers = [], Counter()
    nominal_count, shared_count = 0, 0
    for fold in rebuilt["folds"]:
        held = fold["held_out_block_id"]
        centers = {
            c: {
                name: tuple(
                    median([rows[c][name][i] for b, rows in projected.items() if b != held])
                    for i in (0, 1)
                )
                for name in FEATURES
            }
            for c in CONDITIONS
        }
        for recorded in fold["queries"]:
            truth = recorded["condition"]
            query, own = projected[held][truth], centers[truth]
            terms = {
                c: {name: distance_terms(query[name], centers[c][name]) for name in FEATURES}
                for c in CONDITIONS
            }
            replayed = {
                c: {
                    edge: ratio(sum(terms[c][n][i] for n in FEATURES) / len(FEATURES))
                    for i, edge in enumerate(("lower", "upper"))
                }
                for c in CONDITIONS
            }
            if replayed != recorded["distances"]:
                raise ValueError("independent distance reconstruction disagrees")
            comparisons = {}
            for rival in CONDITIONS:
                if rival == truth:
                    continue
                coordinates = {}
                for name in FEATURES:
                    q, a, b = query[name], own[name], centers[rival][name]
                    independent = terms[rival][name][0] - terms[truth][name][1]
                    nominal = abs(sum(q) / 2 - sum(b) / 2) - abs(sum(q) / 2 - sum(a) / 2)
                    coordinates[name] = {
                        "own_distance_upper": ratio(terms[truth][name][1]),
                        "rival_distance_lower": ratio(terms[rival][name][0]),
                        "independent_margin": ratio(independent),
                        "shared_query_margin_lower": ratio(shared_query_gap_lower(q, a, b)),
                        "midpoint_margin": ratio(nominal),
                    }
                comparisons[rival] = {
                    key: ratio(sum(fraction(v[key]) for v in coordinates.values()) / len(FEATURES))
                    for key in (
                        "independent_margin",
                        "shared_query_margin_lower",
                        "midpoint_margin",
                    )
                }
                comparisons[rival]["coordinate_terms_unscaled"] = coordinates
            limiting = min(
                comparisons, key=lambda c: fraction(comparisons[c]["independent_margin"])
            )
            kind = (
                "ambiguous"
                if recorded["robust_condition"] is None
                else "robust_correct"
                if recorded["uniquely_correct"]
                else "robust_wrong"
            )
            summaries[truth]["responses"] += 1
            summaries[truth][kind] += 1
            nominal = all(fraction(v["midpoint_margin"]) > 0 for v in comparisons.values())
            shared = all(fraction(v["shared_query_margin_lower"]) > 0 for v in comparisons.values())
            nominal_count += nominal
            shared_count += shared
            if kind != "robust_correct":
                for name, values in comparisons[limiting]["coordinate_terms_unscaled"].items():
                    if fraction(values["independent_margin"]) < 0:
                        drivers[name] += 1
            cases.append(
                {
                    "held_out_fitting_block": held,
                    "condition": truth,
                    "recorded_robust_condition": recorded["robust_condition"],
                    "recorded_outcome": kind,
                    "limiting_rival": limiting,
                    "pairwise_truth_margins": comparisons,
                    "midpoint_truth_strictly_closest_diagnostic_only": nominal,
                    "shared_query_truth_strictly_separated_diagnostic_only": shared,
                }
            )
    envelopes = {
        c: {
            name: {
                "minimum_lower": ratio(min(rows[c][name][0] for rows in projected.values())),
                "maximum_upper": ratio(max(rows[c][name][1] for rows in projected.values())),
                "median_interval_width": ratio(
                    median([rows[c][name][1] - rows[c][name][0] for rows in projected.values()])
                ),
            }
            for name in FEATURES
        }
        for c in CONDITIONS
    }
    return {
        "release": RELEASE,
        "method_content_hash": fitted["method_content_hash"],
        "frozen_calibration_replayed": True,
        "all_recorded_distances_reconstructed_exactly": True,
        "scope": "posthoc_training_fold_diagnosis_not_validation_or_method_adoption",
        "query_cases_opened": 0,
        "calibration_state_unchanged": rebuilt["state"],
        "thresholds_unchanged": rebuilt["thresholds"],
        "condition_summary": summaries,
        "negative_coordinate_terms_in_failed_limiting_comparison": dict(drivers),
        "exploratory_only": {
            "midpoint_truth_strictly_closest_count": nominal_count,
            "shared_query_truth_strictly_separated_count": shared_count,
            "fitting_responses": len(cases),
            "classifier_fitted_or_changed": False,
            "thresholds_weights_or_features_tuned": False,
            "held_out_performance_estimated": False,
            "shared_query_bound_does_not_restore_cross_coordinate_dependence": True,
        },
        "training_response_envelopes": envelopes,
        "cases": cases,
        "empirical_acceptance": False,
        "acquisition_authority": False,
    }


def diagnose_file(fit, expected_sha256, output):
    raw = fit.read_bytes()
    digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise ValueError("frozen fitting byte hash differs")
    if output.resolve().is_relative_to(fit.parent.resolve()) or fit.resolve().is_relative_to(
        output.resolve()
    ):
        raise ValueError("diagnostic output must be separate from frozen inputs")
    result = diagnose_fit(strict_json_loads(raw.decode("utf-8")))
    if fit.read_bytes() != raw:
        raise ValueError("frozen fitting bytes changed during diagnosis")
    output.mkdir(mode=0o700)
    result["input_fit_sha256"] = digest
    (output / "diagnosis.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fit", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = diagnose_file(args.fit, args.expected_sha256, args.output)
    print(json.dumps({k: result[k] for k in ("release", "condition_summary", "exploratory_only")}))


if __name__ == "__main__":
    main()
