# P0 Pixelated Adapter and Controlled Experiment

This document defines how one real Pixelated record reaches the detached matcher. It demonstrates integration feasibility, not diagnosis accuracy.

## Bundle adapter

`src/latency_fingerprinting/adapters/pixelated_bundle.py` consumes an existing bundle or extracted directory:

```text
run-metadata.json
stream-telemetry.csv
stream-events.csv
summary.json
performance-network.png  # not used by the matcher
```

It also accepts the additive v2 contract:

```text
bundle-manifest.json
run-metadata.json
stream-telemetry.csv
engine-telemetry.csv
stream-events.csv
summary.json
```

The adapter detects v2 from the manifest, validates its phase/comparison/run
identity and privacy declaration, checks engine/encoder source identity, and
keeps the original v1 path unchanged. The hardened boundary also rejects links,
duplicate TAR members and duplicate JSON keys; caps archive members, bytes and
CSV rows; checks the explicit workload context; requires strict per-source time
ordering; cross-checks elapsed and UTC clocks; aligns engine samples with the
browser window; and retains exporter-declared invalidity.

It must validate files and columns, reject unsafe TAR paths, select explicit phases, aggregate telemetry, map names into core metrics, preserve provenance, report missing evidence and never ingest credentials.

The core matcher must not know Pixelated filenames or CSV columns.

## Evidence boundary

Bundle v1 provides FPS, received bitrate, packet loss, jitter, connection state,
metadata and lifecycle events. Bundle v2 adds browser decode/jitter-buffer
signals, interval engine-process resources and encoder-path counters. It still
does not provide direct encode time, input-to-frame or exact display timing; P0
must not claim those metrics. `pipelineDelayProxyMs` stays missing until a
validated proxy exists.

P0 counter-derived features retain the frozen median interval-delta semantics.
Before captures with different sampling cadence are compared, the next contract
must version these as rates and/or total-window deltas as described in
[`../NEXT_IMPLEMENTATION_PLAN.md`](../NEXT_IMPLEMENTATION_PLAN.md).

## Control boundary

The camera bridge applies FPS, bitrate and encoder profile at launch. It has no tested live mutation and rollback path. P0 therefore uses paired runs:

```text
degraded run with normal stream setting
vs.
relief run with one lower-cost setting
```

This is `stream_profile_relief` with `applicationMethod: paired_run`, not live probing.

## Controlled run 001

Use one repeatable host/encoder-pressure condition:

1. Fix one workload, browser, client, route and procedure.
2. Capture a healthy reference run.
3. Activate a bounded experiment-only CPU-pressure workload.
4. Capture a degraded run with the normal stream setting.
5. Keep pressure constant and capture a relief run with one lower-cost setting.
6. Stop pressure and verify restoration.
7. Record run order, duration and every changed setting.
8. Build degraded and relief observation windows.
9. Calculate a response and run the matcher.

Prefer one changed control. If a preset changes several controls, record all of them and treat it as one composite probe.

## Safety and truthfulness

The pressure workload must be experiment-only, bounded, cleaned up on failure and leave the runtime healthy. Starting load is not ground truth; record whether observable behavior actually changed.

If no stable response appears, keep the integration artifact and return `unknown`. Do not relabel the run to force success.

## Artifacts

```text
experiments/controlled-run-001/
├── README.md
├── context.json
├── manifest.json
├── restoration-evidence.json
├── probe.json
├── fingerprint.json
├── healthy/
├── degraded/
├── relief/
├── observation.json
└── match-result.json
```

Large raw bundles may stay outside Git. Commit sanitized checksums and reproducibility metadata without personal paths or device identity.

## CLI workflow

```bash
latency-fingerprint validate observation.json
latency-fingerprint ingest-pixelated path/to/degraded-bundle.tar \
  --phase degraded \
  --comparison-case-id controlled-run-001 \
  --context context.json > degraded.json
latency-fingerprint ingest-pixelated path/to/relief-bundle.tar \
  --phase relief \
  --comparison-case-id controlled-run-001 \
  --context context.json > relief.json
latency-fingerprint build-response \
  --degraded degraded.json \
  --relief relief.json \
  --probe probe.json > observation.json
latency-fingerprint match observation.json --fingerprints fixtures/
```

The explicit context file is required because a browser export cannot
truthfully supply the edge-node, runtime, encoder and version fields needed by
the research contract. Paired degraded and relief runs must use the same
nominal context; their actual stream profiles remain distinct effective
settings on their generated windows.

Commands emit JSON to stdout, diagnostics to stderr and non-zero exit codes on failure.

## Completion evidence

- [x] Sanitized bundle fixture exercises the adapter.
- [x] Unsafe TAR and missing-column cases are tested.
- [x] Healthy, degraded and relief runs are captured and ingested.
- [x] The controlled-real response and conservative matcher result validate.
- [x] The executed probe records every changed control.
- [x] Run 001 restoration and runtime-health evidence is recorded; run 002
  truthfully retains restoration as `unknown` because separate evidence was not
  captured.
- [x] Both real responses pass validation and normalization.
- [x] Both matcher outputs are schema-valid.
- [x] Results remain honest: run 001 preserves `unknown`, and run 002 is labeled
  only preliminary within-context repeatability.
