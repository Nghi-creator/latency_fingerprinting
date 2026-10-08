# N1 software closeout

> Archived milestone record, retained with its original results and limitations.
> The [active N4 plan](../../plans/NEXT_IMPLEMENTATION_PLAN.md) now covers stage-level observability.

**Slice:** N1 — Metric Semantics Foundation
**Closed locally:** 2026-10-06
**Software status:** Steps 0–10 implemented and locally verified
**Hosted verification:** Python 3.11 and GitHub CI results remain pending

Subsequent hardening and current verification are recorded in the
[post-N1 architecture audit](ARCHITECTURE_AUDIT.md). The results below retain the
original Step 10 milestone evidence.

N1 delivers a versioned measurement foundation alongside the frozen P0 path.
It supplies explicit metric meaning, bounded raw extraction, deterministic gauge
and counter summaries, and a diagnostic migration report. It is software and
arithmetic verification, not new diagnosis evidence. No live probe, remediation,
runtime instrumentation or experiment was executed during N1. Proposed v2
features are not production matcher inputs; a separate observation-v2 adoption
slice is still required.

## Delivered boundary

| Deliverable | Verified behavior |
| --- | --- |
| [Semantic inventory](../../measurement/METRIC_SEMANTICS_V2.md) | All 23 P0 features map once to 31 reviewed outputs: 15 gauges, eight rates and eight audit totals |
| [Registry models](../../measurement/REGISTRY_MODELS.md) | Strict finite, immutable definitions with units, versions, clocks, missing/reset policies and cross-field validation |
| [Canonical registry](../../measurement/CANONICAL_REGISTRY.md) | Fixed `latency-metrics-v2.0.0` release, definition version `1.0.0`, deterministic artifact/schema export and drift checks |
| [Sample extraction](../../measurement/SAMPLE_EXTRACTION.md) | Existing bounded directory/TAR envelopes; immutable timestamped source rows; shared counter rate/total samples; explicit missing/rejection evidence |
| [Gauge aggregation](../../measurement/GAUGE_AGGREGATION.md) | Registered min/median/nearest-rank P95/max; stable finite arithmetic; sample-based statistics and separate interval coverage |
| [Counter derivation](../../measurement/COUNTER_AGGREGATION.md) | Accepted contiguous deltas, rates, totals, observed duration, units, gap/reset evidence and no extrapolation |
| [Migration inspection](../../measurement/MEASUREMENT_INSPECTION.md) | P0 comparison, raw/frozen reconstruction classes, privacy-preserving deterministic shadow JSON, optional-source states |
| [Arithmetic fixtures](../../measurement/ARITHMETIC_FIXTURES.md) | 13 explicitly synthetic cases with independent expected summaries and no-write exact-byte drift checks |
| [Quality gates](../../measurement/QUALITY_GATES.md) | Both Python CI jobs enforce 85% branch-inclusive coverage and pinned registry/report reproduction; public CLI resource/failure regression tests |

Public additive commands are `export-metric-registry` and `inspect-measurements`.
`export-schemas` includes the N1 registry schema, and `validate` accepts the registry
root. Inspection reports have `measurement-inspection-v1`, an explicit shadow
notice and `matcherInput=false`; they are excluded from production root validation,
response construction and matching. N1 introduces no `observation-v2` record.

## Verification and artifact pins

Final local environment: Python **3.13.13** on macOS. Final result: **892 tests
passed; 91.53% branch-inclusive coverage**, above the existing 85% floor.
Registry, extraction and inspection modules have 100% branch-inclusive coverage;
aggregation and measurement models report 99% rounded. Ruff lint/format, installed
dependencies, all schema/registry checks, both fixture drift checks, registry/report
pins, controlled-artifact validation and byte reproduction pass. CI YAML syntax
and both configured jobs were inspected. Local Markdown links and diff whitespace
checks pass.

| Frozen artifact | SHA-256 |
| --- | --- |
| [Registry JSON](../../../schemas/metric-registry-v1.json) | `50329d193303c271194b28e9164ae8627dd257d7620174c5ab136ba209864884` |
| Sanitized inspection report | `295f57a6f0e0ab80f64c7323be3cd5fc4e278aac712825f0173955594513c423` |

The report pin is reproduced read-only from the existing sanitized v2 fixture;
there is no checked-in production observation generated from it. Expected
arithmetic fixture values are authored independently of the aggregation code.
Changing meanings or rendered bytes requires deliberate release/pin review.

Reproduce local gates without rewriting artifacts:

```bash
.venv/bin/pytest --cov=latency_fingerprinting --cov-branch \
  --cov-report=term-missing --cov-fail-under=85
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m pip check
.venv/bin/python -m latency_fingerprinting export-schemas --output schemas --check
.venv/bin/python -m latency_fingerprinting export-metric-registry \
  --output schemas/metric-registry-v1.json --check
.venv/bin/python -m tests.measurement.check_reproduction
.venv/bin/python -c \
  'from latency_fingerprinting.synthetic_fixtures import fixture_drift; assert fixture_drift() == {}'
.venv/bin/python -c \
  'from tests.measurement.fixture_cases import fixture_drift; assert fixture_drift() == {}'
.venv/bin/python experiments/controlled-run-001/record_seed_fingerprint.py --check
.venv/bin/python -m latency_fingerprinting match \
  experiments/controlled-run-002/observation.json \
  --fingerprints experiments/controlled-run-001 > /tmp/n1-run002-match.json
cmp experiments/controlled-run-002/match-result.json /tmp/n1-run002-match.json
```

The five controlled P0 observation/fingerprint/match artifacts also validate with
`latency-fingerprint validate`. Existing regression tests retain controlled-run
observation reconstruction and frozen matcher reproduction. See the
[progress record](N1_IMPLEMENTATION_PROGRESS.md) for milestone-specific evidence.

## P0 preservation

Protected baseline: `b1cd7aa07eebf39629572c22cdd20428a78de826`. A final Git comparison
against that baseline found no changes in the three P0 schemas, existing reference/
query fixtures, controlled-run artifacts, P0 models, bundle adapter/helpers,
normalization configuration, pipeline, matcher or matching implementation.
Run 002 still reproduces its stored match result exactly. CLI and model exports
were extended additively for N1; P0 behavior and analytical feature meaning remain
unchanged. The existing P0 CI gates are retained.

## Limitations and remaining verification

- **Hosted CI is pending.** Python 3.11 is not installed locally, and no hosted
  job success is claimed. Both Python 3.11 and 3.13 jobs are configured with the
  required coverage, drift and pinned reproduction gates. Their results must be
  reviewed before claiming cross-version release verification.
- **Clock provenance is limited.** Existing exported elapsed timestamps are
  wall-clock-derived. Increasing elapsed values support numerical inspection,
  not a verified monotonic-clock or synchronized one-way latency claim.
- **Producer limitations remain.** Legacy zero fallbacks cannot always be
  separated from measured zero; the current pipeline-delay proxy is unsupported;
  exported decode/buffer means are producer interval statistics. Float processing
  cannot restore integer precision or events already lost before export.
- **Coverage is observed support.** Gauge coverage does not imply interpolation
  or persistence. Counter totals/rates use accepted intervals only. Missing,
  rejected and incomplete results never become fabricated measurements.
- **Migration is diagnostic.** Frozen P0 median counter deltas cannot reconstruct
  rates, totals, gaps or resets. Compatible frozen gauge scalars cannot recover
  raw support or coverage. Inspection independently reads the P0/N1 paths and
  requires checksum agreement for successful comparison.
- **Scientific validation is unchanged.** The registry, aggregation engine and
  synthetic arithmetic examples are foundations, not evidence of cause
  discrimination, diagnosis accuracy, calibrated confidence, recovery benefit
  or transfer. No new controlled-real evidence was collected.

No local implementation blocker remains in the reviewed N1 boundary. Software
closeout does not imply defect-free software or completed hosted verification.

## Exact next boundary

N2 is additive **observation-v2 contract and offline adoption** of the frozen N1
registry. Start with explicit versioned window/observation contracts, registry and
clock provenance, missing/rejected/incomplete state rules and isolation from v1
compatibility. Import only reconstructable raw evidence; never relabel frozen P0
counter medians. Define optional stage-local timing/support representation before
adding measurements, and keep unavailable timing explicit.

N2 must preserve P0 schemas and matcher results. It does not automatically adopt
v2 rates into the production matcher, invent normalization, mutate live encoders,
run remediation or claim improved diagnosis. Fingerprint/matcher-v2 adoption and
new runtime capture remain separately reviewed boundaries. The implementation
sequence is preserved in the [archived N2 plan](../../plans/archive/N2_OBSERVATION_V2_ADOPTION_PLAN.md).
The subsequent [archived N3 plan](../../plans/archive/N3_ANALYTICAL_FEATURES_AND_MATCHING_PLAN.md) records delivered analytical work.
The [archived N1 plan](../../plans/archive/N1_METRIC_SEMANTICS_FOUNDATION_PLAN.md)
preserves the completed checklist; the [full roadmap](../../plans/FULL_IMPLEMENTATION_PLAN.md)
remains the broader sequence.
