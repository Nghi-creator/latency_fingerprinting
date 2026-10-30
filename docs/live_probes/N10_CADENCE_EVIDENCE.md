# Offline capture-cadence evidence

`cadence-probe-evidence-v1`, method `n10-cadence-evidence-v1`, is an additive,
immutable forensic record for the producer's explicit isolated Gst WebRTC cadence
worker. It does not execute control, qualify a policy, clear a dirty runtime
journal or establish diagnostic relief. The bitrate-only
[`live-probe-evidence-v1`](N10_MODELS.md) and all earlier schemas retain their
bytes and meaning. The new [JSON Schema](../../schemas/cadence-probe-evidence-v1.schema.json)
validates the structural format; Python validators additionally enforce hashes,
chronology and cross-field constraints.

## Import and inspect

Capture JSON from the producer's [isolated worker](../../../Pixelated-Studio-Edition/docs/n10-cadence-controller.md).
Retain the original report, its source/image acquisition receipt and any private
runtime journal separately. Then import offline:

```sh
latency-fingerprint import-cadence-report \
  --report worker-report.json --output cadence-evidence.json \
  --acquisition-id isolated-run-1 \
  --producer-revision <40-lowercase-hex-commit> \
  --image-hash sha256:<64-lowercase-hex> \
  --source-manifest-hash sha256:<64-lowercase-hex>
latency-fingerprint validate cadence-evidence.json
```

The command uses bounded, duplicate-safe JSON, no-follow input opens and atomic
output. It rejects overwriting the report through the same name, a hard-link
alias or a symlink. On invalid input/output it emits a fixed error without
native exceptions or input content. It imports evidence only; it never starts
Docker, GI, a media pipeline, a network connection or a probe.

`producer_revision`, `image_hash` and `source_manifest_hash` are supplied acquisition
declarations. A revision alone does not describe uncommitted code. For a dirty
source acquisition, retain a manifest of actual mounted source-file SHA-256
hashes and compute its canonical content hash with
`latency_fingerprinting.analytical.policy_release.payload_hash`. Preserve that
manifest with the receipt. A supplied manifest/image hash is not authentication
or verification that those bytes executed.

```python
from pathlib import Path
from latency_fingerprinting.live_probes import (
    CadenceProbeEvidence,
    import_cadence_worker_report,
    inspect_cadence_probe_evidence,
)

evidence = CadenceProbeEvidence.model_validate_json(Path("cadence-evidence.json").read_bytes())
inspection = inspect_cadence_probe_evidence(evidence)
print(inspection.model_dump(mode="json"))
```

`import_cadence_worker_report(report, *, acquisition_id, producer_revision,
image_hash, source_manifest_hash)` also accepts a supplied report object. It
validates and normalizes nested data before sealing. Collections become bounded
tuples and all nested evidence models are frozen. The content-derived ID is
`cadence-evidence-<sha256>`; `content_hash` covers all other root fields.
`source_report_hash` covers the **normalized typed report**, including explicit
null/empty defaults for absent partial observations. It is not a byte hash of the
original stdout file. Keep the latter for acquisition provenance.

## Retained observations and limits

The source report is closed to the current worker version and fixed experiment:
640×360 synthetic moving-ball VP8 over a Gst sender/receiver pair, 30→24→30 fps,
a three-second request, 500 ms application settling and the worker's declared
250 ms PTS/500 ms pull-gap and ±10% rate screens. These are engineering experiment
parameters, not production quality/safety limits.

The record retains supplied owner/pipeline/peer generations, at most two setter
brackets, 512 source/receiver counter observations, three phase windows and 1,200
received-frame observations. Old reports without generations remain importable
but cannot meet the complete local screen. Missing setup/output/result/protocol
observations stay absent; no inferred frames, successful calls or recovery facts
are substituted. Partial and failed acquisitions remain valid evidence.

Each counter observation has its recorded observation time, exact configured and
negotiated integer FPS, source/received-frame counters, declared health and an
unrelated-settings digest. These are point observations, not measured read-call
brackets. Window endpoints must be retained observations, progress in time,
exclude setter brackets and settling, and follow baseline/application/restoration
order. Settings and counter changes remain available for inspection rather than
being discarded as invalid evidence.

Setter and pull times are nanoseconds relative to one worker monotonic origin.
Received PTS belong to the receiver pipeline and are **not aligned** to source,
browser or wall-clock time. No cross-clock subtraction is performed. Reversed,
gapped or stale received output can be retained and fails continuity inspection.
The format represents this fixed single-worker acquisition; do not merge epochs
or relabel source/local decoder observations as WebRTC/browser reception.

## Meaning of inspection

`inspect_cadence_probe_evidence` independently recomputes phase source/received
rates with exact integer arithmetic, matching configured/negotiated FPS and
healthy observations. It checks PTS/pull continuity, missing output, resets,
receiver-counter consistency against the retained timeline, declared generations
and unrelated-settings stability. It compares these checks with the producer's
assessment instead of trusting its `met` flag.

`local_screen` is `met`, `not_met` or `incomplete`. A met screen describes only the
supplied synthetic transport observations. `declared_restoration_supported`
requires measured restoration progress, continuity, settings, a declared
lifetime, the worker's claimed port proof and clean journal declaration. It does
not independently verify private durable intent, budget accounting, watchdog
operation, journal persistence or ownership. A dirty/missing declaration cannot
support restoration; process teardown cannot substitute for live restoration.

Every evidence/inspection fixes `live_authority=false` and capability
`unavailable_unqualified`. Receiver scope remains `gst_loopback_not_browser`;
quality/resource costs remain `not_evaluated` and diagnostic value `unverified`.
Game capture, browser presentation, perceptual quality, disturbance/resource
measurements and production qualification require additional evidence.


The producer's separate [game/browser procedure](../../../Pixelated-Studio-Edition/docs/n10-game-browser-trial.md)
uses a different operator report version and scope for a real 2D game and
headless presentation/resource measurements. This importer intentionally rejects
that report rather than broadening its frozen synthetic Gst-to-Gst contract. The
separate [game/browser evidence contract](N10_GAME_BROWSER_EVIDENCE.md) imports
those engineering observations without qualifying a capability.
