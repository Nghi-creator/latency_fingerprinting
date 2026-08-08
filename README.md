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

## Development setup

The local development environment uses Python 3.13 while the package supports Python 3.11 and newer.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

The synthetic analytical path and its offline CLI are implemented and
regression-tested. Pixelated bundle ingestion is the next integration stage.

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
```

## Current status

- Existing Pixelated testbed and research-run export: implemented.
- P0 research contract and architecture: specified.
- Python 3.13 virtual environment and declared dependencies: installed.
- Python analytical core: validation, raw deltas, normalization, fingerprint
  loading, evidence and conservative matching implemented.
- Synthetic matcher fixtures and end-to-end regression pipeline: implemented.
- Offline CLI: validation, schema export/checking, response construction and
  matching implemented.
- Pixelated bundle adapter and `ingest-pixelated` command: not implemented.
- Controlled real fingerprinting run: not captured.

Update this section whenever implementation or evidence changes.
