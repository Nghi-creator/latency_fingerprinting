# N1 implementation progress

> Archived milestone record, retained with its original results and limitations.
> The [active N4 plan](../../plans/NEXT_IMPLEMENTATION_PLAN.md) now covers stage-level observability.

**Updated:** 2026-10-06
**Completed boundary:** Steps 0–10 implemented and locally verified; N1 software closed out.
**Next boundary:** N2 additive observation-v2 contract/adoption. Hosted CI verification remains pending.
**Final record:** [N1_SOFTWARE_CLOSEOUT.md](N1_SOFTWARE_CLOSEOUT.md). Historical entries below preserve each milestone boundary.

## Protected P0 baseline

Baseline commit: `b1cd7aa07eebf39629572c22cdd20428a78de826`.
The checkout was clean before this milestone. Local Python is 3.13.13.

Before editing, all of the following passed:

```bash
.venv/bin/pytest --cov=latency_fingerprinting --cov-branch \
  --cov-report=term-missing --cov-fail-under=85
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m latency_fingerprinting export-schemas --output schemas --check
.venv/bin/python -c \
  'from latency_fingerprinting.synthetic_fixtures import fixture_drift; assert fixture_drift() == {}'
.venv/bin/python experiments/controlled-run-001/record_seed_fingerprint.py --check
.venv/bin/python -m pip check
```

Result: **369 tests passed; 88.20% coverage including branches** (85% floor).
Ruff checked formatting for 93 Python files. Schema, synthetic fixture and run-001
seed checks reported no drift; dependency checks found no broken requirements.

Run 002 was reproduced by capturing stdout from
`.venv/bin/python -m latency_fingerprinting match experiments/controlled-run-002/observation.json --fingerprints experiments/controlled-run-001`
and comparing the bytes directly with the frozen
`experiments/controlled-run-002/match-result.json`; the comparison passed.

## Step 1 deliverables

[`METRIC_SEMANTICS_V2.md`](../../measurement/METRIC_SEMANTICS_V2.md) maps every one of the 23 P0
features exactly once and declares 31 proposed outputs: 15 gauge summaries,
eight counter rates and eight counter totals. Decisions include explicit binary
RSS naming, freeze frequency per minute, freeze duration in ms/s, audit-only
totals, no interval-rate P95, advisory cadence, and deferred v2 normalization.

[`test_metric_inventory.py`](../../../tests/measurement/test_metric_inventory.py)
guards adapter/config completeness, unique output declarations, gauge units and
raw fields, cumulative counter inputs, distinct rate/total names, fixture header
compatibility and exclusion of configured settings. Step 1 added no runtime
registry; the subsequent model and canonical registry work is recorded below.

The producer audit exposed wall-clock-derived exported elapsed timestamps,
upstream zero fallbacks, and a null pipeline-delay proxy in the current camera
producer. The inventory preserves these limitations. Increasing exported elapsed
time supports numerical shadow inspection but is not verified monotonic-clock
evidence; future capture instrumentation remains outside N1.

## Step 1 verification

The full suite passed with **374 tests and 88.20% coverage including branches**.
Ruff lint and formatting passed. The three P0 schema checks, synthetic fixture
drift check, run-001 seed check and exact run-002 byte reproduction all passed
again. All local Markdown links in the new measurement documents resolve.
Verification ran locally on Python 3.13.13; Python 3.11 CI has not been run here.

Step 1 changes were limited to this progress record, the semantic inventory, five inventory
tests and plan status/navigation. No files under `src/`, `schemas/`, `fixtures/` or
`experiments/` were modified. The P0 immutability gate stays open in the plan because
it must continue to hold throughout later N1 implementation steps.

## Step 2 deliverables and verification

[`models/measurement.py`](../../../src/latency_fingerprinting/models/measurement.py)
adds strict frozen `MetricDefinition` and `MetricRegistry` contracts with intentional
public exports. It validates required nullable fields, closed enums, source/unit
types, gauge/counter semantics, primary/available aggregation consistency, cadence,
reset/width policies, unique names and UTC release timestamps. Input lists become
immutable tuples in canonical order; epoch timestamp coercion is rejected.

One counter definition has one output unit, so total/rate definitions remain
distinct. Reserved event/derived kinds cannot instantiate unsupported definitions.
Declared wraparound requires an explicit 1–64 bit width; canonical N1 definitions
will continue to use segment rejection without widths. Optional normalization and
clipping metadata is deferred until it has a consumer. Internal sample/summary
contracts remain part of the later extraction/aggregation steps.

