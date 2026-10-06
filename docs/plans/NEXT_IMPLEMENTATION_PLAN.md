# Next Slice Implementation Plan: Additive Observation-v2 Adoption

**Slice ID:** N2
**Status:** Steps 0–2 locally complete; Step 3 offline adoption next
**Updated:** 2026-10-06
**Parent roadmap:** [FULL_IMPLEMENTATION_PLAN.md](FULL_IMPLEMENTATION_PLAN.md)
**Predecessor:** [N1 software closeout](../measurement/N1_SOFTWARE_CLOSEOUT.md)

N1 Steps 0–10 are implemented and locally verified. Its Python 3.11/hosted CI
results remain pending; review those results before claiming cross-version
release verification. The [archived N1 plan](archive/N1_METRIC_SEMANTICS_FOUNDATION_PLAN.md)
preserves the completed software checklist. N2's baseline and field specification
are recorded in [N2 progress](../measurement/N2_IMPLEMENTATION_PROGRESS.md).
Strict observation-v2 models/schemas are implemented; raw-bundle adoption and
v2 matching are not implemented yet.

## Outcome and boundary

Adopt the frozen N1 measurement registry in an additive observation-v2 contract
and offline bundle-to-record path. Retain metric meaning, units, versions, source
support, interval evidence, coverage and clock provenance in validated records.
Define the smallest useful optional stage-local timing/support representation
before adding new capture measurements. Missing timing must remain explicit.

P0 models, schemas, feature configuration, controlled artifacts and match outputs
remain frozen. N2 will not relabel P0 counter medians, change existing matcher
inputs, invent normalization, execute live probes/remediation or introduce new
runtime instrumentation. Fingerprint/matcher-v2 adoption and scientific validation
remain separate boundaries after records have stable contracts.

## Step 0 — Preserve the N1 baseline

**Local gate:** Passed at `6b185f5ff8f12a1b50e91e1d99c371d6e9725c9b`;
924 tests, 91.89% coverage and all frozen reproduction checks pass. Hosted
Python 3.11/3.13 results remain pending.

- Review hosted CI results when available and resolve any N1 regressions separately.
- Record the starting commit and reproduce all [N1 quality gates](../measurement/QUALITY_GATES.md).
- Retain the registry/report hashes and P0 controlled-run byte checks.
- Preserve the distinction between local software verification and remote CI results.

Gate: no new contract work silently changes N1 definitions or P0 artifacts.

## Step 1 — Freeze the observation-v2 field contract

**Specification gate:** Complete in
[OBSERVATION_V2_CONTRACT.md](../measurement/OBSERVATION_V2_CONTRACT.md),
design version 1.0.0, clarified as 1.0.1 during Step 2. Runtime enforcement is
documented in the [model guide](../measurement/OBSERVATION_V2_MODELS.md).

Document the field-level design before implementation, using the
[N1 inventory](../measurement/METRIC_SEMANTICS_V2.md) and
[summary guides](../measurement/COUNTER_AGGREGATION.md) as the semantic source.
The design must specify:

- explicit new schema versions for v2 window and observation roots;
- registry version and content hash, definition semantic versions and source identity;
- required clock basis/provenance, elapsed bounds, capture-method version and support state;
- per-metric summaries with available values, missing/rejected/incomplete states,
  accepted duration/coverage, interval evidence and safe reasons;
- analytical rate outputs versus audit-only totals, without treating absence as zero;
- degraded/relief pair identity and compatibility rules separate from frozen v1 rules;
- whether records embed definitions or reference a separately verified registry snapshot;
- an explicit optional stage-local timing/support shape and privacy policy.

Specify how incompatible registry meanings fail validation. Do not silently
compare v1 median deltas with v2 rates, nor assign v2 normalization parameters
without a separately reviewed feature/adoption contract.

Gate: the schema proposal distinguishes every N1 state, unit and provenance limit
and identifies which timing fields are measured, estimated or unavailable.

