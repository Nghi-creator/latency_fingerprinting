# Independent profile statistics and lifecycle examples

These are synthetic design calculations, not adopted N3/N6 measurement records
or scientific evidence. They freeze expected N7 behavior before its implementation.
The [machine-readable vectors](N7_DESIGN_VECTORS.json) accompany the
[contract](N7_PROFILE_CONTRACT.md) and [policy](N7_PROFILE_POLICY_SPEC.json).
Symbolic group names/arrays describe arithmetic only; they do not fabricate valid
source receipts or real-provenance data. Extreme vectors test the numerical
helper's whole finite binary64 domain, independently of which values a physical
N3 measurement could produce.

## Two levels, one group vote

Consider one feature in five eligible training groups:

| Group | Eligible window feature values | One group median |
| --- | --- | --- |
| A | 0, 0, 0, 0, 0 | 0 |
| B | 1 | 1 |
| C | 2 | 2 |
| D | 3 | 3 |
| E | 4 | 4 |

The center of `[0,1,2,3,4]` is 2. Absolute deviations are `[2,1,0,1,2]`;
the raw MAD is 1. Five groups contribute, availability is 5/5, weight is 1.
Pooling all nine windows would instead give center 0 and MAD 0. The five A
windows are distinct eligible records with the same value for this feature;
actual duplicate exports must first be excluded by N6. Re-encoding an export
never supplies another group vote.

For six group medians `[0,2,4,6,8,10]`, center is the midpoint of 4 and 6 = 5.
Sorted deviations are `[1,1,3,3,5,5]`; raw MAD is the midpoint of 3 and 3 = 3.
An outlier in `[0,1,2,3,100]` leaves center 2 and MAD 1. There is no Gaussian
scale factor, clipping or inferred covariance.

## Missing support and exact gate boundaries

| Feature evidence | Expected support |
| --- | --- |
| Four groups `[0,1,2,3]`, all available | Center 1.5, MAD 1; excluded: `insufficient_group_support` |
| Five groups `[0,1,2,3,4]`, all available | Center 2, MAD 1; supported |
| Four contributing out of five selected groups | Availability 4/5 passes; count 4 still fails group support |
| Three contributing out of five | Availability 3/5; both group support and availability fail |
| Eight contributing out of ten | Availability 8/10 = 4/5; count and availability pass |
| Six contributing out of ten | Count passes; availability 6/10 = 3/5 fails |
| Five groups all equal 2 | Center 2, MAD 0; excluded: `zero_dispersion`, weight 0 |
| One observed value 2 among five groups | Center 2, MAD 0; group support, availability and zero dispersion all fail |
| No observed values among five selected groups | Center/MAD null; availability 0/5; missing, group support and availability reasons |
| No selected groups | Center/MAD null; availability `{numerator:0,denominator:0,value:null}`; same three reasons |

Keep diagnostic statistics for unsupported nonempty evidence. Missing does not
mean zero, and failure of one gate does not hide another reason. Compare count
fractions exactly by cross-multiplication; the rendered 0.8 is not the threshold
comparison oracle.

A full candidate with five training groups and 17 supported features is
provisional. Sixteen supported features gives coverage 16/22 <3/4 and fails
both active-feature reasons. With four groups, no feature can satisfy the five-group
minimum, so active count is zero and all three candidate gates fail. Even a
supported provisional candidate is not trusted or match-eligible in this release.

## Binary64 rounding and failure cases

The vectors retain both expected numeric values and exact `float.hex()` forms.
Use an exact rational midpoint/difference followed by one nearest-even binary64
rounding. Computed zero is positive zero.

- The median of two maximum finite positive floats is that same maximum, even
  though their naive sum overflows. The negative counterpart is also finite.
- The median of two identical smallest subnormal floats is that subnormal.
  Separately halving the operands first would incorrectly erase it.
- The midpoint of zero and the smallest positive subnormal rounds to zero;
  this release rejects that nonzero-to-zero underflow. The exact midpoint of
  the positive and negative smallest subnormal is genuinely zero and is allowed.
- The midpoint between 1.0 and its next representable float rounds to 1.0.
  The next adjacent pair rounds to its even upper endpoint. Do not use decimal
  display equality as an oracle for these ties.
- For group medians `[-max,-max,+max]`, center is `-max`, but the last absolute
  deviation cannot fit binary64. The whole build fails, even though MAD's rank
  might otherwise select zero. No partial candidate/report is accepted.
- A median helper called with no values fails. A feature with no observed values
  handles absence explicitly and never calls that helper on an empty list.

Booleans, NaN, infinities and strings in numeric positions are invalid, not missing
feature values. Input map null denotes an explicitly unavailable feature only.

## Held-out and synthetic evidence

Training group values `[0,1,2,3,4]` give center 2/MAD 1 whether validation and
final-test values are 1000/-1000 or replaced with maximum finite negative/positive
floats. Fit-time extraction must not access those held-out values. Full N6 input
validation and changed source receipts may still change snapshot identity.

The frozen N6 `reviewed-roles` corpus has three entries, one per role, all synthetic.
Expected N7 selection: 3 retained, 0 selected entries, 0 selected groups; values
are null for every input. Only its training response creates a candidate key,
which remains rejected with 0 active features. The held-out entries do not add
candidates. The N6 `missing` and baseline-only datasets produce no response
candidates; they remain valid rejected builds with their original inventory.

For an otherwise selectable group/partition with two different labels, exclude
all its otherwise selectable entries as `mixed_group_labels`. An unverified or
held-out label must not poison selectable training evidence. Changing a partition
never merges source support; identical labels from different partitions remain
separate candidates. Preserve entry, group and missing-feature denominators.

## Lifecycle examples

An explicit policy-only create produces a `created` draft with no source report,
empty inputs/profiles and zero counts. Building it uses fresh N6 inspection; an
otherwise supported candidate produces a `provisional` snapshot, while a
synthetic-only input yields a valid `rejected` snapshot. Rejected drafts may be
rebuilt; they cannot be staled/superseded before acquiring a source report.

A provisional snapshot may be marked stale with an exact-parent review; its
policy/source/statistics remain byte-for-byte equivalent after canonicalization,
while lifecycle and snapshot ID change. Missing review or a mismatched subject
fails. A stale snapshot may be rejected, or superseded by a different fully
validated provisional replacement. A rejected/stale replacement fails; superseded
history is terminal. A review for one parent or replacement cannot be reused for
a different identity. No transition overwrites its parent.

`trusted` is not an accepted state. Promotion, supplying a trusted state string,
or presenting an opaque evidence hash cannot bypass the absent held-out validation
method. Current lifecycle reviews withdraw/replace candidates conservatively;
they authenticate neither a person nor real acquisition truth.

## Independent checks

The design-vector tests use a bounded, high-precision Decimal reference oracle
and literal expected results; they import no N7 statistics implementation.
Production is specified to use bounded rational binary64 arithmetic. The policy
identity and design-vector file are pinned separately. Review a changed policy
or expected vector explicitly; do not derive expected results from future builder
output to make a failing check pass. These design vectors are not additional
production schema roots or a runtime fixture-release update mechanism.
