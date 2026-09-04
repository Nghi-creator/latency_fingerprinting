# Latency Fingerprinting: Full Implementation Plan

**Status:** Full post-P0 roadmap through production and final evaluation  
**Updated:** 2026-09-04  
**Starting point:** The offline P0 path is complete and hardened. Diagnosis accuracy,
live probing, recovery benefit, and transfer remain unproven.

This document defines the complete sequence of major slices required to finish
the engine. It intentionally stays at roadmap level. The implementation-ready
plan for only the active slice lives in
[`NEXT_IMPLEMENTATION_PLAN.md`](NEXT_IMPLEMENTATION_PLAN.md).

## Outcome to build toward

The next system should move from a repeatable offline response matcher to a
safe, evaluable latency diagnosis and control engine:

```text
cross-layer observation
-> persistent-degradation gate
-> passive hypothesis set
-> bounded informative probe when needed
-> single or mixed bottleneck estimate
-> capability-aware corrective action
-> post-action outcome verification
-> trusted fingerprint update or rollback
```

A separate fast loop should prevent stale frame work while the slow diagnosis
loop operates:

```text
frame timestamp + deadline budget
-> predicted completion/slack
-> enqueue, replace stale work, or preserve minimum cadence
```

## Implementation principles

- Keep the Python engine offline or on the slow control path. Per-frame policy
  stays in the capture/GStreamer process.
- Version any change to metric meaning. Never compare old and new feature
  semantics under one compatibility group.
- Preserve raw per-run traces. Aggregates alone are insufficient for tail
  latency, variance, sensitivity analysis, or later reprocessing.
- Use deterministic safety rules for probes and actions even if ML is added.
- Treat `unknown`, rollback, and no-action as first-class outcomes.
- Split evaluation by complete run/session, node, workload, or scenario; never
  randomly split frames from one run across train and test data.

## Phase 1 — Measurement contract v2 and experiment foundation

This phase begins with the registry and aggregation foundation specified in
[`NEXT_IMPLEMENTATION_PLAN.md`](NEXT_IMPLEMENTATION_PLAN.md). Better matching
is premature until features have stable timing and scientifically consistent
semantics. Observation-v2 adoption and new instrumentation follow as later
slices within this phase.

### 1.1 Version metric semantics

- Define `observation-v2` and a metric registry containing feature name, unit,
  aggregation, source, sampling cadence, missing-data policy, and version.
- Replace ambiguous cumulative-counter features with one declared meaning:
  preferably a rate such as frames/second for cadence comparisons, while also
  retaining total window deltas for audit.
- Migrate `frames_decoded`, `frames_dropped`, freezes, and encoder frame
  counters. P0 currently stores median interval deltas; do not silently mix
  those values with totals or rates.
- Add capture-method and feature-registry versions to compatibility checks.
- Provide an explicit P0-to-v2 migration tool only where raw traces exist.
  Frozen P0 records without raw data remain P0 records.

Exit gate: two records cannot match when a feature name has different sampling
or aggregation semantics.

### 1.2 Add stage-level observability

- Introduce stable session, frame, and trace identifiers.
- Record monotonic timestamps at render-ready, capture, pre-encode,
  post-encode, sender enqueue/send, receive, decode, render, and display proxy
  points where available.
- Measure capture and encoder queue depth/sojourn time, encode duration, sender
  pacing/queue indicators, decoder work, freezes, and rendered/dropped frames.
- Derive frame age, remaining deadline slack, deadline-hit status, and stale
  work. Document every unavailable stage.
- Record clock domain, clock error assumptions, feedback delay, sampling
  cadence, and instrumentation overhead. Do not claim exact one-way latency
  without measured synchronization error.
- Add GPU/render and hardware-encoder adapter interfaces, but make claims only
  after real hardware validation.

Exit gate: a sanitized bundle can reconstruct stage-local timing and explain
which latency components are observed, estimated, or unavailable.

### 1.3 Build a reproducible scenario harness

- Automate healthy, host contention, render/capture slowdown, encoder overload,
  delay, jitter, loss, bandwidth pressure, and client decode pressure.
- Add mixed and changing scenarios after each single cause is stable.
- Verify ground truth from measured effects, not only from successful fault
  injector startup.
- Capture warm-up, degraded, probe, recovery, and cooldown windows with one
  machine-readable experiment manifest.
- Record random seeds, tool versions, node state, workload procedure, action
  timing, and checksums.
- Run enough independent repetitions to estimate within-scenario variance.

Exit gate: at least two real single-bottleneck classes have repeated runs and
held-out queries, with no source run reused as its own fingerprint query.

## Phase 2 — Calibrated diagnosis and safe probes

### 2.1 Replace point fingerprints with robust profiles

- Store repeated response distributions rather than one point vector.
- Estimate robust center, dispersion, feature availability, and covariance when
  sample size supports it.
- Learn or set feature weights from repeatability and discriminative value;
  zero-weight features never satisfy evidence gates.
- Add fingerprint lifecycle state: created, provisional, trusted, stale,
  rejected, and superseded.
- Expire or isolate fingerprints after material context, driver, encoder,
  workload, or measurement-contract changes.
