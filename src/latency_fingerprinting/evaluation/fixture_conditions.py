"""Opt-in blocked fixture recognition experiment, without broad diagnostic trust.

Bindings and correlation blocks are caller declarations requiring linked witness
inspection. This module checks internal consistency, not physical authenticity or
independence. Calibration is not untouched evaluation or acquisition authority.
"""

import re
from collections.abc import Mapping
from copy import deepcopy
from fractions import Fraction

from ..analytical.policy_release import POLICY_CONTENT_HASH, payload_hash
from ..calibration.records import partition_id, windows
from ..profile_matching.arithmetic import rounded
from ..profiles.policy_release import FEATURE_NAMES
from .median_response import (
    METHOD_CONTENT_HASH as MEDIAN_METHOD_CONTENT_HASH,
)
from .median_response import _alias, _origins, _response, _rms, summarize_engineering_responses

RELEASE = "n11-fixture-condition-block-experiment-v1"
ERROR = "invalid_fixture_condition_experiment"
METHOD_CONTENT_HASH = "sha256:57baea1a16b96e2aa57fce22dd5de34c9d657b6f29fa0cf3e2eb41e2251318eb"
CONDITIONS = ("no_injected_fault", "owned_identity_delay", "owned_cpu_pressure")
BINDING_RELEASE = "n11-fixture-condition-binding-v1"
ASSURANCE = "caller_declarations_require_linked_witness_and_block_review"
_METHOD = dict(
    method_release=RELEASE,
    conditions=list(CONDITIONS),
    response_policy_hash=POLICY_CONTENT_HASH,
    median_method_content_hash=MEDIAN_METHOD_CONTENT_HASH,
    feature_names=list(FEATURE_NAMES),
    arithmetic="binary64_stage_rounding_reject_overflow_or_nonzero_underflow",
    synthetic_inputs="arithmetic_only_never_empirical_evidence",
    minimum_training_blocks=6,
    maximum_training_blocks=32,
    responses_per_condition_per_block=1,
    within_condition_center="median_of_one_response_per_block",
    mask="training_eligibility_intersection_all_conditions_all_blocks_minimum_17_of_22",
    folds="leave_one_complete_block_out_all_conditions",
    minimum_fold_support_groups=5,
    minimum_fold_feature_availability=dict(numerator=4, denominator=5),
    distance="equal_weight_rms_unscaled_n3_normalized_units_no_mad_divisor",
    calibration="all_folds_unique_correct_positive_gap_or_unavailable_no_dropping",
    radius="per_condition_maximum_correct_leave_block_out_distance",
    minimum_gap="minimum_positive_leave_block_out_runner_up_gap",
    query="rebuild_inputs_unique_nearest_within_radius_and_at_least_minimum_gap",
    query_mask="all_frozen_features_required_no_adaptation",
    assurance=ASSURANCE,
    diagnostic_authority=False,
)


def fixture_condition_method_spec():
    """Return a detached explicit specification; no collection/count approval."""
    if payload_hash(_METHOD) != METHOD_CONTENT_HASH:
        raise ValueError(ERROR)
    return {**deepcopy(_METHOD), "content_hash": METHOD_CONTENT_HASH}


def _hash(value):
    if type(value) is not str or re.fullmatch(r"sha256:[a-f0-9]{64}", value) is None:
        raise ValueError(ERROR)


def declare_fixture_condition_binding(
    response, *, condition, witness_acquisition_sha256, witness_inspection_sha256
):
    """Declare a binding after external linked inspection; do not authenticate it."""
    try:
        record = _response(response)
        if type(condition) is not str or condition not in CONDITIONS:
            raise ValueError(ERROR)
        _hash(witness_acquisition_sha256)
        _hash(witness_inspection_sha256)
        return dict(
            method_release=BINDING_RELEASE,
            condition=condition,
            assurance=ASSURANCE,
            comparison_case_id=record.observation.comparison_case_id,
            response_id=record.response_id,
            source_hashes={
                w.phase.value: w.source_artifact.content_hash for w in windows(record, "response")
            },
            witness_acquisition_sha256=witness_acquisition_sha256,
            witness_inspection_sha256=witness_inspection_sha256,
        )
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError(ERROR) from None


