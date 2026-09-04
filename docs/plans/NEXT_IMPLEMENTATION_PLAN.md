# Next Slice Implementation Plan: Metric Semantics Foundation

**Slice ID:** N1  
**Status:** Ready for implementation  
**Updated:** 2026-09-04  
**Parent roadmap:** [`FULL_IMPLEMENTATION_PLAN.md`](FULL_IMPLEMENTATION_PLAN.md)  
**Starting point:** P0 is complete, hardened, and frozen as
`observation-v1`, `fingerprint-v1`, and `match-result-v1`.

## Slice outcome

Build the first post-P0 measurement foundation: a versioned, machine-readable
metric registry and deterministic aggregation engine that gives every current
feature one explicit meaning.

The slice must prove, using existing Pixelated bundle data, that gauges and
cumulative counters can be converted into auditable summaries without mixing
sampling cadence, interval deltas, rates, and window totals.

```text
raw timestamped bundle samples
-> registered metric definition
-> strict sample parsing
-> gauge or counter-specific derivation
-> auditable metric-series summary
-> deterministic registry and migration report
```

This slice runs beside P0 in shadow/offline mode. It does not change P0 matcher
results or claim improved diagnosis.

## Why this is the next slice

P0 proves the software path, but several current counter features are medians
of per-sample interval deltas. Their values depend on capture cadence. A median
of `60 frames per one-second interval` and a median of `300 frames per
five-second interval` describe similar throughput with incompatible numbers.

Before adding more fingerprints, live probes, control, ML, or confidence, the
engine needs to answer these questions mechanically:

- What physical quantity does each feature represent?
- Is its raw source a gauge, event, or cumulative counter?
- Which clock and sampling cadence apply?
- Which transformation produces its analytical value?
- What happens across gaps, resets, unavailable rows, and irregular cadence?
- Which feature-registry version governs the result?

If these meanings remain implicit, additional data makes the fingerprint
library larger without making it scientifically comparable.

## Scope

This slice includes:

- a strict `MetricDefinition`/`MetricRegistry` contract;
- a checked-in canonical registry covering every current P0 feature;
- explicit gauge, cumulative-counter, interval-delta, rate, and window-total
  semantics;
- deterministic aggregation over timestamped samples;
- counter gap/reset handling with no silent bridging or zero imputation;
- per-series provenance, cadence, coverage, and rejection metadata;
- a P0-to-registry mapping and migration-readiness report;
- shadow evaluation against existing sanitized v2 Pixelated bundles;
- generated schema/drift checks, unit tests, integration tests, CLI inspection,
  and documentation.

## Explicit non-goals

Do not include any of the following in N1:

- changing existing P0 schema files or artifact bytes;
- making `observation-v2`, `fingerprint-v2`, or `match-result-v2` production
  roots;
- changing P0 feature names in persisted v1 records;
- changing current matcher scores, thresholds, decisions, or fixtures;
- live stream mutation, probe scheduling, remediation, or rollback;
- fingerprint candidate promotion or a persistent fingerprint database;
- new Pixelated runtime instrumentation;
- GPU/hardware encoder claims;
- statistical calibration, covariance distance, mixed-cause inference, ML, or
  RL;
- a daemon, HTTP service, dashboard, or hosted component.

Those belong to later slices in the full roadmap.

## Frozen design decisions for N1

These decisions prevent implementation from reopening the slice boundary.

### 1. P0 remains immutable

The following remain byte-compatible and continue to pass their existing
tests:

- `observation-v1.schema.json`;
- `fingerprint-v1.schema.json`;
- `match-result-v1.schema.json`;
- synthetic fixtures;
- controlled-run 001/002 artifacts;
- run-002 byte-for-byte matcher reproduction.

N1 may read P0 records and report how their features map to the new registry,
but it must not rewrite them.

### 2. Registry version is separate from root schema version

Use a stable registry identifier such as:

```text
latency-metrics-v2.0.0
```

The exact identifier is frozen in code and the checked-in registry artifact.
It is not inferred from the package version. A future observation-v2 record
will carry this identifier explicitly.

### 3. Metric names encode physical meaning

Do not reuse a name when its meaning changes. In particular, do not silently
reinterpret P0 `*.frames_*_delta` values as rates.

