# N5 implementation progress

**Updated:** 2026-10-16. **Status:** library and end-to-end coding workflows delivered; real runtime acceptance remains pending.
**Active plan:** [N5 reproducible scenario harness](../plans/NEXT_IMPLEMENTATION_PLAN.md).
**Inherited gates:** [N4 runtime acceptance](../observability/N4_RUNTIME_ACCEPTANCE.md).

## Current handoff, 2026-10-15

The [pre-manual audit](../../experiments/phase-1-audit-20261015/README.md) records
the prior 2,015-test Python 3.11/3.13 baseline (93.61% coverage), all 25 schemas and
unchanged release pins. Pixelated's full Node suites, lint/builds, browser
interaction harness, 79 Linux scenario tests and 58 Linux trace tests pass.
Both merged baselines now have verified hosted CI, including Pixelated image
security and desktop packaging. Campaign-8 still verifies all 18 actual trials;
selected-workload and browser execution overhead checks remain passing.

The audit fixes malformed-manifest error handling, nonblocking special-file
rejection and the remaining moderate dependency advisory. Current local fixes
need their ordinary CI after merge. User desktop/game-picker and trace export
sign-off remain pending. Earlier step sections below retain historical counts,
then-pending gates and original software closeout evidence.

The [latest script/CI verification](../../experiments/phase-1-script-ci-20261016/README.md)
passes 2,032 core tests on Python 3.13 (93.55% coverage) and 780 Pixelated Node
tests, with one existing external-artifact skip. It adds archive/export failure
hardening and focused source/test splits. Linux/minimum-version and hosted reruns
of these new patches remain CI work, separate from the earlier actual results.

## Step 1 — Baseline and ownership inventory

Both checkouts were clean before this step:

| Repository | Starting commit |
| --- | --- |
| Core | `2a15bbfefba4a76dc5c5f7ed0e76672ecd963287` |
| Pixelated testbed | `b65eeed2fba67987610b957a82ed8a39876c5410` |

No applicable AGENTS.md was found in either repository. At Step 1, N5 changes were
plan/progress/transition documentation, not a new runtime harness, fault injection
or a measured scenario. No commit, deployment or hosted workflow was performed.

### Reproduced local software baseline

- Core Python 3.13: **1745 tests pass / 93.69% branch-inclusive coverage**, unchanged
  85% floor. Ruff lint/format, dependency consistency, twelve schemas, canonical
  registry, N1/N2/N3/N4 pinned reproduction and original synthetic fixtures pass.
  Controlled P0 records, run-001 seed and exact run-002 match are preserved.
- Producer Node 26.4.0/npm 11.17.0: 185 API, 133 engine, 245 web, 90 desktop and
  61 smoke/contract/security tests pass: **714 total**, one existing external
  mirror-artifact engine skip. All **42** nested Python trace cases pass under
  Python 3.14.4. Whole-workspace lint, lockfile consistency, API TypeScript checks
  and production web build pass.
- Actual synthetic host/browser/unsupported-API collector exports reproduce all
  pinned N4 record and summary bytes through core adoption and inspection APIs/CLI.
  These artifacts remain synthetic; their placeholder producer versions do not
  identify real captures.

### Inspected starting surfaces

