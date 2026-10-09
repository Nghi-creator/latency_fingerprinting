# N4 browser instrumentation

**Delivered:** Step 4 software, 2026-10-09. [Trace contract](N4_TRACE_CONTRACT.md)
and [real-capture/overhead gates](N4_PRODUCER_CAPABILITIES.md) remain authoritative.

The sibling Pixelated Studio Edition web app now has a bounded in-memory collector
in `apps/web/src/features/player/observability/`, attached by `useBrowserStageTrace`
in `PlayerExperience` beside `useStreamPlayback`. Collection makes no React state updates per frame and
preserves existing playback, black-frame detection and cumulative WebRTC metrics.

## Enablement and scope

Vite build-time settings (rebuild the web app after changing them):

| Setting | Default / accepted range |
| --- | --- |
| `VITE_N4_STAGE_TRACE` | `0`; exactly `1` enables collection |
| `VITE_N4_STAGE_TRACE_EVERY_NTH_FRAME` | `1`; decimal integer 1–1000 |
| `VITE_N4_STAGE_TRACE_MAX_FRAMES` | `2000`; decimal integer 1–2000 |
| `VITE_N4_STAGE_TRACE_MAX_EVENTS` | `10000`; decimal integer 1–10000 |

Disabled mode allocates no recorder or frame callback and ignores trace knobs.
Invalid enabled configuration emits one fixed diagnostic per recorder initialization
and disables collection. There is no browser deadline budget. [Step 5](N4_TRACE_ADOPTION.md) adds explicit
finish/export control with a required VITE_N4_STAGE_TRACE_PRODUCER_VERSION commit. Configuration is copied, bounded and frozen.

One mounted playback hook owns a recording across at most sixteen video/media
lifetimes. The frame/event limits apply globally across retained closed lifetimes;
capacity never evicts/refills a prefix. Stream/status changes detach the old binding
and create new stream/epoch/clock aliases. React effect replay also creates separate
lifetimes. Component unmount cancels callbacks; its in-memory recording is discarded.
A frame counter repeat/reset or callback clock regression closes the scope with
source_error; recording resumes only on a new lifecycle attachment, with new aliases.
Playback continues when collection stops or exhausts its limits.

## Evidence and unavailable boundaries

Only `requestVideoFrameCallback` callback `now`, metadata `presentationTime` and
`presentedFrames` are read. Both callback registration and cancellation must exist;
otherwise presentation_proxy is unavailable/api_unavailable with no frames/events.
Initial registration failure also declares it unavailable. A later failure keeps
supported capability for the interval in which the callback was actually active.

`presentation_proxy` records compositor submission; `presentation_callback`
records callback delivery. Their local delta is callback lag, including scheduling
and main-thread feedback delay. It is not physical display completion or decoder
execution time. Callbacks may skip presentations. This follows the
[rvfc specification](https://wicg.github.io/video-rvfc/).

All ten other capabilities are unavailable/unsupported_source, including wire_send,
receive, decode_ready and render_ready. Optional receiveTime, captureTime, RTP/media
timestamps, processingDuration and expectedDisplayTime never enter this trace.
Existing cumulative decode/buffer means and RTT remain separate observations.
There is no engine/browser frame mapping or synchronized one-way latency claim.

Frame source_sequence counts observed callbacks, beginning at one per lifetime;
exact correlation means only the two endpoints of that callback. Sampling uses
`(sequence - 1) % N == 0`, independently of presentedFrames. Missed presentations
sum positive gaps minus one between adjacent observed counters, including unsampled
callbacks; no loss before the first callback is inferred. Invalid/reset counters
close the interval instead of guessing a gap.

The private origin is performance.now at attachment. Endpoints become relative
integer ns with `Math.round((timestamp_ms - origin_ms) * 1e6)`, positive ties up.
Nonfinite, negative-relative or unsafe values drop that endpoint and retain exact
loss/sequence accounting. Clock resolution is null because effective browser
quantization has not been assessed. No timeOrigin, UTC or absolute timestamp is
exported. Negative pair deltas remain evidence for later reconstruction exclusions.

## Teardown, bounds and verification

One callback is outstanding per binding. Cleanup is idempotent; a stopped flag
neutralizes late delivery even if native cancellation fails. Callback/registration
failures stop tracing without escaping into playback. `finish()` cancels all active
bindings; `snapshot(commit, provenance)` then returns a detached, sanitized v1
record. It requires a lowercase forty-hex producer commit and explicit provenance.
Snapshots do no synchronous work inside callbacks. [Persistence/adoption](N4_TRACE_ADOPTION.md) is delivered in Step 5; timing
[reconstruction](N4_TIMING_RECONSTRUCTION.md) is delivered in Step 6.

Step 4 checks: 38 independent browser collector/configuration/lifecycle cases;
220 total web tests; web lint and production TypeScript/Vite build pass. All 23
synthetic snapshots from those cases pass strict Python N4 validation. Existing
core/schema/reproduction gates are preserved. These are software/fake-video checks,
not live browser timing, Linux/X11 capture or measured overhead evidence.
