# P0 Data Model and Matcher

This document translates [`RESEARCH_CONTRACT.md`](RESEARCH_CONTRACT.md) into records and algorithms. The contract is authoritative when wording differs.

## Schema roots

### `observation-v1.schema.json`

The observation root contains:

```text
schemaVersion
contractVersion
context
degradedWindow
reliefWindow
probe
responseDelta
normalizedResponse
provenance
```

`ContextKey` includes an anonymized node, workload, capture, encoder, transport, network scenario, client, stream profile, relevant versions and `compatibilityGroup`.

`ObservationWindow` includes phase, bounds, duration, sample count, metric aggregates, missing metrics and source provenance. For each numeric metric, retain count, median, P95, minimum and maximum when enough samples exist.

### `fingerprint-v1.schema.json`

The fingerprint root contains:

```text
schemaVersion
contractVersion
fingerprintId
bottleneckLabel
compatibility
normalizedResponse
featureWeights
provenance
sourceRunIds
createdAt
softwareVersion
validationStatus
notes
```

P0 labels are `healthy`, `network_pressure` and `host_encoder_pressure`. These exercise software behavior; they are not a complete bottleneck taxonomy.

### `match-result-v1.schema.json`

The match-result root contains:

```text
schemaVersion
acceptedLabel | unknown
matchStrength
scoreMargin
rankedCandidates
sharedFeatureCount
featureCoverage
supportingEvidence
conflictingEvidence
missingFeatures
compatibility
thresholds
warnings
decisionReason
```

## Initial metric vocabulary

The Pixelated adapter retains the four v1 browser metrics:

- `client.received_fps`;
- `client.received_bitrate_kbps`;
- `transport.jitter_ms`;
- `transport.packets_lost_delta`;
- connection and playback validity indicators.

From a Pixelated research bundle v2 it additionally derives nullable,
window-level aggregates for:

- browser RTT, decode time, jitter-buffer delay and available incoming bitrate;
- decoded/dropped-frame and freeze counter deltas;
- Node, game-runtime and camera/GStreamer interval CPU and RSS;
- encoder input/output/drop counter deltas and queue level;
- a pipeline-delay proxy only when it is explicitly measured.

The v2 manifest is validated against phase, comparison-case and run identity.
Event wall-clock timestamps must be valid UTC values and remain consistent with
their event elapsed-time sequence. Summary total and available sample counts
must exactly match the telemetry rows. Unsupported measurements remain missing;
cumulative counters that reset are rejected, and unavailable samples break
counter continuity instead of creating a delta across an observation gap.

Legacy lifetime-average CPU snapshots remain unsuitable. Only the interval CPU
samples carried by bundle v2 are represented as window-level utilization.

Direct encode, input-to-frame and exact display timing remain missing until
instrumentation exists.

## Response calculation

```text
raw delta = relief aggregate - degraded aggregate
normalized delta = raw delta / max(abs(reference value), feature epsilon)
```

Every feature uses the frozen P0 unit, epsilon and clipping configuration.
Persisted observations and fingerprints are revalidated against that canonical
configuration before their normalized values may be scored. Raw values are
retained, missing values are not imputed as zero, clipping is recorded, and
incomparable windows fail validation.

## Weighted-distance matcher

Use normalized weighted Euclidean distance. It supports a healthy near-zero response vector, unlike cosine similarity, whose direction is undefined at zero.

```text
distance = sqrt(sum(w[i] * (q[i] - c[i])^2) / sum(w[i]))
base match strength = 1 / (1 + distance)
adjusted match strength = base match strength * shared-feature coverage
```

Matching steps:

1. Reject incompatible contract/schema major versions, probe types or compatibility groups.
2. Compare only finite shared features.
3. Enforce minimum positive-weight shared-feature count and coverage. Zero-weight
   features remain visible for audit but cannot satisfy an evidence gate.
4. Apply declared feature weights.
5. Calculate weighted distance and adjusted match strength.
6. Rank candidates and calculate the top-two margin.
7. Explain per-feature residuals.
8. Return a label or `unknown` with a reason code.

All scoring inputs and intermediate sums must remain representable as finite
binary64 values. A candidate whose residual contribution, total weight, or
weighted residual sum exceeds that range is not partially scored or allowed to
crash the run: it is rejected as unscorable evidence and the matcher continues
conservatively with an explicit warning.

Provisional software-test defaults are match strength `0.75`, margin `0.10`, three shared features and `60%` coverage. They are not calibrated research results.

## Evidence

For every feature, report observed value, candidate value, residual, weight and
weighted squared residual. Model validation recomputes both residual equations
without leaking floating-point overflow. Residuals must reconstruct the
distance. Small residuals support the match; large residuals conflict with it.

## Synthetic fixtures

- `healthy.json`: near-zero response to relief.
- `network_pressure.json`: transport indicators respond while other represented evidence remains stable.
- `host_encoder_pressure.json`: FPS or host/encoder indicators respond while jitter/loss remain comparatively stable.

All use one explicitly synthetic compatibility group and provenance `synthetic`.

## Required tests

- [x] Schema generation is deterministic.
- [x] Valid records round-trip.
- [x] Invalid versions, windows, NaN and infinity fail.
- [x] Delta sign and normalization are correct.
- [x] Clear and noisy fixtures match correctly.
- [x] Weak, tied and conflicting evidence returns `unknown`.
- [x] Missing features use only the valid intersection.
- [x] Coverage and compatibility are enforced.
- [x] Weighted residuals reconstruct distance.
- [x] CLI output validates against the result schema.

These tests validate implementation behavior only.
