# Implementation plans

- [NEXT_IMPLEMENTATION_PLAN.md](NEXT_IMPLEMENTATION_PLAN.md) is the active **N3**
  plan for v2 analytical features, normalization, fingerprints and offline matching.
  Steps 0–6 are complete locally; separate analytical fixtures and closeout are next.
  [Strict policy/response models](../analysis/N3_ANALYTICAL_MODELS.md) and
  [pure response derivation](../analysis/N3_RESPONSE_DERIVATION.md) and
  [v2 fingerprints/repositories](../analysis/N3_FINGERPRINTS.md) and
  [v2 matching](../analysis/N3_MATCHING.md) and
  [additive commands](../analysis/N3_COMMANDS.md) are implemented.
- [N3 analytical field contract](../analysis/N3_ANALYTICAL_CONTRACT.md) and
  [policy specification](../analysis/N3_FEATURE_POLICY_SPEC.json) freeze the feature
  inventory, provisional parameters, record roots and conservative decision rules.
- [N3 progress](../analysis/N3_IMPLEMENTATION_PROGRESS.md) records baseline
  reproduction, specification and delivered policy/response validation.
- [Archived N2 plan](archive/N2_OBSERVATION_V2_ADOPTION_PLAN.md) preserves completed
  observation-v2 contracts/adoption and local verification. Actual Python 3.11/hosted
  execution remains pending.
- [N2 field contract](../measurement/OBSERVATION_V2_CONTRACT.md) freezes the new
  root, registry, support, pair and timing semantics before implementation.
- [N2 software closeout](../measurement/N2_SOFTWARE_CLOSEOUT.md) records delivered
  behavior, final evidence, remaining verification and the next contract boundary.
- [N2 fixtures and gates](../measurement/OBSERVATION_V2_FIXTURES.md) documents exact-byte
  snapshots and read-only CI reproduction.
- [Post-N2 health audit](../measurement/N2_ARCHITECTURE_AUDIT.md) records contract
  hardening, fixture/test maintenance and current full-tree verification.
- [N2 progress](../measurement/N2_IMPLEMENTATION_PROGRESS.md) records baseline
  verification, completed steps and pending hosted results.
- [N2 model guide](../measurement/OBSERVATION_V2_MODELS.md) documents strict root
  validation, schema exports and P0 isolation.
- [N2 adoption guide](../measurement/OBSERVATION_V2_ADOPTION.md) documents one-read
  raw evidence adoption and the separate v2 importer/command.
- [FULL_IMPLEMENTATION_PLAN.md](FULL_IMPLEMENTATION_PLAN.md) is the broader roadmap
  from the frozen P0 path through production and final evaluation.
- [Archived N1 plan](archive/N1_METRIC_SEMANTICS_FOUNDATION_PLAN.md) preserves the
  completed N1 software checklist and pending hosted-verification boundary.
- [N1 software closeout](../measurement/N1_SOFTWARE_CLOSEOUT.md) records the delivered
  artifacts, final checks, limitations and exact next boundary.
- [N1 progress](../measurement/N1_IMPLEMENTATION_PROGRESS.md) preserves milestone history.
- [Metric inventory](../measurement/METRIC_SEMANTICS_V2.md) is the authoritative
  reviewed mapping of P0 features to N1 outputs.
- [Registry models](../measurement/REGISTRY_MODELS.md) and
  [canonical registry](../measurement/CANONICAL_REGISTRY.md) explain contracts and exports.
- [Sample extraction](../measurement/SAMPLE_EXTRACTION.md),
  [gauges](../measurement/GAUGE_AGGREGATION.md) and
  [counters](../measurement/COUNTER_AGGREGATION.md) document the shadow measurement APIs.
- [Inspection](../measurement/MEASUREMENT_INSPECTION.md),
  [fixtures](../measurement/ARITHMETIC_FIXTURES.md) and
  [quality gates](../measurement/QUALITY_GATES.md) document diagnostics and verification.

Preserve each completed plan in the archive and retain its software closeout
before replacing the active plan. Keep local software verification distinct from hosted CI and scientific
validation. The full roadmap stays at major-slice level.
