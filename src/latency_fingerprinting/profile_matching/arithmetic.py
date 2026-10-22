"""Exact bounded binary64 N8 arithmetic; each declared stage rounds once."""

import math
from fractions import Fraction


def number(value):
    if type(value) not in (int, float) or (type(value) is int and value.bit_length() > 1024):
        raise ValueError("invalid_profile_match_arithmetic")
    try:
        result = float(value)
        if not math.isfinite(result):
            raise ValueError
        return result
    except (ValueError, OverflowError):
        raise ValueError("invalid_profile_match_arithmetic") from None


def rounded(value):
    try:
        result = float(value)
        if not math.isfinite(result) or (value != 0 and result == 0):
            raise ValueError
        return 0.0 if result == 0 else result
    except (ValueError, OverflowError):
        raise ValueError("invalid_profile_match_arithmetic") from None


def deviation(value, center):
    return rounded(abs(Fraction(number(value)) - Fraction(number(center))))


def standardize(value, scale):
    value, scale = number(value), number(scale)
    if value < 0 or scale <= 0:
        raise ValueError("invalid_profile_match_arithmetic")
    return rounded(Fraction(value) / Fraction(scale))


def mean(values):
    if not isinstance(values, (list, tuple)) or not 1 <= len(values) <= 22:
        raise ValueError("invalid_profile_match_arithmetic")
    values = [number(v) for v in values]
    if any(v < 0 for v in values):
        raise ValueError("invalid_profile_match_arithmetic")
    return rounded(sum((Fraction(v) for v in values), Fraction()) / len(values))


def margin(runner_up, best):
    runner_up, best = number(runner_up), number(best)
    if best < 0 or runner_up < best:
        raise ValueError("invalid_profile_match_arithmetic")
    return rounded(Fraction(runner_up) - Fraction(best))
