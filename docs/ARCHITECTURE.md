# Latency-Fingerprinting Architecture

**Decision:** Detached Python research core with TypeScript/Node testbed adapters

## System boundary

Existing Pixelated components continue to own:

- browser WebRTC telemetry collection;
- research-run bundle export;
- Electron and Docker orchestration;
- game/session lifecycle;
- runtime stream settings and future action adapters.

The Python core owns:

- contract validation;
- observation-window aggregation;
- response-delta calculation;
- normalization;
- file-based fingerprint loading;
- interpretable matching and `unknown` handling;
- evidence generation;
- offline experiments and later statistical/ML analysis.

The future deadline scheduler remains in the capture/GStreamer runtime because per-frame decisions must not depend on a slow external process.

## Data flow

P0 exercises the research core with synthetic fixtures and controlled-real
paired observation windows. A probe is represented by metadata plus its
degraded and relief windows; the Python core analyzes the recorded intervention
but does not execute it against a live engine.

```text
Pixelated browser/runtime or synthetic fixture
    -> versioned bundle or contract windows
    -> Pixelated adapter when needed
    -> degraded + relief observation windows + probe
    -> raw response delta
    -> normalized response vector
    -> compatible file-based fingerprints
    -> weighted-distance matcher
    -> matched or unknown JSON result

Future slow loop:
    Python diagnosis/policy -> bounded runtime action adapter

Future fast loop:
    capture/GStreamer deadline scheduler -> frame-local decision
```

Loose coupling is established through contracts and adapters. P0 does not create another desktop application, daemon or HTTP service.

## Repository structure

The editable architecture diagram is stored at [`diagrams/latency-fingerprinting-architecture.svg`](diagrams/latency-fingerprinting-architecture.svg).

```text
latency-fingerprinting/
├── README.md
├── pyproject.toml
├── docs/
│   ├── ARCHITECTURE.md
│   ├── diagrams/
│   └── p0/
├── schemas/
│   ├── observation-v1.schema.json
│   ├── fingerprint-v1.schema.json
│   └── match-result-v1.schema.json
├── src/latency_fingerprinting/
│   ├── models/
│   │   ├── common.py
│   │   ├── context.py
│   │   ├── response.py
│   │   ├── fingerprint.py
│   │   └── match.py
│   ├── validation.py
│   ├── windows.py
│   ├── normalization.py
│   ├── pipeline.py
│   ├── fingerprints.py
│   ├── matcher.py
│   ├── matching/
│   │   ├── compatibility.py
│   │   ├── scoring.py
│   │   └── decision.py
│   ├── evidence.py
│   ├── schemas.py
│   ├── json_io.py
│   ├── cli.py
│   ├── __init__.py
│   └── adapters/
│       ├── pixelated_bundle.py
│       ├── pixelated_bundle_io.py
│       ├── pixelated_bundle_metrics.py
│       ├── pixelated_bundle_validation.py
│       └── pixelated_bundle_v2.py
├── fixtures/
│   ├── reference_cases/
│   │   ├── network_pressure/
│   │   └── host_encoder_pressure/
│   └── query_cases/
│       ├── similar_network/
│       ├── similar_encoder/
│       └── unknown/
├── experiments/
│   ├── controlled-run-001/
│   └── controlled-run-002/
└── tests/
    └── data/
```

Package markers such as `__init__.py` and `__main__.py` may be added. Virtual environments, caches and large/private raw experiment bundles must be ignored by Git.

Each fixture case contains paired `degraded.json` and `relief.json` observation
windows plus an expected fingerprint or match result. Reference cases build the
known fingerprint library; query cases test matching and conservative `unknown`
handling. Fixtures are stable regression inputs, while `experiments/` stores
artifacts from complete research trials and, later, real controlled runs.

## Python choice

Use Python 3.11 or newer for the detached core because:

- the matcher operates offline or over slow observation windows;
- Python has strong numerical, statistical and visualization tooling;
- later ML work can reuse the same records;
- it is common and inspectable in research environments;
- no working product component needs to be rewritten.

P0 runtime dependency:

- Pydantic 2;

Development tools:

- pytest;
- pytest-cov;
- Ruff.

Use standard-library `argparse` for the CLI. Do not add pandas, scikit-learn, FastAPI, SQLite or notebook infrastructure unless a concrete P0 blocker requires one.

Public JSON file boundaries use `json_io.py` to reject duplicate keys,
non-standard non-finite constants, invalid UTF-8 and oversized records before
model validation. The Pixelated boundary additionally caps archive members,
per-file bytes, total readable bytes and CSV rows; rejects links and duplicate
TAR members; and cross-checks workload/session identity plus browser/engine
clock alignment.

Pydantic models are the Python source of truth. Checked-in JSON Schemas are generated from the models, with a regression test preventing drift.

## Runtime constraint

The current camera bridge receives FPS, bitrate and encoder profile through `PIXELATED_STREAM_PROFILE` when it launches. It does not safely mutate the running GStreamer `vp8enc`.

Therefore:

- P0 models controlled probes with paired synthetic or controlled-real windows;
- P0 does not claim live in-session probing;
- controlled-real paired runs are ingested through the completed Pixelated
  adapter;
- dynamic bounded probing is deferred until the runtime exposes a tested mutation and rollback path.

## Deferred architecture

P0 does not include:

- an HTTP or gRPC fingerprint service;
- a separately installed latency-engine application;
- SQLite or hosted storage;
- autonomous action execution;
- the deadline scheduler;
- ML serving;
- distributed multi-node coordination.