[`test_measurement.py`](../../../tests/models/test_measurement.py) adds 127 cases,
including malformed and overflow-range inputs, duplicate root/nested JSON keys via
the existing bounded reader, immutable nested sequences, deterministic round trips
and generated JSON Schema shape. The new module has **100% branch-inclusive
coverage** in the full suite. Details and file-ingestion usage are in
[`REGISTRY_MODELS.md`](../../measurement/REGISTRY_MODELS.md).

Final verification on Python 3.13.13: **501 tests passed; 88.85% branch-inclusive
coverage**. Ruff lint/format, dependency validation, P0 schema/fixture drift,
run-001 seed drift and exact run-002 byte reproduction passed. The existing
export-schemas command still checks the three P0 roots only; Step 3 adds the
registry schema and export/check support. Python 3.11 CI has not been run locally.

The only production files changed in Step 2 are the new N1 model module and public
model exports. P0 root models, schemas, synthetic fixtures, controlled artifacts
and matcher implementation were not modified.

## Step 3 deliverables and verification

[`measurement/metric_registry.py`](../../../src/latency_fingerprinting/measurement/metric_registry.py)
declares all 31 outputs independently of P0 configuration, with fixed registry
version `latency-metrics-v2.0.0`, per-definition version `1.0.0`, and fixed release
timestamp `2026-10-06T00:00:00Z`. It provides immutable canonical definitions,
registered-name lookup, deterministic rendering, atomic export and bounded
exact-byte drift checks. Old P0 delta names cannot resolve to new rate definitions.

Added artifacts:
[`metric-registry-v1.json`](../../../schemas/metric-registry-v1.json) and
[`metric-registry-v1.schema.json`](../../../schemas/metric-registry-v1.schema.json).
`export-schemas` includes the registry schema additively; `export-metric-registry`
writes/checks the registry, and `validate` accepts registry roots through the
existing bounded duplicate-safe reader. Export uses the existing atomic schema
writer; check mode creates no directories and performs no writes. Both Python CI
test suites check frozen bytes, with an explicit registry check in the quality job.

[`test_metric_registry.py`](../../../tests/measurement/test_metric_registry.py) adds
19 cases covering reviewed definitions/policies, fixture source fields, fixed
release version/time and hash, exact artifacts, Pydantic and JSON Schema validation,
atomic export/failure cleanup, CLI errors, duplicate keys and no-write drift checks.
`jsonschema` was added to development dependencies only; no runtime dependency
was added. The registry module has **100% branch-inclusive coverage**.

Final verification on Python 3.13.13: **520 tests passed; 89.06% branch-inclusive
coverage**. Ruff lint/format, dependency checks, all four schema checks, registry
artifact check, P0 fixture/seed drift and exact run-002 reproduction passed.
Python 3.11 execution remains for CI; it was not run locally. All measurement
documentation links resolve and the diff passes whitespace checks.

The three frozen P0 schemas, synthetic fixtures, controlled artifacts, adapter,
normalization configuration and matcher implementation remain unchanged. New CLI
and schema support is additive. Gauge/counter aggregation and shadow bundle reports
remain unimplemented. Usage, release pin and next boundary are in
[`CANONICAL_REGISTRY.md`](../../measurement/CANONICAL_REGISTRY.md).

## Step 4 deliverables and verification

[`adapters/pixelated_measurement_samples.py`](../../../src/latency_fingerprinting/adapters/pixelated_measurement_samples.py)
adds a separate N1 raw extraction API using the existing bounded bundle, JSON,
CSV and envelope validation helpers. It parses each source once, preserves global
CSV row ordinals and UTC/elapsed timestamps, and shares immutable raw sample tuples
between counter rate/total definitions. `MeasurementSample` adds captured UTC time
and distinct missing/rejection reasons to the planned internal sample shape.

Browser missing fields, inactive source rows and unavailable engine rows stay
explicit. Manifest-declared unsupported measurements stay missing even with stale
cells; available engine rows missing required numeric cells become rejected
evidence. Malformed/non-finite/overflow-range/negative cells carry source, row and
reason without echoing malformed content. Invalid clocks or identity/envelope
contracts fail closed before returning samples; timestamp errors retain original
rows. Clock provenance explicitly remains wall-clock-derived, not verified monotonic.

