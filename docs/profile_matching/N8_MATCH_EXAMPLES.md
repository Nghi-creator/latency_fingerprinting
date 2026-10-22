# Independent matching and evaluation examples

These synthetic design calculations were frozen before N8 production code.
They are abstract arithmetic/selection kernels, not complete N6/N7 model roots,
linked acquisitions, a fixture release or evidence of diagnostic accuracy. The
[machine-readable vectors](N8_DESIGN_VECTORS.json) and
[policy](N8_MATCH_POLICY_SPEC.json) accompany the
[matching](N8_MATCH_CONTRACT.md) and [evaluation](N8_EVALUATION_CONTRACT.md) contracts.

With 22 common features, query value 0, a healthy profile centered at 0/MAD 1 and
a host profile centered at 2/MAD 2 give distances 0 and 1. Both labels share one
mask and denominator. The gap 1 passes the provisional 0.25 margin gate and best
distance 0 passes the distance gate. Changing the query's evaluation label cannot
change those numbers or choose a different class.

If one label supports features 0–16 and another supports 5–21, their intersection
has only 12 features. Compute no ranking; the outcome is unknown with insufficient
common count and coverage. Comparing each label on its own 17-feature subset is
not the method. A null query value contributes no zero, weight or standardized
term. Retain every feature exclusion and every candidate, including incompatible
or unsupported candidates that never participated in the common mask.

A best/runner-up pair 0.5/0.75 passes the absolute-margin boundary exactly;
0.5/0.625 fails. Equal distances are ambiguous even if lexical order displays one
first. Best distance 3 passes, while 3.5 fails. One label at distance 0 still has
no competing-label evidence and remains unknown. A far single label retains both
`no_competing_label` and `distance_exceeded`. Sixteen common features fail both
count and coverage gates; 17 pass.

A shared connected component, source alias or primary receipt excludes a candidate.
Actual N6 cross-role contradictions fail inspection before scoring. Source aliases
are meaningful only within the one declared inspected dataset; changing alias
spellings or using different datasets cannot assert independence. Same-label old
snapshot revisions are rejected inputs, not extra votes or competing classes.
A stale/rejected/created/superseded snapshot yields unknown rather than a restored
profile. A standalone report is not proof that linked files were inspected.

For binary64 arithmetic, `1/3` standardization rounds to
`0x1.5555555555555p-2`; a minimum subnormal divided by 2 fails for nonzero-to-zero
underflow. Maximum finite divided by 0.5 fails for overflow. Absolute difference
of positive and negative maximum finite fails before standardization, even if a
large later scale might have reduced it. In contrast, the mean of two maximum
finite standardized terms is maximum finite: the exact rational sum is allowed
to exceed binary64 before division. Computed zero is positive; raw signed zero
may remain in a query map.

For a fold with group values `[0, 2]`, `[1]`, `[2]`, `[3]`, `[4]`, `[5]`, holding out
the first group removes both windows. Remaining group votes are 1–5, center 3,
raw MAD 1 and group count 5. Removing just the first window would leave an extra
group and give a different center; it is leakage. With only five groups 0–4,
removing group 0 leaves center 2.5 and MAD 1 but only four contributing groups;
that feature is unsupported. A fold can also leave five constant group votes,
giving MAD zero and excluded weight. Neither fold may borrow a held-out scale.

For three response groups with true labels healthy, host, healthy and predictions
`[healthy, healthy]`, `[unknown]`, `[host]`, there are three group votes, not four
window votes. Correct=1, incorrect=1, unknown=1; accuracy and unknown rate are both
1/3, truth coverage is 3/3. An unknown prediction is retained in accuracy's known
truth denominator. Disagreement within a group produces unknown. An unverified
truth contributes to the full matrix, truth-coverage denominator and unknown-rate
denominator, not silently to a successful known-label result. Empty cohorts have
null ratios with exact 0/0 counts.

The design tests pin policy/vector bytes and compare literal examples with an
independent high-precision Decimal oracle. They also check label blindness,
feature-mask symmetry, reason ordering, whole-group removal and denominators.
Production is specified separately to use bounded rational binary64 arithmetic.
Change expected outcomes only after reviewing the specification, never by copying
scorer output. The [standalone models](N8_MODELS.md) now reconstruct this method;
linked source inspection and matching/evaluation commands remain a separate gate.

The [runtime fixture release](N8_FIXTURES.md) additionally freezes complete model
roots and linked command outcomes with independent expectations and source pins.
