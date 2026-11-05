"""Synthetic-qualified candidate folds; not integrated with acquisition protocols."""

from bisect import bisect_left, bisect_right
from fractions import Fraction
from statistics import median

from ..analytical.policy_release import payload_hash
from ..calibration.records import partition_id, windows
from ..profiles.policy_release import FEATURE_NAMES
from .fixture_conditions import CONDITIONS, _prepare
from .median_response import _alias, _origins, _response
from .rank_geometry import _number, fit_rank_geometry, rank_geometry_spec

RELEASE = "n11-within-session-rank-condition-candidate-v1"
ERROR = "invalid_rank_condition_candidate"
_SPEC = dict(
    release=RELEASE,
    geometry_content_hash=rank_geometry_spec()["content_hash"],
    scope="candidate_same_session_only_not_integrated_collection_method",
    training_blocks=6,
    mask="all_training_eligibility_intersection_minimum_17_of_22",
    folds="leave_one_complete_correlated_block_out_refit_support_on_other_five",
    center="coordinate_median_of_transformed_training_responses_per_condition",
    distance="equal_weight_mean_absolute_rank_coordinate_difference",
    support="all_frozen_features_inside_closed_fold_training_support_or_unavailable",
    calibration="all_18_fold_responses_uniquely_correct_positive_gap_or_unavailable",
    thresholds="per_condition_maximum_correct_fold_radius_and_minimum_positive_gap",
    query="rebuild_training_same_session_fresh_source_and_block_no_truth_input",
    arithmetic="exact_rank_and_median_rationals_binary64_distances_before_decisions",
    independent_support_groups=0,
    empirical_acceptance=False,
    acquisition_authority=False,
)


def rank_condition_candidate_spec():
    return {**_SPEC, "content_hash": payload_hash(_SPEC)}


def _vector(record, mask):
    return {name: record.features[name].normalized_value for name in mask}


def _transform(vector, geometry):
    coordinates, outside = {}, []
    for name, support in geometry.support:
        value = _number(vector[name])
        if not support[0] <= value <= support[-1]:
            outside.append(name)
        else:
            coordinates[name] = Fraction(
                bisect_left(support, value) + bisect_right(support, value), 2 * len(support)
            )
    return coordinates, outside


def _model(prepared, mask):
    geometry = fit_rank_geometry(
        [_vector(record, mask) for rows in prepared.values() for record in rows.values()],
        feature_names=mask,
    )
    coordinates = {
        condition: [
            _transform(_vector(rows[condition], mask), geometry)[0] for rows in prepared.values()
        ]
        for condition in CONDITIONS
    }
    centers = {
        condition: {name: median([row[name] for row in coordinates[condition]]) for name in mask}
        for condition in CONDITIONS
    }
    return geometry, centers


def _score(record, mask, geometry, centers):
    coordinates, outside = _transform(_vector(record, mask), geometry)
    if outside:
        return dict(
            state="unavailable",
            reason_codes=["outside_training_support"],
            outside_support_features=outside,
            distances={},
            nearest_condition=None,
            runner_up_gap=None,
        )
    distances = {
        condition: float(
            sum((abs(coordinates[n] - center[n]) for n in mask), Fraction()) / len(mask)
        )
        for condition, center in centers.items()
    }
    ranked = sorted(CONDITIONS, key=lambda condition: (distances[condition], condition))
    gap = float(Fraction(distances[ranked[1]]) - Fraction(distances[ranked[0]]))
    return dict(
        state="candidate_distances_available",
        reason_codes=[],
        outside_support_features=[],
        distances=distances,
        nearest_condition=ranked[0],
        runner_up_gap=gap,
    )


