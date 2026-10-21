"""Bounded exact binary64 midpoint/deviation arithmetic; no files or ambient state."""

import math
from fractions import Fraction


def _number(value):
    if type(value) not in (float, int) or (type(value) is int and value.bit_length() > 1024):
        raise ValueError("invalid_profile_arithmetic")
    try:
        value = float(value)
        if not math.isfinite(value):
            raise ValueError
        return value
    except (ValueError, OverflowError):
        raise ValueError("invalid_profile_arithmetic") from None


def _rounded(value):
    try:
        result = float(value)
        if not math.isfinite(result) or (value != 0 and result == 0):
            raise ValueError
        return 0.0 if result == 0 else result
    except (ValueError, OverflowError):
        raise ValueError("invalid_profile_arithmetic") from None


def median(values):
    if not isinstance(values, (list, tuple)) or not 1 <= len(values) <= 256:
        raise ValueError("invalid_profile_arithmetic")
    values = sorted(_number(value) for value in values)
    middle = len(values) // 2
    if len(values) % 2:
        return 0.0 if values[middle] == 0 else values[middle]
    return _rounded((Fraction(values[middle - 1]) + Fraction(values[middle])) / 2)


def absolute_deviation(value, center):
    return _rounded(abs(Fraction(_number(value)) - Fraction(_number(center))))


def ratio(numerator, denominator):
    if (
        type(numerator) is not int
        or type(denominator) is not int
        or not 0 <= numerator <= denominator <= 256
    ):
        raise ValueError("invalid_profile_arithmetic")
    return dict(
        numerator=numerator,
        denominator=denominator,
        value=_rounded(Fraction(numerator, denominator)) if denominator else None,
    )


def feature_statistics(group_values, denominator):
    """Reconstruct a feature from bounded per-group medians and candidate group count."""
    if not isinstance(group_values, (list, tuple)) or len(group_values) > 256:
        raise ValueError("invalid_profile_arithmetic")
    values = [_number(value) for value in group_values]
    availability = ratio(len(values), denominator)
    center = median(values) if values else None
    dispersion = median([absolute_deviation(value, center) for value in values]) if values else None
    reasons = []
    if not values:
        reasons.append("missing_measurements")
    if len(values) < 5:
        reasons.append("insufficient_group_support")
    if denominator == 0 or len(values) * 5 < denominator * 4:
        reasons.append("insufficient_availability")
    if dispersion == 0:
        reasons.append("zero_dispersion")
    return dict(
        state="excluded" if reasons else "supported",
        reason_codes=reasons,
        weight=0.0 if reasons else 1.0,
        contributing_groups=len(values),
        availability=availability,
        center=center,
        dispersion=dispersion,
    )


def candidate_support(groups, active):
    if (
        type(groups) is not int
        or type(active) is not int
        or not 0 <= groups <= 256
        or not 0 <= active <= 22
    ):
        raise ValueError("invalid_profile_arithmetic")
    reasons = []
    if groups < 5:
        reasons.append("insufficient_training_groups")
    if active < 17:
        reasons.append("insufficient_active_features")
    if active * 4 < 22 * 3:
        reasons.append("insufficient_active_coverage")
    return dict(
        state="rejected" if reasons else "provisional",
        reason_codes=reasons,
        active_feature_count=active,
        active_feature_coverage=ratio(active, 22),
    )
