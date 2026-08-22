# P0 Build Plan

**Status:** Complete  
**Scope:** Initial latency-fingerprinting vertical slice  
**Completed:** 2026-08-13

## Purpose

This document is the ordered implementation plan for the architecture defined
in [`../ARCHITECTURE.md`](../ARCHITECTURE.md). It complements
[`IMPLEMENTATION_TRACKER.md`](IMPLEMENTATION_TRACKER.md): the tracker records
high-level completion, while this plan defines the order, deliverables and gate
for each build step.

The P0 exit condition is:

> Given a compatible context and comparable degraded/relief windows, the Python
> prototype calculates a normalized response, explains its ranking, and refuses
> ambiguous evidence. Run 001 traverses the controlled-real path and becomes an
> unvalidated seed; independently captured run 002 provisionally matches it
> with full feature coverage.

## Build order

```text
contract and schemas
    -> comparable observation windows
    -> raw response delta
    -> normalized response vector
    -> compatible fingerprint repository
    -> weighted ranking and evidence
    -> matched or unknown result
    -> CLI
    -> Pixelated adapter
    -> controlled real paired run
    -> P0 thesis evidence
```

Do not begin a dependent step until the previous step's gate passes. Tests are
added alongside each component rather than postponed until the end.

## Current state

- [x] Research contract frozen at `1.0.0`.
- [x] Python package scaffold and development tooling configured.
- [x] Pydantic context, window, probe, response, fingerprint, match and outcome
  models implemented under `src/latency_fingerprinting/models/`.
- [x] Three deterministic JSON Schemas generated and checked in.
- [x] Schema drift and root-alias tests added.
- [x] Full contract validation and JSON round-trip tests completed.
- [x] Analytical core implemented.
- [x] Synthetic end-to-end vertical slice completed.
- [x] Offline P0 command-line interface implemented.
- [x] Pixelated research-bundle adapter implemented with sanitized fixtures.
- [x] Pixelated controlled-real runs 001 and 002 completed and validated.

## Step 1: Lock the model and schema boundary

### Work

- Add valid JSON round-trip tests for `ObservationRecord`, `Fingerprint` and
  `MatchResult`.
- Reject invalid schema and contract versions.
- Reject `NaN`, positive infinity and negative infinity.
- Test invalid time bounds, metric summaries and paired-window references.
- Test simulated probes cannot claim execution, observed settings or runtime
  restoration.
- Test `matched` and `unknown` result invariants.
- Keep generated schemas byte-for-byte synchronized with the Pydantic models.

### Deliverables

- focused model tests under `tests/models/`
- Existing `tests/test_schemas.py` expanded when needed
- Current files under `schemas/`

### Gate

- [x] All valid root records round-trip through JSON.
- [x] Invalid contract records fail with useful validation errors.
- [x] Schema drift check passes.

## Step 2: Implement window comparability validation

### Work

Create `src/latency_fingerprinting/validation.py`. It must evaluate, without
performing response calculations:

- degraded and relief phases are correct;
- both windows are individually valid;
- contexts and compatibility groups match;
- comparison-case identifiers are present and equal;
- probe identifiers reference the supplied windows;
- provenance is consistent;
- durations are sufficiently similar under an explicit P0 tolerance;
- shared metrics use identical units and compatible aggregation functions;
- effective-setting changes match the declared probe;
- unrelated changes are absent or recorded as confounders.

Return a structured comparability result with reason codes. Reserve exceptions
for malformed program input; an incomparable pair is an expected analytical
result and should retain its reasons.

### Deliverables

- `src/latency_fingerprinting/validation.py`
- `tests/test_validation.py`

### Gate

- [x] Valid synthetic pairs are accepted.
- [x] Every comparability rule has a focused rejection test.
- [x] Rejection reasons can later map to a match `unknown` decision.

## Step 3: Calculate raw response deltas

### Work

Create `src/latency_fingerprinting/windows.py`:

- accept degraded and relief windows plus their declared probe;
- call the comparability validator first;
- use only finite features present in both windows;
- require matching units and aggregation functions;
- calculate `raw delta = relief - degraded`;
- retain degraded value, relief value, unit and aggregation function;
- preserve missing and rejected features rather than imputing zero;
- return an invalid response with reasons when the pair is incomparable.

