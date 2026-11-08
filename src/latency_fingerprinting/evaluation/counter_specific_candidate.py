"""Separate counter-getter interval candidate; original combined method stays frozen."""

from copy import deepcopy

from ..analytical.policy_release import payload_hash
from .combined_interval_candidate import (
    _binding,
    _fit,
    _prepare,
    _score_candidate,
    combined_interval_candidate_spec,
)
from .counter_specific_projection import (
    counter_specific_projection_spec,
    project_counter_specific_resource,
)

RELEASE = "n11-counter-specific-interval-condition-candidate-v1"
BINDING_RELEASE = "n11-counter-specific-condition-binding-candidate-v1"
ERROR = "invalid_counter_specific_candidate"
_SPEC = {
    **combined_interval_candidate_spec(),
    "release": RELEASE,
    "projection_contract_hash": counter_specific_projection_spec()["content_hash"],
    "binding_release": BINDING_RELEASE,
    "legacy_method": "separate_unchanged_no_automatic_adoption_or_retrospective_conversion",
}
_SPEC.pop("content_hash")


def counter_specific_candidate_spec():
    return {**deepcopy(_SPEC), "content_hash": payload_hash(_SPEC)}


def declare_counter_specific_binding(source, *, condition, context_hash, inspection_sha256):
    """Bind externally reviewed declarations to actual counter-specific projection bytes."""
    try:
        return _binding(
            project_counter_specific_resource(source),
            condition=condition,
            context_hash=context_hash,
            inspection_sha256=inspection_sha256,
            binding_release=BINDING_RELEASE,
        )
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError(ERROR) from None


def fit_counter_specific_candidate(blocks, *, session_id):
    """Same fixed nine-coordinate arithmetic and all-fold gate; never divides by MAD."""
    try:
        return _fit(
            *_prepare(
                blocks,
                projector=project_counter_specific_resource,
                binding_release=BINDING_RELEASE,
            ),
            session_id,
            method_spec=counter_specific_candidate_spec(),
        )
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError(ERROR) from None


def score_counter_specific_candidate(
    source, blocks, *, session_id, query_session_id, query_block_id, context_hash
):
    """Truth-free prediction or abstention after rebuilding the exact training method."""
    try:
        return _score_candidate(
            source,
            blocks,
            session_id=session_id,
            query_session_id=query_session_id,
            query_block_id=query_block_id,
            context_hash=context_hash,
            projector=project_counter_specific_resource,
            binding_release=BINDING_RELEASE,
            method_spec=counter_specific_candidate_spec(),
        )
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError(ERROR) from None