Use distinct proposed v2 names for distinct quantities, for example:

```text
client.frames_decoded_rate_fps
client.frames_decoded_window_total
encoder.frames_out_rate_fps
encoder.frames_out_window_total
client.freeze_count_rate_per_min
client.freeze_count_window_total
```

The naming inventory is reviewed in Step 1 before code is considered stable.

### 4. Aggregation is definition-driven

Adapter modules may extract raw values, availability, timestamps, and source
identity. They must not independently choose metric semantics. The aggregation
engine receives a `MetricDefinition` and applies the registered derivation.

### 5. Missing, rejected, and incomplete remain different

- **Missing:** no usable source values were supplied.
- **Rejected:** values were supplied but violated a declared rule.
- **Incomplete:** some valid data exists, but coverage/gaps limit the result.

No state is converted into a numeric zero.

### 6. Wall-clock and monotonic/elapsed time are not interchangeable

Rate derivation uses strictly increasing elapsed/monotonic time from the source
clock. UTC timestamps remain for correlation and audit. The result records its
clock basis.

### 7. Shadow mode only

N1 outputs registry artifacts and inspection reports. P0 production APIs still
use `P0_FEATURE_CONFIG` and the existing adapter aggregation until a later
observation-v2 slice adopts the registry.

## Mathematical contract

### Gauge series

For usable gauge samples $x_1,\ldots,x_n$, retain at minimum:

$$
n,\quad \min(x),\quad \operatorname{median}(x),\quad P_{95}(x),\quad \max(x)
$$

The registry declares which statistic is the analytical `value`. N1 preserves
the existing nearest-rank P95 definition for deterministic comparison unless a
new method is explicitly versioned.

### Cumulative counters

For consecutive usable counter samples $(t_{i-1},c_{i-1})$ and $(t_i,c_i)$:

$$
\Delta c_i=c_i-c_{i-1}
$$

$$
\Delta t_i=t_i-t_{i-1}
$$

The pair is valid only when:

$$
\Delta t_i>0 \quad\text{and}\quad \Delta c_i\ge 0
$$

The interval rate is:

$$
r_i=\frac{\Delta c_i}{\Delta t_i}
$$

Window total over accepted contiguous intervals is:

$$
C_{window}=\sum_i \Delta c_i
$$

Time-weighted mean rate is:

$$
\bar r=\frac{\sum_i \Delta c_i}{\sum_i \Delta t_i}
$$

Do not use the unweighted mean of interval rates when intervals have different
durations.

### Gaps and resets

An unavailable, missing, malformed, or rejected sample breaks counter
continuity. The first usable sample after a break establishes a new baseline
and does not create a delta across the gap.

If $c_i<c_{i-1}$, record a reset according to the metric's registered reset
policy. N1 does not infer wraparound unless a finite counter width is explicitly
declared.

### Coverage

For a window of duration $T$ and accepted interval duration
$T_{observed}=\sum_i\Delta t_i$:

$$
coverage=\min\left(1,\frac{T_{observed}}{T}\right)
$$

Sample coverage and interval coverage are also retained as counts. Coverage is
diagnostic metadata in N1; thresholds for observation-v2 are deferred.

### Numerical safety

Every input, delta, duration, rate, total, and aggregate must remain finite and
representable. Overflow-range arithmetic becomes structured rejected evidence,
never `inf`, `NaN`, an uncaught `OverflowError`, or a partial result.

## Proposed contracts

Names may be adjusted during Step 1 only; semantics may not remain ambiguous.

### `MetricKind`

Enum values:

- `gauge`;
- `cumulative_counter`;
- `event_count`;
- `derived`.

### `AggregationKind`

Enum values required by N1:

- `median`;
- `nearest_rank_p95`;
- `minimum`;
- `maximum`;
- `window_total`;
- `time_weighted_rate`.

### `MissingDataPolicy`

Enum values required by N1:

- `omit_missing_samples` for gauges;
- `break_counter_continuity` for counters;
- `reject_series_on_any_invalid_sample` only where scientifically necessary.

### `CounterResetPolicy`

Enum values:

- `reject_segment`;
- `reject_series`;
- `allow_declared_wraparound` reserved but unsupported unless width is present.