### Deliverables

- `src/latency_fingerprinting/windows.py`
- `tests/test_windows.py`

### Gate

- [x] Jitter `20 ms -> 8 ms` produces `-12 ms`.
- [x] FPS `35 -> 55` produces `+20 FPS`.
- [x] Missing values never become zero-valued evidence.
- [x] Incomparable windows cannot produce a valid delta.

## Step 4: Normalize response vectors

### Work

Create `src/latency_fingerprinting/normalization.py` and an explicit feature
configuration containing each P0 metric's unit, epsilon and optional clipping
bounds.

Use:

```text
normalized delta = raw delta / max(abs(reference value), feature epsilon)
```

Normalization must occur after the raw delta is calculated. Record the
reference value, epsilon and whether clipping occurred.

### Deliverables

- `src/latency_fingerprinting/normalization.py`
- `tests/test_normalization.py`

### Gate

- [x] Zero and near-zero references remain finite.
- [x] Missing features remain missing.
- [x] Clipping, when configured, is visible in the output.
- [x] Raw values remain available for audit.

## Step 5: Create the synthetic fixture corpus

### Work

Create stable, clearly synthetic paired-window cases:

```text
fixtures/
├── reference_cases/
│   ├── healthy/
│   ├── network_pressure/
│   └── host_encoder_pressure/
└── query_cases/
    ├── similar_network/
    ├── similar_encoder/
    ├── weak/
    ├── ambiguous/
    ├── conflicting/
    └── incompatible_context/
```

Each fixture case should contain inspectable degraded and relief records plus
the expected response, fingerprint or match decision. All synthetic fixtures
must use synthetic provenance and an explicit P0 compatibility group.

### Gate

- [x] Every contract fixture validates through its Pydantic model and root schema
  drift checks pass.
- [x] Values make the intended cross-layer response pattern inspectable.
- [x] Fixture documentation says these are software-test inputs, not findings.

## Step 6: Implement the fingerprint repository

### Work

Create `src/latency_fingerprinting/fingerprints.py`:

- load fingerprint JSON files from a directory;
- validate every record with Pydantic;
- reject duplicate fingerprint identifiers;
- reject incompatible schema or contract versions;
- filter candidates by compatibility group and probe type;
- return candidates in deterministic order;
- report corrupt or rejected files with useful reasons.

P0 storage remains versioned JSON files. Do not add a database or service.

### Deliverables

- `src/latency_fingerprinting/fingerprints.py`
- `tests/test_fingerprints.py`

### Gate

- [x] The three synthetic reference fingerprints load deterministically.
- [x] Invalid, duplicate and incompatible records are tested.

## Step 7: Implement per-feature evidence

### Work

Create `src/latency_fingerprinting/evidence.py`. For each shared feature,
calculate:

- query value;
- candidate value;
- residual;
- feature weight;
- weighted squared residual;
- whether the feature supports or conflicts with the candidate.

The evidence should be generated from the same values used by the matcher so
the explanation cannot disagree with the score.

### Deliverables

- `src/latency_fingerprinting/evidence.py`
- `tests/test_evidence.py`

### Gate

- [x] Per-feature weighted residuals reconstruct the candidate distance.
- [x] Supporting and conflicting evidence is deterministic.

## Step 8: Implement the matcher and `unknown`

### Work

Create `src/latency_fingerprinting/matcher.py` using normalized weighted
Euclidean distance:

```text
distance = sqrt(sum(weight * residual^2) / sum(weight))
base strength = 1 / (1 + distance)
adjusted strength = base strength * shared-feature coverage
```

Apply checks in this order:

1. contract, schema, probe and context compatibility;
2. finite shared-feature intersection;
3. minimum positive-weight shared-feature count;
4. minimum feature coverage;
5. non-degenerate vector and usable weights;
6. weighted-distance ranking;
7. top-two margin;
8. conflicting-evidence policy;
9. matched or `unknown` decision.

Use the provisional P0 defaults from
[`DATA_MODEL_AND_MATCHER.md`](DATA_MODEL_AND_MATCHER.md). Match strength is an
engineering similarity measure, not probability or calibrated confidence.

