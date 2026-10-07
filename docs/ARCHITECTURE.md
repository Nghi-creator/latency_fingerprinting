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

## N1 shadow measurement foundation

The completed N1 registry, extraction, aggregation and inspection milestones add
strict immutable measurement definitions, a canonical 31-output registry, raw
timestamped samples and auditable gauge/counter summaries alongside P0.
Definitions specify raw source fields, physical units, clocks, aggregation and
gap/reset policies. The registry
and generated schema have deterministic export/check commands and CI drift gates.
P0 normalization and matching continue to use their frozen configuration.

```text
Implemented: source-declared definitions -> strict registry -> schema/artifact export/check
             bounded bundle reader -> immutable raw timestamped samples
             registered gauge/counter aggregation -> immutable series summaries
             P0 comparison -> diagnostic shadow/migration report
Verified:    independent synthetic arithmetic fixtures and read-only drift checks
Configured:  Python 3.11/3.13 branch coverage and pinned reproduction CI gates
Closed out:  N1 software implementation and local verification
Pending:     Python 3.11 and hosted CI verification
Successor:   N2 additive observation-v2 contract/offline adoption (delivered below)
```

Registry metadata uses fixed release versions and creation time. Legacy exported
elapsed timestamps retain their wall-clock-derived limitation; a registry clock
label does not assert verified monotonic capture. N1 includes no observation-v2
root, live instrumentation or matcher adoption. The implemented N1 boundary and
historical successor are documented in the
[`N1 software closeout`](measurement/N1_SOFTWARE_CLOSEOUT.md) and
[archived N2 plan](plans/archive/N2_OBSERVATION_V2_ADOPTION_PLAN.md).

The implemented module dependencies are shown below. The inspection layer joins
the two paths for comparison; it does not feed N1 summaries into the P0 matcher.

```mermaid
flowchart TD
    Bundle[Recorded Pixelated bundle] --> Reader[Bounded bundle I/O and envelope validation]
    Reader --> P0[P0 adapter and observation-v1 windows]
    Reader --> Raw[N1 immutable raw samples]
    Registry[Canonical metric registry] --> Raw
    Registry --> Aggregate[Pure gauge and counter aggregation]
    Raw --> Aggregate
    Aggregate --> Summary[Validated measurement summaries]
    P0 --> Pipeline[P0 comparability, delta and normalization]
    Pipeline --> Matcher[P0 evidence and conservative matcher]
    P0 --> Inspect[Shadow inspection report]
    Summary --> Inspect
```

See the [post-N1 architecture audit](measurement/ARCHITECTURE_AUDIT.md) for
validation fixes, file-size review and remaining verification gaps.

## N2 additive contracts

N2 Steps 0–5 add strict `observation-window-v2` and `observation-v2` roots,
trusted registry binding, typed support, immutable context/settings, local clock
provenance, paired intervention compatibility and unavailable-only stage timing.
`validate` and schema exports support these roots. Their models are separate from
frozen v1 contracts; P0 response construction and matching reject v2 inputs.
`ingest-pixelated-v2` adopts raw evidence using N1 extraction/aggregation and
opt-in metadata from one validated read. The pure
[stage timing helper](../src/latency_fingerprinting/measurement/stage_timing.py)
populates four unavailable records from typed source support; existing means and
proxies remain separate metrics. Three deterministic software fixtures and pinned
read-only reproduction are configured in both Python CI jobs. Local software
[closeout](measurement/N2_SOFTWARE_CLOSEOUT.md) is complete; hosted execution and
v2 feature/normalization/fingerprint/matcher adoption remain separate boundaries. See the
[field contract](measurement/OBSERVATION_V2_CONTRACT.md),
[model guide](measurement/OBSERVATION_V2_MODELS.md) and
[adoption guide](measurement/OBSERVATION_V2_ADOPTION.md), plus
[N2 progress](measurement/N2_IMPLEMENTATION_PROGRESS.md). The
[post-N2 health audit](measurement/N2_ARCHITECTURE_AUDIT.md) records instance-boundary
hardening, fixture provenance corrections and current whole-tree verification.
The active [N3 plan](plans/NEXT_IMPLEMENTATION_PLAN.md) specifies separate v2
feature-policy, response, normalization, fingerprint and matching modules with
explicit compatibility and conservative evidence rules. These analytical modules
and commands are specified in the [N3 contract](analysis/N3_ANALYTICAL_CONTRACT.md)
and [policy artifact](analysis/N3_FEATURE_POLICY_SPEC.json), but not implemented.
Steps 0–1 are complete locally; strict policy/response models are next. P0 remains
the current matching path.

## Target system overview

![Target architecture showing the hosted control plane, local diagnosis and control loop, runtime deadline scheduler, and client telemetry](diagrams/latency-fingerprinting-architecture.png)

This diagram shows the intended full system, not the completed P0 feature set.
P0 implements the offline response-analysis path described above. Live probe
planning, autonomous actions and outcome verification, mixed-cause inference,
calibrated confidence, the deadline scheduler and optional ML remain future work.
The diagram's matcher-before-probe ordering represents hypothesis narrowing or
reuse of existing compatible evidence; response matching still requires a
measured response to a compatible probe. P0 match strength is not a calibrated
probability.

