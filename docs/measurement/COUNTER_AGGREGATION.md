# N1 cumulative-counter derivation

Counter summaries validate interval endpoints against the ordered usable source
rows. A shared row must retain one elapsed timestamp, each interval connects
adjacent usable rows, and wrapped transitions must appear in the reset audit.
Indexed row lookups keep this evidence validation linear in the number of rows.

[`aggregate_counter`](../../src/latency_fingerprinting/measurement/aggregation.py)
is a pure Python API alongside [gauge aggregation](GAUGE_AGGREGATION.md). It
accepts a registered cumulative-counter definition, an immutable tuple of
validated samples, finite elapsed window bounds and explicit registry/provenance
metadata. It performs no file I/O, normalization or matcher adoption.

## Usage

After [extracting a bundle](SAMPLE_EXTRACTION.md):

```python
from latency_fingerprinting.measurement.aggregation import aggregate_counter
from latency_fingerprinting.measurement.metric_registry import get_metric_definition

series = bundle.series["client.frames_decoded_rate_fps"]
summary = aggregate_counter(
    get_metric_definition(series.metric_name),
    series.samples,
    window_start_ms=bundle.elapsed_start_ms,
    window_end_ms=bundle.elapsed_end_ms,
    registry_version=bundle.registry_version,
    warnings=bundle.warnings,
    source_missing_reason=series.missing_reason,
)
print(summary.model_dump_json(by_alias=True))
```

Use a separate total definition such as `client.frames_decoded_window_total` to
publish a total in its registered unit. Rate/total definitions share the raw
sample tuple and produce equal accepted interval evidence under equal policies.
Only the registered primary aggregate is published; no interval-rate P95 is added.
Wrong kinds, mutable inputs and invalid window bounds raise `ValueError`.

## Accepted intervals and units

For adjacent usable source samples, delta is current minus previous cumulative
value and duration is current minus previous elapsed ms. Every accepted
[`CounterInterval`](../../src/latency_fingerprinting/models/measurement.py) retains
both CSV row identities, elapsed endpoints, positive duration, non-negative delta,
finite rate and an explicit wrap flag. Zero delta is legitimate activity evidence
and produces zero rate and total.

Window total is `math.fsum` of accepted deltas. The time-weighted mean rate is
accepted total divided by accepted duration, with the registered time-unit scale:

| Quantity | Total unit | Interval/mean rate unit | Scale per elapsed ms |
| --- | --- | --- | --- |
| Frame count | frames | frames/s | 1000 |
| Freeze count | freezes | freezes/min | 60000 |
| Freeze duration | ms | ms/s | 1000 |
| Packet loss | packets | packets/s | 1000 |

For deltas 100 and 100 over durations one and four seconds, the rate is 40/s,
not the unweighted interval-rate average of 62.5/s. One-second increments of 60
and five-second increments of 300 both produce 60/s. Window totals still reflect
actual observed activity and duration.

Ratio arithmetic uses floating mantissas/exponents to avoid unnecessary
intermediate overflow or underflow. Positive rates that cannot be represented
are rejected rather than rounded to fabricated zero. Subtraction of validated
non-negative finite counters is bounded by the finite range; explicit guards
remain in place. Interval-rate, total-sum or final-rate overflow rejects the whole
series, clearing partial aggregates, intervals and observed duration. Raw usable
row identities and rejection reasons remain available when unambiguous.

## Gaps, resets and chronology

Unavailable, missing, malformed, negative or out-of-width values break continuity.
The first usable sample after a gap establishes a baseline; no delta crosses it.
`gapSourceRows` retains the unusable row identities, and reasons remain explicit.
The registered strict missing policy rejects the whole series when any unusable
row is present; canonical N1 uses `break_counter_continuity`.

A decreasing usable counter records its current row in `resetSourceRows`:

- `reject_segment` rejects that transition and starts a new baseline at the
  current sample. Earlier and later valid intervals remain available.
- `reject_series` suppresses all aggregates and accepted intervals. Later resets
  and gaps are still recorded.
- `allow_declared_wraparound` applies modular subtraction only with an explicitly
  declared 1–64 bit width and integral values inside that width. Wrapped pairs
  carry `wrapped=true` and a warning. No canonical N1 definition declares this policy.

Finite float input cannot restore precision already lost by a producer. Large
integer counters must be exactly representable as supplied; rounded values at or
above the declared modulus are rejected. Wraparound does not infer multiple
unobserved cycles or distinguish an undeclared device reset.

Duplicate row identities, non-increasing elapsed/UTC clocks and out-of-window
samples reject the entire sequence; source chronology is never sorted or repaired.
Ambiguous duplicate row identities also clear row-level audit lists, retaining
reasons and a warning. Cadence summaries use source timestamps; advisory cadence
warnings do not independently reject usable evidence.

## Coverage and result states

Observed duration sums accepted intervals only. Coverage is observed duration
divided by the declared window duration; rounding at the boundary is clamped.
Neither a total nor a rate is extrapolated over unsupported time. Gaps and rejected
reset transitions therefore reduce coverage.

`MetricSeriesSummary` extends the [gauge summary contract](GAUGE_AGGREGATION.md)
with immutable counter intervals, interval rate unit, reset rows and gap rows.
Validation checks interval counts, ordered in-window usable endpoints, units,
interval rates, reconstructed duration and reconstructed published aggregate.

- `complete`: full coverage, numeric aggregate, no missing/rejected evidence.
- `incomplete`: numeric aggregate over partial evidence, or usable samples without
  any adjacent pair. A single sample has `value=None`, zero intervals and coverage.
- `missing`: no usable or rejected evidence and no aggregate.
- `rejected`: chronology, strict policy, invalid-only/reset-only evidence or
  arithmetic prevents publication. No partial aggregate is published.

The extractor's wall-clock provenance warnings remain explicit. These results
are offline diagnostic summaries, not verified monotonic-clock measurements.

[`test_counter_aggregation.py`](../../tests/measurement/test_counter_aggregation.py)
covers unit conversion, cadence, time weighting, all policies, gaps/resets,
finite arithmetic, interval contracts, no I/O, immutability, JSON round trips,
sanitized bundles and deterministic offset/scaling/splitting/gap invariants.
P0 models, configuration, aggregation and match outputs remain unchanged.
[Step 7](MEASUREMENT_INSPECTION.md) implements the migration-readiness report
and inspection CLI.
