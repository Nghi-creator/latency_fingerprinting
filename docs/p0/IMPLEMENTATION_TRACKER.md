# P0 Implementation Tracker

Use this file as the build checklist. The ordered implementation sequence,
deliverables and phase gates live in [`P0_BUILD_PLAN.md`](P0_BUILD_PLAN.md).
Design details live in the other linked documents.

## Exit statement

> Given a compatible context and comparable degraded/relief windows, the Python prototype calculates a normalized response, explains the ranking, and refuses ambiguous evidence. Run 001 traverses the controlled-real path and becomes an unvalidated seed; independently captured run 002 provisionally matches it with full feature coverage.

## 1. Research contract

Reference: [`RESEARCH_CONTRACT.md`](RESEARCH_CONTRACT.md)

- [x] Define context, windows and comparability.
- [x] Define probe and paired-run limitation.
- [x] Define response delta and fingerprint.
- [x] Define match result, `unknown` and validated outcome.

## 2. Package scaffold

Reference: [`../ARCHITECTURE.md`](../ARCHITECTURE.md)

- [x] Add `pyproject.toml` and package markers.
- [x] Configure Python, dependencies, pytest and Ruff.
- [x] Add repository and experiment-data ignore rules.
- [x] Add the console entry point when `cli.py` is implemented.
- [x] Document and verify clean-environment installation.

## 3. Models and schemas

Reference: [`DATA_MODEL_AND_MATCHER.md`](DATA_MODEL_AND_MATCHER.md)

- [x] Implement context, metric, window and probe models.
- [x] Implement response, fingerprint, match and evidence models.
- [x] Generate three JSON Schemas.
- [x] Add drift, validation and round-trip tests.

## 4. Analytical core

- [x] Validate window comparability.
- [x] Calculate raw deltas from aggregate window metrics.
- [x] Aggregate raw adapter telemetry into window metrics.
- [x] Normalize with declared feature scales.
- [x] Load versioned fingerprint JSON.
- [x] Implement weighted-distance ranking and coverage.
- [x] Implement per-feature matching evidence.
- [x] Implement all `unknown` reasons.

## 5. Fixtures and tests

- [x] Add three clearly synthetic fingerprints.
- [x] Add clear/noisy matching tests.
- [x] Add weak/tied/conflicting `unknown` tests.
- [x] Add missing-feature and context-mismatch tests.

## 6. CLI

- [x] Implement `validate` and `export-schemas`.
- [x] Implement `build-response`.
- [x] Implement `ingest-pixelated` with the Pixelated adapter.
- [x] Implement `match`.
- [x] Use JSON stdout, diagnostic stderr and non-zero failure codes.

## 7. Pixelated adapter

Reference: [`PIXELATED_ADAPTER_AND_EXPERIMENT.md`](PIXELATED_ADAPTER_AND_EXPERIMENT.md)

- [x] Read TAR or extracted bundle.
- [x] Validate files, columns and archive paths.
- [x] Map telemetry and aggregate phases.
- [x] Preserve provenance and missing evidence.
- [x] Add sanitized fixtures and tests.

## 8. Controlled real run

- [x] Implement a bounded experiment-only pressure workload and capture protocol.
- [x] Capture healthy, degraded and paired relief runs.
- [x] Restore and verify runtime health.
- [x] Create sanitized manifest and checksums.
- [x] Pass the real response through the CLI.
- [x] Record the conservative `unknown` output without forcing a label.
- [x] Freeze run 001 as an explicitly unvalidated controlled-real seed.
- [x] Process independent run 002 and preserve its preliminary repeat match.

## 9. Verification

```bash
python -m pip install -e '.[dev]'
pytest
ruff check .
ruff format --check .
latency-fingerprint export-schemas --check
latency-fingerprint match fixtures/query_cases/similar_network/observation.json --fingerprints fixtures/reference_cases
```

- [x] Clean install and all software checks pass.
- [x] Schemas match generated models.
- [x] Example output validates against its schema.
- [x] No secret, ROM, private path or personal device identity is committed.

## 10. Outreach readiness

- [x] README shows completed, in-progress and planned work.
- [x] Example records are inspectable.
- [x] Synthetic fixtures and completed controlled-real evidence are clearly distinguished.
- [x] Real output is called feasibility evidence.
- [x] Live probing, calibrated confidence and comparative benefit are not claimed.

## Deferred beyond P0

- live encoder mutation and automated rollback;
- persistent database;
- calibrated probabilities and mixed bottlenecks;
- GPU/Wi-Fi deep instrumentation;
- deadline scheduler;
- ML/RL and cross-node transfer;
- powered baseline comparison;
- dashboard or separate installed application.
