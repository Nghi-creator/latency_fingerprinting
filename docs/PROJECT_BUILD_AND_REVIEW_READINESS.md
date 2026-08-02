# Project Build and Technical-Review Readiness

**Project:** Latency diagnosis and optimization mechanisms for heterogeneous edge cloud-gaming systems  
**Immediate milestone:** Complete one executable P0 vertical slice of latency fingerprinting  
**Purpose:** Keep implementation, evidence and technical claims aligned

## Bottom line

```text
versioned testbed record
-> comparable degraded/relief windows
-> response delta
-> normalized response vector
-> stored candidate fingerprints
-> interpretable match or unknown
```

The P0 threshold is:

> The operational testbed and telemetry path exist, the research contract is represented in code, a transparent matcher runs on labeled synthetic fixtures, and one controlled real Pixelated record passes through the same offline pipeline. Performance and generalization claims remain hypotheses.

The detailed build gate lives in [`p0/IMPLEMENTATION_TRACKER.md`](p0/IMPLEMENTATION_TRACKER.md).

## 1. Current project status

### Implemented in the Pixelated testbed

- Self-hosted edge cloud-gaming runtime.
- Desktop orchestration and Dockerized workload host.
- GStreamer capture and VP8/Opus encoding.
- WebRTC media and input paths.
- Lightweight browser client.
- Runtime health snapshots with process-lifetime CPU and current RSS indicators.
- Browser telemetry for FPS, received bitrate, packet loss, jitter and connection state.
- Versioned research-run bundles with metadata, telemetry, lifecycle events, summaries and graphs.

### Specified in this repository

- Frozen P0 research terminology and invariants.
- Detached Python/TypeScript architecture boundary.
- Initial record and JSON Schema design.
- Weighted-distance matcher and conservative `unknown` behavior.
- Pixelated bundle-adapter contract.
- Controlled paired-run experiment procedure.

### Not implemented yet

- Python domain models and generated schemas.
- Window aggregation, response normalization and matching code.
- Synthetic fingerprints and tests.
- Pixelated bundle adapter.
- Controlled real P0 run.
- Live bounded probes and runtime action execution.
- Calibrated confidence, mixed bottlenecks and comparative evaluation.
- Deadline-aware scheduler.

Do not describe planned work as completed.

## 2. P0 build scope

### A. Research contract

Completed in [`p0/RESEARCH_CONTRACT.md`](p0/RESEARCH_CONTRACT.md).

The contract defines context, observation windows, probes, response deltas, fingerprints, match results, `unknown`, validated outcomes and provenance.

### B. Detached Python core

Architecture: [`ARCHITECTURE.md`](ARCHITECTURE.md).

The existing TypeScript/Node system remains responsible for telemetry export, orchestration and future action adapters. Python owns validation, aggregation, normalization, matching, evidence and offline evaluation.

### C. Interpretable matcher

Design: [`p0/DATA_MODEL_AND_MATCHER.md`](p0/DATA_MODEL_AND_MATCHER.md).

P0 uses normalized weighted Euclidean distance because it is transparent and supports a healthy near-zero response vector. The matcher must rank candidates, expose residual evidence and return `unknown` for weak, tied, incompatible or incomplete inputs.

### D. Synthetic fixtures

P0 includes three explicitly synthetic classes:

1. `healthy`;
2. `network_pressure`;
3. `host_encoder_pressure`.

They validate software behavior, not the research hypothesis.

### E. One real integration path

Procedure: [`p0/PIXELATED_ADAPTER_AND_EXPERIMENT.md`](p0/PIXELATED_ADAPTER_AND_EXPERIMENT.md).

The camera profile is currently fixed at launch, so P0 uses controlled paired runs under one stable degradation. This demonstrates real-data integration without claiming live in-session probing.

### P0 exit statement

> Given a compatible context and comparable degraded/relief windows, the Python prototype calculates a normalized response, compares it with three synthetic fingerprints, explains the ranking, and refuses ambiguous evidence. The same pipeline processes one controlled real Pixelated paired-run record.

## 3. Work after P0

### Preliminary evidence

- Add a second real bottleneck class.
- Define a healthy baseline distribution.
- Repeat controlled scenarios to estimate variance.
- Produce a preliminary table or graph.
- Compare with one passive or threshold baseline.

Call this limited engineering validation until the experiment design and sample size support stronger conclusions.

### Automated bounded probe

Turn the paired-run relief change into one safe runtime probe with:

- persistent-degradation precondition;
- maximum intensity and duration;
- before/during/after windows;
- abort condition;
- rollback and cooldown;
- measured probe overhead and quality cost.

One probe will not identify every bottleneck.

### Later thesis mechanisms

- Multiple probe families and informative-probe selection.
- Cause-specific action planning and outcome verification.
- Mixed-bottleneck inference.
- Deadline-aware frame scheduling.
- Broader CPU/GPU, capture, encoder and client instrumentation.
- Cross-node evaluation.
- ML only if the deterministic baseline exposes a concrete limitation.