### `MetricDefinition`

Required fields:

```text
name
semanticVersion
source
rawFields
kind
canonicalUnit
primaryAggregation
availableAggregations
clockBasis
expectedCadenceMs (nullable)
cadenceToleranceRatio (nullable)
missingDataPolicy
counterResetPolicy (nullable)
nonNegative
description
```

Optional future-facing fields may be included only when N1 can validate them:

```text
normalizationEpsilon
clipMin
clipMax
improvementDirection
```

Do not add decorative metadata without a consumer or invariant.

### `MetricRegistry`

Required fields:

```text
schemaVersion
registryVersion
createdAt
definitions
```

Invariants:

- definition names are unique and deterministically ordered;
- `(name, semanticVersion)` identifies one immutable meaning;
- units, kinds, and policies use closed enums where appropriate;
- counter-only fields cannot appear on gauges;
- primary aggregation belongs to available aggregations;
- expected cadence and tolerance are positive finite values;
- all descriptions are non-empty;
- registry serialization is deterministic.

### `MeasurementSample`

Internal immutable dataclass or strict Pydantic model:

```text
elapsedMs
value
available
sourceRow
rejectionReason (nullable)
```

It must represent unavailable/rejected input without inventing a value.

### `MetricSeriesSummary`

Internal result with enough information to reconstruct its output:

```text
metricName
semanticVersion
registryVersion
clockBasis
windowDurationMs
sourceSampleCount
usableSampleCount
acceptedIntervalCount
observedDurationMs
coverage
aggregates
missingReasons
rejectedReasons
warnings
```

`aggregates` contains only registered aggregations. Its numeric values are
finite. Empty series have no aggregate values.

## Proposed repository changes

Keep modules small and separate contracts from algorithms.

```text
docs/
├── measurement/
│   └── METRIC_SEMANTICS_V2.md
└── plans/
    ├── FULL_IMPLEMENTATION_PLAN.md
    └── NEXT_IMPLEMENTATION_PLAN.md

schemas/
└── metric-registry-v1.schema.json

src/latency_fingerprinting/
├── models/
│   └── measurement.py
├── metric_registry.py
├── measurement_aggregation.py
├── measurement_inspection.py
└── adapters/
    └── pixelated_measurement_samples.py

tests/
├── models/
│   └── test_measurement.py
├── test_metric_registry.py
├── test_measurement_aggregation.py
├── test_measurement_inspection.py
└── data/
    └── measurement/
```

Use different names only if the implementation reveals a clearer boundary;
record the reason in the final slice closeout.

## Detailed implementation sequence

## Step 0 — Protect the P0 baseline

Before changing code, run and record:

```bash
.venv/bin/pytest --cov=latency_fingerprinting --cov-branch \
  --cov-report=term-missing --cov-fail-under=85
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m latency_fingerprinting export-schemas \
  --output schemas --check
.venv/bin/python -c \
  "from latency_fingerprinting.synthetic_fixtures import fixture_drift; assert fixture_drift() == {}"
.venv/bin/python experiments/controlled-run-001/record_seed_fingerprint.py --check
```

Reproduce run 002 byte-for-byte as CI currently does. Save the baseline commit
and test count in the slice closeout.

### Tests

- Existing suite passes before work begins.
- Add no baseline snapshots that normalize an already failing state.

### Gate

- [ ] Working baseline is documented.
- [ ] Existing artifacts reproduce exactly.
- [ ] P0 files are not rewritten by later N1 commands.

## Step 1 — Freeze the metric inventory and naming map

Create `docs/measurement/METRIC_SEMANTICS_V2.md` with one row for every current
P0 feature and every proposed v2 output.

Required columns:

```text
P0 feature
raw source file/source kind
raw field(s)
current P0 meaning
problem or ambiguity
proposed v2 feature
physical quantity
canonical unit
metric kind
primary aggregation
clock basis
gap policy
reset policy
normalization status
```

Audit at least:

- browser WebRTC gauges;
- browser cumulative frame/freeze counters;
- engine runtime CPU/RSS gauges;
- encoder cumulative frame counters;
- encoder queue/pipeline gauges;
- configured settings that must remain context rather than metrics.

Decisions that must be explicit:

- whether rates use seconds or minutes;
- whether each total is useful analytically or audit-only;
- whether zero is a valid measurement for every feature;
- whether a P95 of raw gauges and a P95 of interval rates are required;
- whether expected cadence is fixed, advisory, or source-declared;
- which P0 names have no safe automatic migration.

### Tests/review

- A test asserts every current adapter metric appears exactly once in the
  inventory/mapping.
- A test asserts every proposed registered name has one definition.
- No setting such as target FPS is accidentally treated as an observed outcome.

### Gate

- [ ] Every existing feature has a documented physical meaning.
- [ ] Ambiguous P0 counter names map to new names rather than changing meaning.
- [ ] Open semantic decisions are resolved before registry code is frozen.

## Step 2 — Implement strict registry models

Add the enums and contracts described above to
`models/measurement.py`. Follow existing `ContractModel` conventions:

- strict types;
- camelCase aliases;
- unknown fields forbidden;
- non-empty trimmed strings;
- finite numeric values;
- timezone-aware UTC creation time;
- cross-field model validators;
- deterministic order and uniqueness.

Expose only intentional public types from `models/__init__.py`.

### Required negative tests

- duplicate metric names;
- empty definitions;
- unknown enum values;
- non-finite or non-positive cadence;
- boolean accepted as a number;
- primary aggregation absent from the available set;
- reset policy on a gauge;
- cumulative counter without reset policy;
- wraparound policy without counter width;
- non-counter with counter width;
- negative limits where forbidden;
- non-UTC or naive creation timestamp;
- extra fields;
- duplicate JSON keys at the public file boundary.

### Gate

- [ ] Invalid registry states cannot be represented.
- [ ] Model JSON aliases match the documented contract.
- [ ] Direct validation errors do not leak arithmetic exceptions.

## Step 3 — Build the canonical registry

Create `metric_registry.py` containing one immutable canonical registry object
or a deterministic builder from explicit definitions.

Rules:

- definitions are declared in source, not loaded from an unchecked runtime
  plugin;
- output ordering is stable by metric name;
- the registry version is a constant;
- `createdAt` is fixed release metadata, not the current time during rendering;
- every definition has an individual semantic version;
- changing meaning requires a registry-version change and a failing drift test;
- raw source fields may map to more than one derived feature, such as rate and
  total;
- `P0_FEATURE_CONFIG` remains frozen and separate during N1.

Add deterministic export/check support. Either extend `export-schemas` for the
registry schema and add `export-metric-registry`, or provide one cohesive new
command. Prefer:

```bash
latency-fingerprint export-metric-registry --output schemas/metric-registry-v1.json
latency-fingerprint export-metric-registry \
  --output schemas/metric-registry-v1.json --check
```

The command must use atomic replacement for writes and must not rewrite in
`--check` mode.

### Tests

- repeated rendering is byte-identical;
- checked-in artifact equals the canonical builder;
- `--check` detects drift and leaves the file unchanged;
- output validates through `MetricRegistry` and its JSON Schema;
- registry names exactly match the reviewed inventory;
- all referenced raw fields are known to the relevant sanitized fixture schema;
- CLI errors return nonzero without tracebacks.

### Gate

- [ ] Registry and schema artifacts are deterministic and checked in.
- [ ] CI fails on registry drift.
- [ ] Registry version changes cannot occur accidentally.

## Step 4 — Implement finite timestamped sample parsing

Add `pixelated_measurement_samples.py` as an extraction boundary. Reuse the
existing bounded TAR/directory, JSON, CSV, UTF-8, identity, and timestamp
validation. Do not create a second unsafe reader.

Extraction responsibilities:

- select rows for the registered source;
- parse elapsed time and the raw numeric field;
- preserve source row number;
- convert source availability/error state into structured sample state;
- enforce strictly increasing time within each source series;
- preserve gaps rather than dropping them invisibly;
- reject non-finite and overflow-range values;
- return immutable `MeasurementSample` sequences.

Extraction must not calculate rates, totals, percentiles, normalization, or
matcher features.

### Required tests

