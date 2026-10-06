# N1 implementation progress

**Updated:** 2026-10-06
**Completed boundary:** Steps 0–2: baseline, inventory and strict registry models.
**Next boundary:** Step 3 canonical registry, schema/export and drift checks. N1 is not complete.

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
compatibility and exclusion of configured settings. No runtime registry is added
in this milestone; its models and canonical builder remain Steps 2 and 3.

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

P0 production behavior and artifacts are unchanged. No live probe, remediation or
runtime instrumentation was executed. Proposed v2 features are not matcher inputs;
the separate observation-v2 adoption slice remains required.