## 4. Explicit P0 non-goals

Do not expand P0 into:

- a fingerprint database or hosted service;
- autonomous runtime control;
- live encoder mutation;
- GPU or hardware-encoder validation;
- exact cross-device input-to-display measurement;
- mixed-bottleneck decomposition;
- calibrated probabilities;
- deadline scheduling;
- ML or reinforcement learning;
- cross-machine generalization;
- a statistically powered comparison;
- a production dashboard.

## 5. Explanations to keep ready

### Short explanation

> This project studies latency diagnosis in a self-hosted edge cloud-gaming pipeline. It first observes cross-layer telemetry. When several causes remain plausible, it measures how the system responds to a small controlled relief change. That context-specific response pattern becomes a latency fingerprint. The research tests whether matching these fingerprints can identify the active bottleneck and guide a lower-cost recovery more effectively than generic threshold or passive-only approaches.

### Technical walkthrough

Cover these points in order:

1. **Problem:** similar latency symptoms can originate in different pipeline stages.
2. **Limitation:** passive correlation may not reveal which intervention will help.
3. **Mechanism:** collect passive evidence, then use a bounded intervention only when needed.
4. **Fingerprint:** store context, controlled change, normalized response and cost.
5. **Decision:** rank compatible fingerprints and return a match or `unknown`.
6. **Verification:** measure whether the selected action actually improves the stream.
7. **Evaluation:** compare diagnosis, recovery, latency, quality and probe cost with baselines.
8. **Status:** separate implemented mechanisms from hypotheses and planned work.

Do not claim that the project has reduced latency, generalized across nodes or outperformed a baseline until those results exist.

## 6. Technical-review questions

### Research framing

#### What problem is being solved?

The project addresses cross-layer bottleneck diagnosis and cause-specific recovery, not generic bitrate adaptation. Capture, encoding, host contention, transport, client decode and stale queues can produce similar visible latency symptoms but require different actions.

#### What is the research question?

> Can context-specific perturbation-response fingerprints distinguish cross-layer bottlenecks and guide lower-cost recovery more accurately than static, threshold-based or passive-telemetry approaches in heterogeneous edge cloud-gaming systems?

#### What is the hypothesis?

The method should reduce false diagnoses and ineffective actions while restoring frame-deadline compliance with less quality degradation. This remains a hypothesis until comparative experiments support it.

#### What would weaken the hypothesis?

- Response patterns overlap too heavily.
- Probe disturbance exceeds its diagnostic value.
- Fingerprints fail to remain useful inside a declared compatible context.
- Passive or threshold baselines perform equally well at lower cost.
- Hidden variables make results unstable or irreproducible.

These are valid research outcomes, not failures to conceal.

### Fingerprint mechanism

#### What is a latency fingerprint?

It is not one CPU, RTT or FPS snapshot. It represents how metrics change under a declared controlled intervention:

```text
context + degraded condition + controlled change + response delta + cost
```

#### Is probing the novelty?

No. Probing, calibration, adaptive streaming and deadline-aware scheduling already exist. The proposed contribution is their concrete integration into a cross-layer perturbation-response representation with context compatibility, bounded disturbance, conservative matching, action verification and explicit `unknown` behavior.

#### How does it differ from Pudica and Hostping?

- Pudica probes a known network subsystem to estimate utilization and avoid network queues.
- Hostping probes known intra-host RDMA paths and maps anomalies to hardware topology.
- This project begins with an ambiguous end-to-end interactive-streaming symptom and compares response evidence across multiple pipeline domains before selecting a cloud-gaming action.

#### Is this causal diagnosis?

The initial claim is **intervention-informed diagnosis within evaluated contexts**, not unrestricted causal inference. Controlled changes provide stronger local evidence than passive correlation, but hidden variables, delayed feedback and probe overhead remain possible confounders.

### Matching and uncertainty

#### How does the first matcher work?

Explain feature normalization, weighted distance, compatible-feature intersection, coverage, acceptance threshold, top-two margin, residual evidence and `unknown` rules. `matchStrength` is not calibrated probability.

#### How are thresholds selected?

Start with declared engineering defaults for software tests. Later select settings using calibration data and evaluate sensitivity on held-out sessions, scenarios, workloads or nodes.

#### What happens with mixed or unseen bottlenecks?

P0 returns `unknown`. Later work may evaluate fingerprint mixtures or additional probes, but forcing a single class is unsafe.

#### Why not use ML immediately?

The initial dataset is small and context-dependent. An interpretable matcher establishes the baseline and reveals whether nonlinear overlap, transfer or probe selection actually requires ML.

### Experimental design

#### How is ground truth established?

Use controlled experiment-only conditions and verify that the intended stage actually changed. Starting a load generator is not sufficient if it creates no observable pressure or introduces unrelated effects.

