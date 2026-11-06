"""Candidate same-worker counter-rate response; never per-frame latency or diagnosis."""

from collections.abc import Mapping
from copy import deepcopy
from fractions import Fraction

from ..analytical.policy_release import payload_hash
from .contrast_bounds import MAX_INT, _read, counter_rate_bounds

RELEASE = "n11-temporal-rate-response-candidate-v1"
ERROR = "invalid_temporal_rate_response"
PHASES = ("healthy", "degraded", "relief", "post")
MIN_SAMPLES, MAX_SAMPLES = 4, 64
MIN_DURATION_NS, MAX_DURATION_NS = 2_000_000_000, 5_000_000_000
MAX_SAMPLE_GAP_NS, MAX_READ_SPAN_NS = 1_500_000_000, 100_000_000
MAX_BETWEEN_WINDOW_GAP_NS = 15_000_000_000
READ_KEYS = {"clock_id", "read_start_ns", "read_end_ns", "counter", "sequence"}
FEATURES = {
    "degraded_vs_healthy": ("degraded", "healthy"),
    "relief_vs_degraded": ("relief", "degraded"),
    "post_vs_healthy": ("post", "healthy"),
}
_SPEC = dict(
    release=RELEASE,
    counter="encoded_buffers_one_declared_worker_generation_clock",
    input="exact_four_named_windows_all_supplied_samples_no_value_based_trimming",
    window_order=list(PHASES),
    minimum_samples=MIN_SAMPLES,
    maximum_samples=MAX_SAMPLES,
    minimum_inner_duration_ns=MIN_DURATION_NS,
    maximum_outer_duration_ns=MAX_DURATION_NS,
    maximum_outer_adjacent_gap_ns=MAX_SAMPLE_GAP_NS,
    maximum_read_span_ns=MAX_READ_SPAN_NS,
    maximum_between_window_gap_ns=MAX_BETWEEN_WINDOW_GAP_NS,
    ordering="strictly_increasing_sequence_nonoverlapping_reads_nondecreasing_counter_globally",
    rate="endpoint_counter_rate_bounds_with_fixed_one_buffer_sensitivity_guard",
    features={name: dict(numerator=n, denominator=d) for name, (n, d) in FEATURES.items()},
    response="nonnegative_interval_ratio_minus_one_exact_rational_no_epsilon",
    denominator="strictly_positive_lower_rate_bound_or_feature_unavailable",
    vector="all_three_features_required_no_imputation_or_subset_scoring",
    provenance="caller_projection_requires_external_source_binding_review",
    underlying_counter_freshness="not_authenticated_by_read_brackets",
    confidence=False,
    physical_capture_latency=False,
    n3_policy_change=False,
    empirical_acceptance=False,
    acquisition_authority=False,
)


PROJECTION_RELEASE = "n11-contained-temporal-rate-projection-candidate-v1"
_PROJECTION_SPEC = dict(
    release=PROJECTION_RELEASE,
    response_contract_hash=payload_hash(_SPEC),
    source_method="n11-contained-condition-witness-v1",
    source_validation="existing_native_counter_inspector_plus_global_reference_and_recovery_order",
    selected_windows="unique_healthy_post_references_and_all_degraded_relief_native_samples",
    validated_but_omitted_coordinate_phase="recovery",
    projection_fields="worker_clock_read_brackets_sequence_encoded_buffers_only",
    configured_and_negotiated_targets="30_except_relief_24_validity_checks_not_features",
    ignored_measurements="observer_at_ns_capture_counter_control_witness_labels_doses_properties",
    provenance="canonical_source_payload_hash_not_execution_authentication",
    acquisition_authority=False,
    empirical_acceptance=False,
)


def temporal_rate_projection_spec():
    return {**deepcopy(_PROJECTION_SPEC), "content_hash": payload_hash(_PROJECTION_SPEC)}


def temporal_rate_response_spec():
    """Candidate identity and fixed engineering bounds; no prospective approval."""
    return {
        **_SPEC,
        "window_order": list(PHASES),
        "features": {name: dict(numerator=n, denominator=d) for name, (n, d) in FEATURES.items()},
        "content_hash": payload_hash(_SPEC),
    }


def _fraction(ratio):
    return Fraction(ratio["numerator"], ratio["denominator"])


