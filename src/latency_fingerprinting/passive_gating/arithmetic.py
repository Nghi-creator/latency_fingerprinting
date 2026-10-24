"""Exact bounded N9 level arithmetic; zero spread is diagnostic, never a divisor."""

from fractions import Fraction

from ..profiles.arithmetic import _number, _rounded
from ..profiles.arithmetic import absolute_deviation as _deviation
from ..profiles.arithmetic import median as _median


def number(value):
    try:
        result = _number(value)
        if result < 0:
            raise ValueError
        return result
    except ValueError:
        raise ValueError("invalid_passive_arithmetic") from None


def median(values):
    if not isinstance(values, (list, tuple)) or not 1 <= len(values) <= 256:
        raise ValueError("invalid_passive_arithmetic")
    try:
        return _median([number(value) for value in values])
    except ValueError:
        raise ValueError("invalid_passive_arithmetic") from None


def deviation(value, center):
    try:
        return _deviation(number(value), number(center))
    except ValueError:
        raise ValueError("invalid_passive_arithmetic") from None


def ratio(value, center):
    try:
        value, center = number(value), number(center)
        if center <= 0:
            raise ValueError
        return _rounded(Fraction(value) / Fraction(center))
    except ValueError:
        raise ValueError("invalid_passive_arithmetic") from None


def classify(value, center):
    value, center = Fraction(number(value)), Fraction(number(center))
    if center <= 0:
        raise ValueError("invalid_passive_arithmetic")
    if 5 * value <= 4 * center:
        return "low"
    return "recovered" if 10 * value >= 9 * center else "band"


def statistics(groups):
    if not isinstance(groups, (list, tuple)) or len(groups) > 256:
        raise ValueError("invalid_passive_arithmetic")
    if any(not isinstance(g, (list, tuple)) for g in groups) or sum(map(len, groups)) > 256:
        raise ValueError("invalid_passive_arithmetic")
    values = [median(group) for group in groups if group]
    center = median(values) if values else None
    spread = median([deviation(value, center) for value in values]) if values else None
    reasons = []
    if len(groups) < 5:
        reasons.append("insufficient_training_groups")
    if len(values) < 5:
        reasons.append("insufficient_metric_groups")
    if not groups or 5 * len(values) < 4 * len(groups):
        reasons.append("insufficient_availability")
    if center is None or center <= 0:
        reasons.append("baseline_center_not_positive")
    return dict(
        center=center,
        raw_mad=spread,
        state="rejected" if reasons else "provisional",
        reason_codes=reasons,
    )
