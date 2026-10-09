# Documentation index

**Current slice:** [N4 stage-level observability](plans/NEXT_IMPLEMENTATION_PLAN.md),
Steps 0–1 complete locally; Step 2 models/schemas are next. [N4 progress](observability/N4_IMPLEMENTATION_PROGRESS.md)
records both repository baselines, producer checks and runtime limitations.
The [trace contract](observability/N4_TRACE_CONTRACT.md),
[producer capabilities/acceptance](observability/N4_PRODUCER_CAPABILITIES.md) and
[independent examples](observability/N4_TRACE_EXAMPLES.md) are specified; trace
implementation has not begun. The [roadmap](plans/FULL_IMPLEMENTATION_PLAN.md)
keeps the subsequent scenario harness and scientific evaluation separate.

## Current implemented references

| Topic | Documents |
| --- | --- |
| System boundary | [Architecture](ARCHITECTURE.md), [P0 research contract](p0/RESEARCH_CONTRACT.md), [P0 matcher](p0/DATA_MODEL_AND_MATCHER.md) |
| Metric meaning | [Inventory](measurement/METRIC_SEMANTICS_V2.md), [registry](measurement/CANONICAL_REGISTRY.md), [registry models](measurement/REGISTRY_MODELS.md) |
| Raw measurements | [Extraction](measurement/SAMPLE_EXTRACTION.md), [gauges](measurement/GAUGE_AGGREGATION.md), [counters](measurement/COUNTER_AGGREGATION.md), [inspection](measurement/MEASUREMENT_INSPECTION.md) |
| Observation adoption | [N2 contract](measurement/OBSERVATION_V2_CONTRACT.md), [models](measurement/OBSERVATION_V2_MODELS.md), [adoption](measurement/OBSERVATION_V2_ADOPTION.md) |
| Analytical records | [N3 contract](analysis/N3_ANALYTICAL_CONTRACT.md), [approved policy](analysis/N3_FEATURE_POLICY_SPEC.json), [models](analysis/N3_ANALYTICAL_MODELS.md), [derivation](analysis/N3_RESPONSE_DERIVATION.md) |
| Offline matching | [Fingerprints/repositories](analysis/N3_FINGERPRINTS.md), [matching](analysis/N3_MATCHING.md), [commands](analysis/N3_COMMANDS.md) |
| Verification | [Quality gates](measurement/QUALITY_GATES.md), [N1 fixtures](measurement/ARITHMETIC_FIXTURES.md), [N2 fixtures](measurement/OBSERVATION_V2_FIXTURES.md), [N3 fixtures](analysis/N3_ANALYTICAL_FIXTURES.md) |

N2 stage timing remains unavailable; no N4 method implementation or trace schema is delivered.
N3 policy parameters remain provisional. Current local baseline is 1,539 passing
tests with 93.58% branch-inclusive coverage; actual hosted/minimum-version,
full-limit scaling and scientific validation remain pending.

## Historical evidence

Completed closeouts, progress and health audits are in the
[milestone archive](archive/README.md). Completed N1–N3 plans are in the
[plan archive](plans/archive/README.md). Contracts and API/fixture guides above
remain current references; archiving historical work does not change their meaning.
Controlled-real artifacts and their procedures remain in
[experiments](../experiments/CONTROLLED_RUN_PROCESSING.md).