## Step 2 — Implement additive strict models and schemas

**Local gate:** Complete. Two additive schema roots, immutable strict models and
CLI root validation pass 168 new contract cases. Full suite: 1,092 tests and
92.60% branch-inclusive coverage; frozen reproduction checks pass.

Add new v2 modules and exports without editing the frozen v1 root contracts.
Validate finite values, bounds, registry hashes/version agreement, summary metadata,
source support, metric uniqueness, counter reconstruction and pair compatibility.
Generate new schema files additively and include no-write drift checks.

Tests must cover null/missing/zero distinctions, wrong units/versions, altered
registry hashes, duplicate metric names and JSON keys, impossible duration/coverage,
incompatible pairs, non-finite/overflow values, immutable metadata and round trips.

Gate: malformed v2 records fail closed and all v1 schemas/artifacts remain identical.

## Step 3 — Build the offline raw-bundle adoption path

Reuse [N1 extraction](../measurement/SAMPLE_EXTRACTION.md) and pure aggregation.
Build new v2 records only from validated raw evidence with an explicit context,
phase and comparison case. Pin registry content and retain clock limitations.
Make directory/TAR output deterministic and avoid ambient timestamps/identifiers.

Expose a separate offline command after the root contract is reviewed. Existing
`ingest-pixelated`, response building and matching keep their current v1 behavior.
A frozen P0 aggregate alone cannot populate new counter rates/totals or coverage.
The [migration report](../measurement/MEASUREMENT_INSPECTION.md) remains diagnostic;
it is not a substitute input contract for adoption.

Gate: raw evidence reconstructs each published value; unavailable or rejected
measurements cannot fabricate v2 values, and no v1 record is overwritten.

## Step 4 — Add the minimum timing/support representation

Start with declared clock provenance, observed interval duration and source
support already present in N1. Define optional stage-local timing fields with
explicit source, method, unit and clock domain. Populate them only when the
producer supplies evidence matching the reviewed meaning.

Existing decode/buffer interval means and pipeline-delay proxies cannot become
direct per-frame stage latency. Unsupported capture/encode/render timings stay
unavailable, and no synchronized one-way latency claim is made. If a new timing
meaning requires a metric definition, review and version that registry extension;
do not alter the frozen `latency-metrics-v2.0.0` release in place.

Gate: every timing field has auditable measured/estimated/unavailable provenance.
New capture instrumentation is a later slice rather than an implicit N2 dependency.

## Step 5 — Verify, document and close the offline contract slice

Keep both Python versions, the 85% branch floor, bounded-resource/CLI regression
coverage and existing P0/N1 reproduction gates. Add focused v2 fixtures with
explicit provenance, deterministic expected records and exact-byte drift checks.
Verify privacy and unchanged input files, directory/TAR equality, raw-to-summary
reconstruction, incompatible registry rejection and unchanged P0 match results.

Update the architecture, per-module guides, command documentation and a dedicated
N2 software closeout. Record local versus hosted verification, remaining timing
limitations and the exact next boundary for fingerprint/matcher-v2 adoption.

## Exit checklist

- [x] V2 roots and field semantics are specified, locally reviewed and separately versioned.
- [x] Registry, capture method and clock provenance are explicit and validated.
- [x] Missing/rejected/incomplete/zero states and audit totals remain distinct.
- [ ] Raw bundles produce deterministic additive v2 records without rewriting v1.
- [ ] Frozen P0 counter aggregates are never silently upgraded.
- [ ] Timing/support representation makes no unsupported per-frame or one-way claim.
- [ ] Both Python CI suites and resource, privacy and reproduction gates pass.
- [ ] P0 artifacts, N1 release pins and existing match results are unchanged.
- [ ] Documentation and N2 software closeout match delivered behavior.

The next implementation action is Step 3: deterministic offline raw-bundle adoption.
Steps 0–2 are locally complete; hosted verification remains pending. No N2
implementation is included in the historical N1 closeout.
