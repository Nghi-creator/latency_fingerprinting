# N1 implementation progress

**Updated:** 2026-10-06
**Completed boundary:** Step 0 baseline protection and Step 1 semantic inventory.
**Next boundary:** Step 2 strict registry models. N1 is not complete.

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

## Verification after the milestone

The full suite passed with **374 tests and 88.20% coverage including branches**.
Ruff lint and formatting passed. The three P0 schema checks, synthetic fixture
drift check, run-001 seed check and exact run-002 byte reproduction all passed
again. All local Markdown links in the new measurement documents resolve.
Verification ran locally on Python 3.13.13; Python 3.11 CI has not been run here.

Changes are limited to this progress record, the semantic inventory, five inventory
tests and plan status/navigation. No files under `src/`, `schemas/`, `fixtures/` or
`experiments/` were modified. The P0 immutability gate stays open in the plan because
it must continue to hold throughout later N1 implementation steps.

P0 production code and artifacts are unchanged. No live probe, remediation or
runtime instrumentation was executed. Proposed v2 features are not matcher inputs;
the separate observation-v2 adoption slice remains required.