The API computes no rates, deltas, totals, percentiles or normalization. Counter
resets are retained as raw values. Packet loss reads the registered cumulative
field rather than invoking P0's interval-delta consistency policy. P0 ingestion
and its existing validation/aggregation behavior remain unchanged.

Added 83 cases across
[`sample model tests`](../../../tests/models/test_measurement_samples.py) and
[`extraction tests`](../../../tests/pixelated/test_measurement_samples.py). They cover
all source categories, optional sources, original rows, gaps, rejected cells,
stale values, raw resets, immutable/shared samples, one bundle read, directory/TAR
equality, file immutability, clocks/identities and inherited JSON/file/CSV/archive
bounds. The extractor has **100% branch-inclusive coverage** in the full suite.

Final verification on Python 3.13.13: **603 tests passed; 90.16% branch-inclusive
coverage**. Ruff lint/format, dependency checks, all schema/registry drift checks,
P0 fixture/seed drift and exact run-002 reproduction passed. Python 3.11 execution
remains for CI. All local measurement/plan documentation links resolve and the
diff passes whitespace checks. No existing P0 model, adapter implementation,
schema, fixture, controlled artifact or matcher implementation was modified.
Only additive N1 types and extraction exports were added to the model/adapter APIs.

The API and sample/clock failure distinctions are documented in
[`SAMPLE_EXTRACTION.md`](../../measurement/SAMPLE_EXTRACTION.md). Gauge aggregation is next; counter
aggregation and the shadow inspection command still remain unimplemented.

P0 production behavior and artifacts are unchanged. No live probe, remediation or
runtime instrumentation was executed. Proposed v2 features are not matcher inputs;
the separate observation-v2 adoption slice remains required.

## Step 5 deliverables and verification

[`measurement/aggregation.py`](../../../src/latency_fingerprinting/measurement/aggregation.py)
adds pure `aggregate_gauge` for validated registered definitions, explicit window
bounds and immutable samples. It computes only registered minimum, maximum,
stable odd/even median and integer nearest-rank P95. Signed values follow the
definition. Missing and rejected values follow the registered omission/rejection
policy; chronology and overflow failures return structured rejection without
partial aggregates. Empty or missing series never receive fabricated zero values.

`MetricSeriesSummary` and `MetricSeriesStatus` add frozen, finite result contracts
with read-only aggregates, definition/version/unit metadata, source/usable counts,
usable row identities, interval counts, observed duration, coverage, cadence,
reasons and warnings. Cross-field validation prevents inconsistent summaries.
Adjacent usable source rows support diagnostic interval coverage; gaps break
support. Statistics remain sample-based without interpolation or extrapolation.
Single samples retain numeric statistics with zero coverage and incomplete status.
Legacy clock-provenance warnings remain explicit.

[`test_aggregation.py`](../../../tests/measurement/test_aggregation.py) adds **80 cases**
covering order statistics, registered subsets, zeros, signed/finite extremes,
missing policies, gaps, invalid clocks/rows/bounds, arithmetic failure, source
immutability, detached result mappings, serialization, no I/O and sanitized bundle
gauges. The aggregation module has **99% branch-inclusive coverage** and the
measurement models have **100%** in the full suite.

Final verification on Python 3.13.13: **683 tests passed; 90.77% branch-inclusive
coverage**. Ruff lint/format, dependencies, all schema/registry checks, P0
fixture/seed checks and exact run-002 byte reproduction passed. Python 3.11 remains
for CI. Documentation links and whitespace checks pass. No P0 model, adapter,
schema, fixture, controlled artifact, normalization or matcher implementation
changed. New summary types are additive model exports.

The API and coverage/status semantics are documented in
[`GAUGE_AGGREGATION.md`](../../measurement/GAUGE_AGGREGATION.md). Step 6 counter/rate derivation is
next; the shadow inspection CLI and observation-v2 matcher adoption remain future
work. N1 is not yet complete.

## Step 6 deliverables and verification

[`measurement/aggregation.py`](../../../src/latency_fingerprinting/measurement/aggregation.py)
adds pure `aggregate_counter` for registered cumulative-counter definitions and
immutable timestamped samples. It derives deltas/rates only across adjacent usable
source rows, sums accepted deltas and durations with `math.fsum`, and publishes
the registered total or time-weighted rate. Unit conversion preserves frames/s,
freezes/min, ms/s and packets/s. Rates use accepted duration without extrapolating
unsupported parts of the declared window.