| Owner | Surface | Existing behavior / N5 gap |
| --- | --- | --- |
| Core | `experiments/CONTROLLED_RUN_PROCESSING.md`, controlled-run-001/002 | Manual sanitized healthy/degraded/relief processing and P0 evidence; no N5 scheduler or held-out campaign |
| Core | `experiments/bounded_cpu_pressure.py` | Monitored experiment-only pressure, 30–300 s and 1–8 workers, explicit acknowledgement and cleanup; not a unified adapter or measured-effect verifier |
| Producer | `engine/runtime/src/runtime/processes/` and `launchers/` | Existing process/session ownership and camera launch; inspect cancellation/cleanup before reusing in an experiment runner |
| Producer | `engine/runtime/camera_trace*.py`, `camera.py` | Bounded trace lifecycle and shutdown export; no interactive fresh post-warm-up recording reset |
| Producer | `apps/web/src/features/player/observability/` | Browser callback evidence and explicit finish/export; current recording cannot restart after export without a new collector |
| Producer | `apps/web/src/features/research-mode/researchRunConfig.ts` and player research exporters | Existing healthy/degraded/relief research phases; N5 warm-up/probe/recovery/cooldown need an additive manifest, not v2 enum reinterpretation |
| Producer | `scripts/lan/`, `scripts/hosted/`, `scripts/web/` | Smoke/interaction tools and cleanup helpers; successful smoke/fault startup is not verified scenario ground truth |
| Core | `src/latency_fingerprinting/observability/`, analytical-v2 APIs | Strict offline artifacts/inspection and matching boundaries; experiment phases/actions cannot silently become N3 features |

All producer paths above are in the sibling testbed. The core must not gain a
runtime dependency on that checkout. At Step 1, N5 had no approved fault adapter matrix yet:
network shaping privileges, encoder/render controls and client pressure all need
actual ownership/effect inspection in Step 2. Existing smoke scripts are references,
not authorization to run live hosted calls or alter host networking in this step.

### Contract decisions required next at Step 1 (historical)

Freeze separate experiment identity/versioning; phase boundaries and monotonic
clock scope; requested actions versus executed/verified effects; support states;
bounded duration/worker/resource budgets; cancellation/restoration/crash recovery;
seeds and independent repeat/reference/query assignments; sanitized artifact paths,
hashes and byte/row/depth bounds. Author independent arithmetic/lifecycle examples.

N4 traces are capped at 2000 frames/10000 events across lifetimes. A multi-phase
run can exceed those ceilings at full sampling. Step 2 subsequently declared artifact scopes
and sampling/phase budgets; never enlarge frozen N4 limits to hide overflow or
pool independently restarted clocks. Preserve earlier research phase meanings.

### Remaining runtime and verification gates

Docker and Python 3.11 are absent from the current command path. No actual Linux
Xvfb/PulseAudio capture with a draining receiver, real browser callbacks/picker,
paired overhead measurement, producer Node 24 or hosted verification was run.
The [N4 live acceptance ledger](../observability/N4_RUNTIME_ACCEPTANCE.md) retains
all criteria and the recording-control gap. N5 can address the shared runner/control
in Step 4, but its baseline does not pass those gates.

Phase 1.3 still requires at least two real single-bottleneck classes with repeated
runs and held-out queries. Existing controlled artifacts and synthetic fixtures do
not newly establish those results. Mixed/changing scenarios wait for stable single
causes; no scientific calibration or Phase 1 completion is claimed.

Documentation check: 726 core and 32 producer local targets resolve; both trees
pass whitespace checks. N4 plan/progress/closeout/audit were archived with links
updated. Normative N4
contracts, usage/integration guides, schemas and fixtures remain current.

**Step 1 handoff (historical):** Step 2 scenario/phase/evidence/cleanup contract and independent examples.

## Step 2 — Frozen experiment/evidence and cleanup contract

The [contract](N5_EXPERIMENT_CONTRACT.md), [capability matrix](N5_ADAPTER_CAPABILITIES.md)
and [independent examples](N5_EXPERIMENT_EXAMPLES.md) specify three additive roots,
immutable planned manifest versus executed result, raw phase intervals, six-phase
order/timing, bounded CPU actions, integer effect thresholds and verified cleanup.
Available adapter preflight is separate from action startup, measured effect and
scientific causality. Healthy/host contention are approved for implementation;
other fault classes and mixed/changing scenarios are explicitly unsupported in v1.

Fresh post-warm-up/per-phase N4 collector control remains Step 4. Planned phase
budgets must fit unchanged N4 caps, with no clock bridging. The producer must add
owned-worker CPU evidence and bounded lease/journal/reap/restore; existing smoke
cleanup and core pressure joins do not already satisfy that contract. Six complete
phase-evidence files are required for a completed run; timing gaps cannot be filled.