- valid browser gauge series;
- valid browser counter series;
- valid engine-runtime series;
- valid encoder series;
- header-only/unavailable optional source;
- missing cell;
- malformed number;
- `NaN`, `Infinity`, and overflow-range number;
- negative elapsed time;
- duplicate/decreasing elapsed time;
- unavailable row with a stale numeric cell;
- available row missing a required numeric cell;
- mixed source identities;
- source row numbers preserved in errors.

### Gate

- [ ] Raw extraction is deterministic and contains no aggregation policy.
- [ ] Every rejected source value has a source and reason.
- [ ] Existing bundle security bounds remain in force.

## Step 5 — Implement gauge aggregation

Add pure functions to `measurement_aggregation.py`. They accept a definition,
window bounds, and immutable samples; they perform no file I/O.

For gauges:

- validate that the definition kind is `gauge`;
- select usable samples according to the registered missing policy;
- compute only registered aggregates;
- preserve source/usable counts, coverage inputs, warnings, and rejections;
- use deterministic nearest-rank P95;
- use `math.fsum` or a stable algorithm where a sum is required;
- reject overflow-range results;
- return an empty structured summary when nothing is usable.

### Required tests

- odd/even median;
- one-value series;
- nearest-rank P95 for small and large sequences;
- unordered inputs rejected rather than silently sorted by time;
- duplicate timestamps rejected;
- missing samples under each supported policy;
- invalid samples under each supported policy;
- legitimate zero retained;
- negative value accepted or rejected according to definition;
- finite extremes and overflow behavior;
- deterministic result independent of dictionary insertion order;
- source input remains unmodified.

### Gate

- [ ] Gauge summaries reconstruct from the accepted samples.
- [ ] Missing and rejected input never becomes zero.
- [ ] Aggregate semantics come exclusively from the registry.

## Step 6 — Implement cumulative-counter derivation

For counters:

- validate that the definition kind is `cumulative_counter`;
- derive deltas only between consecutive usable samples in one contiguous
  segment;
- break continuity at every unavailable, missing, or malformed sample;
- reject zero/negative time intervals;
- apply the registered reset policy to negative deltas;
- calculate interval rates from each accepted pair;
- calculate window total and time-weighted mean rate;
- retain accepted interval count and observed duration;
- report resets/gaps and partial coverage;
- never infer wraparound without declared width;
- never extrapolate an incomplete series to the full window.

### Required tests

- constant counter produces zero rate and zero total;
- regular one-second cadence;
- regular five-second cadence produces the same rate for proportionate deltas;
- irregular cadence uses time weighting;
- missing middle row breaks continuity;
- unavailable middle row breaks continuity;
- malformed middle row breaks continuity and records rejection;
- one sample produces no interval aggregate;
- repeated timestamp is rejected;
- counter reset with `reject_segment`;
- counter reset with `reject_series`;
- multiple independent contiguous segments;
- huge finite counters whose subtraction remains representable;
- subtraction/rate/sum overflow becomes rejected evidence;
- source samples remain unmodified.

### Property-style invariants

Use deterministic parametrized/generated cases without adding a dependency
unless justified:

- adding a constant offset to a non-wrapping counter leaves rates/deltas
  unchanged;
- scaling all interval durations and deltas equally leaves rate unchanged;
- splitting one interval into proportional subintervals leaves total and
  time-weighted mean rate unchanged;
- a gap never increases accepted interval count;
- accepted observed duration never exceeds the declared window duration beyond
  the configured timestamp tolerance.

### Gate

- [ ] Counter output is cadence-aware.
- [ ] Gaps and resets cannot fabricate deltas.
- [ ] Rates and totals can be independently reconstructed.

## Step 7 — Produce a P0 migration-readiness report

Add `measurement_inspection.py` to compare current P0 aggregation with the new
registered semantics over an existing bundle. The report is diagnostic and
does not rewrite an observation.

For each current P0 feature report:

```text
P0 feature name
P0 value and aggregation
registered source definition
proposed v2 feature name(s)
new value(s)
sample/interval counts
observed duration and coverage
migration classification
notes/rejections
```

Migration classifications:

- `identity_safe`: same physical meaning and compatible aggregation;
- `recomputable_from_raw`: meaning changes, but raw bundle can derive it;
- `not_recoverable_from_aggregate`: frozen P0 aggregate lacks required raw data;
- `unsupported_source`: source is absent;
- `rejected`: source violates the registered contract.

