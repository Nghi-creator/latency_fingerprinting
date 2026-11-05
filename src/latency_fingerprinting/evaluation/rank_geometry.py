"""Candidate training-only rank geometry; no classifier or acquisition authority."""

from bisect import bisect_left, bisect_right
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from math import isfinite

from ..analytical.policy_release import payload_hash

RELEASE = "n11-pooled-midrank-geometry-candidate-v1"
ERROR = "invalid_rank_geometry_input"
_SPEC = dict(
    release=RELEASE,
    state="candidate_arithmetic_only_not_a_recognition_method",
    fit="unlabelled_training_pool_only_refit_inside_each_training_fold",
    transform="(count_less_than_value_plus_half_count_equal_to_value)/pool_size",
    duplicates="retain_frequency_equal_values_receive_equal_midrank",
    constant_features="rank_one_half_no_scale_divisor_or_epsilon",
    distance="mean_absolute_difference_of_feature_midranks",
    range="both_vectors_within_closed_training_support_or_unavailable",
    missingness="all_caller_frozen_features_required_no_imputation_or_query_adaptation",
    arithmetic="exact_rational_from_finite_binary64_inputs_then_float_output",
    feature_selection=False,
    classifier=False,
    empirical_acceptance=False,
    acquisition_authority=False,
)


def rank_geometry_spec():
    """Detached design identity, distinct from frozen recognition method releases."""
    return {**_SPEC, "content_hash": payload_hash(_SPEC)}


def _number(value):
    if type(value) not in (int, float):
        raise ValueError(ERROR)
    try:
        number = float(value)
        if not isfinite(number) or (value != 0 and number == 0):
            raise ValueError(ERROR)
        return Fraction(number)
    except (OverflowError, TypeError):
        raise ValueError(ERROR) from None


@dataclass(frozen=True)
class RankGeometry:
    """Immutable sorted training support. Construct with fit_rank_geometry."""

    support: tuple[tuple[str, tuple[Fraction, ...]], ...]

    def __post_init__(self):
        try:
            if type(self.support) is not tuple or not 1 <= len(self.support) <= 22:
                raise ValueError(ERROR)
            names, sizes = set(), set()
            for entry in self.support:
                if type(entry) is not tuple or len(entry) != 2:
                    raise ValueError(ERROR)
                name, values = entry
                if type(name) is not str or not name or name in names:
                    raise ValueError(ERROR)
                if type(values) is not tuple or not 2 <= len(values) <= 96:
                    raise ValueError(ERROR)
                if any(type(v) is not Fraction for v in values) or tuple(sorted(values)) != values:
                    raise ValueError(ERROR)
                names.add(name)
                sizes.add(len(values))
            if len(sizes) != 1:
                raise ValueError(ERROR)
        except (TypeError, AttributeError):
            raise ValueError(ERROR) from None


def fit_rank_geometry(samples, *, feature_names):
    """Fit only caller-selected training vectors; no labels or query argument.

    Callers must freeze eligibility and keep validation/query vectors out of the
    pool. This numerical primitive cannot authenticate their data-role choices.
    """
    try:
        if type(feature_names) not in (list, tuple) or not 1 <= len(feature_names) <= 22:
            raise ValueError(ERROR)
        if any(type(n) is not str or not n for n in feature_names):
            raise ValueError(ERROR)
        if len(set(feature_names)) != len(feature_names):
            raise ValueError(ERROR)
        if type(samples) not in (list, tuple) or not 2 <= len(samples) <= 96:
            raise ValueError(ERROR)
        if any(not isinstance(row, Mapping) for row in samples):
            raise ValueError(ERROR)
        return RankGeometry(
            tuple(
                (name, tuple(sorted(_number(row[name]) for row in samples)))
                for name in feature_names
            )
        )
    except (KeyError, TypeError, AttributeError):
        raise ValueError(ERROR) from None


def rank_distance(left, right, geometry):
    """Compare complete vectors, abstaining outside frozen training support.

    The result is a distance only, with no condition prediction or thresholds.
    Extra vector fields are ignored; every frozen feature must be present.
    """
    if not isinstance(geometry, RankGeometry) or not all(
        isinstance(vector, Mapping) for vector in (left, right)
    ):
        raise ValueError(ERROR)
    missing, outside, terms = [], [], []
    for name, support in geometry.support:
        if name not in left or name not in right:
            missing.append(name)
            continue
        a, b = _number(left[name]), _number(right[name])
        if not support[0] <= a <= support[-1] or not support[0] <= b <= support[-1]:
            outside.append(name)
            continue
        ranks = [
            Fraction(bisect_left(support, value) + bisect_right(support, value), 2 * len(support))
            for value in (a, b)
        ]
        terms.append((name, abs(ranks[0] - ranks[1])))
    reasons = []
    if missing:
        reasons.append("missing_frozen_features")
    if outside:
        reasons.append("outside_training_support")
    return dict(
        release=RELEASE,
        state="unavailable" if reasons else "candidate_distance_available",
        reason_codes=reasons,
        missing_features=missing,
        outside_support_features=outside,
        distance=None if reasons else float(sum((v for _, v in terms), Fraction()) / len(terms)),
        feature_distances={} if reasons else {name: float(v) for name, v in terms},
        empirical_acceptance=False,
        acquisition_authority=False,
    )