def _ratio(value):
    return dict(numerator=value.numerator, denominator=value.denominator)


def _inspect_windows(windows):
    if not isinstance(windows, Mapping) or set(windows) != set(PHASES):
        raise ValueError(ERROR)
    summaries, clock, previous = {}, None, None
    for phase in PHASES:
        rows = windows[phase]
        if type(rows) not in (list, tuple) or len(rows) > MAX_SAMPLES:
            raise ValueError(ERROR)
        reasons = []
        if len(rows) < MIN_SAMPLES:
            reasons.append("insufficient_samples")
        endpoints, prior = [], None
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping) or set(row) != READ_KEYS:
                raise ValueError(ERROR)
            sequence = row["sequence"]
            if type(sequence) is not int or not 0 <= sequence <= MAX_INT:
                raise ValueError(ERROR)
            read = {key: value for key, value in row.items() if key != "sequence"}
            row_clock, start, end, counter = _read(read)
            if clock is None:
                clock = row_clock
            if row_clock != clock:
                raise ValueError(ERROR)
            if previous and (
                start <= previous[0] or counter < previous[1] or sequence <= previous[2]
            ):
                raise ValueError(ERROR)
            if index == 0 and previous and start - previous[0] > MAX_BETWEEN_WINDOW_GAP_NS:
                reasons.append("between_window_gap_too_wide")
            if end - start > MAX_READ_SPAN_NS and "read_span_too_wide" not in reasons:
                reasons.append("read_span_too_wide")
            if (
                prior
                and end - prior[0] > MAX_SAMPLE_GAP_NS
                and "sample_gap_too_wide" not in reasons
            ):
                reasons.append("sample_gap_too_wide")
            prior = (start, end)
            previous = (end, counter, sequence)
            endpoints.append(read)
        if len(endpoints) >= 2:
            inner = endpoints[-1]["read_start_ns"] - endpoints[0]["read_end_ns"]
            outer = endpoints[-1]["read_end_ns"] - endpoints[0]["read_start_ns"]
            if inner < MIN_DURATION_NS:
                reasons.append("window_too_short")
            if outer > MAX_DURATION_NS:
                reasons.append("window_too_long")
        summaries[phase] = dict(
            state="unavailable" if reasons else "candidate_window_available",
            reason_codes=reasons,
            sample_count=len(rows),
            rate=None if reasons else counter_rate_bounds(endpoints[0], endpoints[-1]),
        )
    return summaries, clock


def temporal_rate_response(windows):
    """Projected encoded-counter reads only; no condition labels, doses or truth.

    All samples supplied for each preselected window are validated. The caller
    must bind this projection to source artifacts and a prospective recipe.
    This primitive cannot authenticate an execution or counter update times.
    """
    try:
        summaries, clock = _inspect_windows(windows)
        features = {}
        for name, (numerator, denominator) in FEATURES.items():
            needed = [
                phase
                for phase in (numerator, denominator)
                if summaries[phase]["state"] == "unavailable"
            ]
            reasons = ["required_window_unavailable"] if needed else []
            interval = None
            if not reasons:
                n = summaries[numerator]["rate"]["guarded_rate_fps"]
                d = summaries[denominator]["rate"]["guarded_rate_fps"]
                lower, upper = _fraction(d["lower"]), _fraction(d["upper"])
                if lower <= 0:
                    reasons.append("denominator_interval_includes_zero")
                else:
                    interval = dict(
                        lower=_ratio(_fraction(n["lower"]) / upper - 1),
                        upper=_ratio(_fraction(n["upper"]) / lower - 1),
                    )
            features[name] = dict(
                state="unavailable" if reasons else "candidate_interval_available",
                reason_codes=reasons,
                unavailable_windows=needed,
                ratio_minus_one=interval,
            )
        invalid_windows = [phase for phase in PHASES if summaries[phase]["state"] == "unavailable"]
        invalid_features = [name for name, row in features.items() if row["state"] == "unavailable"]
        payload = dict(
            method_release=RELEASE,
            method_spec=temporal_rate_response_spec(),
            state="unavailable"
            if invalid_windows or invalid_features
            else "candidate_response_available",
            reason_codes=(["window_eligibility_failed"] if invalid_windows else [])
            + (["incomplete_response_vector"] if invalid_features else []),
            input_content_hash=payload_hash(windows),
            clock_id=clock,
            windows=summaries,
            features=features,
            unavailable_features=invalid_features,
            scope="controlled_fixture_temporal_rate_sensitivity_not_latency_or_diagnosis",
            confidence=None,
            diagnostic_label=None,
            accepted_diagnostic_groups=0,
            independent_support_groups=0,
            empirical_acceptance=False,
            acquisition_authority=False,
            source_authenticity="not_authenticated_by_projection",
            underlying_counter_freshness="not_authenticated_by_read_brackets",
        )
        return {**payload, "response_id": "temporal-rate-candidate-" + payload_hash(payload)[7:]}
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, ZeroDivisionError):
        raise ValueError(ERROR) from None


