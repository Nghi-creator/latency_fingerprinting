"""Conservative interval-condition candidate; declarations are not study acceptance."""

import re
from collections.abc import Mapping
from copy import deepcopy
from fractions import Fraction
from statistics import median

from ..analytical.policy_release import payload_hash
from .fixture_conditions import CONDITIONS
from .median_response import _alias
from .temporal_rate_response import (
    FEATURES,
    project_temporal_rate_response,
    temporal_rate_projection_spec,
    temporal_rate_response_spec,
)

RELEASE = "n11-temporal-interval-condition-candidate-v1"
ERROR = "invalid_temporal_interval_candidate"
_SPEC = dict(
    release=RELEASE,
    response_contract_hash=temporal_rate_response_spec()["content_hash"],
    projection_contract_hash=temporal_rate_projection_spec()["content_hash"],
    training_blocks=6,
    folds="leave_one_complete_correlated_block_out_other_five_only",
    features=list(FEATURES),
    missingness="all_three_coordinates_and_all_four_windows_required",
    centers="per_condition_coordinate_endpoint_medians_exact_rational",
    distance="mean_absolute_box_distance_enclosure_all_coordinates_equal_weight",
    selection="candidate_upper_distance_strictly_below_every_rival_lower_distance",
    calibration="all_18_fold_responses_robustly_uniquely_correct_or_unavailable",
    thresholds="maximum_correct_upper_distance_per_condition_and_minimum_robust_fold_gap",
    query="rebuild_training_same_session_context_fresh_source_clock_and_block_no_truth_input",
    arithmetic="exact_rational_no_midpoint_epsilon_clipping_or_fitted_scale",
    support="no_rank_support_gate_query_distance_radius_and_gap_must_pass",
    assurance="caller_source_context_condition_and_inspection_bindings_require_external_review",
    independent_support_groups=0,
    empirical_acceptance=False,
    acquisition_authority=False,
)


def temporal_interval_candidate_spec():
    return {**deepcopy(_SPEC), "content_hash": payload_hash(_SPEC)}


def _hash(value):
    if type(value) is not str or re.fullmatch(r"sha256:[a-f0-9]{64}", value) is None:
        raise ValueError(ERROR)


def _ratio(value):
    return dict(numerator=value.numerator, denominator=value.denominator)


def _intervals(response):
    return {
        name: tuple(
            Fraction(
                row["ratio_minus_one"][bound]["numerator"],
                row["ratio_minus_one"][bound]["denominator"],
            )
            for bound in ("lower", "upper")
        )
        for name, row in response["features"].items()
    }


def _centers(prepared):
    return {
        condition: {
            name: tuple(
                median([row[condition]["values"][name][i] for row in prepared.values()])
                for i in (0, 1)
            )
            for name in FEATURES
        }
        for condition in CONDITIONS
    }


def _distance(left, right):
    lower, upper = Fraction(), Fraction()
    for name in FEATURES:
        al, au = left[name]
        bl, bu = right[name]
        lower += max(Fraction(), al - bu, bl - au)
        upper += max(abs(al - bu), abs(au - bl))
    return lower / len(FEATURES), upper / len(FEATURES)


def _score(values, centers):
    distances = {c: _distance(values, center) for c, center in centers.items()}
    gaps = {
        c: min(distances[rival][0] for rival in CONDITIONS if rival != c) - d[1]
        for c, d in distances.items()
    }
    winners = [c for c in CONDITIONS if gaps[c] > 0]
    winner = winners[0] if len(winners) == 1 else None
    return distances, winner, gaps[winner] if winner else None


def _distance_report(distances):
    return {c: dict(lower=_ratio(d[0]), upper=_ratio(d[1])) for c, d in distances.items()}


def _binding(projected, *, condition, context_hash, inspection_sha256):
    if type(condition) is not str or condition not in CONDITIONS:
        raise ValueError(ERROR)
    _hash(context_hash)
    _hash(inspection_sha256)
    return dict(
        release="n11-temporal-condition-binding-candidate-v1",
        condition=condition,
        context_hash=context_hash,
        inspection_sha256=inspection_sha256,
        source_payload_hash=projected["source_payload_hash"],
        response_id=projected["response"]["response_id"],
        assurance=_SPEC["assurance"],
    )


