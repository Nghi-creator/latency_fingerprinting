# P0 Research Contract

**Status:** Frozen for initial implementation  
**Scope:** Initial latency-fingerprinting vertical slice  
**Contract version:** `1.0.0`

## Purpose

This document defines what the P0 system means by context, observation, probe, response, fingerprint, match, unknown and validated outcome. Python models, generated JSON Schemas, fixtures, experiments and explanations must use these meanings.

P0 is an offline software vertical slice. It uses synthetic fixture windows to
exercise the complete analytical path; it does not collect telemetry from or
change a live Pixelated engine.

Changes that alter the meaning or required fields of a record require a contract-version change. Editorial clarifications do not.

## Record conventions

- Pydantic models are the implementation source of truth; checked-in JSON Schemas are generated from them.
- Every schema root carries `schemaVersion` and `contractVersion`.
- JSON field names use `camelCase`; Python may use `snake_case` with explicit aliases.
- Identifiers are opaque strings and must not contain secrets or personal machine data.
- Timestamps use UTC ISO 8601 when real time exists; synthetic fixtures may use elapsed-time bounds.
- Numeric metric values declare units, and serialized numbers must be finite.

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
- nominal stream profile;
- relevant application, runtime, codec and driver versions when known.

### Required behavior

- Every observation, fingerprint and match request references one context.
- Context identifiers must be stable for repeated runs but must not expose personal or secret machine data.
- A `compatibilityGroup` explicitly states which records may be compared during P0.
- Matching must reject incompatible contract major versions, probe types or compatibility groups.
- A compatibility group is an explicit P0 test boundary, not proof that records are scientifically comparable.
- Temporary settings represented by a probe do not mutate the nominal context. Each observation records the effective settings used during that window.
- Missing context must not be silently replaced with a generic default.

### P0 limitation

P0 does not prove transfer across different machines, workloads, codecs or clients. It matches only within declared compatible contexts.

## 2. Observation window

### Definition

An **observation window** is a bounded set of measurements collected and aggregated over a declared interval under one stable context and experimental phase.

One `observation-v1` record represents one window. Pairing degraded and relief
windows is an analytical operation; it does not turn them into one window.

Allowed phases are:

- `baseline`: normal reference condition;
- `degraded`: controlled or observed latency problem;
- `relief`: condition while a controlled relief change is applied;
- `recovery`: condition after restoration or corrective action.

### Required fields

- run and window identifiers;
- comparison-case identifier when the window belongs to a pair;
- context reference;
- phase;
- start/end time or elapsed-time bounds;
- duration and sample count;
- effective stream and runtime settings;
- aggregate metric values, units and aggregation functions;
- missing or rejected metrics;
- validity state and reasons;
- source artifact and provenance.

### Comparability rule

Two windows are comparable only when:

- their context and workload procedure are compatible;
- the changed control is declared;
- unrelated settings are held constant or recorded as confounders;
- their durations and aggregation rules are sufficiently similar;
- both pass validity checks such as active playback and usable connection state.

For P0 fixtures, comparable degraded and relief windows must share a comparison-case identifier, compatibility group, aggregation rules and declared synthetic probe. Their values are constructed test evidence, not engine measurements.

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

P0 represents `stream_profile_relief` with
`applicationMethod: simulated_pair`. It describes the change whose response the
fixture models; the prototype does not execute that change. Real `paired_run`
and live bounded-probe methods are deferred to engine integration.

Prefer changing one control while holding the others fixed. If a preset changes bitrate, FPS and encoder settings together, record every change and treat the preset as one composite probe. Do not attribute its response to one control.

### Probe record

A probe record contains:

- probe type and version;
- requested settings and, only when executed, observed settings;
- intensity and application method;
- associated degraded and relief windows;
- execution status and paired-window ordering;
- restoration status;
- safety notes and known confounders;
- quality cost when measurable.

For `simulated_pair`, execution and restoration status must both state that no
runtime action occurred. Any quality cost is modeled fixture data, not an
observed cost.

