# N5 Implementation Plan: Reproducible Scenario Harness

**Slice ID:** N5
**Status:** Software and live method/campaign checks pass; merged-baseline CI verified; manual desktop acceptance and normal CI for subsequent audit fixes pending
**Updated:** 2026-10-16
**Parent roadmap:** [Phase 1.3](FULL_IMPLEMENTATION_PLAN.md#13-build-a-reproducible-scenario-harness)
**Predecessor:** [N4 software closeout](../archive/observability/N4_SOFTWARE_CLOSEOUT.md)
**Archived plan:** [N4 stage observability](archive/N4_STAGE_LEVEL_OBSERVABILITY_PLAN.md)
**Progress:** [N5 implementation progress](../scenarios/N5_IMPLEMENTATION_PROGRESS.md)
**Inherited open gates:** [N4 runtime acceptance](../observability/N4_RUNTIME_ACCEPTANCE.md)

N5 begins with N4 software complete locally and real N4 acceptance explicitly
pending. Starting N5 does not establish real capture, instrumentation overhead,
clock synchronization, minimum-version execution or hosted CI success. Preserve
all P0/N1/N2/N3/N4 contract bytes, fixture pins, registry/policy releases, matcher
thresholds and existing commands. Core validation/analysis stays outside producer
frame callbacks; producer trace hooks do bounded in-memory collection.

## Outcome and ownership

Build bounded, reproducible experiment orchestration with declared scenarios,
seeds, tool/runtime versions, workload, phase/action timing, evidence checksums,
measured effects and restoration evidence. Injector startup is not ground truth.
Use distinct independent source runs for references and held-out queries.

Pixelated owns live runtime/video hooks, process/fault lifecycle and evidence
capture. The core owns detached manifest/evidence validation and offline inspection.
Inspect available boundaries before freezing APIs or privileged adapters. Existing
CPU-pressure and smoke tools are starting surfaces, not a finished harness.

The target scenario inventory includes healthy, host contention, render/capture
slowdown, encoder overload, delay, jitter, loss, bandwidth pressure and client
decode pressure. Each must have a declared support state and measured-effect
criterion. Unsupported cases cannot count toward acceptance. Add mixed/changing
cases only after single causes are stable. Live probes/remediation, calibrated
confidence, profile promotion and the deadline scheduler remain later phases.

## Step 1 — Preserve baseline and inventory experiment surfaces

**Local gate:** Complete, 2026-10-10. Both trees started clean at the commits in
[N5 progress](../scenarios/N5_IMPLEMENTATION_PROGRESS.md). Reproduce core/producer
checks and pinned outputs; inspect existing controlled-run, pressure, smoke,
telemetry, recording and cleanup surfaces. Record runtime limitations and carry
forward every N4 pending gate before changing experiment contracts.

Gate: a recorded reproducible software baseline and explicit ownership/gap
inventory. No fault injection or new runtime measurement is performed here.

## Step 2 — Freeze scenarios, phases, evidence and cleanup contract

**Specification gate:** Complete, 2026-10-10. [Experiment contract](../scenarios/N5_EXPERIMENT_CONTRACT.md), [adapter capabilities/effect criteria](../scenarios/N5_ADAPTER_CAPABILITIES.md) and [independent examples](../scenarios/N5_EXPERIMENT_EXAMPLES.md) freeze three additive roots, phases/actions, integer evidence, bounds, cleanup, per-phase recording and intended inspection. V1 approves healthy/host contention for later implementation; other classes remain explicitly unsupported. No N5 models/runner/CLI or real trial is delivered here.

Define a separately versioned experiment manifest and scenario/adapter inventory.
Specify warm-up, healthy, degraded, probe, recovery and cooldown boundaries,
monotonic timing versus UTC metadata, bounded durations/workers/actions, seeds,
repeat IDs, evidence references/checksums and privacy/resource bounds. Establish
measured-effect and restoration predicates before trials. Define cancellation,
partial failure, crash recovery, single-owner cleanup and unavailable states.

Keep independent clocks separate; distinguish requested/supported/executed actions
from verified effects. Specify fresh post-warm-up trace recording control needed
by N4 acceptance. Freeze intended APIs/CLI only after inspecting actual runtime
ownership. Author independent positive/failure examples before implementation.

Gate: every claimed scenario/effect/result has explicit evidence meaning and a
bounded cleanup path; no silent reinterpretation of earlier artifact contracts.

## Step 3 — Implement strict additive experiment contracts

**Local software gate:** Complete, 2026-10-10. [Strict models/schemas and validation](../scenarios/N5_EXPERIMENT_MODELS.md) deliver the three roots and independent regressions. Linked hash/effect verification remains Step 6.

Add immutable strict manifest/result models, schemas and validation under the
Step 2 contract. Reject unknown versions/actions, ambiguous references, invalid
phase order, nonfinite/coerced numbers, unsafe resources and identity/hash drift.
Test independent complete/partial/unavailable/failure cases and copied instances.

Gate: deterministic validation with unchanged earlier schemas/pins/CLI outputs.

## Step 4 — Implement bounded run lifecycle and recording control

**Local software gate:** Complete, 2026-10-11. [Producer lifecycle/recording control](../scenarios/N5_RUN_LIFECYCLE.md) implements the cooperative runner, exact ownership journal/recovery and fresh actual collectors with fake-runtime tests. [Concrete adapters/effect checks](../scenarios/N5_SUPPORTED_ADAPTERS.md) subsequently delivered in Step 5; software tests do not establish a real trial.

Implement producer-side orchestration for reproducible workload and phases,
monotonic action timing, cancellation, cleanup and restoration. Add a fresh
post-warm-up recording path without bridging old frames/epochs/clocks or doing
I/O in frame hooks. Exercise healthy, interruption, restart, duplicate ownership
and failed cleanup with fake runtime dependencies before real execution.

Gate: run lifecycle and fresh recording can be exercised safely and independently;
software tests are not evidence of real fault effects or measured overhead.

## Step 5 — Add supported single-cause adapters and effect verification

**Local software gate:** Complete, 2026-10-11. [Supported adapters/effect checks](../scenarios/N5_SUPPORTED_ADAPTERS.md) deliver actual camera hooks, bounded parked Linux children, private durable pidfd identity/recovery, owned CPU clocks and independent fixed predicates. Fake-dependency tests pass; native idle-child execution and live fault/capture remain unverified on this Mac.

Implement the approved bounded adapters incrementally, starting with healthy and
host contention using inspected producer ownership. Add remaining single-cause
adapters only where effects and restoration can be observed. Host/network/browser
privileges and tool versions must be explicit; unavailable adapters fail closed.
Do not alter unrelated machine settings or invoke unbounded shell fault commands.

Gate: supported actions have bounded lifecycle, independent measured-effect checks
and restoration evidence; no scenario passes solely because an injector started.

## Step 6 — Export, adopt and inspect experiment evidence

**Local software gate:** Complete, 2026-10-11. [Export and detached inspection](../scenarios/N5_EXPERIMENT_INSPECTION.md) deliver bounded deterministic producer bundles, hash/ownership validation, independent integer effect recomputation and private atomic CLI output. Synthetic actual-collector handoffs pass; real runtime gates remain open.

Export sanitized versioned manifests/results with checksummed existing trace and
observation artifacts; preserve their separate meanings. Add bounded no-follow
adoption/inspection and atomic outputs. Retain partial runs, failed effects,
missing sources, recovery and cleanup results without fabricating measurements.

Gate: producer evidence can be inspected offline deterministically with truthful
phase/action/effect coverage and no implicit promotion into N3 matching features.

## Step 7 — Pin independent fixtures and cross-repository reproduction

**Local software gate:** Complete, 2026-10-12. [Independent experiment fixtures/reproduction](../scenarios/N5_EXPERIMENT_FIXTURES.md) pin eight synthetic cases and exact uncompressed producer member bytes; directory/API/CLI parity and both configured core CI gates are delivered. Actual local reproduction passes. Subsequent minimum-version and core hosted checks pass; see the current [runtime ledger](../scenarios/N5_RUNTIME_ACCEPTANCE.md) for the passing cohort and remaining manual desktop gate and normal CI for subsequent audit fixes.

Author independent synthetic success/failure/partial/unsupported fixtures and
read-only pins. Exercise producer export → core adoption/inspection, preserve all
legacy reproduction gates and run applicable full suites, lint/builds and doc checks.
Keep configured CI distinct from actual hosted/minimum-version execution.

Gate: independently reviewed synthetic expectations reproduce; real trial gates
remain explicit and cannot be passed by fake runtime output.

## Step 8 — Execute real repetitions and close out software/runtime separately

**Software closeout:** Recorded, 2026-10-12. [Closeout](../scenarios/N5_SOFTWARE_CLOSEOUT.md) separates delivered local software from actual runtime/hosted results. [Live acceptance ledger](../scenarios/N5_RUNTIME_ACCEPTANCE.md) records initial macOS preflight unavailability and subsequent real Docker Desktop Linux trials, retained corrected-cohort failures, verified N4 overhead/lifecycle checks, actual minimum-version execution and native image build/smoke; the [additive campaign/pacing workflow](../scenarios/N5_CAMPAIGN_WORKFLOW.md) now delivers the second adapter and live-entry/overhead tools. Fresh campaign-8 passes all 18 trials and selected-scene overhead passes; browser execution method checks now pass locally; merged-baseline hosted checks pass. Manual desktop acceptance and the normal CI run for subsequent audit fixes remain pending; Phase 1 is not closed.

Run supported real single causes with measured effects, recovery, seeds/config,
all trial values and independent repetitions. Freeze reference/query assignments
before analysis; no source run may query its own fingerprint. Phase 1.3 requires
at least two real single-bottleneck classes with repeated runs and held-out queries.
Mixed/changing scenarios wait until stable single causes. Run inherited N4 capture
and all predeclared overhead gates without changing thresholds after measurement.

Publish separate software/runtime/hosted outcomes. If runtime is unavailable,
retain a concrete pending gate; do not call Phase 1 complete. Archive progress,
plan/audits/closeout on the following transition, keeping normative guides current.

## Exit checklist

- [x] Baseline, ownership inventory and inherited pending gates recorded.
- [x] Scenario/phase/evidence/cleanup contract frozen with independent examples.
- [x] Strict additive models/schemas preserve existing releases.
- [x] Bounded lifecycle and fresh post-warm-up recording control implemented.
- [x] Approved adapters implement evidence-based effect/restoration checks; unsupported states explicit (software only).
- [x] Versioned producer export/core adoption and inspection agree in synthetic software checks.
- [x] Independent fixtures/pins and both repository software gates reproduce locally.
- [x] Real repetitions and disjoint reference/query acquisitions recorded: campaign-8, 18/18 verified.
- [x] Merged-baseline hosted verification passes in both repos; [exact receipts](../../experiments/phase-1-audit-20261015/hosted-ci.json).
- [ ] Full inherited N4 acceptance: user desktop/picker/export sign-off remains open; subsequent audit fixes need normal CI after merge.
- [x] Software/runtime/hosted outcomes and current docs agree; fault cohort and core hosted results verified; remaining manual acceptance and subsequent audit CI explicit.

**Readiness audit:** The [follow-up review](../../experiments/phase-1-readiness-20261015/README.md) hardens compressed legacy archives and browser save cleanup, splits mixed telemetry/API-test/scenario-test modules and preserves releases. This is preparation for the next phase; it does not close the manual gates below.

**Remaining acceptance action:** User desktop/game-picker and trace-export/cancel/retry checks. Hosted gates pass on the merged baselines; the subsequent audit fixes need their normal CI after merge. See the [pre-manual audit](../../experiments/phase-1-audit-20261015/README.md). Opt-in browser execution coding, independent fixtures/API/CLI handoff and local live overhead/coverage/diagnostic checks now pass ([evidence](../../experiments/n5-browser-execution-20261014/README.md)). Fresh campaign-8 now verifies all 18 healthy/contention/pacing reference/query acquisitions; source receipt windows are disjoint. Selected-scene five-pair overhead also passes. Nominal N4 capture/overhead and host lifecycle cases now pass; actual Python 3.11/Node 24 and native build/smoke are recorded. Local software closeout is recorded; runtime acceptance is pending. N5 and Phase 1 remain open.