def _prepare(blocks):
    if not isinstance(blocks, Mapping) or not 1 <= len(blocks) <= 32:
        raise ValueError(ERROR)
    for block in blocks:
        _alias(block)
    prepared, origins, partitions, witnesses, missing, bindings = {}, {}, set(), set(), [], []
    for block in sorted(blocks):
        rows = blocks[block]
        if not isinstance(rows, Mapping) or set(rows) != set(CONDITIONS):
            raise ValueError(ERROR)
        prepared[block] = {}
        for condition in CONDITIONS:
            slot = rows[condition]
            if slot is None:
                missing.append(dict(block_id=block, condition=condition))
                continue
            if not isinstance(slot, Mapping) or set(slot) != {"response", "binding"}:
                raise ValueError(ERROR)
            record, binding = _response(slot["response"]), slot["binding"]
            if not isinstance(binding, Mapping):
                raise ValueError(ERROR)
            expected = declare_fixture_condition_binding(
                record,
                condition=condition,
                witness_acquisition_sha256=binding.get("witness_acquisition_sha256"),
                witness_inspection_sha256=binding.get("witness_inspection_sha256"),
            )
            if dict(binding) != expected:
                raise ValueError(ERROR)
            identity = binding["witness_acquisition_sha256"]
            if identity in witnesses:
                raise ValueError(ERROR)
            inspection_identity = binding["witness_inspection_sha256"]
            if inspection_identity in witnesses:
                raise ValueError(ERROR)
            witnesses.update((identity, inspection_identity))
            bindings.append(
                dict(block_id=block, condition=condition, content_hash=payload_hash(expected))
            )
            for origin in _origins(record):
                if origin in origins:
                    raise ValueError(ERROR)
                origins[origin] = (block, condition)
            partitions.add(partition_id(record, "response"))
            prepared[block][condition] = record
    if len(partitions) > 1:
        raise ValueError(ERROR)
    return prepared, set(origins), next(iter(partitions), None), missing, bindings


def _centers(blocks):
    return {
        c: summarize_engineering_responses({b: [rows[c]] for b, rows in blocks.items()})
        for c in CONDITIONS
    }


def _distances(query, centers, mask):
    scores = {c: _rms(query, centers[c]["features"], mask)[0] for c in CONDITIONS}
    ranked = sorted(CONDITIONS, key=lambda c: (scores[c], c))
    gap = rounded(Fraction(scores[ranked[1]]) - Fraction(scores[ranked[0]]))
    return scores, ranked[0], gap


