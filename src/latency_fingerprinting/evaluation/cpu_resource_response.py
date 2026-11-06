"""Generic CPU/throttling interval differences; no condition or ownership inputs."""

import re
from collections.abc import Mapping
from copy import deepcopy
from fractions import Fraction

from ..analytical.policy_release import payload_hash

RELEASE = "n11-cgroup-cpu-difference-response-candidate-v1"
ERROR = "invalid_cpu_resource_response"
PHASES = ("healthy", "degraded", "relief", "recovery", "post")
COUNTERS = (
    "usage_usec",
    "user_usec",
    "system_usec",
    "nr_periods",
    "nr_throttled",
    "throttled_usec",
)
READ_KEYS = {
    "method",
    "scope",
    "clock_id",
    "sequence",
    "read_start_ns",
    "read_end_ns",
    "source_identity",
    "quota",
    "counters",
    "counter_units",
    "underlying_counter_freshness",
    "source_authenticity",
    "live_authority",
    "phase",
}
CONSTANTS = dict(
    method="n11-private-cgroup-cpu-read-candidate-v1",
    scope="private_container_cpu_counters_not_ownership_or_diagnosis",
    counter_units="microseconds_for_usec_fields_counts_for_nr_fields",
    underlying_counter_freshness="not_authenticated_by_read_brackets",
    source_authenticity="declared_namespace_quota_and_file_identity_only",
)
COMPARISONS = dict(
    degraded_minus_healthy=("degraded", "healthy"),
    relief_minus_degraded=("relief", "degraded"),
    post_minus_healthy=("post", "healthy"),
)
_SPEC = dict(
    release=RELEASE,
    source_read_method=CONSTANTS["method"],
    windows=list(PHASES),
    minimum_samples=4,
    maximum_samples_per_window=64,
    maximum_total_samples=128,
    minimum_inner_duration_ns=2_000_000_000,
    maximum_outer_duration_ns=5_000_000_000,
    maximum_read_span_ns=50_000_000,
    maximum_adjacent_outer_gap_ns=1_500_000_000,
    maximum_between_window_gap_ns=15_000_000_000,
    source="same_controller_clock_contiguous_sequence_zero_origin_fixed_file_identity_quota",
    quota=dict(quota_usec=200000, period_usec=100000),
    rates="endpoint_counter_delta_with_fixed_one_microsecond_sensitivity_not_confidence",
    units=dict(
        cpu_quota_fraction="cpu_seconds_per_wall_second_divided_by_quota_cores",
        throttled_seconds_per_wall_second="reported_throttled_seconds_per_wall_second_not_utilisation",
    ),
    comparisons={n: list(v) for n, v in COMPARISONS.items()},
    difference="[numerator_lower-reference_upper,numerator_upper-reference_lower]",
    arithmetic="exact_rational_no_midpoint_epsilon_clipping_or_feature_selection",
    availability="all_five_windows_and_all_six_difference_coordinates_required",
    authority="caller_source_projection_requires_separate_raw_and_inspector_replay",
    n3_policy_change=False,
    empirical_acceptance=False,
    acquisition_authority=False,
)


def cpu_resource_response_spec():
    return {**deepcopy(_SPEC), "content_hash": payload_hash(_SPEC)}


def _integer(value):
    if type(value) is not int or not 0 <= value <= 2**63 - 1:
        raise ValueError(ERROR)
    return value


def _exact(value, keys):
    if not isinstance(value, Mapping) or set(value) != set(keys):
        raise ValueError(ERROR)


def _ratio(value):
    return dict(numerator=value.numerator, denominator=value.denominator)


def _envelope(values):
    return dict(lower=_ratio(values[0]), upper=_ratio(values[1]))