def declare_temporal_condition_binding(acquisition, *, condition, context_hash, inspection_sha256):
    """Bind caller declarations after external witness review; do not authenticate it."""
    try:
        return _binding(
            project_temporal_rate_response(acquisition),
            condition=condition,
            context_hash=context_hash,
            inspection_sha256=inspection_sha256,
        )
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError(ERROR) from None


def _prepare(blocks):
    if not isinstance(blocks, Mapping) or not 1 <= len(blocks) <= 6:
        raise ValueError(ERROR)
    prepared, contexts, origins, clocks, inspections, bindings, missing, unavailable = (
        {},
        set(),
        set(),
        set(),
        set(),
        [],
        [],
        [],
    )
    for block in sorted(blocks):
        _alias(block)
        rows = blocks[block]
        if not isinstance(rows, Mapping) or set(rows) != set(CONDITIONS):
            raise ValueError(ERROR)
        prepared[block] = {}
        for condition in CONDITIONS:
            slot = rows[condition]
            if slot is None:
                missing.append(dict(block_id=block, condition=condition))
                continue
            if not isinstance(slot, Mapping) or set(slot) != {"acquisition", "binding"}:
                raise ValueError(ERROR)
            projected = project_temporal_rate_response(slot["acquisition"])
            binding = slot["binding"]
            if not isinstance(binding, Mapping):
                raise ValueError(ERROR)
            expected = _binding(
                projected,
                condition=condition,
                context_hash=binding.get("context_hash"),
                inspection_sha256=binding.get("inspection_sha256"),
            )
            if dict(binding) != expected:
                raise ValueError(ERROR)
            source, response = projected["source_payload_hash"], projected["response"]
            clock, inspection = response["clock_id"], binding["inspection_sha256"]
            if source in origins or clock in clocks or inspection in inspections:
                raise ValueError(ERROR)
            origins.add(source)
            clocks.add(clock)
            inspections.add(inspection)
            contexts.add(binding["context_hash"])
            bindings.append(dict(block_id=block, content_hash=payload_hash(expected), **expected))
            if response["state"] == "unavailable":
                unavailable.append(
                    dict(block_id=block, condition=condition, reason_codes=response["reason_codes"])
                )
            prepared[block][condition] = dict(
                response_id=response["response_id"],
                values=_intervals(response) if response["state"] != "unavailable" else None,
            )
    if len(contexts) > 1:
        raise ValueError(ERROR)
    return prepared, next(iter(contexts), None), origins, clocks, bindings, missing, unavailable


def _fit(prepared, context, origins, clocks, bindings, missing, unavailable, session_id):
    _alias(session_id)
    reasons = []
    if len(prepared) < 6:
        reasons.append("insufficient_training_blocks")
    if missing:
        reasons.append("incomplete_blocks")
    if unavailable:
        reasons.append("unavailable_training_response")
    folds, radii, gaps = [], {c: [] for c in CONDITIONS}, []
    if not reasons:
        for held, queries in prepared.items():
            training = {b: rows for b, rows in prepared.items() if b != held}
            centers = _centers(training)
            results = []
            for truth in CONDITIONS:
                distances, winner, gap = _score(queries[truth]["values"], centers)
                correct = winner == truth
                results.append(
                    dict(
                        condition=truth,
                        response_id=queries[truth]["response_id"],
                        distances=_distance_report(distances),
                        robust_condition=winner,
                        robust_gap=_ratio(gap) if gap is not None else None,
                        uniquely_correct=correct,
                    )
                )
                if correct:
                    radii[truth].append(distances[truth][1])
                    gaps.append(gap)
            folds.append(
                dict(
                    held_out_block_id=held,
                    training_block_ids=list(training),
                    queries=results,
                    complete_and_correct=all(q["uniquely_correct"] for q in results),
                )
            )
        if not all(f["complete_and_correct"] for f in folds):
            reasons.append("calibration_folds_not_all_robustly_correct")
    payload = dict(
        method_release=RELEASE,
        method_spec=temporal_interval_candidate_spec(),
        state="unavailable" if reasons else "candidate_calibration_available",
        reason_codes=reasons,
        session_id=session_id,
        context_hash=context,
        session_components=1,
        independent_support_groups=0,
        independent_performance="not_estimated_same_session_only",
        bindings=bindings,
        source_payload_hashes=sorted(origins),
        source_clock_ids=sorted(clocks),
        training_block_ids=list(prepared),
        missing_slots=missing,
        unavailable_slots=unavailable,
        folds=folds,
        calibration_query_count=sum(len(f["queries"]) for f in folds),
        thresholds=None
        if reasons
        else dict(
            class_radius={c: _ratio(max(radii[c])) for c in CONDITIONS},
            minimum_gap=_ratio(min(gaps)),
        ),
        centers={}
        if reasons
        else {
            c: {n: dict(lower=_ratio(v[0]), upper=_ratio(v[1])) for n, v in rows.items()}
            for c, rows in _centers(prepared).items()
        },
        diagnostic_label=None,
        confidence=None,
        accepted_diagnostic_groups=0,
        empirical_acceptance=False,
        acquisition_authority=False,
        assurance=_SPEC["assurance"],
    )
    return {**payload, "experiment_id": "temporal-interval-candidate-" + payload_hash(payload)[7:]}