Independent arithmetic covers 30→24→30 fps with 60% one-core pressure, inclusive
28.5 fps/50% thresholds, inadequate baselines, unobserved faults/recovery, partial
or reset/gapped counters, cancellation, restoration failure, unsupported adapters,
trace capacity and reference/query leakage. Examples run no live pressure and do
not create or refresh pinned fixtures. Independent Fraction arithmetic verifies
nominal/boundary values and capacity. All 753 core and 32 producer local
documentation targets resolve, and both trees pass whitespace checks.
The unchanged Step 1 full-suite numbers are historical baseline results, not a new
suite execution in this specification step. No new models/schemas/runner/CLI existed at Step 2.

**Step 2 handoff (historical):** Step 3 strict additive models/schemas and independent validation tests.
V1 alone does not meet Phase 1.3's two real bottleneck classes. N4 real/overhead and
actual minimum-version/hosted evidence remain pending.


## Step 3 — Strict additive models, schemas and generic validation

[Model/API guide](N5_EXPERIMENT_MODELS.md) documents the three public roots,
required strict fields, frozen instances/tuples and revalidated copies, closed
scenario/adapter vocabulary, exact integer phase/recording budgets, actual
contiguous counter coverage, execution/action/cleanup consistency and sanitized
artifact references. Generic `validate` accepts each root through duplicate-safe,
size/depth-bounded JSON and existing canonical output. All fifteen exported
schemas reproduce; the twelve prior schemas remain byte-for-byte unchanged.

The 155 independent regressions use hand-authored Step 2 tables rather than
production exporters or an effect calculator. They cover complete, partial,
unavailable, cancelled, unsupported and failed-effect/cleanup states, strict
numeric/version/identity bounds, required and extra fields, container preflight,
mutable copied instances, JSON Schema shape and isolated subprocess CLI imports.
Artifact hashes/bytes in these shape examples are explicit placeholders, not
runtime evidence or new release pins.

Cross-root hashes, requested/actual agreement, artifact provenance/clock ownership
and effect thresholds from sufficient complete evidence require Step 6 inspection;
standalone validation cannot certify them. No runtime runner/control, live fault,
measurement or producer source change is introduced here. Both repositories' current
plan/readme/handoff documents now point to Step 4; historical Step 1/2 outcomes
remain labelled. Fixture pinning remains Step 7.

### Step 3 verification

Final full core suite: **1900 tests pass / 93.91% branch-inclusive coverage** under
Python 3.13.13, unchanged 85% floor. All 155 new N5 cases pass. Ruff lint/format,
dependency consistency, fifteen schema exports, canonical registry and N1/N2/N3/N4
pinned reproduction pass. Original P0 synthetic fixtures, five controlled roots,
both executed probes, the run-001 seed and exact run-002 match bytes are preserved.
No existing fixture, policy, registry or schema release was changed.

All 742 core and 24 producer local documentation targets outside fenced examples
resolve; both trees pass whitespace checks. Producer runtime code/dependencies
are unchanged, so Step 1 producer full-suite/build results remain historical,
not a Step 3 rerun. No actual minimum-version or hosted execution was performed.

**Step 3 handoff (historical):** Step 4 bounded producer lifecycle, resource ownership/cancellation and fresh recording control.
N4 runtime/overhead, minimum-version/hosted and two real bottleneck-class gates
remain pending.


## Step 4 — Bounded producer lifecycle, ownership and fresh recording

[Lifecycle guide](N5_RUN_LIFECYCLE.md) and the producer guide describe a stdlib-only
single-use runner, immutable bounded local plans, actual six-phase offsets,
continuous degraded/probe counters, fixed recording budgets and explicit
cancellation/deadlines. A private no-follow exclusive lease and atomic journal
record exact resource/generation intent before runtime mutation. Dirty intent
requires explicit recovery; unknown/foreign resources are never restored by guess.
Restoration failures retain the run and attempt other owned resources within a
cooperative ten-second release budget. Pressure stop/restoration must precede
recovery and fit the declared action duration. Setup is bounded before warm-up's
origin; final private watchdog times are not public N5 clock evidence.

