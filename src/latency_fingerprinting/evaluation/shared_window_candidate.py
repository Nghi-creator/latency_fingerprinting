"""Same-session calibration using shared phase-rate separation certificates."""

from copy import deepcopy
from fractions import Fraction
from functools import partial

from ..analytical.policy_release import payload_hash
from .combined_interval_candidate import (
    _binding,
    _distance,
    _distance_report,
    _fit,
    _prepare,
    _score_candidate,
    combined_interval_candidate_spec,
)
from .shared_window_projection import (
    project_shared_window_source,
    shared_window_projection_spec,
)
from .shared_window_separation import (
    compare_shared_window_centers,
    shared_window_separation_spec,
)

RELEASE = "n11-shared-window-condition-candidate-v1"
BINDING_RELEASE = "n11-shared-window-condition-binding-v1"
ERROR = "invalid_shared_window_candidate"
_SPEC = {
    **combined_interval_candidate_spec(),
    "release": RELEASE,
    "binding_release": BINDING_RELEASE,
    "projection_contract_hash": shared_window_projection_spec()["content_hash"],
    "separation_contract_hash": shared_window_separation_spec()["content_hash"],
    "distance": "equal_weight_mean_absolute_distance_over_all_nine_coordinates",
    "selection": "unique_condition_with_strictly_positive_shared_window_bounds_against_both_rivals",
    "thresholds": "max_correct_marginal_box_upper_distance_per_class_and_min_certified_fold_gap",
    "arithmetic": "exact_rational_feasible_witnesses_and_fixed_subdivision_budget",
    "radius": "conservative_marginal_box_upper_distance_even_with_shared_window_certificate",
}
_SPEC.pop("content_hash")


_EVENT_SPEC = dict(
    _SPEC,
    release="n11-shared-window-event-span-condition-candidate-v1",
    binding_release="n11-shared-window-event-span-condition-binding-v1",
    projection_contract_hash=shared_window_projection_spec(event_span=True)["content_hash"],
)


def shared_window_candidate_spec(*, event_span=False):
    spec = _EVENT_SPEC if event_span else _SPEC
    return {**deepcopy(spec), "content_hash": payload_hash(spec)}


def _project(source, *, event_span):
    projected = project_shared_window_source(source, event_span=event_span)
    return {
        **projected,
        "response_id": projected["projection_id"],
        "features": projected["marginal_bounds"],
        "reason_codes": ["incomplete_component_responses"]
        if projected["unavailable_components"]
        else [],
    }


def _evaluate(row, centers):
    distances = {c: _distance(row["values"], center) for c, center in centers.items()}
    center_boxes = {c: _distance_report(coordinates) for c, coordinates in centers.items()}
    certificate = compare_shared_window_centers(row["phase_rates"], center_boxes)
    winner = certificate["separated_condition"]
    comparisons = certificate["comparisons"]
    gap = (
        min(Fraction(**pair["lower"]) for pair in comparisons[winner].values())
        if winner is not None
        else None
    )
    return distances, winner, gap, {"separation_comparisons": comparisons}


def declare_shared_window_binding(
    source, *, condition, context_hash, inspection_sha256, event_span=False
):
    """Bind a caller-reviewed condition and inspection to the shared-window projection."""
    spec = shared_window_candidate_spec(event_span=event_span)
    try:
        return _binding(
            _project(source, event_span=event_span),
            condition=condition,
            context_hash=context_hash,
            inspection_sha256=inspection_sha256,
            binding_release=spec["binding_release"],
        )
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError(ERROR) from None


def fit_shared_window_candidate(blocks, *, session_id, event_span=False):
    """Rebuild six leave-block-out folds and require all eighteen certificates."""
    spec = shared_window_candidate_spec(event_span=event_span)
    try:
        return _fit(
            *_prepare(
                blocks,
                projector=partial(_project, event_span=event_span),
                binding_release=spec["binding_release"],
            ),
            session_id,
            method_spec=spec,
            evaluator=_evaluate,
        )
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError(ERROR) from None


def score_shared_window_candidate(
    source, blocks, *, session_id, query_session_id, query_block_id, context_hash, event_span=False
):
    """Rebuild calibration before testing a fresh query against the learned limits."""
    spec = shared_window_candidate_spec(event_span=event_span)
    try:
        result = _score_candidate(
            source,
            blocks,
            session_id=session_id,
            query_session_id=query_session_id,
            query_block_id=query_block_id,
            context_hash=context_hash,
            projector=partial(_project, event_span=event_span),
            binding_release=spec["binding_release"],
            method_spec=spec,
            evaluator=_evaluate,
        )
        return {"separation_comparisons": {}, **result}
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError(ERROR) from None
