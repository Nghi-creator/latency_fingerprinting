# Shared-window separation prototype

`evaluation.shared_window_separation.compare_shared_window_centers` implements
`n11-shared-window-separation-prototype-v1`. It produces a conditional numerical
certificate or abstains. `evaluation.shared_window_candidate` uses this primitive
for same-session fitting and scoring under a separate method identity.

Supply `phase_rates[group][phase]` for the encoded rate, CPU quota fraction and
reported throttled seconds per wall second. Each group has healthy, degraded,
relief and post windows. Supply `centers[condition][feature]` for all three fixture
conditions and all nine existing coordinates. Each interval uses `lower` and
`upper` exact rational endpoints, with integer `numerator` and positive integer
`denominator`. Rate bounds are nonnegative; healthy and degraded encoded rates
must have strictly positive lower bounds. Missing and invalid inputs fail closed.

`evaluation.shared_window_projection.project_shared_window_source(source)`
produces these phase-rate boxes from the same `acquisition_json` and
`resource_artifact` inputs as the counter-specific projection. It runs the
existing validators and extracts the guarded rates from the validated component
responses. It requires exact rational agreement between the resulting marginal
bounds and all nine counter-specific intervals. An unavailable component yields
empty rate and marginal maps. The projection ID binds the source bytes, the
canonical resource artifact, and the original counter-specific response ID.
Execution provenance still requires the producer inspector and custody replay.

## Event-span source

Pass `event_span=True` to the source projection, binding, fit, and score APIs
to select the event-span releases. The projection validates the acquisition
and CPU artifact, then reconstructs the five event windows from recorded
phase boundaries. It checks the worker generation clock, declared time
namespace, controller origin, snapshot count reconciliation, and consistency
with the recorded getter reads. All five phase spans must be eligible,
including recovery. Missing or unreconciled event evidence makes the encoded
component unavailable. Bindings identify the selected release and projection.

The event rate uses the number of completed buffer intervals between
bracketed callbacks inside each phase. The guarded CPU rates use their
original sample endpoints. Event and CPU windows can therefore cover
different intervals within a phase. The original polled contracts remain
the default.

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

## Fitting and query decisions

`declare_shared_window_binding` binds an externally reviewed condition and
inspection to the shared-window source projection ID. `fit_shared_window_candidate`
rebuilds the projection from each source and requires six complete blocks with one
case for each condition. The six leave-block-out folds each build centers from
the other five blocks. Each center coordinate uses the median of the lower
endpoints and the median of the upper endpoints across those blocks.

Calibration requires all 18 held-out fitting cases to certify their declared
condition. For each certified case, its margin is the smaller of its two
certified lower bounds against the rivals. The minimum of the 18 margins becomes
the query margin threshold. Each class radius is the maximum upper distance to
the correct center among its six held-out fitting cases. The radius uses the
conservative marginal box distance, including all nine coordinates. Failed folds
leave calibration unavailable with null thresholds.

`score_shared_window_candidate` rebuilds calibration from the original fitting
sources, then compares the query with centers built from all six fitting blocks.
The query must have a compatible context and session and a fresh block, source,
and clocks. A prediction requires a unique certificate, an upper distance within
its class radius, and a certified margin at least as large as the fitted minimum.
The reported pairwise comparisons retain the bounds and witnesses, including
when the radius or margin test leads to abstention.

## Condition-specific event-span recognition

Pass `condition_specific=True` to binding, fit, and score to select the
condition-specific event-span release. Delay versus no fault compares the
three encoded coordinates in both directions. A comparison involving owned
CPU pressure uses all nine coordinates. Each certificate averages over
its selected coordinates and the witness lists the corresponding rate
groups. This reflects the effects targeted by the two controlled
interventions and avoids using CPU variation as direct delay evidence.

All nine coordinates and all five source phases are required. Each candidate
must certify separation from both rivals. If no candidate does so, the
classifier abstains, including when pairwise preferences form a cycle. The
original all-coordinate class radius and the all-fold calibration requirement
also apply. Binding releases keep calibration inputs for each method distinct.

## Precision planning for a prospective protocol

1. For the polled source, bound rates from actual counter deltas and
   first/last read brackets, retain one-buffer and one-microsecond guards, and
   require all original windows and coordinates. Existing read-span, duration,
   order, clock, quota and ownership checks still apply. The source adapter
   binds phase rates to the verified acquisition and resource artifact. For the
   event-span source, use the callback timing bounds and retain the CPU guard.
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
4. Before any prospective use, verify source custody for the selected inputs,
   freeze the profile/calibration contract and justify the precision target on
   evidence appropriate to that design. Keep the existing all-fold requirement
   and an untouched evaluation.

`experiments/plan_shared_window_precision.py` checks the supplied fitting file's
SHA-256, then reports the nominal margin, center uncertainty penalty and query
uncertainty penalty for both rivals in each fitting fold. Its duration scenarios
hold the observed rate midpoints constant and add explicit timing and counter
rounding allowances. The resulting budget is a prospective design screen and
requires evidence that the chosen acquisition can sustain the modeled rates.

Synthetic regressions cover a shared CPU difference and an encoded ratio whose
independent coordinate extrema cannot occur together, uncertain centers, ties,
search exhaustion and witness replay against an independently evaluated grid.
They establish arithmetic behavior, not recognition performance.

## Frozen calibration across documented sessions

`evaluation.cross_session_candidate.score_cross_session_candidate` uses a
separate release for transfer queries. Supply the exact frozen fitting JSON
and its expected SHA-256, a session record and its expected canonical hash,
the query source, declared query and block IDs, and prior prediction receipts.
The scorer rebuilds the fitting artifact and verifies its identity before
applying its centers, radii and minimum gap. It reports calibration and query
session IDs separately.

The session record identifies the prior session end and current session
start, operator documentation and observed host, boot, browser, source and
runtime context. Its hash must be bound by the operator's custody workflow.
The scorer checks the record's structure and runtime compatibility. Execution
provenance and the truth of a session boundary require external records.

The scorer abstains when the session matches calibration, the runtime is
incompatible, a fitting block/source/clock is reused, a prior query ID/source/
clock is reused, or a block appears under conflicting sessions. Complete
measurements and the existing certificate, radius and minimum-gap rules
apply. Malformed records and changed calibration raise a validation error.

`experiments/cross_session_study.py` inspects a pinned transfer protocol and
scores its next declared query. It verifies scorer dependencies, checks the
ordered prior-prediction ledger and writes the new prediction exclusively.
The caller supplies the full ledger and the externally verified acquisition.
Three documented host sessions are reported as session groups. Statistical
independence requires additional evidence.