The actual camera now exposes a local single-peer recording-owner API. A bounded
IDLE source barrier retires old callbacks and creates fresh collectors/clocks for
healthy/degraded/probe/recovery. Private admission floors reject stale queued
buffers; exact failed registration/removal handles survive for cleanup retry.
The barrier spans phase rotation and releases during close; default disabled
tracing remains unchanged. Both runtime image COPY lists ship the modules. Warm-up
is separate and cannot be relabelled; phase export/inspection remains Step 6.

At the Step 4 handoff, concrete workload/draining-peer and native worker
identity/handshake/TERM/KILL/reap adapters remained Step 5 (delivered below). The scheduler requires trusted cooperative hooks and
cannot preempt arbitrary blocking Python/GI code. The private execution structure
is not an exported ExperimentResult and contains no verified-effect assertion.
No actual process injection, Linux pipeline, container build or measured trial
was run. Synthetic source rotation is not measured overhead acceptance.

### Step 4 verification

Final full producer suite: **716 Node tests pass**, one existing external-artifact
engine skip (717 discovered): 185 API, 135 engine, 245 web, 90 desktop and 61
smoke/security. The engine wrappers execute **70 Python cases**: 50 trace/control
and 20 lifecycle/lease, including actual runner→collector integration with fake
pads. Cases cover strict budgets and capacity, fractional intervals, cancellation,
setup origin, pressure-stop allowance, clock/counter/worker/generation failure,
duplicate ownership, restart recovery, missing barriers and cleanup retry.
Whole-workspace lint/lockfile checks and final engine lint/build pass. Python
syntax compilation and focused Ruff lint/format pass for the new modules/tests.

Actual synthetic producer host/browser/unsupported-API exporters still reproduce
all frozen N4 record/summary pins through core API and CLI adoption/inspection.
Core schema drift and lint checks pass; no core source, schemas, registry, policy
or fixtures changed. The last full core count remains Step 3's 1900/93.91%, not a
new full-suite run. API typecheck/production web build from Step 1 remain historical;
actual minimum-version, hosted and live Linux evidence remain pending.

Both trees' documentation links and whitespace checks pass. Current readmes,
architecture, capabilities, model guides, inherited N4 ledger and next plan agree.

**Step 4 handoff (historical):** Step 5 concrete healthy/owned host-CPU adapters, native process ownership,
bounded reaping, raw worker/frame counters and fixed measured-effect predicates.
Four N5 steps remained at this handoff. Unsupported classes cannot count toward Phase 1.3's two
real bottleneck-class gate; inherited N4 real/overhead acceptance remains open.


## Step 5 — Supported camera/native adapters and fixed measured effects

[Supported adapter guide](N5_SUPPORTED_ADAPTERS.md) and the producer guide describe
actual camera hooks for one existing draining Linux peer, read-only preflight,
fixed actual caps/configuration, visible affinity/cgroup allocation, source progress
and owned high-resolution process CPU clocks. Workload identity/seed and engine
Node version are explicit campaign-owner declarations, not inferred scene proof.
Plan/recording generation changes fail closed; retired camera callbacks cannot
increment a replacement peer's counters. Healthy launches no workers.

Trusted native children stay parked until all exact boot/start/PID identities are
durably recorded. Native pidfds are pinned before generation checks and signals.
Bounded TERM/KILL/exit/reap keeps exact partial-startup handles, attempts owned
workers, preserves dirty failures and rejects foreign PID reuse. Restart cleanup
checks actual native state rather than trusting a stopped declaration. Native-only
restoration does not certify unknown workload/GI ownership. EOF/park timeout and
an independent active watchdog bound orphan pressure; owner SIGKILL cannot promise
whole-runtime restoration. Only prior clean native sidecars are pruned on the next
run, keeping private retention bounded.

