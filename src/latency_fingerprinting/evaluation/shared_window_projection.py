"""Project verified counter-specific source structure into shared phase-rate boxes."""

from copy import deepcopy

from ..analytical.policy_release import payload_hash
from .counter_specific_projection import (
    _counter_specific_components,
    counter_specific_projection_spec,
)
from .shared_window_separation import (
    GROUPS,
    PHASES,
    _hull,
    _interval,
    _parse_phase_rates,
    _ratio,
    shared_window_separation_spec,
)

RELEASE = "n11-shared-window-source-projection-prototype-v1"
ERROR = "invalid_shared_window_source"
_SPEC = dict(
    release=RELEASE,
    counter_specific_projection_hash=counter_specific_projection_spec()["content_hash"],
    separation_contract_hash=shared_window_separation_spec()["content_hash"],
    rates="guarded_component_window_rates_extracted_after_full_projection_validation",
    marginal_parity="exact_rational_hulls_equal_all_nine_existing_feature_intervals",
    source_binding="exact_raw_bytes_canonical_auxiliary_artifact_and_parent_response",
    ownership="external_producer_inspector_and_source_custody_replay_required",
    acquisition_authority=False,
    empirical_acceptance=False,
)


def shared_window_projection_spec():
    return {**deepcopy(_SPEC), "content_hash": payload_hash(_SPEC)}


def project_shared_window_source(source):
    """Validate the original source and expose the rates used by its response bounds."""
    try:
        projection, encoded, cpu = _counter_specific_components(source)
        phase_rates, bounds = {}, {}
        available = projection["state"] == "candidate_combined_response_available"
        if available:
            phase_rates = {
                "encoded": {
                    phase: encoded["windows"][phase]["rate"]["guarded_rate_fps"] for phase in PHASES
                },
                **{
                    group: {
                        phase: cpu["windows"][phase]["rate_intervals"][group] for phase in PHASES
                    }
                    for group in GROUPS
                    if group != "encoded"
                },
            }
            rates = _parse_phase_rates(phase_rates)
            for group, coordinates in GROUPS.items():
                for name, (a, b) in coordinates.items():
                    lo, hi = _hull(rates[group][a], rates[group][b], group == "encoded")
                    bounds[name] = dict(lower=_ratio(lo), upper=_ratio(hi))
            original = projection["features"]
            if bounds.keys() != original.keys() or any(
                _interval(value) != _interval(original[name]) for name, value in bounds.items()
            ):
                raise ValueError(ERROR)
        payload = dict(
            method_spec=shared_window_projection_spec(),
            state="shared_window_rates_available" if available else "unavailable",
            unavailable_components=projection["unavailable_components"],
            source_bytes_sha256=projection["source_bytes_sha256"],
            source_payload_hash=projection["source_payload_hash"],
            resource_artifact_hash=payload_hash(source["resource_artifact"]),
            runtime_context_hash=projection["runtime_context_hash"],
            source_worker_clock=projection["source_worker_clock"],
            source_controller_clock=projection["source_controller_clock"],
            counter_specific_response_id=projection["response_id"],
            phase_rates=phase_rates,
            marginal_bounds=bounds,
            acquisition_authority=False,
            empirical_acceptance=False,
        )
        return {**payload, "projection_id": "shared-window-source-" + payload_hash(payload)[7:]}
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError(ERROR) from None
