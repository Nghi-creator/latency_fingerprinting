# Conditional contrast bounds and worker counter reads

These opt-in engineering APIs supplement the
[median-response experiment](N11_MEDIAN_RESPONSE_EXPERIMENT.md). They emit no
cause diagnosis, accepted profile, calibration or acquisition authority. Existing
N3/N7/N8/N11 methods and prior acquisition results retain their meanings.

## Processing-envelope model

```python
from latency_fingerprinting.evaluation.contrast_bounds import pacing_contrast_bounds

unknown = pacing_contrast_bounds(prior_fps=30, target_fps=24, delay_us=37_500)
```

`n11-pacing-contrast-envelope-v2` reports unavailable when extra-period bounds are
unknown. It never silently substitutes zero overhead. An explicit pair of integer
microsecond bounds also requires a `bounds_declaration_sha256`. The declaration is
unverified provenance, not evidence that these bounds hold or transfer to another
run. Bounds must be independently justified before a prospective protocol uses
them; the model cannot fit them from an observed success or failure.

Conditionally, if delay is `d` and extra period is in `[a, b]`, the modeled rate
range is `[1_000_000/(d+b), 1_000_000/(d+a)]` FPS. All arithmetic is exact rational.
A strict modeled crossing requires the lower rate above the target and the upper
rate below the prior cadence. Equality is insufficient. Output rationals use
`numerator`/`denominator` integers. All existing 24–60 FPS / 20% reduction limits
remain. A conditional model still reports measured contrast/utility unavailable
and acquisition authority false. The original envelope-v1 remains a nominal-only
model; its positive ceiling test is insufficient to qualify a native contrast.

## Guarded counter windows

```python
from latency_fingerprinting.evaluation.contrast_bounds import (
    native_worker_clock_id,
    counter_rate_bounds,
    compare_counter_rate_bounds,
)

clock = native_worker_clock_id({"owner": "owner", "pipeline": "pipeline", "peer": "peer"})
first = dict(clock_id=clock, read_start_ns=0, read_end_ns=0, counter=0)
last = dict(clock_id=clock, read_start_ns=2_000_000_000, read_end_ns=2_000_000_000, counter=54)
window = counter_rate_bounds(first, last)
```

Inputs are closed dictionaries of one declared worker clock, read-start/read-end
nanoseconds and an integer counter. Nonoverlapping read brackets, monotonic time
and nondecreasing counts are required; changed clocks, resets and zero/ambiguous
elapsed spans fail. No clock alignment or parent/worker timestamp subtraction is
performed. Integers are strict, nonnegative and at most `2**63-1`.

For first bracket `[a0,a1]` and last `[b0,b1]`, elapsed time lies in
`[b0-a1, b1-a0]`. With observed counter delta `n`, this experiment declares a fixed
one-buffer boundary sensitivity guard. Its rate range is
`[max(0,n-1)*1e9/(b1-a0), (n+1)*1e9/(b0-a1)]` FPS. The guard is explicit and fixed;
it is not a statistical confidence interval or a bound on arbitrary bursts,
underlying counter staleness, future throughput or component latency. No floating
point rounding can turn equality into separation.

`compare_counter_rate_bounds` additionally requires chronological initial/relief
windows on the same worker clock. Guarded separation requires initial lower rate
strictly above target and strictly above relief upper rate. A tiny positive point
estimate alone is insufficient. A positive result remains conditional finite-window
evidence, not diagnostic utility, stationarity, independent truth or acceptance.

## Reading original native receipts

`inspect_native_counter_reads(acquisition)` accepts the explicit contrast receipt
and extracts only `native-counter-read-brackets-v1` evidence. The clock ID is bound
to the exact three-part controller generation via SHA-256 of compact sorted JSON.
It checks whole recorded phase order, configured/negotiated cadence, read sequence,
clock identity and counter continuity. It rebuilds guarded windows for all phases.

Older receipts with no worker brackets return unavailable. Partial, replayed,
foreign or malformed brackets fail; parent event times and `encoder.updatedAt`
cannot be substituted. The function checks internal consistency only: original
byte hashes, execution authenticity and native rollback/cleanup must be inspected
separately. It cannot promote a receipt to trusted N6 data or a N9 timing source.
Primary source-local N3 rates keep their existing clock/support semantics; this
auxiliary evidence does not replace them or revise an earlier outcome.
