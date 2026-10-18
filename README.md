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

Commands emit JSON to stdout and diagnostics to stderr. Use
`latency-fingerprint --help` for the complete command list.

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
- [Controlled-run processing](experiments/CONTROLLED_RUN_PROCESSING.md) explains
  how to process recorded experiments. Sanitized experimental artifacts remain
  under `experiments/`; synthetic regression inputs remain under `fixtures/`.

P0 and v2 are separate contracts and matching paths. Existing cumulative means and
proxies are not direct stage latency measurements. The core does not run live
probes or autonomous recovery, and the supplied experiments do not establish
cause discrimination, recovery benefit or cross-context generalization.

## Development checks

```sh
python -m pytest --cov=latency_fingerprinting --cov-branch --cov-fail-under=85
ruff check .
ruff format --check .
latency-fingerprint export-schemas --output schemas --check
```

The [testing guide](docs/measurement/QUALITY_GATES.md) covers fixture reproduction,
registry checks, packaging and cross-repository integration.