Missing, unavailable, malformed, negative and out-of-width samples break
continuity. Registered strict missing policy rejects the series. `reject_segment`
discards the decreasing transition and establishes a new baseline; `reject_series`
suppresses all results while retaining later reset/gap evidence. Explicit finite
integer widths permit declared modular wraparound; no canonical definition enables
it. Invalid chronology rejects the whole source sequence. Duplicate row identities
clear ambiguous row-level audit lists and retain reasons/warnings.

Frozen `CounterInterval` records retain source endpoints, timestamps, durations,
deltas, finite interval rates and wrap flags. `MetricSeriesSummary` adds these
records, their rate unit, reset rows and gap rows. Validation checks unit/count
consistency, ordered usable endpoints and reconstruction of interval rates,
observed duration and the published aggregate. A single counter sample has no
interval aggregate and remains incomplete. Real constant counters retain zero.
Arithmetic overflow or unrepresentable positive rates reject publication without
partial results. Stable ratio arithmetic avoids needless intermediate overflow
and underflow; validated non-negative counter subtraction is inherently bounded.

[`test_counter_aggregation.py`](../../../tests/measurement/test_counter_aggregation.py)
adds **103 cases** covering all registered unit families, equivalent regular and
irregular cadence, policies, gaps/resets, declared width, huge/tiny finite values,
rate/sum arithmetic failures, invalid clocks, source immutability, no I/O,
serialization, interval/summary contracts and sanitized bundles. Deterministic
cases prove offset/scaling/splitting invariance, gap interval-count monotonicity
and accepted duration bounded by the declared window. The combined aggregation
module and measurement model module each have **99% branch-inclusive coverage**.

Final verification on Python 3.13.13: **786 tests passed; 91.16% branch-inclusive
coverage**. Ruff lint/format, dependency checks, schema/registry checks, P0
fixture/seed checks and exact run-002 byte reproduction passed. Local documentation
links and whitespace checks pass. Python 3.11 execution remains for CI. P0 models,
registry artifacts, schemas, fixtures, controlled artifacts, configuration,
adapter implementation and matcher remain unchanged. Counter support is additive
N1 aggregation and internal summary metadata.

API usage, units, evidence and failure policies are documented in
[`COUNTER_AGGREGATION.md`](../../measurement/COUNTER_AGGREGATION.md). Steps 0–6 are verified; Step 7
migration-readiness reporting is next. N1 is not yet complete and proposed v2
features remain outside the P0 matcher.

## Step 7 deliverables and verification

[`measurement_inspection.py`](../../../src/latency_fingerprinting/measurement_inspection.py)
adds deterministic diagnostic comparison of all 23 P0 features with all 31
registered N1 outputs. It reuses the unchanged P0 ingestion and N1 extraction/
aggregation paths, requiring checksum agreement for successful comparisons.
Each output retains its definition, value, complete summary, migration class,
separate frozen-aggregate classification and explanatory notes.

Available compatible gauges are identity-safe, including the binary RSS name
correction. Counter outputs are recomputable only from usable raw intervals;
no P0 median delta is declared sufficient for rates or totals. Missing interval
baselines, absent/inactive/unsupported sources, and rejected series remain
explicit. Frozen-window inspection permits compatible gauge scalars while leaving
all summaries null and never reconstructing counter values or coverage.

The additive `inspect-measurements` CLI emits `measurement-inspection-v1` JSON
with an explicit shadow/non-matcher notice. It is intentionally excluded from
production root validation/schema export. It preserves P0 ingestion/validity
status, keeps N1 results on P0-only rejection, and never rewrites observations.
Reports omit source identities, context, private producer values, absolute paths,
effective settings and raw rejection text. Clock-provenance limitations remain
visible. N1 source-contract failures fail closed with no partial JSON.

[`test_inspection.py`](../../../tests/measurement/test_inspection.py) adds **47 cases**
covering inventory-exact mapping, classes, unsupported/header-only sources,
privacy, checksum disagreement, invalid P0 validity, frozen-only/domain rejection,
CLI/API equality, immutable source files and directory/TAR/repeated-process byte
equality. An existing sanitized capture is adapted in a test from five-second
increments of 300 frames to one-second increments of 60: both N1 rates are
60 frames/s while P0 median deltas and observed totals correctly differ.

