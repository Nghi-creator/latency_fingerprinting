# Offline game/browser engineering evidence

`game-browser-probe-evidence-v1`, method `n10-game-browser-evidence-v1`, accepts
observations from the producer's [contained game/browser experiment](../../../Pixelated-Studio-Edition/docs/n10-game-browser-trial.md).
It is a separate immutable forensic format. The earlier bitrate-only and
synthetic Gst-to-Gst cadence schemas retain their bytes, scope and meaning.
This format accepts evidence structurally; it does not qualify a runtime, policy,
quality floor or diagnostic response, and does not execute control.

## Import and inspect

```sh
latency-fingerprint import-game-browser-report \
  --report game-browser-acquisition.json --output game-browser-evidence.json \
  --acquisition-id engineering-run-1 --producer-revision "$PRODUCER_REVISION"
latency-fingerprint validate game-browser-evidence.json
```

`PRODUCER_REVISION` is the declared 40-character lowercase Git base revision used
at acquisition. Uncommitted sources are described by the acquisition's actual
source hashes, not inferred from the revision. Keep the original acquisition,
source/image receipt, optional receiver image and private runtime journal under
local operator storage. Do not publish session receipts in project documentation.

The importer uses bounded, duplicate-safe JSON and pinned no-follow input reads.
Atomic output rejects the input path, hard-link aliases and symlink targets.
Invalid import input/output produces a fixed error without native exception or
input-content echoes. It never loads GI, starts Docker, opens a browser, reads
source paths from the manifest or modifies a private runtime journal.

```python
from pathlib import Path
from latency_fingerprinting.live_probes import (
    GameBrowserProbeEvidence,
    import_game_browser_acquisition,
    inspect_game_browser_evidence,
)

evidence = GameBrowserProbeEvidence.model_validate_json(
    Path("game-browser-evidence.json").read_bytes()
)
inspection = inspect_game_browser_evidence(evidence)
print(inspection.model_dump(mode="json"))
```

The Python factory is `import_game_browser_acquisition(acquisition, *,
acquisition_id, producer_revision)`. Its input is the producer's raw operator
acquisition, including its source-hash object. Normalization converts that object
into sorted, unique, immutable `SourceBinding` entries. All nested evidence models
are frozen; bounded sequences become tuples. Unsupported observations remain
explicitly null or absent, never substituted with zeros or successful outcomes.

`evidence_id=game-browser-evidence-<sha256>` and `content_hash` bind all other root
fields. `acquisition_hash` binds the normalized typed acquisition, including
explicit null/empty defaults. `source_manifest_hash` binds the canonical mapping
of source names to file SHA-256 hashes. These are not byte hashes of original
stdout or authentication that those bytes executed. Revision, image, browser,
workload, generation and cleanup facts remain supplied declarations.

## Fixed scope and retained data

The closed source version is `n10-game-browser-acquisition-v1` containing
`n10-isolated-game-browser-v1`: scripted Frozen-Bubble level one, a private
640×480 display, software VP8/Gst sender and dedicated headless Chromium video.
The fixed provisional protocol is 30→24→30 source FPS, a three-second request,
500 ms application settling and 200 ms restoration settling followed by 750 ms
of restoration measurement. It includes warm-up, baseline duration, presentation
gap, dropped-frame/freeze and visual-sampling declarations. It is not a generic
browser/game import surface or a production safety policy.

Changed, unchanged-control, cancellation and receiver-loss modes remain distinct.
An unchanged control cannot carry setter receipts, a controller result or a
journal state. A cancellation can retain an aborted request and shorter during
window alongside measured restoration. Missing setup/report/phase/result data and
dirty/unknown recovery stay representable. Process teardown never becomes live
restoration. The import does not create a request or refund/reset a budget.

The format bounds each acquisition to two setter brackets, 512 source/counter
observations, three phase windows, 1,200 presentation observations, 128 browser
statistics and visual samples each, 512 worker/game resource reads, 128 host
browser resource reads and 32 source bindings. Statistics have required nullable
fields: unsupported decode/freeze/resource counters remain null. Native process
IDs, signaling credentials, SDP and ICE candidates are outside this format.

Window endpoints must be retained ordered observations. Windows cannot overlap,
cross setters, precede their required settling or include declared baseline
warm-up. Resource reads retain their own read brackets and refer to retained
worker observations. Counter resets, bad presentation sequences and missing
values can be retained for inspection rather than erased as successful evidence.

Worker observations, browser callback times and host browser CPU observations
have three separate declared clocks with `clock_alignment=none`. Received media
PTS have their own browser media timeline. Inspect only differences within the
same sequence/domain. Browser stats and visual samples are classified by worker
receipt times; this does not align browser presentation, source capture or host
resource intervals. Source observations are recorded points, not read-call
brackets or proof of a shared hardware clock.

## Independent inspection

`inspect_game_browser_evidence` recomputes source/presentation rates, observed
settings, freshness and browser decode progress. It checks presentation PTS and
callback gaps, callback lifetime/count consistency, unchanged settings, known RTP
counter reversals and source/workload declarations. It checks nonblank samples
and per-window visual coverage after warm-up, preserving startup samples. Full
changed/control during windows need at least two usable seconds; baseline and
restoration must meet their declared measurement durations. Short/missing windows
remain incomplete. Cancellation can retain its shorter aborted during interval.

The original producer assessment stays in the evidence. Its eight flags are
compared separately from the stronger core engineering screen: agreeing with the
producer does not substitute for complete windows, decode progress, consistent
counters, expected mode/result, lifetime/context declarations and known cleanup.
`engineering_screen` is `met`, `not_met` or `incomplete` and describes only these
limited supplied observations.

Per-phase CPU rates use worker read intervals and exact owned-game tick frequency.
Interior resets invalidate CPU estimates even when endpoint differences look
positive. Missing reads/frequency stay unknown. `peak_game_rss_bytes` is the
maximum retained RSS sample, not a continuously measured process high-water mark.
Browser CPU uses its separate host interval and current process-inventory hash;
missing counters, changed inventory or resets cannot become zero cost. CPU rates
are descriptive point estimates under instrumentation. They are not combined
across hosts, clock-aligned or treated as causal relief/resource qualification.

`declared_restoration_supported` requires restoration observations, supported
presentation/health, consistent settings/counters, the declared port proof and a
clean journal declaration. It is false for unchanged controls, absent restoration
or dirty state. This library does not independently prove durable intent,
watchdog operation, actual journal persistence, authorization or ownership.
Subsequent teardown/cleanup declarations remain separate from this limited
restoration-support field.

Every root and inspection fixes `live_authority=false`, capability
`unavailable_unqualified`, evidence role `engineering`, perceptual quality
`not_evaluated` and diagnostic value `unverified`. Pixel variation/nonblank video
is not perceptual fidelity or full desktop playability. These engineering records
cannot silently enter N6/N7 training or N11 final-test evidence, become N2/N5
paired-run response features, or authorize a production mutation. Normal worker
integration and predeclared quality/disturbance qualification remain separate.

Integrated camera/multiple-peer cohorts have a separate
[custody record and supplied-observation reconstruction](N10_INTEGRATED_GAME_RECORD.md).
They cannot be imported into this direct-worker evidence contract.