The immutable private effect calculator consumes covered integer intervals and
uses exact threshold comparisons, separately from startup and run completion.
Independent nominal/boundary/failure totals exercise baseline → pressure →
degradation → recovery priority and adapter → incomplete → cleanup → evidence
unavailability. No unavailable rates are fabricated. Hash/cross-root verification,
public experiment export and detached recomputation remain Step 6.

### Step 5 verification

Full producer suite: **716 Node passes**, one existing external-artifact engine
skip, with unchanged 185/135/245/90/61 API/engine/web/desktop/smoke counts. Final
engine checks include **100 passing nested Python cases**, plus one Linux-only
parked-child integration skip: 50 trace/control cases and 50 scenario cases pass
(51 scenario cases discovered). Native/Gst failure tests use fake dependencies;
no GO is sent by the Linux idle integration case. Workspace lint/lockfile checks,
engine build, Python syntax and focused Ruff checks pass. Actual synthetic N4
producer exports still reproduce all frozen records/summaries through core API/CLI.
All four core reproduction modules, schema drift, Ruff and all 155 focused N5
core model regressions pass; no core source,
schemas, registry, policy or fixtures changed. Step 3's 1900/93.91% remains the
historical last full core suite, not a new full run. Step 1 API typecheck/web build
and actual minimum-version/hosted checks retain their prior scope/status.

Both repositories' current documentation and the next plan now point to Step 6.
No live pressure, Linux/GI capture, container build or measured overhead was run.
Additional real fault classes, independent repetitions/held-out separation and
all inherited N4 gates remain open.

**Step 5 handoff (historical):** Step 6 producer export and bounded detached adoption/inspection.
Three N5 steps remain; software adapter support is not live runtime acceptance.

## Step 6 — Producer export and detached linked inspection

**Local software gate:** Complete, 2026-10-11.
[Export/inspection guide](N5_EXPERIMENT_INSPECTION.md) documents the delivered APIs,
container bounds and silent `inspect-experiment` command. Producer export retains
actual raw integer intervals, distinct frozen measured-phase collectors, failed or
aborted runs, unsupported adapters and unknown cleanup offsets without copying
private journal/native/watchdog data. Optional old observation roots retain their
original identities, clocks and phases.

Core inspection checks exact members, duplicate-safe JSON, hashes/lengths, phase
and action ownership/timing, counter continuity, producer/provenance/version and
trace policy. Independent integer predicates recompute effects and reject supplied
contradictions. Inputs remain pinned/no-follow; archive extensions and special files
reject without extraction. Outputs are private and atomic; errors are fixed and
preserve existing files. Lazy API loading keeps standalone contract imports free
of the pipeline/model import cycle.

### Step 6 verification

The full core regression run passes **1,932 tests, 93.67% branch-inclusive coverage**.
Seven subsequent independent boundary/resource tests also pass; the final focused
bundle suite is **39 passing cases** and combined coverage is **93.77%**. In total,
**1,939 distinct core tests** were verified. Core Ruff check/format, fifteen schema
checks, registry, P0/N1/N2/N3/N4 read-only pins and actual synthetic N4 producer→core
API/CLI reproduction pass without refreshing any release bytes.

Producer full workspace tests pass **716 Node tests**, with one existing external
artifact skip. Nested Python verification passes **106 cases** (50 trace/control,
56 scenario), with one Linux-only idle-child skip. Workspace lint and focused
Python Ruff/format checks pass. Six actual synthetic producer exports pass core
API and CLI: healthy, host contention, failed pressure, unavailable runtime,
missing traces and unknown cleanup timing. No live pressure or real capture ran.

Earlier implementation sections record historical handoffs; their future Step 6
requirements are delivered here. No released N5 fixtures/pins exist yet. Real
capture/overhead, native Linux execution, actual minimum versions, container and
hosted execution, held-out source independence and Phase 1.3's second fault class
remain unverified.

**Step 6 handoff (historical):** Step 7 independent fixtures/pins and cross-repository reproduction.
At that handoff two steps remained; Step 7 is delivered below.