#### What are the baselines?

1. Fixed configuration.
2. Threshold adaptation.
3. Passive-telemetry classification/control.
4. Fingerprinting without deadline scheduling.
5. Fingerprinting with deadline scheduling.

Only one simple passive or threshold baseline is needed immediately after P0.

#### What metrics matter?

Diagnosis metrics:

- accuracy/F1 where appropriate;
- false-diagnosis and `unknown` rates;
- time to diagnosis;
- calibration when enough data exists.

Control and experience metrics:

- P50/P95/P99 latency or frame age;
- deadline-hit/miss rate;
- recovery time;
- ineffective actions;
- FPS, bitrate and frame drops;
- visual or temporal quality degradation;
- probe count, duration and disturbance.

Tail metrics matter because averages can hide latency spikes and stale queued work.

#### How is data leakage prevented?

Do not split frames from one session across calibration and test sets. Hold out complete sessions, scenarios, workloads, clients or nodes, and preserve per-run traces.

#### How is cross-device latency measured?

Document monotonic-clock and synchronization assumptions. Do not claim exact one-way latency without measured clock error. Initially prefer stage-local timing, frame-age estimates and external ground truth for selected experiments.

### Safety and control

#### Can a probe worsen the stream?

Yes. Live probes require persistence checks, strict intensity/duration limits, abort conditions, rollback, cooldown and explicit disturbance measurement.

#### Why begin with stream-profile relief?

It is technically accessible, reversible between paired runs and can exercise the response representation. It is not sufficient for every bottleneck and is not yet a live probe.

#### Why not lower bitrate whenever latency rises?

That may help congestion but can unnecessarily damage quality when the bottleneck is capture, encoding, host contention, client decode or stale work.

#### Why separate fingerprinting from deadline scheduling?

Fingerprinting is a slow diagnosis/control loop. Deadline scheduling is a fast data-path mechanism that prevents stale capture work from extending queues while diagnosis occurs.

### Architecture and implementation

#### Why detach the engine from Pixelated?

- The method remains testable offline.
- Pixelated-specific formats stay behind an adapter.
- Other telemetry and runtime implementations can be added.
- The research contribution is separated from one product UI.

P0 detaches at the module and data-contract level; it does not require a service or separate desktop application.

#### Why Python?

Python fits the offline/slow research loop, numerical analysis and later optional ML. Existing TypeScript/Node components continue handling browser telemetry, orchestration and runtime controls.

#### What can currently be observed?

- Browser FPS, received bitrate, packet loss, jitter and connection state.
- Runtime health with process-lifetime CPU and current RSS indicators.
- Versioned run metadata, events, summaries and graphs.

Stage-level encode/capture queues, rich GPU telemetry, decoder internals and exact display timing remain planned.

#### What would a P0 demonstration show?

1. Validate or ingest a versioned record.
2. Show degraded and relief aggregates.
3. Calculate the normalized response.
4. Rank synthetic candidate fingerprints.
5. Display supporting/conflicting evidence.
6. Demonstrate `unknown` on ambiguous input.
7. Process one controlled real Pixelated record through the same path.

A terminal demonstration is sufficient.

### Validity and limitations

The major threats are:

- hardware, workload, codec and client specificity;
- instrumentation and probe effects;
- controlled faults differing from organic incidents;
- overlapping or mixed causes;
- partial client, Wi-Fi, GPU and display observability;
- cross-device clock uncertainty;
- limited-node generalization;
- tuning and testing on the same traces.

Claim reuse at the architectural level and empirical generalization only across evaluated contexts.

## 7. Project-review artifacts

Keep these inspectable:

- architecture diagram;
- frozen research contract;
- generated schemas;
- one example observation, fingerprint and match result;
- reproducible test and CLI commands;
- synthetic-fixture provenance;
- controlled-run manifest and sanitized result;
- preliminary graph/table after P0;
- explicit completed, in-progress and planned status.

Do not include credentials, tokens, ROMs, private machine paths or unnecessary device identity.

## 8. Project-readiness checklist

- [ ] The Python package installs cleanly.
- [ ] Contract models and generated schemas agree.
- [ ] Response calculation and normalization are tested.
- [ ] The matcher ranks candidates and explains residuals.
- [ ] Weak, tied, incomplete and incompatible inputs return `unknown`.
- [ ] Three synthetic fixture classes are clearly labeled.
- [ ] The Pixelated adapter processes a sanitized bundle fixture.
- [ ] One controlled real paired-run record passes through the pipeline.
- [ ] Real and synthetic evidence are clearly separated.
- [ ] All completed and planned features are reported accurately.
- [ ] No result is presented as comparative evidence before a baseline evaluation.

## Final rule

Build enough code and evidence to make the central mechanism inspectable. Keep every claim bounded by what has actually been implemented and measured.
