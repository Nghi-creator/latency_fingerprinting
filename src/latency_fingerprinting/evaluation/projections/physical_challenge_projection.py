"""Separate descriptive projection for constant physical challenge/control sources."""

from copy import deepcopy

from latency_fingerprinting.analytical.policy_release import payload_hash
from latency_fingerprinting.evaluation.bounds.encoded_event_rate import (
    RELEASE as EVENT_RATE_RELEASE,
)
from latency_fingerprinting.evaluation.bounds.shared_window_separation import (
    GROUPS,
    PHASES,
    _hull,
    _parse_phase_rates,
    _ratio,
)
from latency_fingerprinting.evaluation.protocols.physical_challenge_measurements import (
    inspect_challenge_measurements,
)
from latency_fingerprinting.evaluation.responses.cpu_resource_response import (
    cpu_resource_response_spec,
)

RELEASE = "n11-physical-challenge-event-span-projection-v1"
_SPEC = dict(
    release=RELEASE,
    source_method="n11-physical-challenge-acquisition-v1",
    cpu_response_hash=cpu_resource_response_spec()["content_hash"],
    encoded_rate_release=EVENT_RATE_RELEASE,
    phase_rates="unchanged_encoded_event_spans_and_guarded_cgroup_cpu_intervals",
    arithmetic="unchanged_exact_rational_nine_coordinate_hulls_no_MAD_divisor",
    changing_conditions="reject_before_stable_pair_projection_not_computed_abstention",
    labels="no_single_condition_truth_for_mixture_no_labels_in_numerical_coordinates",
    compatibility="separate_source_and_method_identity_new_matched_calibration_required",
    qualification="all_original_byte_custody_media_command_reference_and_delivery_gates_required",
    scoring_authority=False,
    empirical_acceptance=False,
    acquisition_authority=False,
)


def physical_challenge_projection_spec():
    return {**deepcopy(_SPEC), "content_hash": payload_hash(_SPEC)}


def project_physical_challenge(acquisition_bytes):
    """Rebuild a descriptive box; this function does not qualify ownership or fit a model."""
    measurement = inspect_challenge_measurements(acquisition_bytes)
    changing = not measurement["stable_condition"]
    unavailable = [] if measurement["cpu_response"]["state"] != "unavailable" else ["cpu"]
    if measurement["encoded_reason_codes"]:
        unavailable.append("encoded")
    rates, bounds = {}, {}
    if not changing and not unavailable:
        rates = {
            "encoded": {p: measurement["encoded_event_spans"][p]["rate_fps"] for p in PHASES},
            **{
                g: {
                    p: measurement["cpu_response"]["windows"][p]["rate_intervals"][g]
                    for p in PHASES
                }
                for g in GROUPS
                if g != "encoded"
            },
        }
        parsed = _parse_phase_rates(rates)
        for group, coordinates in GROUPS.items():
            for name, (a, b) in coordinates.items():
                lo, hi = _hull(parsed[group][a], parsed[group][b], group == "encoded")
                bounds[name] = dict(lower=_ratio(lo), upper=_ratio(hi))
    payload = dict(
        method_spec=physical_challenge_projection_spec(),
        state="rejected_changing_pair"
        if changing
        else "unavailable"
        if unavailable
        else "descriptive_phase_rates_available",
        reason_codes=["changing_pair_not_stable"]
        if changing
        else ["measurement_windows_unavailable"]
        if unavailable
        else [],
        source_bytes_sha256=measurement["acquisition_sha256"],
        unavailable_components=unavailable,
        phase_rates=rates,
        marginal_bounds=bounds,
        qualification_required=True,
        stable_pair_admitted=False,
        n2_pair_admitted=False,
        diagnostic_label=None,
        scoring_authority=False,
        empirical_acceptance=False,
        acquisition_authority=False,
    )
    return {**payload, "projection_id": "physical-challenge-" + payload_hash(payload)[7:]}
