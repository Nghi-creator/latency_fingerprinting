"""Project verified counter-specific source structure into shared phase-rate boxes."""

from copy import deepcopy

from latency_fingerprinting.analytical.policy_release import payload_hash
from latency_fingerprinting.evaluation.bounds.encoded_event_rate import (
    RELEASE as EVENT_RATE_RELEASE,
)
from latency_fingerprinting.evaluation.bounds.shared_window_separation import (
    GROUPS,
    PHASES,
    _hull,
    _interval,
    _parse_phase_rates,
    _ratio,
    shared_window_separation_spec,
)
from latency_fingerprinting.evaluation.projections.counter_specific_projection import (
    _counter_specific_components,
    counter_specific_projection_spec,
)
from latency_fingerprinting.evaluation.projections.encoded_event_source import (
    TRACE_METHOD,
    inspect_encoded_event_source,
)
from latency_fingerprinting.json_io import strict_json_loads

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


_EVENT_SPEC = dict(
    _SPEC,
    release="n11-shared-window-event-span-projection-v1",
    rates="reconciled_encoded_event_spans_and_original_guarded_cpu_windows",
    marginal_parity="original_cpu_hulls_event_span_encoded_hulls",
    encoded_trace_method=TRACE_METHOD,
    encoded_rate_release=EVENT_RATE_RELEASE,
    encoded_eligibility="all_five_phases_reconciled_and_valid_including_recovery",
    time_alignment="verified_phase_receipts_distinct_encode_event_and_cpu_window_endpoints",
)


def shared_window_projection_spec(*, event_span=False):
    spec = _EVENT_SPEC if event_span else _SPEC
    return {**deepcopy(spec), "content_hash": payload_hash(spec)}


def project_shared_window_source(source, *, event_span=False):
    """Expose phase rates under either the original or the event-span contract."""
    try:
        projection, encoded, cpu = _counter_specific_components(source)
        phase_rates, bounds = {}, {}
        unavailable = projection["unavailable_components"]
        if event_span:
            events = strict_json_loads(source["acquisition_json"])["events"]
            spans, reasons = inspect_encoded_event_source(
                events,
                worker_clock=projection["source_worker_clock"],
                controller_origin=source["resource_artifact"]["context"]["controller_origin_ns"],
            )
            unavailable = (["encoded"] if reasons else []) + (
                ["cpu"] if cpu["state"] == "unavailable" else []
            )
        if not unavailable:
            phase_rates = {
                "encoded": {
                    phase: spans[phase]["rate_fps"]
                    if event_span
                    else encoded["windows"][phase]["rate"]["guarded_rate_fps"]
                    for phase in PHASES
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
            if not event_span:
                original = projection["features"]
                if bounds.keys() != original.keys() or any(
                    _interval(value) != _interval(original[name]) for name, value in bounds.items()
                ):
                    raise ValueError(ERROR)
        payload = dict(
            method_spec=shared_window_projection_spec(event_span=event_span),
            state="unavailable" if unavailable else "shared_window_rates_available",
            unavailable_components=unavailable,
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
        if event_span:
            payload.update(encoded_event_spans=spans, encoded_event_reason_codes=reasons)
        return {**payload, "projection_id": "shared-window-source-" + payload_hash(payload)[7:]}
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError(ERROR) from None
