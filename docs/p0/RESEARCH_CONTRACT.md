# P0 Research Contract

**Status:** Frozen for initial implementation  
**Scope:** Initial latency-fingerprinting vertical slice  
**Contract version:** `1.0.0`

## Purpose

This document defines what the P0 system means by context, observation, probe, response, fingerprint, match, unknown and validated outcome. Python models, JSON Schemas, fixtures, experiments and explanations must use these meanings.

Changes that alter the meaning or required fields of a record require a contract-version change. Editorial clarifications do not.

## 1. Context

### Definition

A **context** identifies the operating environment in which an observation or fingerprint is valid and comparable.

It includes:

- edge-node class and anonymized node identifier;
- operating system and runtime class;
- workload/game identifier or workload class;
- capture implementation;
- encoder family and encoder profile;
- transport implementation and connection mode;
- network scenario label when controlled;
- client/browser class;
- stream profile;
- relevant application, runtime, codec and driver versions when known.

### Required behavior

- Every observation, fingerprint and match request references one context.
- Context identifiers must be stable for repeated runs but must not expose personal or secret machine data.
- A `compatibilityGroup` explicitly states which records may be compared during P0.
- Matching must reject incompatible contract major versions, probe types or compatibility groups.
- Missing context must not be silently replaced with a generic default.

### P0 limitation

P0 does not prove transfer across different machines, workloads, codecs or clients. It matches only within declared compatible contexts.

## 2. Observation window

### Definition

An **observation window** is a set of measurements collected and aggregated over a declared interval under one stable context and experimental phase.

Allowed phases are:

- `baseline`: normal reference condition;
- `degraded`: controlled or observed latency problem;
- `relief`: condition while a controlled relief change is applied;
- `recovery`: condition after restoration or corrective action.

### Required fields

- run and window identifiers;
- context reference;
- phase;
- start/end time or elapsed-time bounds;
- duration and sample count;
- aggregate metric values;
- missing or rejected metrics;
- source artifact and provenance.

### Comparability rule

Two windows are comparable only when:

- their context and workload procedure are compatible;
- the changed control is declared;
- unrelated settings are held constant or recorded as confounders;
- their durations and aggregation rules are sufficiently similar;
- both pass validity checks such as active playback and usable connection state.

P0 may compare windows from paired runs because the current camera profile is fixed at launch. A paired-run comparison must record run order and all changed settings and must not be described as a live probe.

## 3. Probe

### Definition

A **probe** is a small, controlled and recorded change used to obtain response evidence about a suspected bottleneck.

The preferred probe is:

- bounded in intensity and duration;
- reversible;
- applied only after a stable baseline or degradation is observed;
- narrow enough to limit confounding;
- followed by restoration and outcome verification.

### P0 probe form

P0 uses `stream_profile_relief` with `applicationMethod: paired_run`. This is an experimental controlled change, not an automated in-session probe.

Prefer changing one control while holding the others fixed. If a preset changes bitrate, FPS and encoder settings together, record every change and treat the preset as one composite probe. Do not attribute its response to one control.

### Probe record

A probe record contains:

- probe type and version;
- requested and observed settings;
- intensity and application method;
- associated degraded and relief windows;
- start/end or paired-run ordering;
- restoration result;
- safety notes and known confounders;
- quality cost when measurable.

## 4. Response delta

### Definition

A **response delta** is the measured change between comparable observation windows after a declared probe or verified action.

P0 uses one sign convention:

```text
raw response delta = relief aggregate - degraded aggregate
```

Examples:

- jitter falling from `20 ms` to `8 ms` produces `-12 ms`;
- FPS rising from `35` to `55` produces `+20 FPS`;
- packet-loss delta falling from `6` to `1` produces `-5 packets/window`.

### Required behavior

- Raw values, units and aggregation functions must be retained.
- Normalization must happen after raw-delta calculation.
- Missing values must remain missing; they must not become zero.
- The vector stores measured direction and magnitude. It does not assume that every positive or negative value is beneficial.
- A response calculated from incomparable windows is invalid.