### Deliverables

- `src/latency_fingerprinting/matcher.py`
- `tests/test_matcher.py`

### Gate

- [x] Clear network and encoder queries match the intended references.
- [x] Weak, tied, sparse, conflicting and incompatible queries return
  `unknown` with the correct reason.
- [x] Candidate ranking and evidence are deterministic.

## Step 9: Prove the synthetic vertical slice end to end

### Work

Exercise this full path from checked-in JSON:

```text
paired query windows
    -> validation
    -> raw response
    -> normalization
    -> fingerprint loading
    -> matching
    -> JSON match result
```

### Deliverables

- `tests/test_pipeline.py`
- schema-valid example result under `tests/data/`

### Gate

- [x] Clear and noisy expected matches pass.
- [x] All required `unknown` paths pass.
- [x] Output validates against `match-result-v1.schema.json`.
- [x] Repeated runs produce byte-stable JSON output.

## Step 10: Implement the CLI

### Work

Create `src/latency_fingerprinting/cli.py`, add `__main__.py` and configure the
`latency-fingerprint` console entry point in `pyproject.toml`.

Implement commands in this order:

1. `validate`
2. `export-schemas --check`
3. `build-response`
4. `match`
5. `ingest-pixelated` after the adapter exists

Commands emit machine-readable JSON to stdout, diagnostics to stderr and
non-zero exit codes for execution or validation failures. An analytical
`unknown` decision is valid output, not a CLI failure.

### Deliverables

- `src/latency_fingerprinting/cli.py`
- `src/latency_fingerprinting/__main__.py`
- CLI entry in `pyproject.toml`
- `tests/test_cli.py`

### Gate

- [x] Every implemented command has success and failure-path tests.
- [x] CLI match output validates against the result schema.
- [x] `export-schemas --check` detects drift without rewriting files.

## Step 11: Implement the Pixelated bundle adapter

### Work

Create `src/latency_fingerprinting/adapters/pixelated_bundle.py` according to
[`PIXELATED_ADAPTER_AND_EXPERIMENT.md`](PIXELATED_ADAPTER_AND_EXPERIMENT.md):

- accept an extracted bundle or TAR archive;
- reject unsafe archive traversal and links;
- validate required files and columns;
- map browser telemetry to the core metric vocabulary;
- select explicit phases and aggregate them into observation windows;
- preserve source provenance and missing evidence;
- avoid exposing Pixelated filenames or CSV columns to the analytical core;
- never ingest credentials, personal paths or device identities.

### Deliverables

- `src/latency_fingerprinting/adapters/pixelated_bundle.py`
- sanitized adapter fixtures under `tests/data/`
- `tests/test_pixelated_bundle.py`
- working `ingest-pixelated` CLI command

### Gate

- [x] Sanitized valid bundles produce core observation windows.
- [x] Additive Pixelated bundle v2 manifests and engine/encoder telemetry are
  accepted without breaking v1 ingestion.
- [x] Unsafe TAR paths, missing files and missing columns are rejected.
- [x] Unsupported telemetry is represented as missing, not fabricated.

Implementation note (2026-08-10): bundle v2 support is split across the public
adapter, shared parsing helpers, metric aggregation and v2 validation modules.
Sanitized healthy/degraded/relief fixtures exercise directory and TAR ingestion;
the final P0 Python suite has 231 passing tests and generated schemas are current.
This fixture gate does not replace the controlled real evidence required below.

## Step 12: Run controlled real experiment 001

### Work

Under `experiments/controlled-run-001/`:

1. Fix workload, browser, client, route and run procedure.
2. Capture a healthy reference run.
3. Start a bounded experiment-only host/encoder pressure workload.
4. Capture a degraded run with the normal stream setting.
5. Hold pressure constant and capture a paired relief run with one lower-cost
   stream setting.
6. Stop the pressure workload and verify restoration.
7. Record run order, durations and every changed setting.
8. Ingest both runs through the Pixelated adapter.
9. Build and normalize the response.
10. Run the matcher and preserve its result, including `unknown`.

### Deliverables