The report SHA-256 is pinned to
`295f57a6f0e0ab80f64c7323be3cd5fc4e278aac712825f0173955594513c423`.
That same expectation runs in both existing Python CI suites. The inspection
module has **100% branch-inclusive coverage** in the full local suite.

Final verification on Python 3.13.13: **833 tests passed; 91.45% branch-inclusive
coverage**. Ruff lint/format, dependency validation, schema/registry checks,
P0 fixture/seed checks and exact run-002 byte reproduction passed. Documentation
links and whitespace checks pass. Python 3.11 execution remains for CI. P0
adapters, models, configuration, matcher, schemas, fixtures, controlled artifacts
and the canonical registry are unchanged; CLI support is additive.

The report fields, classifications, privacy and usage are documented in
[`MEASUREMENT_INSPECTION.md`](../../measurement/MEASUREMENT_INSPECTION.md). Steps 0–7 are verified;
Step 8 focused fixtures is next. N1 closeout and observation-v2 adoption remain
outstanding.

## Step 8 deliverables and verification

[`fixtures/measurement`](../../../fixtures/measurement/README.md) adds **13 small
synthetic arithmetic fixtures**. They cover the nine required cases: regular and
missing gauges; one-second, equivalent five-second and irregular counters; gaps,
resets, overflow and an empty optional source. Additional cases cover rejected
gauge cells, unavailable/malformed counter rows and a single counter baseline.
Every JSON case declares synthetic provenance, `controlledReal=false`, fixed
registry version, explicit sample/window inputs, a numerical explanation and
expected numerical/audit summary projections.

The one-second and five-second cases cover the same ten seconds and the same
cumulative activity: both produce 600 frames and 60 frames/s. Irregular cadence
produces the hand-calculated 40 frames/s rather than 62.5. Missing/rejected cells
and counter gaps retain reasons and exact accepted pairs. Reset coverage is 2/3;
overflow produces no partial aggregate. Single/empty sources never fabricate zero.

[`fixture_cases.py`](../../../tests/measurement/fixture_cases.py) is test support for
independently authored expectations, deterministic rendering and read-only
exact-byte drift checks. It imports no aggregation implementation and supplies
expected arithmetic explicitly. No ambient timestamps, randomness or runtime
data enter generation. Rejection count/prefix checks retain exact meaning while
avoiding platform-specific suffixes from arithmetic exceptions. The README includes
an intentional regeneration command; CI tests never rewrite fixtures.

[`test_fixture_cases.py`](../../../tests/measurement/test_fixture_cases.py) adds
**32 cases** checking every fixture's provenance and expected numerical/audit
summary against validated aggregation. Tests check registry/units/bounds, immutable
sample input, equal-window cadence invariance, deterministic generation independent
of aggregation, no-write drift checks, missing/changed/unexpected JSON files and
format/CRLF byte drift. These checks run in the existing Python CI suites.

Final verification on Python 3.13.13: **865 tests passed; 91.45% branch-inclusive
coverage**. Ruff lint/format, dependency checks, all schema/registry checks, both
P0 and N1 fixture drift checks, run-001 seed check and exact run-002 byte
reproduction passed. Documentation links and whitespace checks pass. Python 3.11
execution remains for CI. No production Python file, existing P0 fixture, schema,
registry artifact, controlled-run artifact or CI workflow was modified in Step 8.
The new fixture README also satisfies the existing repository-wide provenance gate.

The focused-fixture boundary is documented in
[`ARITHMETIC_FIXTURES.md`](../../measurement/ARITHMETIC_FIXTURES.md). Steps 0–8 are verified; Step 9
quality/CI integration and Step 10 software closeout remain. N1 is not yet complete;
these synthetic arithmetic cases do not establish diagnostic or experimental validity.

## Step 9 deliverables and verification

[`.github/workflows/ci.yml`](../../../.github/workflows/ci.yml) now explicitly enforces
branch-inclusive coverage with the unchanged 85% floor in both Python 3.13 and
3.11 jobs. Both jobs run read-only N1 arithmetic fixture drift and pinned
registry/report reproduction. The minimum-version job also checks schemas,
canonical registry and installed dependencies. Existing P0 quality-job artifact,
fixture, seed and exact-match checks remain in place without changing their commands.

