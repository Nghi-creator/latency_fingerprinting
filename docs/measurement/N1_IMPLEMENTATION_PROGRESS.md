# N1 implementation progress

**Updated:** 2026-10-06
**Completed boundary:** Steps 0–4: baseline, inventory, models, registry and raw extraction.
**Next boundary:** Step 5 gauge aggregation. N1 is not complete.

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

[`METRIC_SEMANTICS_V2.md`](METRIC_SEMANTICS_V2.md) maps every one of the 23 P0
features exactly once and declares 31 proposed outputs: 15 gauge summaries,
eight counter rates and eight counter totals. Decisions include explicit binary
RSS naming, freeze frequency per minute, freeze duration in ms/s, audit-only
totals, no interval-rate P95, advisory cadence, and deferred v2 normalization.

[`test_metric_inventory.py`](../../tests/measurement/test_metric_inventory.py)
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

[`models/measurement.py`](../../src/latency_fingerprinting/models/measurement.py)
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

[`test_measurement.py`](../../tests/models/test_measurement.py) adds 127 cases,
including malformed and overflow-range inputs, duplicate root/nested JSON keys via
the existing bounded reader, immutable nested sequences, deterministic round trips
and generated JSON Schema shape. The new module has **100% branch-inclusive
coverage** in the full suite. Details and file-ingestion usage are in
[`REGISTRY_MODELS.md`](REGISTRY_MODELS.md).

Final verification on Python 3.13.13: **501 tests passed; 88.85% branch-inclusive
coverage**. Ruff lint/format, dependency validation, P0 schema/fixture drift,
run-001 seed drift and exact run-002 byte reproduction passed. The existing
export-schemas command still checks the three P0 roots only; Step 3 adds the
registry schema and export/check support. Python 3.11 CI has not been run locally.

The only production files changed in Step 2 are the new N1 model module and public
model exports. P0 root models, schemas, synthetic fixtures, controlled artifacts
and matcher implementation were not modified.

## Step 3 deliverables and verification

[`measurement/metric_registry.py`](../../src/latency_fingerprinting/measurement/metric_registry.py)
declares all 31 outputs independently of P0 configuration, with fixed registry
version `latency-metrics-v2.0.0`, per-definition version `1.0.0`, and fixed release
timestamp `2026-10-06T00:00:00Z`. It provides immutable canonical definitions,
registered-name lookup, deterministic rendering, atomic export and bounded
exact-byte drift checks. Old P0 delta names cannot resolve to new rate definitions.

Added artifacts:
[`metric-registry-v1.json`](../../schemas/metric-registry-v1.json) and
[`metric-registry-v1.schema.json`](../../schemas/metric-registry-v1.schema.json).
`export-schemas` includes the registry schema additively; `export-metric-registry`
writes/checks the registry, and `validate` accepts registry roots through the
existing bounded duplicate-safe reader. Export uses the existing atomic schema
writer; check mode creates no directories and performs no writes. Both Python CI
test suites check frozen bytes, with an explicit registry check in the quality job.

[`test_metric_registry.py`](../../tests/measurement/test_metric_registry.py) adds
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
[`CANONICAL_REGISTRY.md`](CANONICAL_REGISTRY.md).

## Step 4 deliverables and verification

[`adapters/pixelated_measurement_samples.py`](../../src/latency_fingerprinting/adapters/pixelated_measurement_samples.py)
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
[`sample model tests`](../../tests/models/test_measurement_samples.py) and
[`extraction tests`](../../tests/pixelated/test_measurement_samples.py). They cover
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
[`SAMPLE_EXTRACTION.md`](SAMPLE_EXTRACTION.md). Gauge aggregation is next; counter
aggregation and the shadow inspection command still remain unimplemented.

P0 production behavior and artifacts are unchanged. No live probe, remediation or
runtime instrumentation was executed. Proposed v2 features are not matcher inputs;
the separate observation-v2 adoption slice remains required.