## Step 7 — Independent fixtures/pins and cross-repository reproduction

**Local software gate:** Complete, 2026-10-12.
[Fixture release 1.0.0](N5_EXPERIMENT_FIXTURES.md) adds eight independently authored
synthetic cases: healthy, host, inclusive boundary, failed pressure, cancelled
partial run, unsupported runtime, missing traces and unknown cleanup timing.
The 80 JSON files total 280,156 bytes. Explicit phase/effect/cleanup expectations
and N4 boundary/capability expectations were authored separately from production
export or effect calculation. Sparse tracing keeps the corpus compact without
claiming real tracing coverage. Every fixture byte and exact file inventory are
pinned; the checker has no refresh mode and keeps expectations outside bundles.

The producer's `scripts/n5/exportSyntheticExperiments.py` supplies fixed synthetic
integer execution inputs to actual fresh collectors and production export. All
eight cases reproduce every independent uncompressed member byte, core linked
adoption/effect verification and canonical API/CLI output. Producer regressions
separately pin sorted member-name/hash-map digests, repeated-export determinism
and CLI/private-output behavior. Gzip header hashes are excluded for Python-version
portability. Both configured core CI jobs run the read-only N5 gate; producer
scenario discovery includes its reproduction tests. No hosted run is claimed.

### Step 7 verification

The full core suite passes **1,950 tests, 93.77% branch-inclusive coverage**, including
11 new release/independent-expectation/producer-drift cases. Ruff check/format and
installed dependency checks pass. All fifteen schemas, registry, P0/N1/N2/N3/N4
pins and actual synthetic N4 producer→core reproduction remain current unchanged.
Actual N5 producer export→core API/CLI reproduction passes all eight cases.

Producer full tests pass **716 Node tests**, with the existing external-artifact
skip. Nested Python verification passes **109 cases**: 50 trace/control and 59
scenario cases, with one additional Linux-only idle-child skip (60 discovered).
Three new producer reproduction tests pass. Workspace lint/lockfiles, engine build,
API typecheck and production web build pass; focused new Python Ruff/format checks
pass. Local documentation links and whitespace checks pass in both repositories.
No live workload, pressure, GI capture, container build, actual minimum-version or
hosted execution was performed. Existing runtime limits and open gates are retained.

**Step 7 handoff (historical):** Step 8 real repetitions and separate software/runtime/hosted closeout.
At that handoff one planned step remained. An actual Linux testbed, inherited N4 capture/overhead
acceptance and a second supported real bottleneck class are still required; these
synthetic fixtures cannot pass Phase 1.3 or establish held-out source independence.
Archive active progress/plan only on the subsequent slice transition.

## Step 8 — Software closeout and explicit pending runtime acceptance

**Recorded:** 2026-10-12. [Software closeout](N5_SOFTWARE_CLOSEOUT.md) publishes the
local software outcome separately from [live acceptance](N5_RUNTIME_ACCEPTANCE.md).
Both checkouts started clean at the Step 7 commits recorded in the closeout. This
step changes documentation only; the latest full regression/build counts remain
the actual Step 7 results. Closeout read-only N5 fixture, fifteen-schema and registry
checks pass; both repositories' current documentation links and whitespace pass.

The actual producer Linux camera adapter preflight on this Darwin host returns
`unavailable / runtime_unavailable`, with zero runtime fields, no acquired resources
and no prepared plan. Docker is absent; no Linux connection/testbed or N5 real
campaign artifacts are available. Existing controlled-real P0 runs cannot be
relabeled into N5. Node reports 26.4.0 and Python 3.14.4, not minimum-version
execution. A GStreamer version probe hung on macOS service initialization and was
terminated; no pipeline or fresh GStreamer version result is claimed.

No live camera, workload, native pressure or network change was performed. Real
healthy/host repetitions, acquisition assignments/held-out separation and all
inherited N4 capture/coverage/overhead gates remain pending. V1 supports only one
fault class at that initial closeout; the subsequent additive capture-pacing
extension below delivers the second adapter. Healthy does not satisfy that requirement. Container,
actual minimum-version and hosted execution remain unverified.