## 4. Response delta

### Definition

A **response delta** is the feature-wise change between comparable observation windows associated with a declared probe or verified action. In P0, the values are calculated from synthetic fixture aggregates rather than claimed as physical measurements.

P0 uses one sign convention:

```text
raw response delta = relief aggregate - degraded aggregate
```

Examples:

- jitter falling from `20 ms` to `8 ms` produces `-12 ms`;
- FPS rising from `35` to `55` produces `+20 FPS`;
- packet loss falling from `6%` to `1%` produces `-5 percentage points`.

### Required behavior

- Raw values, units and aggregation functions must be retained.
- Normalization must happen after raw-delta calculation.
- Both windows must use the same unit and compatible aggregation function for a feature.
- Missing values must remain missing; they must not become zero.
- The vector stores measured direction and magnitude. It does not assume that every positive or negative value is beneficial.
- A response calculated from incomparable windows is invalid.
- Non-finite values such as `NaN` and infinity are invalid and must not appear in JSON output.

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
- context and probe compatibility keys;
- raw response delta with feature units;
- normalized response vector and feature weights;
- provenance: `synthetic`, `controlled_real` or `organic_real`;
- source case/window identifiers and, when applicable, run identifiers;
- creation software version;
- validation status and notes.

### P0 storage rule

Fingerprints are versioned JSON files. P0 does not require SQLite, a service or lifecycle automation. P0 fingerprints use `synthetic` provenance and may be described only as software-test references, not experimental findings or scientifically validated profiles.

## 6. Match result

### Definition

A **match result** is the output of comparing one observed response vector with compatible candidate fingerprints.

It contains:

- decision: `matched` or `unknown`;
- predicted bottleneck label, which is null for `unknown`;
- best match strength, when a compatible candidate can be scored;
- margin between the best and second-best candidates, when both exist;
- ranked candidates;
- shared-feature count and coverage;
- supporting and conflicting per-feature evidence;
- missing or rejected features;
- context compatibility result;
- provisional thresholds;
- warnings and decision reason.

### Interpretation rule

`matchStrength` is an engineering similarity measure. It is not a probability and must not be called calibrated confidence during P0.

Match strength and margin must be null when they cannot be computed; they must
not be invented as zero.

A match result suggests which stored response pattern is most similar. It does not by itself prove unrestricted causality.

## 7. Unknown

### Definition

`unknown` is the required decision when evidence is insufficient, incompatible, weak or conflicting. It is a valid result, not an execution failure.

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

Synthetic fixture expectations are regression assertions, not validated
outcomes. P0 defines the validated-outcome model for the later real experiment,
but it must not claim an observed recovery, cost or restoration result from
synthetic data. Outcomes do not automatically update fingerprints or choose the
next action.

## 9. Contract invariants

Every implementation must preserve these rules:

1. A fingerprint is a response pattern, not a passive snapshot.
2. A response delta requires comparable windows and a declared change.
3. Context compatibility is explicit.
4. Missing evidence remains missing.
5. Synthetic, controlled-real and organic-real provenance are distinct.
6. Match strength is not calibrated probability.
7. Weak or conflicting evidence returns `unknown`.
8. An executed controlled change records cost and restoration, not only improvement.
9. P0 simulated pairs are not described as executed or live probing.
10. Software-test success is not integration or diagnosis-accuracy evidence.
11. Nominal context is distinct from temporary effective settings.
12. Synthetic fixture expectations are not validated experimental outcomes.

## 10. P0 completion for this contract

This contract item is complete when:

- [x] The eight terms have normative definitions.
- [x] Simulated, paired-run and live-probe language is distinguished.
- [x] Provenance and truthfulness rules are explicit.
- [x] `unknown` behavior and reason codes are defined.
- [x] Match strength is separated from calibrated confidence.
- [ ] Python models implement these definitions.
- [ ] JSON Schemas are generated and checked against the models.
- [ ] Fixtures and tests demonstrate every invariant that can be enforced in code.