- `experiments/controlled-run-001/README.md`
- sanitized `manifest.json` and checksums
- observation and match-result JSON
- restoration and runtime-health evidence

Large or private raw bundles stay outside Git.

### Required real-run inputs (completed)

Step 12 was completed after the following artifacts were obtained. The first
five came from the actual controlled test; the final two were generated by the
Python pipeline from those inputs.

| Artifact | How it is obtained |
| --- | --- |
| `healthy.tar` | Export from Pixelated with no experiment pressure active. |
| `degraded.tar` | Export under bounded pressure using the nominal stream profile. |
| `relief.tar` | Export under the same pressure using the declared relief profile. |
| finalized `context.json` | Record the fixed, anonymized node, runtime, workload, browser, route, encoder and version context used by all runs. |
| restoration and runtime-health evidence | Record that pressure stopped, the nominal profile was restored, and the engine/stream returned to a healthy state. |
| `observation.json` | Derived after ingestion from the real degraded/relief windows and finalized probe. |
| `match-result.json` | Derived by matching the real observation; an `unknown` result is acceptable. |

Place the private TAR exports under the ignored directory:

```text
experiments/controlled-run-001/raw/
└── full_data/
    ├── healthy.tar
    ├── degraded.tar
    └── relief.tar
```

Do not substitute sanitized fixtures for these artifacts or mark the step
complete before the real captures, restoration evidence and derived outputs
have been validated.

### Gate

- [x] The complete real-data path executes successfully.
- [x] Restoration is verified and recorded.
- [x] Output validates against the checked-in schemas.
- [x] The outcome is described as feasibility evidence, not diagnosis accuracy.

## Step 13: Close and present P0

### Work

- Run the complete clean-environment verification suite.
- Update `IMPLEMENTATION_TRACKER.md` and the README status.
- Document fixture generation and controlled-run reproduction.
- Record known limitations and threats to validity.
- Include inspectable example input, response, ranking evidence and output.
- Ensure no secrets, ROMs, private paths or personal device identity are
  committed.

### Required verification

```bash
python -m pip install -e '.[dev]'
pytest
ruff check .
ruff format --check .
latency-fingerprint export-schemas --check
latency-fingerprint match fixtures/query_cases/similar_network/observation.json \
  --fingerprints fixtures/reference_cases
```

### Software closeout status

- [x] Clean editable installation verified in a new Python 3.13 environment.
- [x] Full test, lint, formatting, schema and CLI verification passed.
- [x] Tracker and README distinguish completed P0 work, evidence limitations and deferred work.
- [x] Fixture generation and controlled-run reproduction are documented.
- [x] Known limitations and threats to validity are recorded in
  [`P0_SOFTWARE_CLOSEOUT.md`](P0_SOFTWARE_CLOSEOUT.md).
- [x] Example input, fingerprint, ranking evidence, matched output and `unknown`
  output are linked and inspectable.
- [x] Repository scan found no committed secret, ROM, raw bundle, personal path
  or private device identity.
- [x] Controlled-real artifacts are added after Step 12 capture and validation.

### Gate

- [x] The P0 exit statement is demonstrated by reproducible artifacts.
- [x] Synthetic versus controlled-real provenance is unmistakable.
- [x] Match strength is never called probability or calibrated confidence.
- [x] Live probing, recovery benefit and generalization are not claimed.

## Deferred until after P0

Do not add these while completing this plan unless a demonstrated P0 blocker
requires revisiting the architecture:

- live encoder mutation and automated rollback;
- HTTP, gRPC or separately installed latency-engine services;
- SQLite or hosted fingerprint storage;
- autonomous diagnosis-to-action execution;
- frame-deadline scheduling;
- ML or RL models and serving;
- calibrated probabilities and mixed-bottleneck inference;
- cross-node transfer claims;
- dashboards and distributed coordination.

## Working rule for future implementation sessions

At the start of each session:

1. identify the first unchecked gate in this plan;
2. implement only the work needed to pass that gate;
3. add or update tests in the same change;
4. run pytest, Ruff and schema drift checks;
5. update this plan and `IMPLEMENTATION_TRACKER.md` with verified progress;
6. record the next concrete task before stopping.
