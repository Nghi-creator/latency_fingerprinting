# N1 gauge aggregation

[`aggregate_gauge`](../../src/latency_fingerprinting/measurement/aggregation.py)
is a pure Python API for registered gauge definitions and immutable timestamped
samples. It performs no file I/O and computes only the definition's registered
median, nearest-rank P95, minimum and maximum. The primary aggregate is exposed
as `summary.value`. [Counter derivation](COUNTER_AGGREGATION.md) is implemented
in Step 6; the [bundle inspection CLI](MEASUREMENT_INSPECTION.md) is implemented
in Step 7.

## Usage

After [extracting a bundle](SAMPLE_EXTRACTION.md), select a registered gauge:

```python
from latency_fingerprinting.measurement.aggregation import aggregate_gauge
from latency_fingerprinting.measurement.metric_registry import get_metric_definition

series = bundle.series["client.received_fps"]
summary = aggregate_gauge(
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

The caller supplies explicit finite, non-negative elapsed bounds with positive
duration, a registry version, and provenance warnings. Counter definitions,
mutable sample lists and invalid bounds raise `ValueError`. Validated sample and
definition constructors are required; Pydantic's unvalidated escape hatches are
not input-validation boundaries.

## Numeric semantics and evidence

Statistics use usable sample values with equal sample weight. Numeric sorting
supports order statistics; source chronology is never repaired by sorting rows.
Duplicate row identities, non-increasing elapsed or UTC timestamps, and samples
outside the declared window reject the whole series with reasons and no aggregates.
Signed values are accepted only when the definition permits them.

Even medians use a stable midpoint calculation that handles same-sign and
opposite-sign finite extremes. P95 selects rank `ceil(0.95 * n)` using integer
arithmetic. Any non-finite arithmetic result or overflow produces a rejected
summary with no partial aggregates. Legitimate zero remains numeric; missing,
unavailable and rejected cells never become zero.

`omit_missing_samples` computes statistics from the remaining usable values and
retains all reasons. `reject_series_on_any_invalid_sample` suppresses aggregates
when any row is missing or rejected. An entirely missing series remains missing
under either policy. Optional absent sources preserve their extractor reason.

[`MetricSeriesSummary`](../../src/latency_fingerprinting/models/measurement.py)
is frozen and contains a read-only aggregate mapping, definition/version/unit
metadata, source and usable counts, usable CSV row identities, accepted interval
count, observed duration, coverage, cadence minimum/median/maximum, reasons and
warnings. Counts, bounds, cadence, coverage and aggregate/status consistency are
validated. Caller-owned dictionaries are detached; JSON uses the existing camelCase
aliases and deterministic aggregate key ordering.

## Coverage and states

Coverage is diagnostic elapsed support: sum the durations between adjacent source
rows only when both are usable, then divide by the declared window duration. A
missing or rejected row breaks support; the algorithm never bridges a gap,
extrapolates to the bounds, interpolates values or time-weights statistics. Advisory
cadence departures produce warnings and do not independently reject samples.
Cadence uses all adjacent source timestamps, including rows with unusable values.

For values `[10, 20, missing, 40, 50]` at one-second spacing over four seconds,
median is 30, usable count is four, accepted intervals are two, and coverage is
0.5. This support measure is not evidence of continuous measurement or verified
monotonic capture. The extractor's wall-clock provenance warning remains explicit.

| Status | Meaning |
| --- | --- |
| `complete` | Numeric aggregates, full interval coverage, no missing/rejected evidence |
| `incomplete` | Numeric aggregates with gaps, rejection evidence or partial coverage |
| `missing` | No usable evidence or rejection evidence; no aggregates |
| `rejected` | Chronology, strict policy, invalid-only evidence or arithmetic prevents aggregation |

A single usable sample produces numeric statistics with zero interval coverage
and `incomplete` status. Rejected summaries can retain usable rows for audit even
though no aggregate is published. Empty summaries expose `value=None`.

[`test_aggregation.py`](../../tests/measurement/test_aggregation.py) covers numeric
ranks/extremes, policies, chronology, gap coverage, immutable contracts,
serialization, no I/O and sanitized bundle gauges. P0 aggregation, normalization
and matcher behavior remain unchanged.
