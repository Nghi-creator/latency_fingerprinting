"""Opt-in, label-free median-response experiment; no N6/N7/N8 trust or decisions."""

import math
import re
from collections.abc import Mapping
from copy import deepcopy
from fractions import Fraction

from ..analytical.policy_release import POLICY_CONTENT_HASH, payload_hash
from ..calibration.records import partition_id, windows
from ..models import AnalyticalResponseV2
from ..profile_matching.arithmetic import deviation, rounded
from ..profiles.arithmetic import candidate_support, feature_statistics, median
from ..profiles.policy_release import FEATURE_NAMES

RELEASE = "n11-median-response-experiment-v1"
ERROR = "invalid_median_response_experiment"
METHOD_CONTENT_HASH = "sha256:b07b61d089e4636aa5169bb8dcc34d836523e7021aef6180a6500e97befcd5ad"
_METHOD = {
    "method_release": RELEASE,
    "authority": "engineering_only_no_diagnosis_or_trust",
    "response_policy_hash": POLICY_CONTENT_HASH,
    "feature_names": list(FEATURE_NAMES),
    "within_group": "median_unique_responses",
    "across_groups": "median",
    "minimum_groups": 5,
    "minimum_feature_groups": 5,
    "minimum_feature_availability": {"numerator": 4, "denominator": 5},
    "minimum_numeric_features": 17,
    "minimum_common_features": 17,
    "minimum_coverage": {"numerator": 3, "denominator": 4},
    "dispersion": "raw_mad_descriptive_only",
    "distance": "equal_weight_rms_in_n3_normalized_units",
    "arithmetic": "binary64_stage_rounding_reject_overflow_or_nonzero_underflow",
    "minimum_profiles": 2,
    "classification_thresholds": None,
    "source_groups": "declared_engineering_known_aliases_rejected",
    "maximum_responses": 256,
    "maximum_candidates": 16,
}


def median_response_method_spec():
    """Return an independent copy of the explicit experimental method specification."""
    if payload_hash(_METHOD) != METHOD_CONTENT_HASH:
        raise ValueError(ERROR)
    return {**deepcopy(_METHOD), "content_hash": METHOD_CONTENT_HASH}


def _alias(value):
    if type(value) is not str or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", value) is None:
        raise ValueError(ERROR)


def _response(value):
    record = AnalyticalResponseV2.model_validate(value)
    if not record.is_valid or record.policy.content_hash != POLICY_CONTENT_HASH:
        raise ValueError(ERROR)
    return record


def _origins(record):
    result = {("response", record.response_id), ("case", record.observation.comparison_case_id)}
    for window in windows(record, "response"):
        result.add(("run", window.run_id))
        result.add(("source", window.source_artifact.content_hash))
    return result


def _prepare(groups):
    if not isinstance(groups, Mapping) or not 1 <= len(groups) <= 256:
        raise ValueError(ERROR)
    for name in groups:
        _alias(name)
    prepared, ownership, partitions = {}, {}, set()
    count = 0
    for name in sorted(groups):
        rows = groups[name]
        if not isinstance(rows, (tuple, list)) or not 1 <= len(rows) <= 256:
            raise ValueError(ERROR)
        count += len(rows)
        if count > 256:
            raise ValueError(ERROR)
        records = {}
        for raw in rows:
            record = _response(raw)
            partitions.add(partition_id(record, "response"))
            for origin in _origins(record):
                if origin in ownership and ownership[origin] != name:
                    raise ValueError(ERROR)
                ownership[origin] = name
            records[record.response_id] = record
        prepared[name] = tuple(records[key] for key in sorted(records))
    if len(partitions) != 1:
        raise ValueError(ERROR)
    return prepared, set(ownership), next(iter(partitions)), count


def _summarize(prepared, origins, partition, input_rows):
    features = {}
    for name in FEATURE_NAMES:
        values = []
        for group, rows in prepared.items():
            observed = [
                r.features[name].normalized_value
                for r in rows
                if r.features[name].state == "eligible"
            ]
            if observed:
                values.append(dict(group_id=group, value=median(observed)))
        original = feature_statistics([row["value"] for row in values], len(prepared))
        reasons = [reason for reason in original["reason_codes"] if reason != "zero_dispersion"]
        features[name] = dict(
            state="unavailable" if reasons else "numeric",
            reason_codes=reasons,
            contributing_groups=len(values),
            availability=original["availability"],
            center=original["center"],
            raw_mad=original["dispersion"],
            unique_group_values=len({row["value"] for row in values}),
            group_values=values,
        )
    numeric = sum(f["state"] == "numeric" for f in features.values())
    support = candidate_support(len(prepared), numeric)
    payload = dict(
        method_release=RELEASE,
        method_spec=median_response_method_spec(),
        scope="engineering_only_no_label_or_independence_review",
        partition_id=partition,
        group_ids=list(prepared),
        response_ids=sorted({r.response_id for rows in prepared.values() for r in rows}),
        input_rows=input_rows,
        source_origins=[list(origin) for origin in sorted(origins)],
        features=features,
        numeric_feature_count=numeric,
        state="unavailable" if support["reason_codes"] else "computable",
        reason_codes=[reason.replace("active", "numeric") for reason in support["reason_codes"]],
        accepted_diagnostic_groups=0,
        diagnostic_label=None,
        distance_units="unscaled_n3_normalized_response",
        dispersion_used_as_divisor=False,
    )
    return {**payload, "summary_id": "median-experiment-" + payload_hash(payload)[7:]}