- Add a small persistent store only when multiple calibration runs require
  lifecycle queries; SQLite is sufficient before any service architecture.
- Separate the automatically retained observation archive, quarantined
  fingerprint candidates, and fingerprints eligible for production matching.
- Accept labels only from declared evidence such as controlled fault injection,
  externally confirmed root cause, or independently verified outcomes. Never
  promote the matcher's own prediction as self-confirming ground truth.
- Require source-run exclusion, independent repetitions, provenance, audit
  history, and reversible promotion/rejection decisions.

Exit gate: thresholds and weights are derived from calibration data and tested
on held-out complete runs, with sensitivity analysis.

### 2.2 Add passive anomaly and hypothesis gating

- Define healthy baseline distributions per compatible context.
- Require persistent degradation with hysteresis before probing.
- Use passive evidence to narrow the candidate causes and decide whether a
  probe is necessary.
- Separate crashes/disconnections from latency diagnosis; they retain the
  existing failure/restart path.
- Report likely causes, missing evidence, and why probing was or was not
  selected.

Exit gate: transient spikes do not trigger probes, and `unknown` remains the
result when passive and active evidence are insufficient.

### 2.3 Implement the first safe live probe families

Start with three independently controlled relief probes:

1. bitrate relief;
2. capture/FPS or latest-frame-wins relief;
3. encoder-cost relief when live encoder mutation is verified.

For every probe implement:

- capability discovery and preconditions;
- maximum intensity, duration, frequency, and cumulative disturbance budget;
- before/during/after windows and explicit application timestamps;
- abort conditions for latency, quality, connection, or runtime health;
- guaranteed rollback, rollback verification, cooldown, and stable fallback;
- measured quality cost and probe overhead;
- idempotency and crash-safe cleanup.

Exit gate: failure-injection tests prove that every partial application either
rolls back or leaves a visible, recoverable `not_restored` outcome.

### 2.4 Extend the analytical matcher

- Add uncertainty intervals and label-level aggregation across repeated
  fingerprints.
- Evaluate robust standardized distance and Mahalanobis-style distance only
  when covariance estimates are well-conditioned.
- Represent mixed bottlenecks using a non-negative response mixture or sparse
  sensitivity model; retain `unknown` when decomposition is unstable.
- Add sequential probe selection based on expected information gain minus
  disturbance cost.
- Calibrate confidence only after enough held-out data exists. Until then keep
  similarity strength clearly separate from probability.

Exit gate: the matcher distinguishes at least two real causes, rejects unseen
and mixed cases conservatively, and exposes evidence that reconstructs every
score.

## Phase 3 — Verified corrective control

### 3.1 Action and capability registry

- Define action contracts separately from probes.
- Register adapter capabilities, limits, expected stabilization time, quality
  cost, interruption cost, resource cost, and rollback support.
- Implement actions in priority order: remove stale/avoidable latency, spend an
  available resource, make a targeted quality tradeoff, then use disruptive
  safety actions.
- Never repeat an ineffective action without new evidence.

### 3.2 Slow-loop controller

- Implement an explicit state machine: healthy, observing, degraded, probing,
  diagnosing, acting, verifying, rollback, cooldown, and failed-safe.
- Persist state transitions and correlation IDs for postmortem replay.
- Score actions by predicted deadline recovery minus quality, interruption,
  resource, and uncertainty costs.
- Verify every action in a recovery window and create a `ValidatedOutcome`.
- Update a fingerprint only after a trustworthy, non-confounded outcome.

Exit gate: controlled tests show cause-specific actions outperform a generic
"lower everything" action on at least one predeclared recovery/quality metric.

### 3.3 Fast deadline scheduler

- Define deadline budgets and remaining-cost estimates close to capture.
- Compare FIFO, bounded FIFO, and capacity-one/latest-frame-wins before encode.
- Cap consecutive drops and preserve minimum visual cadence.
- Preserve audio synchronization, input delivery, and codec/keyframe safety.
- Log drop reason, predicted saved latency, and actual downstream outcome.
- Escalate persistent deadline misses to the slow loop; do not call Python per
  frame.

Exit gate: stale-frame age or tail latency improves without unacceptable
cadence, visual quality, codec, or audio regressions.

### 3.4 Local integration boundary

- Define a local authenticated IPC protocol between Pixelated adapters and the
  slow engine only after the offline controller is stable.
- Include schema negotiation, capability advertisement, idempotency keys,
  deadlines/timeouts, health, and backpressure.
- Keep tokens and raw peer identity out of exported research artifacts.
- Preserve Pixelated pairing, launch, multiplayer, revoke, and failure flows.

### 3.5 Autonomous fingerprint and outcome lifecycle

- Record every valid probe observation automatically without treating every
  observation as a fingerprint.
- Create quarantined candidates only when label evidence and lineage satisfy a
  declared policy.
- Corroborate candidates across independent runs and reject self-evaluation,
  duplicate evidence, incompatible contracts, and circular labels.
- Promote, supersede, expire, or reject candidates through an auditable state
  machine with deterministic policy versions.