def project_temporal_rate_response(acquisition):
    """Read-only projection of the existing contained condition source format.

    Validates all phase reads, including recovery (which is not a response
    coordinate). Control witness labels/properties never enter projected values.
    Source hashes bind bytes represented by the supplied JSON payload, not the
    authenticity of an execution. No runner or acquisition is invoked.
    """
    return _project_temporal_source(
        acquisition, "n11-contained-condition-witness-v1", temporal_rate_projection_spec()
    )


def _project_temporal_source(acquisition, expected_method, projection_spec):
    """Shared arithmetic seam; callers supply a separately identified source contract."""
    from .contrast_bounds import _inspect_native_counter_reads

    try:
        inspected = _inspect_native_counter_reads(acquisition, expected_method)
        if inspected["state"] != "available":
            raise ValueError(ERROR)
        events = acquisition["events"]
        selected = {}
        for phase in ("healthy", "post"):
            references = [
                event
                for event in events
                if event.get("kind") == "n11_pacing_reference" and event.get("phase") == phase
            ]
            if len(references) != 1 or type(references[0].get("samples")) is not list:
                raise ValueError(ERROR)
            selected[phase] = references[0]["samples"]
        for phase in ("degraded", "relief", "recovery"):
            selected[phase] = [
                event
                for event in events
                if event.get("kind") == "n11_pair_native" and event.get("phase") == phase
            ]
        projected, previous = {}, None
        for phase in ("healthy", "degraded", "relief", "recovery", "post"):
            rows = selected[phase]
            if not rows or len(rows) > MAX_SAMPLES:
                raise ValueError(ERROR)
            projected[phase] = []
            for row in rows:
                native = row.get("native_read")
                if (
                    not isinstance(native, Mapping)
                    or set(native)
                    != {"method", "basis", "clock_id", "read_start_ns", "read_end_ns"}
                    or native["method"] != "native-counter-read-brackets-v1"
                    or native["basis"] != "worker_elapsed_monotonic_ns"
                    or native["clock_id"] != inspected["clock_id"]
                ):
                    raise ValueError(ERROR)
                target = 24 if phase == "relief" else 30
                if any(
                    type(row.get(key)) is not int or row[key] != target
                    for key in ("configured_fps", "negotiated_fps")
                ):
                    raise ValueError(ERROR)
                read = {key: native[key] for key in ("clock_id", "read_start_ns", "read_end_ns")}
                read["counter"] = row.get("encoded_buffers")
                _, start, end, counter = _read(read)
                sequence = row.get("sequence")
                if type(sequence) is not int or not 0 <= sequence <= MAX_INT:
                    raise ValueError(ERROR)
                if previous and (
                    start <= previous[0] or counter < previous[1] or sequence <= previous[2]
                ):
                    raise ValueError(ERROR)
                previous = (end, counter, sequence)
                projected[phase].append({**read, "sequence": sequence})
        windows = {phase: projected[phase] for phase in PHASES}
        return dict(
            projection_release=projection_spec["release"],
            projection_spec=deepcopy(projection_spec),
            source_payload_hash=payload_hash(acquisition),
            all_sample_counts={phase: len(rows) for phase, rows in projected.items()},
            omitted_coordinate_phases=["recovery"],
            response=temporal_rate_response(windows),
            source_authenticity="not_authenticated_by_projection",
            empirical_acceptance=False,
            acquisition_authority=False,
        )
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError(ERROR) from None
