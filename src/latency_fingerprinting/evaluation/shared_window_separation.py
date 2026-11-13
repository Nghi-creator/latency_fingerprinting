"""Experimental certificate over shared phase rates, independent of fitting or acquisition."""

from collections.abc import Mapping
from copy import deepcopy
from fractions import Fraction
from heapq import heappop, heappush
from itertools import count

from ..analytical.policy_release import payload_hash
from .combined_interval_candidate import FEATURES
from .cpu_resource_response import COMPARISONS
from .fixture_conditions import CONDITIONS
from .temporal_rate_response import FEATURES as ENCODED_FEATURES

RELEASE = "n11-shared-window-separation-prototype-v1"
MAX_SPLITS = 64
MAX_INPUT_BITS = 256
PHASES = ("healthy", "degraded", "relief", "post")
GROUPS = {
    "encoded": {f"encoded.{name}": pair for name, pair in ENCODED_FEATURES.items()},
    **{
        metric: {f"resource.{metric}.{name}": pair for name, pair in COMPARISONS.items()}
        for metric in ("cpu_quota_fraction", "throttled_seconds_per_wall_second")
    },
}
_SPEC = dict(
    release=RELEASE,
    phases=list(PHASES),
    groups={g: {k: list(pair) for k, pair in terms.items()} for g, terms in GROUPS.items()},
    features=list(FEATURES),
    query_set="one_shared_rate_per_phase_within_metric_independent_outer_groups",
    centers="fixed_outer_coordinate_boxes_no_assumption_of_shared_center_uncertainty",
    objective="infimum_of_mean_absolute_rival_distance_minus_candidate_distance",
    maximum_splits_per_ordered_pair=MAX_SPLITS,
    maximum_input_integer_bits=MAX_INPUT_BITS,
    subdivision="largest_group_bound_gap_then_lowest_leaf_bound_then_widest_relative_phase",
    arithmetic="exact_rational_midpoints_only_for_feasible_witnesses_and_subdivision",
    decision="strict_positive_lower_bound_against_every_rival_else_abstain",
    recovery="retain_post_coordinates_and_existing_upstream_recovery_checks",
    empirical_acceptance=False,
    acquisition_authority=False,
)
ERROR = "invalid_shared_window_separation_input"


def shared_window_separation_spec():
    return {**deepcopy(_SPEC), "content_hash": payload_hash(_SPEC)}


def _keys(value, keys):
    if not isinstance(value, Mapping) or set(value) != set(keys):
        raise ValueError(ERROR)


def _fraction(value):
    _keys(value, ("numerator", "denominator"))
    n, d = value["numerator"], value["denominator"]
    if any(type(x) is not int or x.bit_length() > MAX_INPUT_BITS for x in (n, d)) or d <= 0:
        raise ValueError(ERROR)
    return Fraction(n, d)


def _interval(value):
    _keys(value, ("lower", "upper"))
    lo, hi = _fraction(value["lower"]), _fraction(value["upper"])
    if lo > hi:
        raise ValueError(ERROR)
    return lo, hi


def _ratio(value):
    return dict(numerator=value.numerator, denominator=value.denominator)


def _contrast(x, own, rival):
    return max(Fraction(), rival[0] - x, x - rival[1]) - max(abs(x - z) for z in own)


def _lower(query, own, rival):
    # The contrast is affine between the two rival endpoints and the own midpoint.
    knots = (*query, *rival, sum(own) / 2)
    return min(_contrast(x, own, rival) for x in knots if query[0] <= x <= query[1])


def _hull(a, b, encoded):
    if encoded:
        return a[0] / b[1] - 1, a[1] / b[0] - 1
    return a[0] - b[1], a[1] - b[0]


def _cell(group, box, own, rival):
    midpoint = {p: sum(bounds) / 2 for p, bounds in box.items()}
    lower = upper = Fraction()
    for name, (a, b) in GROUPS[group].items():
        q = _hull(box[a], box[b], group == "encoded")
        x = midpoint[a] / midpoint[b] - 1 if group == "encoded" else midpoint[a] - midpoint[b]
        lower += _lower(q, own[name], rival[name])
        upper += _contrast(x, own[name], rival[name])
    return lower, upper, midpoint


def _pair(rates, own, rival):
    serial = count()
    leaves, upper, witnesses = {}, {}, {}
    for group, box in rates.items():
        lo, hi, point = _cell(group, box, own, rival)
        leaves[group] = [(lo, next(serial), box)]
        upper[group], witnesses[group] = hi, point
    root_lower = sum(heap[0][0] for heap in leaves.values())
    splits = 0
    while True:
        lower = sum(heap[0][0] for heap in leaves.values())
        witness = sum(upper.values())
        if lower > 0 or witness <= 0 or splits == MAX_SPLITS:
            break
        group = max(GROUPS, key=lambda g: upper[g] - leaves[g][0][0])
        parent_lower, _, box = heappop(leaves[group])

        def relative_width(phase, root=rates[group], cell=box):
            a, b = root[phase]
            lo, hi = cell[phase]
            return (hi - lo) / (b - a) if b > a else Fraction()

        phase = max(PHASES, key=relative_width)
        lo, hi = box[phase]
        mid = (lo + hi) / 2
        for interval in ((lo, mid), (mid, hi)):
            child = {**box, phase: interval}
            lb, ub, point = _cell(group, child, own, rival)
            heappush(leaves[group], (max(lb, parent_lower), next(serial), child))
            if ub < upper[group]:
                upper[group], witnesses[group] = ub, point
        splits += 1
    return dict(
        state="strictly_separated"
        if lower > 0
        else "nonpositive_witness"
        if witness <= 0
        else "unresolved_at_split_limit",
        lower=_ratio(lower / len(FEATURES)),
        upper=_ratio(witness / len(FEATURES)),
        root_lower=_ratio(root_lower / len(FEATURES)),
        splits=splits,
        witness_rates={
            g: {p: _ratio(x) for p, x in point.items()} for g, point in witnesses.items()
        },
    )


def compare_shared_window_centers(phase_rates, centers):
    """Compare complete rate and center boxes; returns a conditional certificate or abstains.

    Rates are guarded nonnegative intervals; encoded denominators must be positive.
    Each interval is {lower, upper} with exact {numerator, denominator} endpoints.
    Inputs alone do not authenticate a source, supply a fit, or authorize a study.
    """
    _keys(phase_rates, GROUPS)
    _keys(centers, CONDITIONS)
    rates, profiles = {}, {}
    for group in GROUPS:
        _keys(phase_rates[group], PHASES)
        rates[group] = {p: _interval(phase_rates[group][p]) for p in PHASES}
        if any(
            a < 0 or (group == "encoded" and p in ("healthy", "degraded") and a == 0)
            for p, (a, _) in rates[group].items()
        ):
            raise ValueError(ERROR)
    for c in CONDITIONS:
        _keys(centers[c], FEATURES)
        profiles[c] = {name: _interval(centers[c][name]) for name in FEATURES}
    comparisons = {
        c: {r: _pair(rates, profiles[c], profiles[r]) for r in CONDITIONS if r != c}
        for c in CONDITIONS
    }
    winners = [
        c
        for c, rows in comparisons.items()
        if all(result["state"] == "strictly_separated" for result in rows.values())
    ]
    winner = winners[0] if len(winners) == 1 else None
    return dict(
        state="conditional_separation_certificate" if winner is not None else "abstain",
        separated_condition=winner,
        comparisons=comparisons,
        method_spec=shared_window_separation_spec(),
        empirical_acceptance=False,
        acquisition_authority=False,
    )
