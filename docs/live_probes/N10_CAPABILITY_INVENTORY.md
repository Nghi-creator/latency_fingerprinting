# Live relief capability boundary

N9 returns bounded offline proposals. A proposal, profile label or matching result
has no authority to change a producer. N10 begins by inspecting the exact target
runtime before choosing one isolated live relief family. The detached Python core
continues to consume evidence; it does not import Gst or control frame callbacks.

The producer's [read-only inventory procedure](../../../Pixelated-Studio-Edition/docs/n10-capability-inventory.md)
reports installed Gst properties, read/write/construct flags, advertised PLAYING
mutability and setting reads from fresh NULL-state elements. It does not inspect
an existing peer, apply a setting, measure a response or qualify a live adapter.
Its operator JSON is not a new accepted core artifact/schema or calibration input.
Existing roots, policies, fixtures and defaults retain their original meaning.

## Existing controls and gaps

| Candidate | Existing producer surface | Evidence needed before selecting it |
| --- | --- | --- |
| Bitrate relief, first candidate | `vp8enc.target-bitrate`, bits per second; current stream profiles apply a compound preset at launch | Exact live target encoder, bounded application and observed setting, independent encoded/receiver evidence, unchanged unrelated controls, continuity and restoration |
| Capture-cadence relief, conditional fallback | Camera currently fixes framerate through launch caps; a [contained source-caps experiment](../../../Pixelated-Studio-Edition/docs/n10-cadence-feasibility.md) is available, but no owned live controller is installed | A genuine bounded controller with negotiated caps, independent frame/cadence evidence and receiver continuity; a profile restart is a different operation |
| Encoder-cost relief, deferred | Launch profile selects `cpu-used` and `max-quantizer` alongside bitrate/FPS | Version-specific live mutation, output/quality and restoration proof before implementation |
| Existing N5 capture pacing | Opted-in `identity.sleep-time` adds delay to create a slowdown fault | Removing an owned N5 fault is cleanup, not a general live-relief capability; its leases/evidence cannot be relabelled as N10 proof |

An installed property is not an available probe. `G_PARAM_WRITABLE` is distinct
from Gst's [`GST_PARAM_MUTABLE_PLAYING`](https://gstreamer.freedesktop.org/documentation/gstreamer/gstparamspec.html)
metadata. Presence of the latter is an advertised state property, not measured
application or restoration. Absence is an evidence gap, not proof that a plugin
ignores all live setters. No missing flag is inferred from a successful getter.
The [VP8 encoder documentation](https://gstreamer.freedesktop.org/documentation/vpx/vp8enc.html)
also makes bitrate/quantizer behavior dependent on its rate-control mode.

A fresh NULL element reports plugin defaults, not a running camera's launch
profile. A getter on the setter's own element is a setting observation; it is not
independent proof of encoded output, receiver continuity, benefit or rollback.
A plugin-only `videorate` inventory does not mean the camera contains that element.

## Capability acceptance

Select one family only after a controlled target-runtime feasibility trial
preserves isolated control, unrelated settings and output continuity. Prefer
bitrate only if demonstrated; evaluate a cadence fallback only if justified.
If no family qualifies, retain unavailable with its evidence gaps. Do not replace
an unavailable operation with a preset switch, restart or simulated acknowledgement.

The live contract must then bind an explicit request to an exact owned
pipeline/peer/property generation and preserve:

- Control name/units, prior/requested/applied values, settling exclusions and
  baseline/during/restoration windows with source clocks and acquisition identity.
- Application, acknowledgement and observed-readback times; partial setter
  failures and missing observations remain explicit.
- Local single-owner authorization, durable intent before mutation, idempotence,
  duration/intensity/frequency/cumulative budgets, cancellation and health aborts.
- Independent watchdog, owned-value restoration/readback, dirty/unknown recovery
  and restart behavior. SIGKILL cannot promise in-process rollback.
- Measured disturbance/quality/resource cost and receiver evidence. A completed
  setting change alone establishes neither diagnostic value nor safe restoration.

These are prerequisites for a live contract and adapter, not capabilities conferred
by the inventory. Current N2 wall-clock-derived elapsed time and N5 paired-run
roots cannot silently become monotonic live before/during/after evidence.
Host/runtime acceptance is specific to the tested image and versions; normal
desktop/picker/reconnect acceptance remains a separate prerequisite for using
new behavior that depends on those flows.

The [live-evidence design contract](N10_LIVE_EVIDENCE_CONTRACT.md) specifies the
ownership, clock, window and recovery boundary. The separate [offline evidence
model](N10_MODELS.md) adds a conservative forensic root; neither inventory nor
validated evidence authorizes a live adapter.

For encoder feasibility, the producer's [contained bitrate experiment](../../../Pixelated-Studio-Edition/docs/n10-bitrate-feasibility.md)
has fixed short, settled and unchanged-control protocols. Retain the unchanged
control as well as changed-bitrate results: scene/warm-up drift can change output
without a control effect. Its exact byte/duration screens are synthetic experiment
criteria, not live safety limits or scientific calibration. Even a passed screen
leaves receiver continuity, quality, bounded stalls, watchdog and owned live
restoration/recovery unverified. No isolated result grants live authority.

A successful isolated control/restore screen may select a candidate for a
default-disabled owned implementation. It does not qualify production activation.
The [capture-cadence procedure](../../../Pixelated-Studio-Edition/docs/n10-cadence-feasibility.md)
uses actual source-caps renegotiation rather than N5 delay injection; its private
static-Xvfb and local-decoder scope leaves moving-game workload, real receiver,
quality and production ownership/watchdog/recovery acceptance open. Cadence
operator evidence is distinct from the frozen bitrate-only forensic root; do not
relabel it as `vp8_target_bitrate`.

The producer's [default-disabled cadence lifecycle kernel](../../../Pixelated-Studio-Edition/docs/n10-cadence-controller.md)
adds private request/budget/journal/watchdog mechanics for a dedicated worker.
Its explicit isolated worker now binds its own synthetic Gst WebRTC sender and
receiver, including cancellation and receiver-loss teardown drills. This is not
a production camera/browser binding. The additive [cadence evidence format](N10_CADENCE_EVIDENCE.md)
imports and independently inspects its observations without granting authority.
Quality/resource qualification and production activation remain unavailable.