## 5. Fingerprint

### Definition

A **latency fingerprint** is a context-specific stored response pattern produced by a declared probe or verified action.

It is not:

- one CPU, RTT, FPS or bitrate snapshot;
- a permanent identity for a machine;
- a universal rule that applies to every node;
- proof of a bottleneck without provenance and validation.

Conceptually:

```text
context
+ degraded condition
+ controlled change
+ normalized cross-layer response delta
+ disturbance or quality cost
= latency fingerprint
```

### Required fields

- fingerprint and schema version;
- bottleneck label;
- context/probe compatibility key;
- normalized response vector and feature weights;
- provenance: `synthetic`, `controlled_real` or `organic_real`;
- source run identifiers;
- creation software version;
- validation status and notes.

### P0 storage rule

Fingerprints are versioned JSON files. P0 does not require SQLite, a service or lifecycle automation. Synthetic fingerprints must be clearly labeled and cannot be presented as experimental findings.

## 6. Match result

### Definition

A **match result** is the output of comparing one observed response vector with compatible candidate fingerprints.

It contains:

- accepted bottleneck label or `unknown`;
- best match strength;
- margin between the best and second-best candidates;
- ranked candidates;
- shared-feature count and coverage;
- supporting and conflicting per-feature evidence;
- missing or rejected features;
- context compatibility result;
- provisional thresholds;
- warnings and decision reason.

### Interpretation rule

`matchStrength` is an engineering similarity measure. It is not a probability and must not be called calibrated confidence during P0.

A match result suggests which stored response pattern is most similar. It does not by itself prove unrestricted causality.

## 7. Unknown

### Definition

`unknown` is the required result when evidence is insufficient, incompatible, weak or conflicting.

P0 reason codes include:

- `incompatible_context`;
- `unsupported_probe`;
- `insufficient_feature_coverage`;
- `degenerate_vector`;
- `weak_match`;
- `ambiguous_margin`;
- `invalid_observation`;
- `conflicting_evidence`.

### Required behavior

- The matcher must never force a bottleneck label merely because candidates exist.
- `unknown` must include a reason and the evidence needed to improve the decision.
- An `unknown` result from the controlled real run is acceptable feasibility evidence if the data path executed correctly.

## 8. Validated outcome

### Definition

A **validated outcome** records what happened after a probe or corrective action and whether the expected recovery occurred.

It contains:

- action or probe reference;
- before/after latency and stream indicators;
- recovery time;
- deadline or frame-age improvement when measurable;
- bitrate, FPS, drop or quality cost;
- connection or stability impact;
- restoration/rollback status;
- result: `improved`, `unchanged`, `worsened` or `inconclusive`.

### P0 rule

P0 records the observed paired-run outcome and restoration status. It does not yet use outcomes to update fingerprints automatically or choose the next action.

## 9. Contract invariants

Every implementation must preserve these rules:

1. A fingerprint is a response pattern, not a passive snapshot.
2. A response delta requires comparable windows and a declared change.
3. Context compatibility is explicit.
4. Missing evidence remains missing.
5. Synthetic, controlled-real and organic-real provenance are distinct.
6. Match strength is not calibrated probability.
7. Weak or conflicting evidence returns `unknown`.
8. A controlled change records cost and restoration, not only improvement.
9. P0 paired runs are not described as live probing.
10. Feasibility evidence is not diagnosis-accuracy evidence.

## 10. P0 completion for this contract

This contract item is complete when:

- [x] The eight terms have normative definitions.
- [x] Paired-run and live-probe language is distinguished.
- [x] Provenance and truthfulness rules are explicit.
- [x] `unknown` behavior and reason codes are defined.
- [x] Match strength is separated from calibrated confidence.
- [ ] Python models implement these definitions.
- [ ] JSON Schemas are generated and checked against the models.
- [ ] Fixtures and tests demonstrate every invariant that can be enforced in code.