Expose an offline command such as:

```bash
latency-fingerprint inspect-measurements path/to/bundle.tar \
  --context path/to/context.json \
  --phase degraded \
  --comparison-case-id example-001
```

Output is deterministic JSON. It must clearly state that it is a shadow report,
not `observation-v2` and not matcher input.

### Required tests

- sanitized directory and TAR produce the same report;
- all current P0 features appear in the mapping;
- current counter deltas are classified as recomputable, not identity-safe;
- gauges with unchanged meaning are classified correctly;
- header-only optional sources remain explicit;
- output is byte-identical across repeated runs and Python 3.11/3.13 CI;
- no private identity or absolute path leaks into output;
- input bundle files remain unchanged.

### Gate

- [ ] Existing raw fixtures demonstrate cadence-independent counter rates.
- [ ] No frozen aggregate is falsely declared migratable.
- [ ] The report can drive the following observation-v2 design slice.

## Step 8 — Add focused fixtures

Create small, inspectable fixture series rather than duplicating full bundles
for every arithmetic case.

Minimum cases:

```text
gauge-regular
gauge-missing
counter-1s-cadence
counter-5s-equivalent-cadence
counter-irregular-cadence
counter-gap
counter-reset
counter-overflow
empty-optional-source
```

Every fixture must state whether it is synthetic or sanitized and include its
expected summary. Generation must be deterministic if fixtures are generated.

Do not call a synthetic arithmetic fixture controlled-real evidence.

### Gate

- [ ] Fixture provenance is explicit.
- [ ] Expected values are hand-auditable.
- [ ] Fixture drift is checked without rewriting in CI.

## Step 9 — Integrate quality and CI gates

Extend CI with:

```bash
python -m latency_fingerprinting export-schemas --output schemas --check
latency-fingerprint export-metric-registry \
  --output schemas/metric-registry-v1.json --check
python -c "from latency_fingerprinting.synthetic_fixtures import fixture_drift; assert fixture_drift() == {}"
pytest --cov=latency_fingerprinting --cov-branch \
  --cov-report=term-missing --cov-fail-under=85
ruff check .
ruff format --check .
python -m pip check
```

Keep Python 3.11 and 3.13 coverage. Add exact registry/report reproduction
checks where outputs are checked in.

Security and resource-bound regression coverage must include:

- file and JSON size bounds;
- duplicate keys;
- nesting bounds;
- non-finite/overflow-range numbers;
- maximum sample count;
- deterministic failure on pathological input;
- no raw exception tracebacks through CLI commands.

### Gate

- [ ] Existing 85% branch floor remains enforced.
- [ ] New public modules have meaningful branch coverage.
- [ ] All old P0 gates remain unchanged and green.

## Step 10 — Documentation and slice closeout

Update:

- `README.md` only if new inspection commands are public;
- `docs/ARCHITECTURE.md` with the registry/aggregation shadow path;
- `docs/measurement/METRIC_SEMANTICS_V2.md` as the authoritative inventory;
- local per-module guides for each new important Python file;
- this plan's checklist with verified results;
- a new `docs/measurement/N1_SOFTWARE_CLOSEOUT.md` containing commands, test
  count, coverage, artifacts, limitations, and the exact next boundary.

The closeout must say explicitly:

- P0 artifacts and matcher behavior remain unchanged;
- the registry and aggregation engine are foundations, not diagnosis evidence;
- no live probe or remediation was executed;
- proposed v2 features are not yet production matcher inputs;
- a separate observation-v2 adoption slice is still required.

### Gate

- [ ] Documentation matches implemented names and behavior.
- [ ] All local Markdown links resolve.
- [ ] No completed/planned status is overstated.

## Test matrix

| Area | Unit | Contract/schema | Integration | Regression/security |
|---|---:|---:|---:|---:|
| Registry models | Yes | Yes | Export/check | Duplicate/invalid fields |
| Gauge aggregation | Yes | N/A | Sanitized bundle | Missing/non-finite/overflow |
| Counter derivation | Yes | N/A | Browser + encoder rows | Gap/reset/cadence/overflow |
| Sample extraction | Yes | Internal model | Directory + TAR | Bounds/identity/timestamps |
| Migration report | Yes | Deterministic JSON | P0 comparison | Privacy/no mutation |
| CLI | Focused | Output shape | End to end | Exit codes/no traceback |
| P0 compatibility | Existing suite | Existing schemas | Run 001/002 | Byte reproduction |