[`check_reproduction.py`](../../../tests/measurement/check_reproduction.py) adds a
read-only test-support command that verifies registry artifact/source agreement,
the fixed registry release hash and the sanitized inspection report hash. The
inspection tests share its unchanged report pin. Artifact/pin drift or missing
files produce an error exit code without partial JSON or a traceback. No generator
is invoked and no fixture or artifact is rewritten.

[`test_quality_gates.py`](../../../tests/measurement/test_quality_gates.py) adds
**27 cases** for public inspection CLI failures and reproduction. Root/nested
JSON duplicates, excessive nesting, non-finite/overflow values, pathological
integer literals, invalid UTF-8, context/file/bundle size bounds, CSV field size,
unterminated quotes, duplicate columns, exact configured sample-limit boundaries
and unsafe TAR paths all retain deterministic failure without partial output or
traceback. Invalid numeric metric cells remain structured rejection evidence
with no fabricated value. Reproduction tests cover successful no-write checks,
artifact drift, both pin mismatches and missing files.

Final verification on Python 3.13.13: **892 tests passed; 91.53% branch-inclusive
coverage**. N1 registry, raw extraction and inspection modules retain 100%
branch-inclusive coverage; aggregation and measurement models report 99% rounded.
Ruff lint/format, installed dependencies, schema/registry checks, both fixture
checks and pinned N1 reproduction pass. All five controlled P0 artifacts validate;
run-001 seed check and exact run-002 byte reproduction pass. CI YAML parsing and
both jobs' coverage/reproduction commands were checked. Documentation links and
whitespace checks pass.

No production Python module, P0 artifact, schema, fixture, normalization/matcher
code, registry release or report bytes changed in Step 9. CI additions and test
support preserve the old gates and tighten minimum-version verification.
**Python 3.11 and hosted CI execution remain pending**; the recorded results are
local Python 3.13 results, not a claim of remote job success.

The commands, security/resource regression inventory and local/hosted boundary
are documented in [`QUALITY_GATES.md`](../../measurement/QUALITY_GATES.md). Steps 0–9 are locally
verified and CI gates are configured. Step 10 documentation/software closeout is
next; N1 is not yet marked complete.

## Step 10 software closeout — 2026-10-06

[`N1_SOFTWARE_CLOSEOUT.md`](N1_SOFTWARE_CLOSEOUT.md) consolidates the delivered
registry, extraction, gauge/counter aggregation, migration report, synthetic
fixtures and CI gates. It records final commands, test count, coverage, artifact
pins, P0 preservation, clock/producer/migration/scientific limitations and the
exact next boundary. N1 Steps 0–10 are complete at the locally verified software
boundary; Python 3.11 and hosted CI verification remain separately pending.

The [N1 plan archive](../../plans/archive/N1_METRIC_SEMANTICS_FOUNDATION_PLAN.md)
preserves the completed checklist with that verification qualification.
At this milestone, the plan prepared N2 additive observation-v2 contract/offline
adoption and implementation had not started. That sequence is now preserved in
the [N2 plan archive](../../plans/archive/N2_OBSERVATION_V2_ADOPTION_PLAN.md); the
[archived N3 plan](../../plans/archive/N3_ANALYTICAL_FEATURES_AND_MATCHING_PLAN.md) records the subsequent analytical slice. README, architecture, authoritative inventory, local guides and roadmap
navigation match the delivered N1 boundary. Historical milestone entries remain
intact as records of what was pending at each step.

Final verification on Python 3.13.13 again passes **892 tests and 91.53%
branch-inclusive coverage**. Ruff lint/format, dependencies, all schema/registry
checks, both fixture drift checks, pinned N1 registry/report reproduction,
run-001 seed check and exact run-002 match reproduction pass. All five controlled
P0 artifacts validate. All local Markdown file links across 35 repository documents
resolve; diff whitespace checks pass.

Comparison against the protected baseline
`b1cd7aa07eebf39629572c22cdd20428a78de826` confirms unchanged P0 schemas, reference/
query fixtures, controlled artifacts, root models, adapter/helper implementation,
feature configuration, pipeline and matcher. Step 10 modifies documentation only.
No live probe, remediation, runtime instrumentation, matcher-v2 adoption or new
controlled-real experiment occurred. The software foundation does not establish
diagnosis accuracy or recovery benefit, and proposed v2 features remain outside
production matcher inputs. The separate observation-v2 adoption slice is still
required.
