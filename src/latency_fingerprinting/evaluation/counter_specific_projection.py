"""Separately versioned encoded-getter timing; never alters composite-read v1 results."""

from copy import deepcopy

from ..analytical.policy_release import payload_hash
from .combined_resource_projection import (
    TEMPORAL_SPEC,
    _project_combined_resource,
    combined_resource_projection_spec,
)

RELEASE = "n11-counter-specific-combined-projection-candidate-v1"
ENCODED_SPEC = {
    **deepcopy(TEMPORAL_SPEC),
    "release": "n11-counter-specific-encoded-projection-candidate-v1",
    "counter_read_field": "encoded_counter_read",
    "counter_read_method": "native-encoded-counter-read-brackets-v1",
    "point_binding": "same_reported_encoded_value_worker_clock_and_subset_of_original_snapshot",
    "metadata_integrity": "original_full_snapshot_phase_and_ownership_checks_retained",
    "fallback": "none_all_five_phases_require_recorded_counter_specific_reads",
}
ENCODED_SPEC.pop("content_hash")
ENCODED_SPEC["content_hash"] = payload_hash(ENCODED_SPEC)
_SPEC = {
    **combined_resource_projection_spec(),
    "release": RELEASE,
    "encoded_projection_hash": ENCODED_SPEC["content_hash"],
    "encoded_read_scope": "reported_counter_getter_not_other_snapshot_metadata",
    "legacy_projection": "separate_unchanged_no_automatic_adoption_or_retrospective_conversion",
}
_SPEC.pop("content_hash")


def counter_specific_projection_spec():
    return {**deepcopy(_SPEC), "content_hash": payload_hash(_SPEC)}


def project_counter_specific_resource(source):
    """Use only actually recorded point bounds; CPU, missingness and numeric gates stay fixed."""
    try:
        return _project_combined_resource(
            source,
            projection_spec=counter_specific_projection_spec(),
            temporal_spec=ENCODED_SPEC,
            counter_read_key="encoded_counter_read",
        )
    except ValueError:
        raise ValueError("invalid_counter_specific_combined_projection") from None