## Required acceptance examples

### Equivalent rate under different cadence

One-second samples:

```text
t:       0, 1, 2, 3 seconds
counter: 0, 60, 120, 180
```

Five-second samples:

```text
t:       0, 5, 10, 15 seconds
counter: 0, 300, 600, 900
```

Both must produce:

```text
timeWeightedRate = 60 frames/s
```

Their window totals differ when window duration differs; the report must not
hide that fact.

### Gap does not bridge

```text
t:         0, 1, 2, 3
available: T, F, T, T
counter:  10, -, 130, 190
```

Only the interval from $t=2$ to $t=3$ is accepted. The engine must not produce
a delta from 10 to 130.

### Counter reset remains visible

```text
t:       0, 1, 2, 3
counter: 0, 60, 5, 65
```

The negative transition is a reset. With `reject_segment`, the final 5-to-65
interval may begin a new contiguous segment; with `reject_series`, no aggregate
is emitted. The selected behavior comes from the registry.

## Performance budgets

N1 is offline/shadow work, but establish bounded behavior now:

- time complexity linear in sample count per metric plus the documented
  percentile sort cost;
- no unbounded buffering beyond existing file/sample limits;
- no second full copy of large bundle payloads when avoidable;
- deterministic processing of the maximum supported CSV row count;
- benchmark/report representative and maximum-bound fixtures without turning
  unstable wall-clock timings into hard CI failures;
- document peak memory and runtime observations in closeout.

Optimization must follow profiling. Do not add NumPy or pandas unless the
standard-library implementation demonstrably violates a declared budget.

## Failure behavior

| Failure | Required behavior |
|---|---|
| Unknown metric name | Reject configuration/report request |
| Unsupported raw source | Structured unsupported result |
| No usable samples | Missing summary with no numeric aggregate |
| Malformed sample | Rejected evidence with row/source |
| Counter gap | Break continuity and warn |
| Counter reset | Apply registered policy and record it |
| Duplicate/decreasing time | Reject affected series |
| Non-finite/overflow arithmetic | Reject affected series without traceback |
| Registry drift | Nonzero check command; do not rewrite |
| Incompatible P0 aggregate | `not_recoverable_from_aggregate` |
| Private/sensitive source field | Do not emit it |

## Implementation order and review units

Prefer small reviewable commits/PRs:

1. semantic inventory and frozen names;
2. registry contracts and schema;
3. canonical registry/export/drift;
4. sample extraction;
5. gauge aggregation;
6. counter/rate aggregation;
7. inspection/migration report and CLI;
8. fixtures, full CI, documentation, and closeout.

Do not combine runtime instrumentation or matcher-v2 work into these changes.

## Slice exit checklist

N1 is complete only when every item is true:

- [ ] Every current P0 metric maps to one documented semantic decision.
- [ ] Ambiguous counter meanings have distinct proposed v2 names.
- [ ] Registry models reject invalid cross-field combinations.
- [ ] Canonical registry and JSON Schema are checked in and drift-protected.
- [ ] Gauge summaries are deterministic and auditable.
- [ ] Counter rates are invariant to equivalent sampling cadence.
- [ ] Counter totals, rates, gaps, and resets remain distinguishable.
- [ ] Missing/rejected/incomplete states never become zero.
- [ ] Directory and TAR shadow reports are identical.
- [ ] Migration classification never claims unavailable reconstruction.
- [ ] P0 schemas, fixtures, controlled artifacts, and match output are unchanged.
- [ ] Full tests, branch coverage, Ruff, dependency, schema, fixture, privacy,
      and byte-reproduction gates pass.
- [ ] Architecture, metric semantics, local source guides, and closeout are
      current.

## What follows N1

The following slice should adopt the frozen registry in an additive
observation-v2 contract and add the smallest useful stage-level timing fields.
Only after v2 records and repeated real scenarios exist should work proceed to
calibrated profiles, automatic probe selection, live mutation, remediation, or
autonomous fingerprint promotion.