def fit_temporal_interval_candidate(blocks, *, session_id):
    """Reproject original sources and rebuild all folds. No cached fit or query input."""
    try:
        return _fit(*_prepare(blocks), session_id)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError(ERROR) from None


def score_temporal_interval_candidate(
    acquisition, blocks, *, session_id, query_session_id, query_block_id, context_hash
):
    """Predict only under robust interval separation and rebuilt fold radius/gap limits."""
    try:
        _alias(query_session_id)
        _alias(query_block_id)
        _hash(context_hash)
        prepared, context, origins, clocks, bindings, missing, unavailable = _prepare(blocks)
        fitted = _fit(
            prepared, context, origins, clocks, bindings, missing, unavailable, session_id
        )
        projected = project_temporal_rate_response(acquisition)
        response = projected["response"]
        reasons, distances, gap, prediction = [], {}, None, None
        if query_session_id != session_id:
            reasons.append("different_query_session")
        if query_block_id in prepared:
            reasons.append("query_block_overlap")
        if context_hash != context:
            reasons.append("incompatible_query_context")
        if projected["source_payload_hash"] in origins or response["clock_id"] in clocks:
            reasons.append("query_source_or_clock_overlap")
        if fitted["state"] == "unavailable":
            reasons.append("calibration_unavailable")
        if response["state"] == "unavailable":
            reasons.append("query_response_unavailable")
        if not reasons:
            distances, winner, gap = _score(_intervals(response), _centers(prepared))
            if winner is None:
                reasons.append("ambiguous_interval_distances")
            else:
                limits = fitted["thresholds"]
                radius = limits["class_radius"][winner]
                minimum = limits["minimum_gap"]
                if distances[winner][1] > Fraction(radius["numerator"], radius["denominator"]):
                    reasons.append("outside_condition_radius")
                if gap < Fraction(minimum["numerator"], minimum["denominator"]):
                    reasons.append("insufficient_robust_gap")
                if not reasons:
                    prediction = winner
        return dict(
            method_release=RELEASE,
            experiment_id=fitted["experiment_id"],
            state="abstain" if reasons else "candidate_condition_prediction",
            reason_codes=reasons,
            predicted_condition=prediction,
            distances=_distance_report(distances),
            robust_gap=_ratio(gap) if gap is not None else None,
            query_response_id=response["response_id"],
            query_block_id=query_block_id,
            session_id=session_id,
            session_components=1,
            independent_support_groups=0,
            independent_performance="not_estimated_same_session_only",
            diagnostic_label=None,
            confidence=None,
            accepted_diagnostic_groups=0,
            empirical_acceptance=False,
            acquisition_authority=False,
            assurance=_SPEC["assurance"],
        )
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError(ERROR) from None