def _fit(prepared, origins, partition, missing, bindings, session_id):
    _alias(session_id)
    if not 1 <= len(prepared) <= 6:
        raise ValueError(ERROR)
    mask = (
        [
            name
            for name in FEATURE_NAMES
            if all(
                record.features[name].state == "eligible"
                for rows in prepared.values()
                for record in rows.values()
            )
        ]
        if not missing
        else []
    )
    reasons = []
    if missing:
        reasons.append("incomplete_blocks")
    if len(prepared) < 6:
        reasons.append("insufficient_training_blocks")
    if len(mask) < 17:
        reasons.append("insufficient_fixed_features")
    folds, radii, gaps = [], {condition: [] for condition in CONDITIONS}, []
    if not reasons:
        for held, queries in prepared.items():
            training = {block: rows for block, rows in prepared.items() if block != held}
            geometry, centers = _model(training, mask)
            results = []
            for truth in CONDITIONS:
                result = _score(queries[truth], mask, geometry, centers)
                correct = (
                    result["state"] != "unavailable"
                    and result["nearest_condition"] == truth
                    and result["runner_up_gap"] > 0
                )
                results.append(
                    dict(
                        condition=truth,
                        response_id=queries[truth].response_id,
                        uniquely_correct=correct,
                        **result,
                    )
                )
                if correct:
                    radii[truth].append(result["distances"][truth])
                    gaps.append(result["runner_up_gap"])
            folds.append(
                dict(
                    held_out_block_id=held,
                    training_block_ids=list(training),
                    support_pool_size=len(training) * 3,
                    queries=results,
                    complete_and_correct=all(row["uniquely_correct"] for row in results),
                )
            )
        if not all(fold["complete_and_correct"] for fold in folds):
            reasons.append("calibration_folds_not_all_uniquely_correct")
    support, centers_out = {}, {}
    if not reasons:
        geometry, centers = _model(prepared, mask)
        support = {name: [float(v) for v in values] for name, values in geometry.support}
        centers_out = {c: {n: float(v) for n, v in values.items()} for c, values in centers.items()}
    payload = dict(
        method_release=RELEASE,
        method_spec=rank_condition_candidate_spec(),
        state="unavailable" if reasons else "candidate_calibration_available",
        reason_codes=reasons,
        session_id=session_id,
        session_components=1,
        independent_support_groups=0,
        independent_performance="not_estimated_same_session_only",
        assurance="linked_witness_declarations_not_authenticated_independence",
        partition_id=partition,
        binding_receipts=bindings,
        input_provenance_kinds=sorted(
            {
                w.provenance.value
                for rows in prepared.values()
                for r in rows.values()
                for w in windows(r, "response")
            }
        ),
        source_origins=[list(origin) for origin in sorted(origins)],
        training_block_ids=list(prepared),
        missing_slots=missing,
        fixed_feature_mask=mask,
        folds=folds,
        calibration_query_count=sum(len(f["queries"]) for f in folds),
        thresholds=None
        if reasons
        else dict(class_radius={c: max(radii[c]) for c in CONDITIONS}, minimum_gap=min(gaps)),
        training_support=support,
        rank_centers=centers_out,
        diagnostic_label=None,
        confidence=None,
        accepted_diagnostic_groups=0,
        empirical_acceptance=False,
        acquisition_authority=False,
    )
    return {**payload, "experiment_id": "rank-candidate-" + payload_hash(payload)[7:]}


def fit_rank_condition_candidate(blocks, *, session_id):
    """Rebuild source-linked declarations and all six folds; no query or cached fit."""
    try:
        return _fit(*_prepare(blocks), session_id)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError(ERROR) from None


def score_rank_condition_candidate(query, blocks, *, session_id, query_session_id, query_block_id):
    """Truth-free candidate score; original experiments and protocols stay unchanged."""
    try:
        _alias(query_session_id)
        _alias(query_block_id)
        record = _response(query)
        prepared, origins, partition, missing, bindings = _prepare(blocks)
        fitted = _fit(prepared, origins, partition, missing, bindings, session_id)
        reasons = []
        if query_session_id != session_id:
            reasons.append("different_query_session")
        if query_block_id in prepared:
            reasons.append("query_block_overlap")
        if origins & _origins(record):
            reasons.append("query_source_overlap")
        if partition_id(record, "response") != partition:
            reasons.append("incompatible_query_partition")
        if fitted["state"] == "unavailable":
            reasons.append("calibration_unavailable")
        mask = fitted["fixed_feature_mask"]
        if any(record.features[name].state != "eligible" for name in mask):
            reasons.append("query_missing_fixed_features")
        scores, gap, prediction, outside = {}, None, None, []
        if not reasons:
            geometry, centers = _model(prepared, mask)
            result = _score(record, mask, geometry, centers)
            scores, gap = result["distances"], result["runner_up_gap"]
            outside = result["outside_support_features"]
            reasons.extend(result["reason_codes"])
            if not reasons:
                nearest, limits = result["nearest_condition"], fitted["thresholds"]
                if gap == 0:
                    reasons.append("equal_query_distances")
                if scores[nearest] > limits["class_radius"][nearest]:
                    reasons.append("outside_condition_radius")
                if gap < limits["minimum_gap"]:
                    reasons.append("insufficient_query_gap")
                if not reasons:
                    prediction = nearest
        return dict(
            method_release=RELEASE,
            experiment_id=fitted["experiment_id"],
            state="abstain" if reasons else "candidate_condition_prediction",
            reason_codes=reasons,
            predicted_condition=prediction,
            distances=scores,
            runner_up_gap=gap,
            outside_support_features=outside,
            fixed_feature_mask=mask,
            query_response_id=record.response_id,
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
        )
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError(ERROR) from None
