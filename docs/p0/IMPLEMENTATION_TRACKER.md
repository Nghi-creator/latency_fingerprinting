# P0 Implementation Tracker

Use this file as the build checklist. The ordered implementation sequence,
deliverables and phase gates live in [`P0_BUILD_PLAN.md`](P0_BUILD_PLAN.md).
Design details live in the other linked documents.

## Exit statement

> Given a compatible context and comparable degraded/relief windows, the Python prototype calculates a normalized response, compares it with three synthetic fingerprints, explains the ranking, and refuses ambiguous evidence. The same pipeline processes one controlled real Pixelated paired-run record.

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
- [ ] Add the console entry point when `cli.py` is implemented.
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
- [ ] Aggregate raw adapter telemetry into window metrics.
- [ ] Normalize with declared feature scales.
- [ ] Load versioned fingerprint JSON.
- [ ] Implement weighted-distance ranking and coverage.
- [ ] Implement evidence and all `unknown` reasons.

## 5. Fixtures and tests

- [ ] Add three clearly synthetic fingerprints.
- [ ] Add clear/noisy matching tests.
- [ ] Add weak/tied/conflicting `unknown` tests.
- [ ] Add missing-feature and context-mismatch tests.

## 6. CLI

- [ ] Implement `validate` and `export-schemas`.
- [ ] Implement `ingest-pixelated` and `build-response`.
- [ ] Implement `match`.
- [ ] Use JSON stdout, diagnostic stderr and non-zero failure codes.

## 7. Pixelated adapter

Reference: [`PIXELATED_ADAPTER_AND_EXPERIMENT.md`](PIXELATED_ADAPTER_AND_EXPERIMENT.md)

- [ ] Read TAR or extracted bundle.
- [ ] Validate files, columns and archive paths.
- [ ] Map telemetry and aggregate phases.
- [ ] Preserve provenance and missing evidence.
- [ ] Add sanitized fixtures and tests.

## 8. Controlled real run

- [ ] Bound the experiment-only pressure workload.
- [ ] Capture healthy, degraded and paired relief runs.
- [ ] Restore and verify runtime health.
- [ ] Create sanitized manifest and checksums.
- [ ] Pass the real response through the CLI.
- [ ] Record output without forcing a successful label.

## 9. Verification

```bash
python -m pip install -e '.[dev]'
pytest
ruff check .
ruff format --check .
latency-fingerprint export-schemas --check
latency-fingerprint match tests/data/clear-network-response.json --fingerprints fixtures/
```

- [ ] Clean install and all checks pass.
- [ ] Schemas match generated models.
- [ ] Example output validates against its schema.
- [ ] No secret, ROM, private path or personal device identity is committed.

## 10. Outreach readiness

- [ ] README shows completed, in-progress and planned work.
- [ ] Example records are inspectable.
- [ ] Synthetic and real provenance are obvious.
- [ ] Real output is called feasibility evidence.
- [ ] Live probing, calibrated confidence and comparative benefit are not claimed.

## Deferred beyond P0

- live encoder mutation and automated rollback;
- persistent database;
- calibrated probabilities and mixed bottlenecks;
- GPU/Wi-Fi deep instrumentation;
- deadline scheduler;
- ML/RL and cross-node transfer;
- powered baseline comparison;
- dashboard or separate installed application.
