# Next Slice Implementation Plan: V2 Analytical Features and Offline Matching

**Slice ID:** N3
**Status:** Steps 0–1 complete locally; Step 2 strict analytical models next
**Updated:** 2026-10-07
**Parent roadmap:** [FULL_IMPLEMENTATION_PLAN.md](FULL_IMPLEMENTATION_PLAN.md)
**Predecessor:** [N2 software closeout](../measurement/N2_SOFTWARE_CLOSEOUT.md)
**Archived predecessor plan:** [N2 observation-v2 adoption](archive/N2_OBSERVATION_V2_ADOPTION_PLAN.md)

N1 measurement semantics and N2 observation-v2 adoption are implemented and
locally verified. The [post-N2 audit](../measurement/N2_ARCHITECTURE_AUDIT.md)
records the current baseline: 1,166 passing tests and 93.05% branch-inclusive
coverage. Actual Python 3.11/hosted verification remains pending. This document
now freezes the analytical design in the [N3 field contract](../analysis/N3_ANALYTICAL_CONTRACT.md)
and [policy specification](../analysis/N3_FEATURE_POLICY_SPEC.json). V2 analytical
runtime models, normalization, fingerprints, matching and commands are not yet implemented.

## Outcome and boundary

Connect validated `ObservationRecordV2` pairs to an explicitly versioned feature
policy, auditable response calculation and separate offline fingerprint/matching
path. Carry registry, feature-policy, context and intervention identities through
the calculation so incompatible evidence cannot be compared silently.

Preserve P0 models, commands, numerical behavior, schemas and controlled results.
Preserve N1 registry release meaning and N2 observation roots/adoption bytes.
N2 observations remain immutable inputs; analytical results belong in separate
contracts rather than adding response fields to the frozen observation schema.

N3 adds no live probe/remediation, direct timing instrumentation, training service
or new experiment. Stage timings remain unavailable and audit totals remain audit
evidence. Synthetic matches verify software, not diagnosis accuracy, calibrated
confidence or real relief efficacy.

## Step 0 — Preserve and reproduce the N2 baseline

**Local gate:** Complete at `06e697105e918c0c2f3ae2d25bf75c833f7982ad`;
1,166 tests pass, 93.05% branch-inclusive coverage. All frozen reproduction gates
pass. Actual hosted/minimum-version execution remains pending; see
[N3 progress](../analysis/N3_IMPLEMENTATION_PROGRESS.md).

Record the starting commit and checkout state. Reproduce the
[quality gates](../measurement/QUALITY_GATES.md): six current schemas, three fixture
families, N1 registry/report pins, N2 snapshot pins and exact P0 controlled match
bytes. Retain the unchanged 85% branch-inclusive coverage floor. Track actual
hosted/minimum-version execution separately; unresolved CI failures must not be
presented as a successful release gate.

Gate: record a reproducible local baseline and pending verification without
rewriting frozen artifacts to make checks pass.

## Step 1 — Freeze the analytical and matching field contract

**Specification gate:** Complete in [N3_ANALYTICAL_CONTRACT.md](../analysis/N3_ANALYTICAL_CONTRACT.md),
design 1.0.0, with exact initial [policy JSON](../analysis/N3_FEATURE_POLICY_SPEC.json).
The policy selects 22 registered primary outputs, preserves exclusions, defines
signed responses and conservative evidence thresholds, and fixes root/version,
compatibility, fingerprint, matching and command semantics before implementation.
Parameters are explicitly software-provisional. Runtime enforcement is Step 2 onward.

Author the field-level N3 design before runtime implementation. Use the
[metric inventory](../measurement/METRIC_SEMANTICS_V2.md),
[registry](../measurement/CANONICAL_REGISTRY.md) and
[N2 contract](../measurement/OBSERVATION_V2_CONTRACT.md) as the source of meaning.
Specify:

- An explicit feature inventory binding each selected metric to registry
  version/hash, definition version, unit and primary aggregation.
- A separately versioned feature-policy identity/content hash, including response
  direction, normalization formula/reference, numerical floors, clipping, weights
  and feature/window eligibility rules.
- Treatment of support, missing/rejected/incomplete summaries, minimum coverage,
  usable evidence, zero values and confounders. Retain explicit exclusions or
  invalidity; never replace absent evidence with zeros.
- A standalone analytical response contract, plus proposed `fingerprint-v2` and
  `match-result-v2` roots. Freeze exact names, independent versions, embedded versus
  referenced evidence and cross-validation rules in this step.
- Fingerprint provenance, source pair references, declared labels/validation status,
  context/probe compatibility and eligibility for analytical comparison.
- Shared-feature/positive-weight requirements, distance, residual evidence,
  deterministic ranking/ties, rejection reasons and conservative `unknown`
  outcomes. Distinguish invalid configuration from insufficient evidence.
- Explicit v1/v2 rejection: no silent renaming, normalization or comparison of v1
  fingerprints/P0 counter aggregates as v2 evidence.

Floors, clipping, coverage limits, weights and decision thresholds must belong to
an explicit named/versioned policy with stated provenance. Do not inherit P0
constants by feature-name coincidence or describe chosen software parameters as
experimentally calibrated. Enumerate the proposed policy and independently
auditable examples; settle these choices before Step 2 consumes them.