- Keep production matching on an atomic repository snapshot so an incomplete
  update cannot alter an in-flight decision.
- Persist `ValidatedOutcome` records for successful, ineffective, aborted, and
  rolled-back actions; do not learn only from successes.

Exit gate: an unattended controlled deployment can collect observations and
manage candidate lifecycle without a terminal while being unable to silently
self-label or promote circular evidence.

## Phase 4 — Comparative evaluation

Implement reproducible modes for:

1. fixed configuration;
2. threshold adaptation;
3. passive telemetry classification/control;
4. fingerprinting without deadline scheduling;
5. fingerprinting with deadline scheduling;
6. an oracle that knows the injected cause, for an upper-bound comparison.

Measure:

- diagnosis precision/recall/F1 where appropriate, false diagnosis, and
  `unknown` rate;
- calibration error only for calibrated probabilities;
- time to detect, diagnose, act, and recover;
- P50/P95/P99 frame age or latency and deadline miss rate;
- ineffective actions, rollbacks, oscillations, and stability failures;
- FPS, bitrate, drops, freezes, visual/temporal quality, and quality preserved
  per millisecond recovered;
- probe count, duration, overhead, and user-visible disturbance.

Hold out complete sessions and then progressively harder contexts: scenario,
workload, client, node, software encoder, and hardware encoder. Predeclare
metrics and stopping rules before making comparative claims.

Exit gate: the final claim is limited to the tested contexts and supported by
reproducible traces, scripts, statistical intervals, and baseline comparisons.

## Phase 5 — Optional ML gate

Add a small model only if the deterministic baseline demonstrates a specific held-out failure:

- nonlinear or overlapping response profiles;
- poor cross-context transfer;
- inefficient next-probe choice;
- inaccurate action outcome/cost prediction.

Compare the model with the analytical matcher, include inference cost, keep
probe/action safety deterministic, and remove it if it does not improve a
predeclared held-out metric. LLMs, unrestricted online learning, deep models,
and reinforcement learning do not belong in the first runtime controller.

## Phase 6 — Production hardening and unattended operation

- Package the slow engine as a supervised local process or embedded service
  with authenticated local IPC, bounded queues, timeouts, health checks, and
  explicit startup/shutdown recovery.
- Add durable schema migrations, repository backup/restore, corruption
  detection, atomic writes, retention limits, and storage-pressure behavior.
- Define least-privilege runtime permissions. Keep credentials, peer identity,
  private paths, and raw sensitive telemetry outside exported research data.
- Add structured logs, metrics, traces, decision replay, and operator-visible
  explanations for probes, matches, actions, rollbacks, and fingerprint state
  changes.
- Test crash recovery at every controller state, lost acknowledgements,
  duplicate commands, stale responses, adapter restarts, engine restarts,
  storage failures, and partial upgrades.
- Bound CPU, memory, disk, network, and telemetry overhead and verify that the
  engine cannot become a material source of latency.
- Support safe configuration rollout, version negotiation, compatibility
  isolation, downgrade behavior, and rollback to the previous known-good
  engine/repository snapshot.
- Keep the CLI as a replay, diagnostics, export, and administrative interface;
  routine deployed operation must not require terminal commands.

Exit gate: the engine survives restart and partial-failure drills, stays within
declared resource budgets, and operates end to end without manual terminal
steps.

## Phase 7 — Final evaluation and project closeout

- Freeze the evaluated software, contracts, registry, controller policy,
  fingerprint snapshot, scenarios, and experiment manifests.
- Run all declared baselines and ablations on held-out complete runs.
- Publish reproducible tables, plots, uncertainty intervals, failure cases,
  resource overhead, disturbance cost, and validity limitations.
- Verify every claimed result against immutable evidence and distinguish
  engineering feasibility, controlled-test findings, and generalization.
- Produce deployment, operations, rollback, privacy, security, data-retention,
  API, and architecture documentation.
- Preserve machine-readable artifacts, checksums, environment versions, and
  exact reproduction commands.

Exit gate: another engineer can reproduce the supported claims, deploy the
bounded engine, inspect every decision, and recover it safely within the stated
scope.

## Definition of finished

The engine is complete only when all of the following are true:

- measurement meanings are versioned and incompatible meanings cannot mix;
- degradation detection resists transient noise and unnecessary probing;
- probes and actions are bounded, reversible, and crash-safe;
- diagnosis distinguishes the evaluated causes and returns `unknown` outside
  supported evidence;
- remediation is verified against latency, quality, stability, and resource
  cost rather than assumed successful;
- fingerprint candidates cannot self-label, self-test, or bypass promotion
  policy;
- slow control and fast deadline handling integrate without placing Python on
  the frame-critical path;
- unattended operation has durable state, observability, security, upgrade,
  and recovery procedures;
- comparative claims are supported by held-out reproducible evaluation; and
- all remaining limitations are explicit.

The current implementation-ready work is specified in
[`NEXT_IMPLEMENTATION_PLAN.md`](NEXT_IMPLEMENTATION_PLAN.md). Dashboard work,
a hosted service, unrestricted online learning, and ML/RL remain out of scope
until measurement semantics, safety, and deterministic baselines justify them.
