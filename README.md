# Latency Fingerprinting

This repository contains the detached Python research core and the documents used to build its initial P0 vertical slice. Pixelated Studio Edition remains the first telemetry-producing testbed and integration target.

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
5. [`docs/p0/IMPLEMENTATION_TRACKER.md`](docs/p0/IMPLEMENTATION_TRACKER.md) is the executable checklist and exit gate.
6. [`docs/p0/P0_BUILD_PLAN.md`](docs/p0/P0_BUILD_PLAN.md) defines the ordered implementation plan and phase gates.
7. [`docs/PROJECT_BUILD_AND_REVIEW_READINESS.md`](docs/PROJECT_BUILD_AND_REVIEW_READINESS.md) consolidates project build gates, technical explanations and review questions.
8. [`docs/p0/P0_SOFTWARE_CLOSEOUT.md`](docs/p0/P0_SOFTWARE_CLOSEOUT.md) records verified software and controlled-real evidence plus the remaining limitations.

## Development setup

The local development environment uses Python 3.13 while the package supports Python 3.11 and newer.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

The synthetic analytical path, offline CLI and Pixelated bundle adapter are
implemented and regression-tested. Controlled run 001 also traverses the full
real-data path and preserves the matcher's conservative `unknown` outcome.

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

### Controlled evidence completed

- Controlled real fingerprinting bundles and sanitized checksums: captured.
- Operator-observed restoration evidence: recorded with an explicit limitation
  that it is not a post-restoration recovery telemetry window.
- Derived real windows and response observation: validated.
- Real matcher output: validated `unknown` because no stored synthetic
  fingerprint shares the real run's compatibility group.
- Evidence claim: end-to-end integration feasibility only; diagnosis accuracy,
  recovery benefit and generalization remain unproven.

### Deferred beyond P0

- Live encoder mutation, autonomous recovery, calibrated probabilities,
  mixed-bottleneck inference, ML/RL and cross-node transfer evaluation.

Inspectable software examples are linked from
[`P0_SOFTWARE_CLOSEOUT.md`](docs/p0/P0_SOFTWARE_CLOSEOUT.md). Match strength is
an engineering similarity measure, not probability or calibrated confidence.

Update this section whenever implementation or evidence changes.