def _inspect(windows):
    _exact(windows, PHASES)
    clock, identity, previous = None, None, None
    count, reports, rates = 0, {}, {}
    for phase in PHASES:
        rows = windows[phase]
        if type(rows) not in (list, tuple) or len(rows) > 64 or count + len(rows) > 128:
            raise ValueError(ERROR)
        reasons = [] if len(rows) >= 4 else ["insufficient_samples"]
        local_previous = None
        for row in rows:
            _exact(row, READ_KEYS)
            if (
                any(row[k] != v for k, v in CONSTANTS.items())
                or row["live_authority"] is not False
                or row["phase"] != phase
            ):
                raise ValueError(ERROR)
            row_clock = row["clock_id"]
            if (
                type(row_clock) is not str
                or re.fullmatch(r"controller-monotonic-[a-f0-9]{64}", row_clock) is None
            ):
                raise ValueError(ERROR)
            if clock is None:
                clock = row_clock
            if clock != row_clock or type(row["sequence"]) is not int or row["sequence"] != count:
                raise ValueError(ERROR)
            _exact(row["quota"], ("quota_usec", "period_usec"))
            if any(
                type(row["quota"][k]) is not int or row["quota"][k] != v
                for k, v in _SPEC["quota"].items()
            ):
                raise ValueError(ERROR)
            _exact(row["source_identity"], ("cgroup", "cpu.stat", "cpu.max"))
            for value in row["source_identity"].values():
                _exact(value, ("device", "inode"))
                _integer(value["device"])
                if _integer(value["inode"]) == 0:
                    raise ValueError(ERROR)
            if identity is None:
                identity = deepcopy(row["source_identity"])
            if identity != row["source_identity"]:
                raise ValueError(ERROR)
            _exact(row["counters"], COUNTERS)
            for value in row["counters"].values():
                _integer(value)
            start, end = _integer(row["read_start_ns"]), _integer(row["read_end_ns"])
            if start > end:
                raise ValueError(ERROR)
            if previous and (
                start <= previous["read_end_ns"]
                or any(row["counters"][k] < previous["counters"][k] for k in COUNTERS)
            ):
                raise ValueError(ERROR)
            if end - start > 50_000_000:
                reasons.append("read_span_too_wide")
            if local_previous and end - local_previous["read_start_ns"] > 1_500_000_000:
                reasons.append("sample_gap_too_wide")
            if not local_previous and previous and start - previous["read_end_ns"] > 15_000_000_000:
                reasons.append("between_window_gap_too_wide")
            previous = local_previous = row
            count += 1
        if len(rows) >= 2:
            first, last = rows[0], rows[-1]
            inner = last["read_start_ns"] - first["read_end_ns"]
            outer = last["read_end_ns"] - first["read_start_ns"]
            if inner < 2_000_000_000:
                reasons.append("window_too_short")
            if outer > 5_000_000_000:
                reasons.append("window_too_long")
        reasons = list(dict.fromkeys(reasons))
        report = dict(
            state="unavailable" if reasons else "candidate_window_available",
            reason_codes=reasons,
            sample_count=len(rows),
            rate_intervals={},
        )
        if not reasons:
            rate = {}
            for name, counter, divisor in (
                ("cpu_quota_fraction", "usage_usec", Fraction(2)),
                ("throttled_seconds_per_wall_second", "throttled_usec", Fraction(1)),
            ):
                delta = last["counters"][counter] - first["counters"][counter]
                rate[name] = (
                    Fraction(max(0, delta - 1) * 1000, outer) / divisor,
                    Fraction((delta + 1) * 1000, inner) / divisor,
                )
            rates[phase] = rate
            report["rate_intervals"] = {name: _envelope(value) for name, value in rate.items()}
        reports[phase] = report
    return reports, rates, clock, identity


def cpu_resource_response(windows):
    """Validate full projected source samples and compute generic resource differences.

    This is numerical/source-consistency checking, not inspector authentication.
    A caller must replay the byte-bound source artifact and ownership separately.
    """
    try:
        reports, rates, clock, identity = _inspect(windows)
        features = {}
        for comparison, (numerator, reference) in COMPARISONS.items():
            missing = [p for p in (numerator, reference) if p not in rates]
            for metric in ("cpu_quota_fraction", "throttled_seconds_per_wall_second"):
                values = None
                if not missing:
                    a, b = rates[numerator][metric], rates[reference][metric]
                    values = _envelope((a[0] - b[1], a[1] - b[0]))
                features[metric + "." + comparison] = dict(
                    state="unavailable" if missing else "candidate_interval_available",
                    reason_codes=["required_window_unavailable"] if missing else [],
                    unavailable_windows=missing,
                    difference=values,
                )
        unavailable = [p for p in PHASES if p not in rates]
        payload = dict(
            method_release=RELEASE,
            method_spec=cpu_resource_response_spec(),
            state="unavailable" if unavailable else "candidate_response_available",
            reason_codes=["window_eligibility_failed"] if unavailable else [],
            input_content_hash=payload_hash(windows),
            clock_id=clock,
            source_identity=identity,
            windows=reports,
            features=features,
            unavailable_windows=unavailable,
            scope="generic_container_resource_sensitivity_not_causal_diagnosis_or_media_effect",
            underlying_counter_freshness="not_authenticated_by_read_brackets",
            source_authenticity="not_authenticated_by_projection",
            diagnostic_label=None,
            confidence=None,
            accepted_diagnostic_groups=0,
            independent_support_groups=0,
            empirical_acceptance=False,
            acquisition_authority=False,
        )
        return {**payload, "response_id": "cpu-resource-candidate-" + payload_hash(payload)[7:]}
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, ZeroDivisionError):
        raise ValueError(ERROR) from None
