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

```text
Pixelated browser/runtime
    -> versioned research bundle
    -> Pixelated Python adapter
    -> contract records
    -> response vector
    -> file-based fingerprint repository
    -> matcher
    -> JSON match result

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
│   ├── outreach/
│   └── p0/
├── schemas/
│   ├── observation-v1.schema.json
│   ├── fingerprint-v1.schema.json
│   └── match-result-v1.schema.json
├── src/latency_fingerprinting/
│   ├── models.py
│   ├── validation.py
│   ├── windows.py
│   ├── normalization.py
│   ├── fingerprints.py
│   ├── matcher.py
│   ├── evidence.py
│   ├── cli.py
│   ├── __init__.py
│   └── adapters/
│       ├── __init__.py
│       └── pixelated_bundle.py
├── fixtures/
│   ├── healthy.json
│   ├── network_pressure.json
│   └── host_encoder_pressure.json
├── experiments/
│   └── controlled-run-001/
└── tests/
    └── data/
```

Package markers such as `__init__.py` and `__main__.py` may be added. Virtual environments, caches and large/private raw experiment bundles must be ignored by Git.

## Python choice

Use Python 3.11 or newer for the detached core because:

- the matcher operates offline or over slow observation windows;
- Python has strong numerical, statistical and visualization tooling;
- later ML work can reuse the same records;
- it is common and inspectable in research environments;
- no working product component needs to be rewritten.

P0 dependencies:

- Pydantic 2;
- NumPy;
- pytest;
- Ruff.

Use standard-library `argparse` for the CLI. Do not add pandas, scikit-learn, FastAPI, SQLite or notebook infrastructure unless a concrete P0 blocker requires one.

Pydantic models are the Python source of truth. Checked-in JSON Schemas are generated from the models, with a regression test preventing drift.

## Runtime constraint

The current camera bridge receives FPS, bitrate and encoder profile through `PIXELATED_STREAM_PROFILE` when it launches. It does not safely mutate the running GStreamer `vp8enc`.

Therefore:

- P0 uses controlled paired runs;
- P0 does not claim live in-session probing;
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
