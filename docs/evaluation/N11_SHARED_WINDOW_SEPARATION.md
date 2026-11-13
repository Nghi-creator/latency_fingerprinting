# Shared-window separation prototype

`evaluation.shared_window_separation.compare_shared_window_centers` implements
`n11-shared-window-separation-prototype-v1`. It produces a conditional numerical
certificate or abstains. It does not acquire data, build profiles, calibrate
thresholds, or score study cases. Existing methods and study gates are unchanged.

Supply `phase_rates[group][phase]` for the encoded rate, CPU quota fraction and
reported throttled seconds per wall second. Each group has healthy, degraded,
relief and post windows. Supply `centers[condition][feature]` for all three fixture
conditions and all nine existing coordinates. Each interval uses `lower` and
`upper` exact rational endpoints, with integer `numerator` and positive integer
`denominator`. Rate bounds are nonnegative; healthy and degraded encoded rates
must have strictly positive lower bounds. Missing and invalid inputs fail closed.

## Dependence and certificate

For one choice of rates `(H, D, R, P)` in a group, the encoded coordinates are
`D/H − 1`, `R/D − 1` and `P/H − 1`. The CPU coordinates are `D − H`, `R − D`
and `P − H` for each metric. The same phase rate is reused everywhere within its
group. Each query coordinate also uses the same value for both class distances.
All nine coordinates keep equal weight, including the three post comparisons.
Recovery evidence continues to be validated upstream; it is never treated as a
missing coordinate or dropped to get separation.

For query coordinate `x`, candidate center interval `A` and rival interval `B`,
the worst pairwise contrast is `dist(x, B) − max(|x − A.low|, |x − A.high|)`.
The minimum over a coordinate interval is exact by checking its endpoints and
the contained breakpoints `B.low`, `B.high` and the midpoint of `A`. For a rate
cell, sum these coordinate minima over the coordinate hulls: this is a lower
bound because each attainable vector lies in those hulls. Evaluate the contrast
at one common rate point in that cell to obtain an upper bound on the minimum.
A midpoint is used only as an admissible witness, never as a replacement for
uncertain data. The whole objective is the sum of the three group contributions
divided by nine.

Bisection partitions the rate domain without losing any point. A child's bound
can inherit the parent's lower bound. The smallest remaining lower bound in
each group and the best feasible witness give a certified enclosure. Up to 64
splits are allowed per ordered pair; the algorithm checks both directions for
each condition pair. A condition is certified only if its lower bounds against
both rivals are strictly positive. A nonpositive witness (including a tie) or
an unresolved bound cannot certify that direction. If no unique condition is
certified, the result is abstention. The reported witness rates allow a caller
to reproduce the upper bound under the stated center-box model.

The domain is still an outer model. Class centers retain their full independent
coordinate boxes. The CPU groups are also treated independently, even though
usage and throttling share elapsed time. The prototype preserves dependence
within each query metric; it does not claim to recover all source or training
correlations. A nonpositive witness is admissible in this outer model, which
need not imply that the same witness can occur in a physical run.

## Precision requirements before source integration

1. Keep the current source checks: bound rates from actual counter deltas and
   first/last read brackets, retain one-buffer and one-microsecond guards, and
   require all original windows and coordinates. Existing read-span, duration,
   order, clock, quota and ownership checks still apply. A future adapter must
   bind phase rates to verified source bytes, not reconstruct them from finished
   feature boxes. No replacement timestamp, guard change or zero-MAD exclusion.
2. Plan precision in **margin units**, not by timestamp width alone. A guarded
   rate has width `scale × ((delta + guard)/inner − max(0, delta − guard)/outer)`.
   Compute the resulting coordinate hulls from those rate intervals. This
   includes the counter guard even for instantaneous reads. Near-zero encoded
   denominators expand the ratio hulls and cannot be repaired with an epsilon.
3. A sufficient planning check is available before running subdivision. At an
   admissible reference rate point, let `M` be the mean worst-center contrast and
   let `e_i` bound how far each coordinate can move from that point. Each of the
   two distance functions is 1-Lipschitz in that coordinate, so `M − 2 Σ e_i/9`
   is a conservative lower bound. A prospective design must justify a positive
   margin target and rate precision that leave room for it under plausible
   response and center variation. Failure of this sufficient check can be
   evaluated with the tighter certificate; it is not a license to narrow the
   input bounds. These are design requirements, not fitted tolerances.
4. Before any prospective use, implement and verify the source-bound adapter,
   freeze the profile/calibration contract and justify the precision target on
   evidence appropriate to that design. Keep the existing all-fold requirement
   and an untouched evaluation. No numeric precision target or collection size
   is approved by this prototype.

Synthetic regressions cover a shared CPU difference and an encoded ratio whose
independent coordinate extrema cannot occur together, uncertain centers, ties,
search exhaustion and witness replay against an independently evaluated grid.
They establish arithmetic behavior, not recognition performance.
