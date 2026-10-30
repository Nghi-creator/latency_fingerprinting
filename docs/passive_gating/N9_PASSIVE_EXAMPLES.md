# Passive gate design examples

These are synthetic arithmetic and state-machine design operands, not recorded
experiments or a runtime acceptance corpus. The
[vectors](N9_DESIGN_VECTORS.json) retain literal expectations; the independent
Decimal oracle is in `tests/passive_gating/test_design.py`. It imports no
N9 production module and does not regenerate expectations from actual results.
The [policy](N9_PASSIVE_POLICY_SPEC.json) and vector bytes have separate release
pins in that test. A changed policy/vector requires explicit review and new pins.

## Baseline and threshold arithmetic

Five independent healthy training groups, each with median 60 FPS, produce center
60 FPS and raw MAD zero. This is a usable provisional baseline: zero spread is
not a reason to divide by a fabricated epsilon. Five zero-FPS group values produce
a rejected zero center. Four contributing groups still fail minimum support even
when availability is 4/5; eight of ten passes both gates, seven of ten fails
availability. One group with nine windows has the same vote as each one-window
group. Metadata-eligible groups missing the selected FPS metric remain in the
denominator; N6-invalid or otherwise metadata-excluded evidence is retained with
its exclusion reasons and does not enter this denominator.

For center 60 FPS, exactly 48 FPS is low, exactly 54 FPS is recovered, and the
open interval between them is the hysteresis band. Adjacent binary64 values on
either side of each threshold have literal expectations. With center 1.0,
binary64 `0.8` is slightly greater than exact 4/5, so it is in the band even
though its rounded relative FPS displays as 0.8. Display ratios cannot choose
the class. Median arithmetic avoids intermediate overflow and rejects a nonzero
exact midpoint or ratio that rounds to zero.

## Timeline

With a usable 60-FPS baseline and contiguous two-second windows at 40 FPS:

| End, ms | Bad windows / credited ms | State | Recommendation |
| --- | --- | --- | --- |
| 2000 | 1 / 2000 | pending_degradation | observe |
| 4000 | 2 / 4000 | pending_degradation | observe |
| 6000 | 3 / 6000 | degraded | probe proposal |

A repeated first window does not count again. A renamed copy of its interval is
out of order. A gap resets persistence and credits only the new window. An overlap
breaks the streak and exposes unknown. Three one-second lows fail the duration
gate; one ten-second low fails the count gate. Two recovered two-second windows
at 54 FPS clear the latch; one long recovered window does not.

A tick at 10999 ms retains the 6000-ms degradation, with no proposal. At 11000 ms
the freshness equality expires it to unknown. A window crossing that stale
barrier cannot restore earlier timing credit. An older tick invalidates the
stream. A generation/context/clock reset is terminal; later old windows cannot
restore it. A new replay requires an explicitly declared stream.

Continued qualifying lows before 36000 ms remain in cooldown after the 6000-ms
proposal. A new low ending exactly at 36000 ms permits the next proposal. After
three proposals, even otherwise qualifying lows return proposal_budget_exhausted.
Ticks never mint proposals. The ledger survives missing evidence and recovery;
its scope is one immutable replay, not a durable live action budget.

## Missing evidence and input boundaries

An unlabelled passive held-out query may be used when its only N6 exclusion is
label_unverified. A query's label never changes the decision. Unverified split,
independence or binding, synthetic acquisition and engineering/training input
remain blocking. Source overlap with any contributing baseline group blocks use.
Missing, response, unsupported, incomplete or undersampled inputs clear the
detector; none establish health. Response relief windows are never a healthy
baseline or passive query substitute.

The abstract replay operands use short synthetic keys and eligibility flags to
isolate transitions. They are not serialized PassiveReplay records and cannot
establish real N6 bindings or authenticate a generation. Typed model tests exercise
representable histories using original N2 windows and retained N6 declarations,
and reject N2-invalid combinations rather than weakening the upstream contract.
Complete retained-root reconstruction and [linked source verification](N9_COMMANDS.md)
are implemented as separate boundaries. Source-binding tests use artificial
on-disk N2/N6 records, not measured acquisitions. A separate
[frozen runtime corpus](N9_FIXTURES.md) retains complete roots and source bytes.
Boolean/fractional/out-of-range times, unsafe arithmetic and excessive histories
fail the operation without a truncated result. No live engine changes occur.
