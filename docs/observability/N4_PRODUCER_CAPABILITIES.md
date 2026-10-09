# N4 producer capabilities and real acceptance

**Inspected:** 2026-10-09. Engine/browser producer commit
`37e50fb7ef919564aba5796af35dbcdc1fc70f3b`.
**Definition:** [Trace contract](N4_TRACE_CONTRACT.md).
**Delivery status:** Step 3 [host hooks](N4_HOST_INSTRUMENTATION.md) implemented locally.
The inventory below records inspected starting behavior; [browser hooks](N4_BROWSER_INSTRUMENTATION.md)
are now delivered as Step 4 software. Real capture
and overhead verification remain pending.

Paths in this document are relative to the sibling `Pixelated-Studio-Edition`
repository. They identify integration locations, not dependencies the Python core
loads at runtime. No applicable AGENTS.md was found in either repository/ancestors.

## Observed source and approved scope

| Boundary / evidence | Existing implementation | Approved N4 v1 scope / remaining gap |
| --- | --- | --- |
| Game render-ready | No hook inspected | Unavailable; do not infer from capture |
| Capture begin / output | `engine/runtime/camera.py`: `ximagesrc` per peer, X11 display `:99` | Step 3: stable source name and src-pad probe delivered for output only; capture duration unavailable |
| Pre-encode queue | Same file: `pre_encoder_queue`, one-buffer downstream-leaky queue; existing sink probe counts frames | Step 3: timestamped sink/src probes delivered; instantaneous occupancy and overrun signals are not sojourn or verified frame-drop counts |
| Encode input/output | Same file: VP8 `video_encoder`; existing src probe counts output buffers | Step 3: sink/src timestamps and conditional unique PTS correlation delivered; includes scheduling/buffering, no CPU-time claim |
| Post-encode queue | `rtpvp8pay` then `post_encoder_queue` | Packet buffers may split one frame; excluded from frame duration methods |
| Sender enqueue / wire send | `webrtcbin` pipeline branch | No approved wire-send hook; enqueue is not send |
| Snapshot / engine resource interval | `camera_state.py` atomic JSON; `src/telemetry/researchTelemetrySnapshot.ts` monotonic interval sampler | Keep existing telemetry; neither is a per-frame timing trace |
| Receive / decode ready | `apps/web/src/lib/webrtc/telemetry/webrtcStatsParser.ts` getStats deltas | Existing decode/jitter means and RTT stay separate; no per-frame receive/decode hook approved |
| Browser presentation | `apps/web/src/features/player/hooks/playback/useStreamPlayback.ts` polls a tiny canvas every 750 ms | Add optional rvfc collector with compositor timestamp/callback timestamp only; feature detection and API failure yield explicit unavailability |
| Physical display | No photodiode/scan-out observation | Unavailable; no browser API claim of photons/display completion |
| Trace export | `apps/web/src/features/player/research/researchRunExportArtifacts.ts`, `researchBundleManifest.ts` export research v2 | Add separate trace bundle v1; never modify v2 layout/semantics |

Engine `handle_offer` creates a separate pipeline for each peer. Source sequences
cannot be pooled across those pipelines. Teardown, GST errors and restarts close
the lifetime and must release probes/maps/buffers. Atomic camera snapshots sum
peer counters and can decrease when a peer disappears; this is not frame identity.
Browser recording elapsed time currently uses UTC-derived values; UI performance
clocks do not retrospectively synchronize the exported research records.

The delivered browser collector belongs alongside playback telemetry, with its
own bounded lifecycle, cancellation and opt-in state. It must not replace the
existing black-frame fallback or getStats path. No `processingDuration`,
`receiveTime`, `captureTime`, RTP timestamp or predicted display-time field is
approved in trace v1. Future approval needs a new method/version and field review.

## Integration rules

Disabled mode installs no new probes or rvfc callback, creates no per-frame trace
objects and performs no tracing I/O. Enabling affects only the configured peer/
video element. Collector work uses bounded memory and counters; filesystem
serialization, HTTP, Python-core imports and export are forbidden in pad callbacks.
Recording snapshots must freeze counters/ledger/events consistently. Export and
inspection cannot mutate a live collector. Correlation metadata is bounded by
frame limits; ambiguity/eviction never guesses an endpoint. Capabilities describe
active hooks and actual feature detection, not availability advertised by factory
lookup or browser version.