The [full-size diagram](diagrams/latency-fingerprinting-architecture.png) is a PNG
export. Its editable source is not currently included in this repository.

## Repository structure

```text
latency-fingerprinting/
├── README.md
├── pyproject.toml
├── docs/
│   ├── ARCHITECTURE.md
│   ├── analysis/
│   ├── diagrams/
│   ├── p0/
│   ├── measurement/
│   └── plans/
├── schemas/
│   ├── observation-v1.schema.json
│   ├── fingerprint-v1.schema.json
│   ├── match-result-v1.schema.json
│   ├── observation-window-v2.schema.json
│   ├── observation-v2.schema.json
│   ├── metric-registry-v1.schema.json
│   └── metric-registry-v1.json
├── src/latency_fingerprinting/
│   ├── models/
│   │   ├── common.py
│   │   ├── context.py
│   │   ├── response.py
│   │   ├── fingerprint.py
│   │   ├── measurement.py
│   │   ├── v2_common.py
│   │   ├── v2_support.py
│   │   ├── observation_v2.py
│   │   ├── observation_pair_v2.py
│   │   └── match.py
│   ├── validation.py
│   ├── windows.py
│   ├── measurement/
│   │   ├── aggregation.py
│   │   ├── feature_config.py
│   │   ├── metric_registry.py
│   │   ├── stage_timing.py
│   │   └── p0_feature_config.py
│   ├── normalization.py
│   ├── measurement_inspection.py
│   ├── pipeline.py
│   ├── fingerprints.py
│   ├── matcher.py
│   ├── matching/
│   │   ├── compatibility.py
│   │   ├── scoring.py
│   │   └── decision.py
│   ├── synthetic/
│   │   ├── builders.py
│   │   ├── definitions.py
│   │   ├── expectations.py
│   │   └── rendering.py
│   ├── synthetic_fixtures.py
│   ├── evidence.py
│   ├── schemas.py
│   ├── json_io.py
│   ├── cli.py
│   ├── __init__.py
│   └── adapters/
│       ├── pixelated_bundle.py
│       ├── pixelated_bundle_common.py
│       ├── pixelated_bundle_io.py
│       ├── pixelated_bundle_metrics.py
│       ├── pixelated_measurement_samples.py
│       ├── pixelated_adoption_metadata.py
│       ├── pixelated_observation_v2.py
│       ├── pixelated_bundle_validation.py
│       └── pixelated_bundle_v2.py
├── fixtures/
│   ├── observation-v2/
│   ├── reference_cases/
│   │   ├── healthy/
│   │   ├── network_pressure/
│   │   └── host_encoder_pressure/
│   ├── query_cases/
│   │   ├── similar_network/
│   │   ├── similar_encoder/
│   │   ├── ambiguous/
│   │   ├── conflicting/
│   │   ├── incompatible_context/
│   │   └── weak/
│   └── measurement/
├── experiments/
│   ├── controlled-run-001/
│   └── controlled-run-002/
└── tests/
    ├── data/
    ├── measurement/
    ├── models/
    ├── observation_v2/
    └── pixelated/
```

Package markers (`__init__.py`) and the CLI module entry point (`__main__.py`)
are implemented. Virtual environments, caches and large/private raw experiment
bundles are ignored by Git.

Each P0 reference/query fixture case contains paired `degraded.json` and `relief.json` observation
windows plus an expected fingerprint or match result. Reference cases build the
known fingerprint library; query cases test matching and conservative `unknown`
handling. Fixtures are stable regression inputs, while `experiments/` stores
artifacts from the completed controlled-real runs and their processing tools.
The separate `fixtures/measurement/` cases contain synthetic raw series,
definitions and independently authored expected N1 summaries; they are not
paired matcher observations.

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
- Ruff;
- jsonschema (N1 registry artifact validation in tests only).

Use standard-library `argparse` for the CLI. Add dependencies only when a concrete
need in the implemented slice justifies them; the current offline paths do not
require pandas, scikit-learn, FastAPI, SQLite or notebook infrastructure.

Public JSON file boundaries use `json_io.py` to reject duplicate keys,
non-finite constants, finite JSON syntax that overflows the runtime float,
excessive nesting, invalid UTF-8 and oversized records before model validation.
The Pixelated boundary additionally caps compressed archive bytes, declared
archive contents, members, per-file bytes, total readable bytes and CSV rows;
rejects links and duplicate TAR members; and
cross-checks workload/session identity plus browser/engine clock alignment.
Fingerprint discovery also caps matching files, total traversed directory
entries and nesting depth without following links. Finite source numbers are
checked again after delta, median and normalization arithmetic so representable
inputs cannot silently become infinities.

Pydantic models are the Python source of truth. Checked-in JSON Schemas are
generated from the models with sibling temporary files and atomic replacement;
a regression test prevents drift.

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
