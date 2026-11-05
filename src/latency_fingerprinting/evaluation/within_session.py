"""Separately versioned correlated repeated-block arithmetic, never independent validation."""

from copy import deepcopy

from ..analytical.policy_release import payload_hash
from . import fixture_conditions as arithmetic
from .median_response import _alias

RELEASE = "n11-within-session-condition-experiment-v1"
ERROR = "invalid_within_session_experiment"
_METHOD = dict(
    method_release=RELEASE,
    arithmetic_reference=arithmetic.METHOD_CONTENT_HASH,
    training_blocks=6,
    session_components=1,
    folds="leave_one_correlated_repeated_block_out_descriptive_only",
    mask="all_training_eligibility_intersection_minimum_17_of_22",
    distance="median_centers_unscaled_rms_no_mad_divisor",
    calibration="all_folds_uniquely_correct_positive_gap_or_unavailable",
    thresholds="maximum_correct_fold_radius_per_condition_and_minimum_positive_gap",
    query="same_session_only_no_truth_input_rebuild_original_training",
    independent_support_groups=0,
    independent_performance="not_estimated_same_session_only",
    broad_diagnostic_authority=False,
)
METHOD_CONTENT_HASH = "sha256:ec17fb878d3d4c9cb89e5cd3809463961c840182f688c944ce51be4b7973dad0"


def within_session_method_spec():
    if payload_hash(_METHOD) != METHOD_CONTENT_HASH:
        raise ValueError(ERROR)
    return {**deepcopy(_METHOD), "content_hash": METHOD_CONTENT_HASH}


def fit_within_session(blocks, *, session_id):
    """All blocks belong to ONE declared session; six repetitions are not six groups."""
    try:
        _alias(session_id)
        if not 1 <= len(blocks) <= 6:
            raise ValueError(ERROR)
        result = arithmetic.fit_fixture_condition_experiment(blocks)
        result.pop("experiment_id")
        result["method_release"] = RELEASE
        result["method_spec"] = within_session_method_spec()
        result["assurance"] = "linked_witness_declarations_one_correlated_session_only"
        result["scope"] = "within_session_fixture_condition_recognition_only"
        result["session_id"] = session_id
        result["session_components"] = 1
        result["independent_support_groups"] = 0
        result["independent_performance"] = "not_estimated_same_session_only"
        result["repeated_training_block_count"] = result.pop("calibration_block_count")
        result["empirical_acceptance"] = False
        result["experiment_id"] = "within-session-experiment-" + payload_hash(result)[7:]
        return result
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError(ERROR) from None


def score_within_session(query, blocks, *, session_id, query_session_id, query_block_id):
    """No query truth argument. Rebuild calibration and abstain outside the declared session."""
    try:
        _alias(query_session_id)
        fitted = fit_within_session(blocks, session_id=session_id)
        result = arithmetic.score_fixture_condition_experiment(
            query, blocks, query_block_id=query_block_id
        )
        if query_session_id != session_id:
            result["state"] = "abstain"
            result["reason_codes"].append("different_query_session")
            result["predicted_condition"] = None
        result.update(
            method_release=RELEASE,
            experiment_id=fitted["experiment_id"],
            session_id=session_id,
            session_components=1,
            independent_support_groups=0,
            independent_performance="not_estimated_same_session_only",
            assurance=fitted["assurance"],
            scope=fitted["scope"],
            empirical_acceptance=False,
        )
        return result
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError(ERROR) from None