**Remaining:** Step 8 runtime acceptance; N5/Phase 1 are not complete. Local software
is closed out and the exact runtime dependencies are recorded. Keep the active
plan/progress and current normative guides until the subsequent slice transition,
when their archival is due. No N6 plan is substituted for unmet acceptance.

## End-to-end coding extension — campaign entry, second control and overhead

**Delivered in software:** 2026-10-12. [Workflow specification](N5_CAMPAIGN_WORKFLOW.md)
and the producer live test guide make the existing library usable from an opt-in
Pixelated engine. The earlier closeout was limited to Step 1–7 libraries/synthetic
handoffs; it did not finish these operator-facing coding surfaces.

Capture pacing uses three additive v2 roots and `n5-capture-pacing-v1`, preserving
all original v1 schema/fixture/policy bytes. A scoped 50 ms identity-element delay
has an exact-owner restoration watchdog and raw stage-delay/FPS predicates. The
core recomputes effects independently; requested settings do not count as measured
verification. Normal startup installs no new element, worker, flags or evidence
volume. Explicit desktop research startup retains nonroot/read-only/capability
isolation and adds a private persistent evidence volume.

The producer freezes bounded reference/query schedules and distinct acquisition
IDs before execution, requires an engine-owner workload/seed declaration and the
observed parent Node version, rejects replay/dirty ownership, supports cancellation,
retains unavailable/failed prefixes, and rearms only new source admission/recording
lifetimes. Missing preflight values never become invented bundle runtime metadata.
The core checks schedule/receipts/windows and every trial; source independence
remains externally verified and no features/Phase 1 acceptance are promoted.

A separate overhead request runs the frozen five alternating disabled/enabled
pairs, raw camera-process CPU/FPS counters, fresh enabled traces, export times and
explicit bounded callback diagnostics. The inspector uses exact rational medians,
checks every baseline, hash/coverage/drop count, order, diagnostic sample count and
cleanup. A smaller trace denominator cannot hide missing encoded-frame coverage.
Model/schema imports are separate from inspectors to prevent schema/registry
import cycles and keep these modules bounded.

### Local coding verification

- Full core suite: **1,978 passed, 93.48% branch-inclusive coverage**. Independent
  pacing/campaign/overhead cases cover exact thresholds, unobserved requested delay,
  strict actions/source assignments, drift, unsafe paths and preserved outputs.
- Producer full suite: **718 Node passed**, including two new desktop research
  opt-in/isolation tests; the existing external-artifact engine skip remains.
  Final nested Python checks: **129 passed** (54 trace/control and 75 scenario),
  with one Linux-only idle-child skip. The last added CLI validation test was
  rerun through the engine wrapper after the full workspace run.
- Core Ruff/format, producer workspace lint and desktop/engine builds pass.
  Focused new Python style/syntax and final source checks pass. All 23 schemas,
  registry and original read-only releases remain current; original v1 actual
  producer exports still match all eight pinned cases byte for byte.
- Actual producer pacing exports pass core API/CLI for verified delay, unobserved
  delay and unknown cleanup, using fixed synthetic collector inputs. No real
  pacing, pressure, capture, Docker image build or acceptance run was performed.
- Both repos' current local documentation links and whitespace checks pass.

**Remaining work is live testing:** use the producer's one test procedure with a
Linux engine inside Docker Desktop or a separate Linux machine, then retain all
real outcomes and the inherited N4 special/browser cases. Actual minimum-version,
container/hosted runs and externally verified held-out source separation remain
pending. The second adapter is now coded; its real effect/restoration still needs
validation. N5/Phase 1 acceptance is not completed by this coding extension.


The [script/CI hardening pass](../../experiments/phase-1-script-ci-20261016/README.md)
splits the remaining large utilities, repairs owned cleanup/validation gaps and
adds full producer regression/deploy gating plus isolated core wheel verification.
The current checks pass locally; new hosted execution and manual sign-off remain open.