UTC snapshots, Python monotonic time, Gst media time and browser performance time
are separate. N4 v1 declares no clock synchronization, error bound or feedback
latency estimate. Consequently transport one-way delay, glass-to-glass latency,
cross-producer frame age and end-to-end deadline slack remain unavailable.

## Minimum real case, fixed before measurement

Step 7 must execute the actual Pixelated X11 capture → leaky queue → VP8 encoder
path in a Linux/Xvfb/PulseAudio runtime. A bare `videotestsrc` unit pipeline or
macOS factory lookup is useful software evidence but does not satisfy this case.
A local WebRTC receiver must keep the pipeline draining. Use one peer, 1280×720,
30 fps, fixed producer settings and a reproducible animated X11 scene (no private
content). Record exact commits, Gst/Python/browser versions, runtime configuration,
CPU allocation, commands and trial data alongside a sanitized exported trace.

Use `every_nth_frame=1`, limits 2000 frames/10000 events; predeclared illustrative
capture-output budget 50,000,000 ns. This budget is not scientific calibration.
After 10 s warm-up, reset/start a fresh trace and collect 30 s. Require:

- At least 500 usable `pre-encode-queue-sojourn` pairs and 500 usable
  `encode-boundary-elapsed` pairs, independently recomputed from exported integers.
- Unique, preserved PTS association demonstrated for admitted usable frames at
  source, queue and VP8 boundaries; identify missing/ambiguous cases explicitly.
  Do not infer preservation from the selected codec. At least 95% of admitted
  frames must yield both pairs, with no negative durations among usable pairs.
- Hash-verified producer bundle → core adoption → inspection; age/budget results
  independently reconstructed, unsupported boundaries declared unavailable and
  no assertion of sender/browser frame alignment.
- Zero collector event/ledger drops in the nominal trial; separate deliberately
  tiny-capacity and interrupted-stream trials must show exact loss accounting,
  bounded memory, partial-pair exclusions, clean teardown and distinct epochs.
- Disable/re-enable and two-peer smoke trials must show independent lifetime IDs
  and no cross-peer/frame/clock pairing. Unsupported rvfc path must export explicit
  capabilities; supported browser path must reproduce callback lag locally.

If VP8 correlation is not preserved, record that failed gate and revise the
approved method/version before widening scope; do not pass by heuristic matching.
Real acceptance requires these minimum pairs, not just a trace containing events.

## Overhead acceptance procedure

Use the same nominal Linux setup and draining receiver. Run five paired trials,
alternating disabled/enabled order (A/B, B/A, A/B, B/A, A/B). Each trial has 10 s
warm-up and 30 s measured collection; enabled trials use the nominal limits above.
Keep codec/settings, scene, CPU allocation and receiver identical. Save every
trial; do not cherry-pick the best pair. Measure camera-process CPU using process
CPU-time difference / wall duration, expressed as percent of one core; throughput
uses encoded frame-count difference / duration. Counters reset per trial.

For each pair compute enabled minus disabled CPU percentage points, and
(enabled_fps - disabled_fps)/disabled_fps. Disabled FPS must be nonzero and at
least 27 in every trial; otherwise the setup fails baseline adequacy. Acceptance:
median CPU increase ≤5 percentage points AND median FPS change ≥−5%, with no
crash/stream failure and no nominal collector drops in any enabled trial.
These are provisional engineering criteria, not a universal latency guarantee.
Report all trial values, medians and runtime limitations. Do not alter thresholds
after seeing measurements without versioned rationale and a fresh trial set.

Also record enabled callback execution cost using a separate diagnostic run
(at least 1000 probes), reporting count/min/mean/max and diagnostic overhead.
It explains collector cost; it cannot substitute for paired process/throughput
measurements. Export/write time stays outside pad callbacks but is reported
separately. No unmeasured performance claim or hardware-encoder certification.

Docker is unavailable on the current macOS host. Step 0 found Gst factories,
which does not satisfy these gates. Missing runtime keeps real integration and
measured overhead pending even after software Steps 2–6 pass.
