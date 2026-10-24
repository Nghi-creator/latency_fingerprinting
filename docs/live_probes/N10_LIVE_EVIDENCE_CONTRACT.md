# Live-relief evidence — N10 design contract

Design revision: `n10-live-evidence-design-v1`. This is an additive design for a
future live adapter and offline reconstruction. The [offline evidence model](N10_MODELS.md)
implements a conservative forensic subset with an additive schema and pure
inspection. No execution command or qualified live capability is implemented. The [capability inventory](N10_CAPABILITY_INVENTORY.md) remains a
metadata-only preflight. N9 proposals carry no authorization to act.

## Identity, authority and clocks

A request binds a bounded opaque request ID, acquisition ID, owner generation,
pipeline generation, peer generation, capability revision and pinned policy hash.
These are export-safe aliases, not tokens, process pointers, addresses or paths.
The producer resolves them to its local exact identities. A missing/mismatched
generation or a changed user control blocks application. A duplicate ID with
identical content returns the retained result; different content is a conflict.
Neither replay nor process restart replenishes durable execution budgets.

The initial candidate is `vp8_target_bitrate`, with integer `bit_per_second`
values and one property, `vp8enc.target-bitrate`. There is no preset switch,
pipeline restart or alternate-family fallback under this identity. The runtime
must first qualify that family on the exact producer/image/encoder configuration.
An unavailable capability retains reasons and permits no mutation.

The owner uses an explicitly identified process-monotonic clock for deadlines and
receipts, represented as integer nanoseconds relative to a recorded local origin.
Clock domain and generation accompany every timestamp. UTC may annotate export
but never drives a deadline or an elapsed subtraction. Browser/WebRTC clocks stay
in their source domains. Cross-domain observations require an explicit measured
alignment with uncertainty; otherwise joint windows are unavailable. A process
restart begins a new domain, not a continuation of elapsed time.

## Request and durable intent

Before mutation, validate capability, exact identities, stable PLAYING state,
receiver health, prior readback and supported rate-control mode. Record all
unrelated launch/encoder controls. Require qualified and predeclared limits for:

- Baseline and requested bitrate, minimum/maximum bitrate and maximum relative
  change; values remain within the runtime-supported range.
- Active duration, application and restoration deadlines, settling exclusions,
  minimum baseline/during/restoration observation durations and sample cadence.
- Request rate/cooldown, cumulative action count, active time and disturbance
  budget, plus connection, frame-progress and quality abort limits.

No live safety numbers are supplied by synthetic design vectors or N9's proposal
policy. Missing limits keep a request unavailable. Store intent and budget
reservation durably before invoking the setter. Reservation is consumed whenever
the setter may have acted, including exceptions and lost acknowledgements. Retain
the preimage, requested value, exact generation and restoration deadline in a
private journal; export only safe evidence. Failed durable intent prevents action.

## Receipts, windows and independent observations

Each attempted setter has a receipt with `call_start_ns`, nullable `call_end_ns`,
requested value and outcome (`returned`, `raised`, `interrupted`, `unknown`).
Capture intent before the call. A missing return time is not proof of no mutation.
Getter observations have start/end timestamps and explicit unavailable reasons;
they are setting observations, not independent effects or acknowledgements from a
receiver. Acknowledgement means only the boundary that actually returned.

Retain the complete ordered baseline, application, settling, during, restoration,
restoration-settling and post-restoration intervals. Windows are half-open
`[start_ns, end_ns)`, positive duration in one declared domain, non-overlapping,
and tied to one acquisition and exact generations. Setting-read brackets must
fall inside their declared observation interval. Excluded settling time remains
visible and is charged to active time/disturbance when a changed control may act.
No phase crosses application or restoration setter brackets. Missing windows
stay absent with reasons, never replaced by a healthy default or zero response.

Independent evidence includes encoded byte/frame counters and decoded/receiver
frame progress, counter reset identities, sampling intervals, negotiated media
configuration, connection state and measured quality/resource costs. Counter
deltas require unchanged generation, nondecreasing counts and a positive duration;
bytes × 8 / elapsed seconds is a measured output rate, not the configured target.
No samples during settling enter a response window. Preserve cadence/gaps: endpoint
progress alone cannot establish uninterrupted playback or bounded maximum stall.
Missing/reset counters and clock failures invalidate derived rates explicitly.

Unrelated controls must remain unchanged throughout usable evidence. Record drops,
frame gaps, CPU/resource use and quality with their actual availability, units and
denominators. A lower encoded rate can follow changed scene complexity or lower
quality; it alone proves neither benefit nor bottleneck causality. Do not derive
N3 paired-run responses or N8 hypotheses from these windows without a separately
versioned and tested response derivation contract.

## Ownership, termination and recovery

Only one owner may execute. An independent watchdog enforces maximum active time;
the control thread must not be its sole timeout mechanism. Cancel, deadline,
receiver loss, generation change, unhealthy progress/quality or foreign control
triggers abort and cleanup. No per-frame control callbacks, Python/filesystem work
in media callbacks, remote mutation endpoint or additional guest privileges.

Restoration is allowed only on the exact owned generation while the setting still
matches a value that this attempt may have applied. A foreign value blocks blind
rollback. A setter that raises may still have acted: re-read and reconcile owned
values; do not discard intent. Retain separate restoration setter/readback and
post-restoration output/receiver observations. A successful getter alone cannot
clear dirty state or establish receiver recovery.

Terminal outcomes keep action outcome (`not_applied`, `applied`, `aborted`,
`partial`, `unknown`) separate from restoration (`not_needed`, `verified`,
`failed`, `unknown`) and capability (`unavailable`, `qualified`). Only a verified
owned restoration plus required post-restoration observations can clear dirty
state after a possible mutation. Retain all failures, cost and budget consumption.
A dirty/unknown journal blocks new actions, including after restart. Recovery
checks actual generation and state before resolving; safe teardown is an explicit
interruption with cost, not successful live restoration. SIGKILL cannot promise
in-process rollback. Logs and idempotency results must survive owner restart.

## Qualification and isolated experiments

The producer's [isolated trial procedure](../../../Pixelated-Studio-Edition/docs/n10-bitrate-feasibility.md)
uses a disposable synthetic encoder/decoder to investigate installed-plugin
behavior. That tool has no live peer and no production journal. Its output is
operator evidence, not an accepted core root or capability grant. Local decoding
is not browser/WebRTC continuity, resource safety, diagnostic value or restoration
of a user's running stream. Even successful isolated trials keep live relief
unavailable until the full exact-runtime ownership, watchdog, receiver, quality
and restart/failure acceptance gates pass.

Existing N2/N5 clocks, paired-run roots, frozen schemas, fixtures and policies
retain their meanings. [Design vectors](N10_DESIGN_VECTORS.json) provide independent
abstract lifecycle expectations for later implementation; they are synthetic,
not production control logic, empirical thresholds or collected acquisitions.
