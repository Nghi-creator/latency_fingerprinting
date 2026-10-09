# N4 host instrumentation

**Delivered:** Step 3 software, 2026-10-09. Real Pixelated capture, correlation
verification and measured overhead remain the [Step 7 gates](N4_PRODUCER_CAPABILITIES.md).
**Meaning:** [Trace contract](N4_TRACE_CONTRACT.md).

The sibling Pixelated Studio Edition repository now contains three focused
stdlib Python helpers in `engine/runtime/`: `camera_trace_config.py` (closed opt-in
configuration), `camera_trace.py` (bounded recording) and `camera_trace_hooks.py`
(GStreamer adapter). `camera.py` installs the helpers before PLAYING, closes them
before setting a peer pipeline to NULL and finalizes the recording on loop exit.
Both runtime Dockerfiles include the helpers. No new Python dependency is required.

## Enablement and scope

Tracing is disabled by default. The engine launcher's existing environment
inheritance carries these camera-process settings:

| Environment variable | Default / accepted range |
| --- | --- |
| `PIXELATED_STAGE_TRACE` | `0`; exactly `1` enables tracing |
| `PIXELATED_STAGE_TRACE_EVERY_NTH_FRAME` | `1`; decimal integer 1–1000 |
| `PIXELATED_STAGE_TRACE_MAX_FRAMES` | `2000`; decimal integer 1–2000 |
| `PIXELATED_STAGE_TRACE_MAX_EVENTS` | `10000`; decimal integer 1–10000 |
| `PIXELATED_STAGE_TRACE_BUDGET_NS` | Absent/null; optional positive safe integer ≤2^53−1 |

Invalid enabled configuration disables tracing with a fixed diagnostic, leaving
playback available. Disabled mode ignores trace-only settings, allocates no
recording, registers no tracing probes or signal handler and makes no per-frame
trace objects. The stable name `video_capture` now identifies ximagesrc; encoder,
queue, codec and playback settings remain unchanged.

One camera process owns one recording, shared by its peer pipelines. Frame/event
limits apply to the whole recording, including closed lifetimes, and never reset
when a peer disconnects. Stream/epoch/clock aliases are unique across at most
sixteen lifetimes. Peers can use identical PTS without sharing frame identity.
Capacity cannot evict earlier ledger entries or refill discarded event slots.
Further lifetimes need a new recording; their playback continues without new
trace collection. [Step 5](N4_TRACE_ADOPTION.md) adds explicit shutdown persistence and separate browser download.

## Boundaries and correlation

The adapter installs five buffer/event probes:

| Event | Exact location |
| --- | --- |
| capture_output | `video_capture` src pad |
| pre_encode_queue_enter | `pre_encoder_queue` sink pad |
| pre_encode_queue_exit | `pre_encoder_queue` src pad |
| encode_input | `video_encoder` sink pad |
| encode_output | `video_encoder` src pad |

Callbacks use only producer-local `time.monotonic_ns()` differences. A short
binding mutex protects lifetime/segment routing; a short recording mutex protects
identity, bounded storage and exact counters. Callbacks do no file, HTTP, export,
core-model validation or synchronous logging. Timing includes callback scheduling
and mutex waiting; overhead has not been measured. Contention and shutdown drop
counters are exactly zero for this blocking collector: events are serialized,
and callbacks after the closed interval are ignored rather than counted as loss.

PTS is an internal correlation key, never exported. Retained mappings and endpoint
sets are bounded by the admitted frame ledger. Unique, increasing source PTS can
associate sampled downstream endpoints; absent/invalid or unprovable regressing
PTS produces missing correlation. Duplicate source PTS invalidates implicated
frames even when the new frame is unsampled; repeated downstream endpoints mark
ambiguity. Final snapshots remove ambiguous downstream events and transfer their
counts to event_correlation_dropped without reusing capacity. These rules are
conservative software association, not proof of real VP8 preservation.

Pad probes also observe SEGMENT and flush events. Each downstream pad must have
the current source segment sequence before its buffers can join that lifetime.
A source segment transition closes the prior epoch; old queued buffers cannot
join the new map before their pad transitions. Reused segment keys suspend
collection. A noninitial source DISCONT flag pauses tracing until a new segment;
the first-buffer flag is accepted. Clock failure, unrepresentable timestamp or
regression closes the timing scope with source_error; it never yields a repaired
cross-reset duration. Gst segment propagation and PTS preservation still need
real-case verification. [GStreamer probe design](https://gstreamer.freedesktop.org/documentation/additional/design/probes.html).

## Teardown and snapshots

All tracing callbacks return Gst.PadProbeReturn.OK, including tracing failures.
Installation resolves all pads first and rolls back partial registration. Teardown
freezes a scope, removes probes and supports idempotent retries if removal fails.
GST errors close with source_error; peer disconnects close with shutdown. Enabled
tracing registers a GLib SIGTERM source so the camera loop exits through cleanup;
SIGKILL/process failure cannot promise a finalized or saved trace.

`HostTraceRecording.finish()` freezes every scope. Only then can
`snapshot(producer_version, provenance)` return detached sanitized record data;
it performs correlation filtering/copying outside callbacks and outside the
recording mutex. A real producer commit is required. Synthetic tests explicitly
set synthetic provenance. [Step 5 export](N4_TRACE_ADOPTION.md) uses this API after shutdown; the Step 6
trace-to-summary algorithm remains pending. Existing v2 exports, cumulative
queue/counter telemetry, unavailable N2 timing and N3 matching remain unchanged.

## Step 3 verification (historical)

Producer `npm run test:engine` builds and passes 133 Node tests with one existing
external-mirror artifact skip (134 discovered). Its two new Node cases run the
**31 Python collector/fake-pad tests** and check camera wiring. These 31 cases are
nested software checks, not 31 additional Node test results. Engine lint and
lockfile consistency pass. Twenty-five snapshots produced by those tests pass
strict core N4 validation, without schema/fixture/policy changes. Core focused
N4/schema/CLI checks pass 109 tests and all twelve schemas reproduce.

A local host GLib loop handles self-SIGTERM and exits/finalizes successfully;
no X11/VP8 pipeline is involved. Docker/Linux capture is still unavailable here.
No real timing, browser hook, clock synchronization, overhead comparison or
hosted/container execution is claimed by these tests. Step 4 subsequently delivers
[browser capability collection](N4_BROWSER_INSTRUMENTATION.md); [trace artifacts/adoption](N4_TRACE_ADOPTION.md) are delivered in Step 5; reconstruction remains Step 6.