def _fit(prepared, origins, partition, missing, bindings):
    mask = (
        [
            name
            for name in FEATURE_NAMES
            if all(
                r.features[name].state == "eligible"
                for rows in prepared.values()
                for r in rows.values()
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
    folds, radii, gaps = [], {c: [] for c in CONDITIONS}, []
    if not reasons:
        for block, queries in prepared.items():
            training = {b: rows for b, rows in prepared.items() if b != block}
            centers = _centers(training)
            if any(
                s["state"] != "computable"
                or any(s["features"][name]["state"] != "numeric" for name in mask)
                for s in centers.values()
            ):
                raise ValueError(ERROR)
            queries_scored = []
            for truth in CONDITIONS:
                scores, nearest, gap = _distances(queries[truth], centers, mask)
                correct = nearest == truth and gap > 0
                queries_scored.append(
                    dict(
                        condition=truth,
                        response_id=queries[truth].response_id,
                        distances=scores,
                        nearest_condition=nearest,
                        runner_up_gap=gap,
                        uniquely_correct=correct,
                    )
                )
                if correct:
                    radii[truth].append(scores[truth])
                    gaps.append(gap)
            folds.append(
                dict(
                    held_out_block_id=block,
                    training_block_ids=list(training),
                    queries=queries_scored,
                    complete_and_correct=all(q["uniquely_correct"] for q in queries_scored),
                )
            )
        if not all(f["complete_and_correct"] for f in folds):
            reasons.append("calibration_folds_not_all_uniquely_correct")
    thresholds = (
        None
        if reasons
        else dict(class_radius={c: max(radii[c]) for c in CONDITIONS}, minimum_gap=min(gaps))
    )
    centers = _centers(prepared) if not reasons else {}
    payload = dict(
        method_release=RELEASE,
        method_spec=fixture_condition_method_spec(),
        state="unavailable" if reasons else "experimental_calibration_available",
        reason_codes=reasons,
        assurance=ASSURANCE,
        scope="fixture_conditions_only_not_broad_diagnosis_or_independent_evaluation",
        partition_id=partition,
        binding_receipts=bindings,
        input_provenance_kinds=sorted(
            {
                w.provenance.value
                for rows in prepared.values()
                for record in rows.values()
                for w in windows(record, "response")
            }
        ),
        training_block_ids=list(prepared),
        missing_slots=missing,
        source_origins=[list(o) for o in sorted(origins)],
        fixed_feature_mask=mask,
        folds=folds,
        thresholds=thresholds,
        centers=centers,
        calibration_block_count=len(prepared),
        calibration_query_count=sum(len(f["queries"]) for f in folds),
        diagnostic_label=None,
        accepted_diagnostic_groups=0,
        acquisition_authority=False,
        independent_performance="unavailable_requires_prospective_untouched_evaluation",
    )
    return {**payload, "experiment_id": "fixture-experiment-" + payload_hash(payload)[7:]}


def fit_fixture_condition_experiment(blocks):
    """Rebuild all whole-block folds; retain failures, never drop or replace slots."""
    try:
        return _fit(*_prepare(blocks))
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError(ERROR) from None


def score_fixture_condition_experiment(query, blocks, *, query_block_id):
    """Rebuild training inputs and score an unlabelled query with abstention.

    Query block IDs are declarations, not independence proof. Return a fixture
    condition only under the separately versioned experimental semantics.
    """
    try:
        _alias(query_block_id)
        record = _response(query)
        prepared, origins, partition, missing, bindings = _prepare(blocks)
        fitted = _fit(prepared, origins, partition, missing, bindings)
        reasons, scores, gap, prediction = [], {}, None, None
        if query_block_id in prepared:
            reasons.append("query_block_overlap")
        if origins & _origins(record):
            reasons.append("query_source_overlap")
        if partition_id(record, "response") != partition:
            reasons.append("incompatible_query_partition")
        if fitted["state"] == "unavailable":
            reasons.append("calibration_unavailable")
        if any(record.features[n].state != "eligible" for n in fitted["fixed_feature_mask"]):
            reasons.append("query_missing_fixed_features")
        if not reasons:
            scores, nearest, gap = _distances(
                record, fitted["centers"], fitted["fixed_feature_mask"]
            )
            thresholds = fitted["thresholds"]
            if gap == 0:
                reasons.append("equal_query_distances")
            if scores[nearest] > thresholds["class_radius"][nearest]:
                reasons.append("outside_condition_radius")
            if gap < thresholds["minimum_gap"]:
                reasons.append("insufficient_query_gap")
            if not reasons:
                prediction = nearest
        return dict(
            method_release=RELEASE,
            experiment_id=fitted["experiment_id"],
            state="abstain" if reasons else "experimental_condition_prediction",
            reason_codes=reasons,
            predicted_condition=prediction,
            distances=scores,
            runner_up_gap=gap,
            fixed_feature_mask=fitted["fixed_feature_mask"],
            query_response_id=record.response_id,
            query_block_id=query_block_id,
            assurance=ASSURANCE,
            diagnostic_label=None,
            confidence=None,
            accepted_diagnostic_groups=0,
            acquisition_authority=False,
            scope="fixture_condition_recognition_not_broad_causal_diagnosis",
        )
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError(ERROR) from None
