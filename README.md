# Latency Fingerprinting

[![CI](https://github.com/Nghi-creator/latency_fingerprinting/actions/workflows/ci.yml/badge.svg)](https://github.com/Nghi-creator/latency_fingerprinting/actions/workflows/ci.yml)

This repository contains the detached Python research core, completed P0/N1–N3 foundations and the active N4 stage-observability plan. Pixelated Studio Edition remains the first telemetry-producing testbed and integration target.

## P0 objective

```text
versioned testbed record
-> comparable observation windows
-> response delta
-> normalized response vector
-> stored candidate fingerprints
-> interpretable match or unknown
```

P0 demonstrates that the proposed mechanism is executable. It does not yet prove diagnosis accuracy, recovery benefit or generalization.

## Reading order

1. [`docs/p0/RESEARCH_CONTRACT.md`](docs/p0/RESEARCH_CONTRACT.md) defines the terminology and behavioral invariants.
2. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) defines the Python/TypeScript boundary and repository structure.
3. [`docs/p0/DATA_MODEL_AND_MATCHER.md`](docs/p0/DATA_MODEL_AND_MATCHER.md) defines records, normalization and matching.
4. [`docs/p0/PIXELATED_ADAPTER_AND_EXPERIMENT.md`](docs/p0/PIXELATED_ADAPTER_AND_EXPERIMENT.md) defines real-data ingestion and the first controlled run.
5. [Archived P0 software closeout](docs/archive/p0/P0_SOFTWARE_CLOSEOUT.md) records verified software and controlled-real evidence plus the remaining limitations.
6. [`experiments/CONTROLLED_RUN_PROCESSING.md`](experiments/CONTROLLED_RUN_PROCESSING.md) is the reusable post-capture command and evidence checklist for controlled runs.
7. [N4 stage-level observability](docs/plans/NEXT_IMPLEMENTATION_PLAN.md) is the active implementation plan; Steps 0–6 and Step 7 synthetic integration are complete locally; real capture/overhead acceptance remains pending.
8. [`docs/plans/FULL_IMPLEMENTATION_PLAN.md`](docs/plans/FULL_IMPLEMENTATION_PLAN.md) is the complete roadmap through final engine delivery and evaluation.

## Development setup

The local development environment uses Python 3.13 while the package supports Python 3.11 and newer.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

The synthetic analytical path, offline CLI and Pixelated bundle adapter are
implemented and regression-tested. Two controlled-real runs now exercise the
same end-to-end path: run 001 establishes a seed and run 002 independently
repeats the experiment as a held-out query.

```bash
latency-fingerprint validate fixtures/query_cases/similar_network/observation.json
latency-fingerprint export-schemas --check
latency-fingerprint build-response \
  --degraded fixtures/query_cases/similar_network/degraded.json \
  --relief fixtures/query_cases/similar_network/relief.json \
  --probe fixtures/query_cases/similar_network/probe.json
latency-fingerprint match \
  fixtures/query_cases/similar_network/observation.json \
  --fingerprints fixtures/reference_cases
latency-fingerprint ingest-pixelated path/to/bundle.tar \
  --phase degraded \
  --comparison-case-id controlled-run-001 \
  --context path/to/context.json
```

## Current status

N1's metric inventory, strict registry models, canonical 31-output registry and
timestamped sample extraction, pure gauge/counter aggregation and migration
inspection reports are implemented. This additive foundation remains
offline/shadow work; P0 still
uses its frozen feature configuration. Registry commands are available:

```bash
latency-fingerprint export-metric-registry --output schemas/metric-registry-v1.json
latency-fingerprint export-metric-registry --output schemas/metric-registry-v1.json --check
latency-fingerprint validate schemas/metric-registry-v1.json
```

`export-schemas` also includes the additive metric-registry schema. Registry
definitions and inspection commands are described in the
[`canonical registry guide`](docs/measurement/CANONICAL_REGISTRY.md). The
[`sample extraction guide`](docs/measurement/SAMPLE_EXTRACTION.md) describes the
Python extraction API. The [`gauge guide`](docs/measurement/GAUGE_AGGREGATION.md)
describes registered statistics, coverage and summary states. The
[`counter guide`](docs/measurement/COUNTER_AGGREGATION.md) describes totals, weighted
rates, gaps and resets. The [`inspection guide`](docs/measurement/MEASUREMENT_INSPECTION.md)
describes the offline migration-readiness report:

```bash
latency-fingerprint inspect-measurements path/to/bundle.tar \
  --context path/to/context.json --phase degraded --comparison-case-id example-001
```

[Focused synthetic arithmetic fixtures](fixtures/measurement/README.md) are checked
in with independent expected summaries and read-only drift checks.
[Quality gates](docs/measurement/QUALITY_GATES.md) cover the implemented P0/N1–N4
paths. N1 metric semantics and aggregation, [N2 observation adoption](docs/measurement/OBSERVATION_V2_ADOPTION.md)
and [N3 analytical matching](docs/analysis/N3_MATCHING.md) are complete locally.
The latest local suite passes **1,739 tests with 93.69% branch-inclusive
coverage**; actual Python 3.11/hosted verification remains pending.

Current N3 references include the [field contract](docs/analysis/N3_ANALYTICAL_CONTRACT.md),
[approved provisional policy](docs/analysis/N3_FEATURE_POLICY_SPEC.json),
[models](docs/analysis/N3_ANALYTICAL_MODELS.md), [response derivation](docs/analysis/N3_RESPONSE_DERIVATION.md),
[fingerprints/repositories](docs/analysis/N3_FINGERPRINTS.md), [commands](docs/analysis/N3_COMMANDS.md)
and [fixture pins](docs/analysis/N3_ANALYTICAL_FIXTURES.md).

**Next: [N4 stage-level observability](docs/plans/NEXT_IMPLEMENTATION_PLAN.md).**
Steps 0–6 are complete locally: baselines, additive trace models/schemas and the
[timing/identity contract](docs/observability/N4_TRACE_CONTRACT.md) are recorded in
[N4 progress](docs/observability/N4_IMPLEMENTATION_PROGRESS.md). Step 7 software integration is delivered; real acceptance remains pending. [Trace models and validation](docs/observability/N4_TRACE_MODELS.md)
and [bounded host hooks](docs/observability/N4_HOST_INSTRUMENTATION.md)
and [browser collection](docs/observability/N4_BROWSER_INSTRUMENTATION.md) are
delivered, alongside [trace export/adoption](docs/observability/N4_TRACE_ADOPTION.md).
[Offline timing reconstruction](docs/observability/N4_TIMING_RECONSTRUCTION.md) is
also delivered; [pinned integrated reproduction](docs/observability/N4_INTEGRATION_VERIFICATION.md) and [software closeout](docs/observability/N4_SOFTWARE_CLOSEOUT.md) are delivered; real capture/overhead acceptance remains pending.
The plan spans Pixelated hooks/export and separate Python trace validation and
inspection, preserving current N2 timing and N3 matching meanings. The scenario
harness remains subsequent Phase 1 work.

Completed milestone records are in the [documentation archive](docs/archive/README.md),
and completed N1–N3 plans are in the [plan archive](docs/plans/archive/README.md).
Their results and pending checks remain historical evidence. The
[current documentation index](docs/README.md) separates active work, implemented
reference guides and archived records.

### Implemented and verified

- Existing Pixelated testbed and research-run export: implemented.
- P0 research contract and architecture: specified.
- Clean Python 3.13 editable installation and declared dependencies: verified.
- Python analytical core: validation, raw deltas, normalization, fingerprint
  loading, evidence and conservative matching implemented.
- Synthetic matcher fixtures and end-to-end regression pipeline: implemented.
- Offline CLI: validation, schema export/checking, response construction and
  matching implemented.
- Pixelated bundle adapter and `ingest-pixelated` command: implemented for TAR
  archives and extracted directories with an explicit research context.
- Post-P0 hardening pass: strict and bounded JSON/file boundaries, stronger
  cross-record derivation/provenance invariants, cross-file telemetry identity
  and clock checks, finite-range-safe adapter, delta, normalization and evidence
  arithmetic, immutable P0 feature semantics, bounded fingerprint traversal,
  atomic schema exports, zero-weight matcher gate correction, and CI
  coverage/security checks implemented.

### P0 result

- Controlled real fingerprinting bundles and sanitized checksums: captured.
- Operator-observed restoration evidence: recorded with an explicit limitation
  that it is not a post-restoration recovery telemetry window.
- Derived real windows and response observation: validated.
- Real matcher output: validated `unknown` because no stored synthetic
  fingerprint shares the real run's compatibility group.
- Run 001 response: frozen as an unvalidated controlled-real seed fingerprint
  for a separately captured run 002 repeatability query.
- Run 002 held-out query: matched the run 001 seed with full feature coverage;
  provisional match strength `0.9819067687174997` over 22 shared features.
- Interpretation: preliminary within-context repeatability only. One seed
  candidate and deterministic effects from the shared composite preset cannot
  establish cause discrimination or diagnosis accuracy.
- Evidence claim: end-to-end integration feasibility only; diagnosis accuracy,
  recovery benefit and generalization remain unproven.

The complete evidence records are
[`controlled-run-001`](experiments/controlled-run-001/README.md) and
[`controlled-run-002`](experiments/controlled-run-002/README.md). Use the
[`controlled-run processing guide`](experiments/CONTROLLED_RUN_PROCESSING.md)
for subsequent captures.

### Deferred beyond P0

- Live encoder mutation, autonomous recovery, calibrated probabilities,
  mixed-bottleneck inference, ML/RL and cross-node transfer evaluation.

The current implementation sequence and exit gates are in the
[N4 implementation plan](docs/plans/NEXT_IMPLEMENTATION_PLAN.md). The broader path to
the finished engine is maintained in the
[`full implementation plan`](docs/plans/FULL_IMPLEMENTATION_PLAN.md).

Inspectable software examples are linked from
[`P0_SOFTWARE_CLOSEOUT.md`](docs/archive/p0/P0_SOFTWARE_CLOSEOUT.md). Match strength is
an engineering similarity measure, not probability or calibrated confidence.
