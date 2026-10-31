# Latency Fingerprinting

A detached Python research core for interpreting latency changes from recorded
perturbation-response experiments. Pixelated Studio Edition is the first telemetry
producer and integration testbed.

The offline pipeline validates observation windows, derives a response vector,
compares compatible stored fingerprints, and returns an interpretable match or
`unknown`. Match strength is a similarity measure, not a calibrated probability
or proof of a bottleneck's cause.

## Install

Python 3.11 or newer is required.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

## Quick start

Validate and match the included synthetic observation:

```sh
latency-fingerprint validate fixtures/query_cases/similar_network/observation.json
latency-fingerprint match \
  fixtures/query_cases/similar_network/observation.json \
  --fingerprints fixtures/reference_cases
```

Construct an observation from a degraded/relief pair and a recorded intervention:

```sh
latency-fingerprint build-response \
  --degraded fixtures/query_cases/similar_network/degraded.json \
  --relief fixtures/query_cases/similar_network/relief.json \
  --probe fixtures/query_cases/similar_network/probe.json
```

Import a Pixelated research bundle with an explicit context:

```sh
latency-fingerprint ingest-pixelated path/to/bundle.tar \
  --phase degraded --comparison-case-id example-001 \
  --context path/to/context.json
```

Output is command-specific: the validation and matching examples above emit
JSON to stdout; calibration, profile and passive-gate commands write artifacts
through required `--output` paths. Diagnostics go to stderr. Use
`latency-fingerprint --help` and the command guides for exact output behavior.

## Documentation

Start with the [documentation index](docs/README.md) and
[architecture](docs/ARCHITECTURE.md).

- [P0 research contract](docs/p0/RESEARCH_CONTRACT.md) and
  [data model/matcher](docs/p0/DATA_MODEL_AND_MATCHER.md) describe the original path.
- [Metric registry](docs/measurement/CANONICAL_REGISTRY.md) and
  [observation-v2 adoption](docs/measurement/OBSERVATION_V2_ADOPTION.md) describe
  versioned raw measurement semantics.
- [Analytical v2 contract](docs/analysis/N3_ANALYTICAL_CONTRACT.md) and
  [commands](docs/analysis/N3_COMMANDS.md) describe explicit feature policies,
  response construction and separate v2 matching.
- [Stage traces](docs/observability/N4_TRACE_CONTRACT.md) describe bounded host and
  browser instrumentation, clocks, loss and same-lifetime timing reconstruction.
- [Scenario contracts](docs/scenarios/N5_EXPERIMENT_CONTRACT.md) and
  [campaign workflow](docs/scenarios/N5_CAMPAIGN_WORKFLOW.md) describe experiment
  bundles and detached effect/cleanup verification.
- [Calibration inspection](docs/calibration/N6_INSPECTION.md) verifies linked
  source evidence, labels, independent splits and retained eligibility decisions.
- [Robust profiles](docs/profiles/N7_COMMANDS.md) fit labelled training
  responses with explicit immutable lifecycle revisions.
- [Profile matching and evaluation](docs/profile_matching/N8_COMMANDS.md) compare
  held-out evidence and evaluate whole-source-group refits.
- [Passive gating](docs/passive_gating/N9_COMMANDS.md) fits healthy FPS baselines
  and replays degradation, recovery, stale evidence and bounded probe proposals.
- [Fixture inventory and maintenance](fixtures/README.md) explains the regression
  families, release pins and why complete retained outcomes are stored.
- [Controlled-run processing](experiments/CONTROLLED_RUN_PROCESSING.md) explains
  how to process recorded experiments. Sanitized experimental artifacts remain
  under `experiments/`; synthetic regression inputs remain under `fixtures/`.
- [Live-probe evidence](docs/live_probes/N10_MODELS.md) validates immutable offline
  declarations and reconstructs counter/setting observations while retaining
  unqualified capability and unverified receiver continuity.

P0 and v2 are separate contracts and matching paths. Existing cumulative means and
proxies are not direct stage latency measurements. The core does not run live
probes or autonomous recovery, and the supplied experiments do not establish
cause discrimination, recovery benefit or cross-context generalization.

The original implementation lives under `src/latency_fingerprinting/p0/`, with
its own models, matching stages, ingestion adapter and synthetic builders.
Use `latency_fingerprinting.p0.*` for P0 implementation imports. Shared and current
contracts remain under `models/`; its public P0 model imports still work.

## Development checks

```sh
python -m pytest --cov=latency_fingerprinting --cov-branch --cov-fail-under=85
ruff check .
ruff format --check .
latency-fingerprint export-schemas --output schemas --check
```

The [testing guide](docs/measurement/QUALITY_GATES.md) covers fixture reproduction,
registry checks, packaging and cross-repository integration.