def summarize_engineering_responses(groups):
    """Rebuild descriptive centers from declared groups of validated N3 responses.

    Group declarations are not authenticated independence/labels or accepted N6
    selections. Known source/case/run aliases cannot be split across groups.
    Repeated responses within one group collapse before its single median vote.
    """
    try:
        return _summarize(*_prepare(groups))
    except (ValueError, TypeError, KeyError, OverflowError, AttributeError):
        raise ValueError(ERROR) from None


def _rms(query, center, names):
    evidence = {}
    for name in names:
        residual = deviation(query.features[name].normalized_value, center[name]["center"])
        square = rounded(Fraction(residual) ** 2)
        evidence[name] = dict(absolute_difference=residual, squared_difference=square)
    mean_square = rounded(
        sum((Fraction(row["squared_difference"]) for row in evidence.values()), Fraction())
        / len(names)
    )
    return math.sqrt(mean_square), evidence


def compare_engineering_responses(query, candidates):
    """Return label-free distances, rebuilding every candidate from its responses.

    This is deliberately not a classifier. No match, label, confidence, N6 trust,
    or final-study acceptance can be emitted by this experimental function.
    """
    try:
        return _compare(_response(query), candidates)
    except (ValueError, TypeError, KeyError, OverflowError, AttributeError):
        raise ValueError(ERROR) from None


def _compare(query, candidates):
    if not isinstance(candidates, Mapping) or not 1 <= len(candidates) <= 16:
        raise ValueError(ERROR)
    for alias in candidates:
        _alias(alias)
    summaries, reasons, seen = {}, [], set()
    query_origins, query_partition = _origins(query), partition_id(query, "response")
    count = 0
    for alias in sorted(candidates):
        prepared, origins, partition, rows = _prepare(candidates[alias])
        count += rows
        if count > 256 or seen & origins:
            raise ValueError(ERROR)
        seen |= origins
        summaries[alias] = _summarize(prepared, origins, partition, rows)
    if seen & query_origins:
        reasons.append("query_source_overlap")
    usable = {
        alias: summary
        for alias, summary in summaries.items()
        if summary["state"] == "computable" and summary["partition_id"] == query_partition
    }
    if len(usable) < 2:
        reasons.append("insufficient_compatible_profiles")
    common = [
        name
        for name in FEATURE_NAMES
        if query.features[name].state == "eligible"
        and usable
        and all(summary["features"][name]["state"] == "numeric" for summary in usable.values())
    ]
    if len(common) < 17 or len(common) * 4 < len(FEATURE_NAMES) * 3:
        reasons.append("insufficient_common_features")
    comparisons = {}
    if not reasons:
        for alias, summary in usable.items():
            distance, evidence = _rms(query, summary["features"], common)
            comparisons[alias] = dict(distance=distance, evidence=evidence)
        centers = {
            tuple(summary["features"][name]["center"] for name in common)
            for summary in usable.values()
        }
        if len(centers) < 2:
            reasons.append("identical_centers")
    ranked = sorted(comparisons, key=lambda alias: (comparisons[alias]["distance"], alias))
    gap = None
    if len(ranked) >= 2:
        gap = rounded(
            Fraction(comparisons[ranked[1]]["distance"])
            - Fraction(comparisons[ranked[0]]["distance"])
        )
        if gap == 0 and "identical_centers" not in reasons:
            reasons.append("equal_distances")
    return dict(
        method_release=RELEASE,
        method_spec=median_response_method_spec(),
        state="unavailable" if reasons else "distances_available",
        reason_codes=reasons,
        query_response_id=query.response_id,
        summaries=summaries,
        common_features=common,
        comparisons=comparisons,
        ranked_candidates=ranked,
        distance_gap=gap,
        diagnostic_label=None,
        classification_authority="unavailable_experimental_method",
        accepted_diagnostic_groups=0,
    )


def pacing_contrast_preflight(*, prior_fps, target_fps, delay_us):
    """Exact serial-delay envelope only; no native acquisition or setter authority."""
    if any(type(v) is not int for v in (prior_fps, target_fps, delay_us)):
        raise ValueError(ERROR)
    if not 24 <= target_fps < prior_fps <= 60 or not 1 <= delay_us <= 1_000_000:
        raise ValueError(ERROR)
    if 100 * (prior_fps - target_fps) > 20 * prior_fps:
        raise ValueError(ERROR)
    ceiling = Fraction(1_000_000, delay_us)
    crossing = target_fps < ceiling < prior_fps
    return dict(
        method_release="n11-pacing-contrast-envelope-v1",
        prior_fps=prior_fps,
        target_fps=target_fps,
        delay_us=delay_us,
        modeled_ceiling=dict(numerator=ceiling.numerator, denominator=ceiling.denominator),
        modeled_crossing=crossing,
        reason_codes=[] if crossing else ["no_strict_modeled_crossing"],
        measured_contrast="unavailable",
        diagnostic_utility="unavailable",
        acquisition_authority=False,
    )