Gate: every published number and decision has a specified, testable meaning.
Exclude audit totals, unsupported proxies and unavailable stages from features.

## Step 2 — Implement strict policy and analytical response models

Add separate immutable analytical modules and additive schemas from Step 1.
Validate policy version/hash agreement, registered bindings, units, finite numbers,
unique features, eligibility/exclusion consistency and reconstructable response/
normalization metadata. Revalidate supplied model instances and detach mutable
caller containers at validated boundaries.

Keep policy loading local, bounded and duplicate-safe. Missing/unknown/altered
policies fail explicitly; records cannot resolve supplied URLs or alter registry
meaning. Add root validation without modifying existing v1/N2 roots.

Gate: malformed records fail closed, valid zero remains numeric, and all existing
schema bytes and reproduction pins remain unchanged.

## Step 3 — Derive auditable responses from validated v2 pairs

Implement pure response/normalization functions taking `ObservationRecordV2` and
an explicit policy. Retain degraded/relief primary values, raw response, normalized
result, units, policy identity, support/coverage and exclusions required by Step 1.

Respect window elapsed/interval semantics. Never subtract cross-domain timestamps
or turn totals into rates without raw intervals. Reuse scalar math only when its
meaning matches the reviewed contract. Reject unrepresentable arithmetic; preserve
zero/missing distinctions, input immutability and audit-only metric roles.

Gate: independent positive/negative/zero, low-denominator and partial/missing-support
cases reconstruct responses. Altered clipping parameters fail the initial approved
policy gate. Equivalent counter activity at different valid cadence retains the
same eligible rate.

## Step 4 — Add v2 fingerprints and bounded repository loading

Implement the separately versioned fingerprint root and dedicated bounded loader.
Bind policy/registry meaning, context and probe semantics to retained response and
provenance. Validate that published features derive from declared evidence; retain
explicit validation/exclusion metadata.

Require declared labels and source evidence; never infer a real bottleneck label
from similarity or mark synthetic fingerprints experimentally validated. Define
read-only deterministic creation without ambient IDs or unrequested file writes.
Reject duplicate IDs, malformed records and mixed roots under the reviewed policy.

Gate: altered vectors, incompatible meanings and false provenance claims fail;
invalid files cannot silently become candidates.

## Step 5 — Implement separate deterministic v2 matching and evidence

Add v2 compatibility, scoring and decision modules around the explicit policy.
Filter by context, registry, policy and intervention meanings before comparing
eligible shared features. Publish residuals, weights, exclusions and rejection
reasons with reconstructable distances and reproducible ranking.

Require positive usable weight and minimum evidence. Handle empty repositories,
no compatible candidates, weak coverage, ambiguity, poor matches and contradictory
evidence with specified `unknown` outcomes. Report similarity/decision evidence
without implying calibrated causal confidence. Preserve the P0 matcher/defaults.

Gate: independently calculated cases prove distance/evidence consistency, stable
tie ordering and conservative decisions under incomplete/contradictory inputs.

## Step 6 — Expose additive offline commands

After contracts/functions pass, expose the specified `build-response-v2`,
`build-fingerprint-v2` and `match-v2` commands. Preserve the field contract
arguments in the command guide; require
explicit local policies where needed. Retain existing `build-response`, `match`
and ingestion behavior.

Emit complete canonical JSON after validation. Preserve bounded file/repository
traversal, privacy-limited reasons, deterministic errors and read-only inputs.
Cover incompatible roots/policies, duplicate keys, byte/depth/file-count limits
and no partial output on public command failures.

Gate: CLI output equals pure API output; no implicit conversion/fallback admits
wrong-version evidence.

## Step 7 — Fixtures, verification, documentation and software closeout

Add explicitly synthetic analytical/fingerprint/match fixtures with independently
authored numerical expectations and exact-byte/SHA-256 drift checks. Cover both
eligible and conservative-unknown paths. Preserve all P0/N1/N2 inputs/pins;
new analytical snapshots have separate pins.

Run both configured Python suites, coverage/resource/privacy checks, schema/policy/
fixture drift and existing reproduction gates. Distinguish local execution from
actual hosted results. Update README, architecture, module/command guides and a
dedicated N3 closeout. Check the whole final tree, including fixture documentation
created during closeout.

Archive this plan when replacing it with a successor. Retain pending verification
explicitly and keep scientific evaluation/new instrumentation separate.

## Exit checklist

- [x] Baseline and frozen P0/N1/N2 reproduction checks are retained locally.
- [x] Feature inventory, policy parameters and compatibility meanings are specified.
- [ ] Strict policy/response/fingerprint/match contracts and schemas are delivered.
- [ ] Responses retain auditable values, support, coverage and exclusions.
- [ ] Matching is deterministic and conservative with insufficient/ambiguous evidence.
- [ ] Separate commands preserve v1 behavior and bounded/read-only inputs.
- [ ] Independent synthetic expectations and new pins reproduce exactly.
- [ ] Whole-tree tests, docs and software closeout match delivered behavior.
- [ ] Actual Python 3.11/3.13 CI execution evidence is recorded.

The next implementation action is Step 2: strict policy and analytical response
models/schemas from the frozen Step 1 contract. N3 runtime implementation has not
started; hosted/minimum-version execution remains separately pending.
