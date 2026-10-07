# N1 measurement inspection and migration readiness

[`measurement_inspection.py`](../../src/latency_fingerprinting/measurement_inspection.py)
compares the unchanged P0 bundle ingestion path with the registered N1
[gauge](GAUGE_AGGREGATION.md) and [counter](COUNTER_AGGREGATION.md) summaries.
The result is a deterministic offline diagnostic report, not `observation-v2`
and not matcher input. It performs no normalization, artifact migration or writes.

## Command and Python APIs

```bash
latency-fingerprint inspect-measurements path/to/bundle.tar \
  --context path/to/context.json \
  --phase degraded \
  --comparison-case-id example-001
```

A sanitized local example:

```bash
.venv/bin/python -m latency_fingerprinting inspect-measurements \
  tests/data/pixelated_bundle/valid-v2 \
  --context tests/data/pixelated_bundle/context-v2.json \
  --phase degraded --comparison-case-id controlled-case-001
```

`inspect_measurements(bundle_path, *, context, phase, comparison_case_id)` returns
a report dictionary. `render_measurement_inspection(report)` renders sorted,
indented UTF-8 JSON with a trailing newline and rejects non-finite output.
`inspect_frozen_window(window)` assesses a validated P0 `ObservationWindow`
without loading or inventing raw samples. There is no aggregate-only CLI in N1.

The report version is `measurement-inspection-v1`. It is intentionally excluded
from the production root-model validator and schema exporter. `validate`, response
building and matching continue to accept their existing production contracts.

## Report content

All 23 reviewed P0 features map explicitly to the 31 canonical N1 definitions.
The mapping is checked against the semantic inventory; RSS aliases explicitly
change `_rss_mb` to `_rss_mib` while retaining the already binary MiB meaning.

Each feature includes P0 aggregate/value/unit/count or a missing/rejected state,
a migration classification, and its proposed outputs. Each output includes:

- the full registered definition, version, source fields, units and policies;
- the new value and complete auditable series summary when raw input is supplied;
- usable row IDs, counts, accepted counter intervals, cadence, duration and coverage;
- missing/rejection reasons, warnings and migration notes;
- `frozenAggregateClassification`, separately assessing the existing P0 scalar.

The root identifies raw-bundle versus frozen-window input, phase, fixed registry
version, optional bundle checksum, P0 ingestion status and P0 window validity.
`matcherInput=false` and the notice make the diagnostic boundary explicit.
An accepted ingestion is not a claim that the P0 window is valid or matcher-ready.

## Classifications

| Classification | Meaning |
| --- | --- |
| `identity_safe` | Compatible gauge quantity, units and aggregation; raw comparisons also require equal usable counts and value with no rejected evidence |
| `recomputable_from_raw` | Raw evidence computes a value that cannot safely be carried over as the existing P0 scalar; includes all counter rates and totals |
| `not_recoverable_from_aggregate` | No valid conversion can reconstruct the output from the P0 aggregate, or supplied raw evidence has no interval/value to publish |
| `unsupported_source` | The source has no supplied rows, is unavailable/inactive, or declares the measurement unsupported |
| `rejected` | N1 rejects the source series or its arithmetic and publishes no value |

Feature-level classification uses the most restrictive output classification in
this order: rejected, unsupported, not recoverable, recomputable, identity safe.
Supported gauges can retain their scalar from frozen windows only when their
unit, primary aggregation and non-negative domain agree with the definition.
This does not recover source support, cadence, intervals or coverage; frozen-only
reports leave all summaries null. Gauges contradicted by raw evidence are not
marked safe conversions of their frozen aggregate.

Every cumulative-counter output has `frozenAggregateClassification` set to
`not_recoverable_from_aggregate`. P0 median deltas lack cumulative rows, elapsed
interval durations and continuity. Rate and total outputs stay separate, including
freezes/min and audit-only totals; no new matcher features are adopted.

The sanitized bundle demonstrates 60 frames/s from five-second deltas of 300.
A test changes that existing capture to equivalent one-second deltas of 60:
P0's median delta changes, while N1's time-weighted rate stays 60 frames/s.
Totals remain 600 over ten seconds versus 120 over two seconds.

## Source boundaries and privacy

Both paths reuse existing bounded directory/TAR, JSON, CSV and envelope validation.
Each reads independently; successful P0 ingestion must have the same bundle
checksum as N1 extraction or inspection fails. Existing adapters are unchanged.
N1 envelope/clock/identity failures fail closed before comparison and CLI stdout
remains empty on failure. A P0-only rejection, such as exported packet-loss delta
inconsistency, leaves N1 raw summaries available and marks all P0 values unavailable.
P0 numeric rejection strings are replaced with fixed notices because legacy
errors can echo malformed producer content.

Reports omit context identities, run/session/workload IDs, comparison-case IDs,
absolute paths, effective settings, raw cell contents and wall-clock timestamps.
Only metric names, registered metadata, numeric evidence, source row ordinals,
safe reasons and the content checksum are exposed. P0 validity reasons are not
echoed; validity itself is retained. Unexpected free-form units/aggregation labels
from frozen windows are masked. Legacy wall-clock-derived elapsed provenance
warnings remain explicit; these are not verified monotonic-clock measurements.

The renderer generates no current timestamps or random identifiers. Directory
and TAR reports are byte-identical for equal files. A sanitized report SHA-256 is
pinned in [`test_inspection.py`](../../tests/measurement/test_inspection.py) and
runs in both existing Python 3.11 and 3.13 CI suites. Local verification uses
Python 3.13; cross-version execution is left to CI.

[Step 8](ARITHMETIC_FIXTURES.md) implements focused inspectable fixture series.
[N2 observation-v2 adoption](OBSERVATION_V2_ADOPTION.md) now uses the raw extraction
API separately; this diagnostic report remains outside the record/matcher input
contracts. V2 feature, normalization and matcher semantics still require review.
