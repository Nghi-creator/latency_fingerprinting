# N4 Implementation Plan: Stage-Level Observability

**Slice ID:** N4
**Status:** Steps 0–1 complete locally; Steps 2–7 remain unimplemented
**Updated:** 2026-10-09
**Parent roadmap:** [Phase 1.2](FULL_IMPLEMENTATION_PLAN.md#12-add-stage-level-observability)
**Predecessor:** [N3 software closeout](../archive/analysis/N3_SOFTWARE_CLOSEOUT.md)
**Archived predecessor plan:** [N3 analytical features and matching](archive/N3_ANALYTICAL_FEATURES_AND_MATCHING_PLAN.md)
**Baseline evidence:** [Post-N3 health audit](../archive/analysis/N3_ARCHITECTURE_AUDIT.md)
**Current progress:** [N4 implementation progress](../observability/N4_IMPLEMENTATION_PROGRESS.md)

N1–N3 are complete locally. The latest recorded Python 3.13.13 baseline is
1,539 passing tests and 93.58% branch-inclusive coverage at the unchanged 85%
floor. Actual Python 3.11/hosted verification remains pending. Current N2 stage
records are explicitly unavailable; current exported elapsed time is derived
from wall clocks. N4 is planned work, not evidence that instrumentation exists.

## Outcome and boundary

Produce sanitized trace evidence that can reconstruct stage-local durations,
queue waiting and frame age where the producer actually observes them. Each
value must identify its method, clock domain, source and coverage. Unobservable
stages remain explicitly unavailable. Independent producer clocks cannot be
subtracted without a reviewed synchronization method and measured error bounds.

Pixelated Studio Edition owns runtime instrumentation and export. This repository
owns strict trace validation, offline reconstruction and evidence inspection.
Per-frame hooks remain in the producer; Python stays off the frame-critical path.
Instrumentation must be opt-in, bounded and removable without changing playback.

Preserve P0/N1/N2/N3 schemas, fixture bytes, registry/policy releases, matcher
thresholds and existing command outputs. In particular, do not relax N2
`StageTiming` validation to admit new measured values under its old contract.
Use additive trace/summary roots and explicitly versioned producer artifacts;
names and versions are frozen in the [Step 1 contract](../observability/N4_TRACE_CONTRACT.md). N4 timing is not automatically
an N3 matching feature or a replacement for cumulative WebRTC means/proxies.

The subsequent reproducible scenario harness remains Phase 1.3 work. N4 does
not implement fault campaigns, diagnosis calibration, live probes, remediation,
a deadline scheduler, hardware certification or synchronized one-way latency.

## Repositories and starting surfaces

| Owner | Existing surface to inspect | N4 responsibility |
| --- | --- | --- |
| Pixelated engine | `engine/runtime/camera.py` and `engine/runtime/camera_state.py` | Locate actual pipeline boundaries, local monotonic clocks and telemetry/queue hooks |
| Pixelated browser | `apps/web/src/features/research-mode/researchTelemetryContract.ts` and player collection code | Declare accessible browser evidence and attribution limits |
| Pixelated exporter | `apps/web/src/features/player/research/researchBundleV2.ts` and `researchRunExportArtifacts.ts` | Add an explicit trace artifact contract with support/loss metadata |
| Python core | [N2 timing support](../../src/latency_fingerprinting/models/v2_support.py), [adoption](../measurement/OBSERVATION_V2_ADOPTION.md), [safe extraction](../measurement/SAMPLE_EXTRACTION.md) | Preserve existing behavior; add separate trace validation/adoption |

Paths above are starting points in the existing sibling producer repository,
not an approved hook inventory. Step 1 must inspect actual ownership and applicable
repository instructions before fixing producer integration locations.

## Step 0 — Preserve and reproduce the post-N3 baseline

**Local gate:** Complete, 2026-10-09. Both starting trees were clean. Core: 1,539
tests, 93.58% branch-inclusive coverage and all preservation gates pass. Producer:
182 web tests pass; engine build succeeds with 131 tests passing and one existing
external-artifact skip. Engine/web lint, web TypeScript compilation and lockfile
consistency pass. Runtime/hosted limitations and starting commits are recorded
in [N4 progress](../observability/N4_IMPLEMENTATION_PROGRESS.md).

Record commits and working-tree state in both repositories. Reproduce this core's
[quality gates](../measurement/QUALITY_GATES.md): full coverage suite, ten schemas,
registry/policy releases, four fixture families, three reproduction modules,
controlled P0 artifacts, run-001 seed and exact run-002 match. Record applicable
producer tests and whether the runtime/hardware is available. Preserve unrelated
working-tree changes and distinguish configured CI from actual execution.

Gate: a reproducible baseline and explicit local/hosted/runtime limitations are
recorded before changing contracts or instrumentation.

## Step 1 — Freeze the timing, identity and capability contract

**Specification gate:** Complete, 2026-10-09. The [field/method contract](../observability/N4_TRACE_CONTRACT.md),
[producer capability matrix and real/overhead criteria](../observability/N4_PRODUCER_CAPABILITIES.md)
and [independent examples](../observability/N4_TRACE_EXAMPLES.md) are fixed. This
delivers definitions only; hooks, schemas, commands and real measurements remain pending.

Inspect real capture, encoder, sender and browser boundaries. Author
`docs/observability/N4_TRACE_CONTRACT.md` and a producer capability matrix with:

- Sanitized session/run/frame/trace identity, sequence scope, restart boundaries,
  timestamp units, clock source/resolution and method versions. Retain explicit
  correlation gaps when a frame cannot be followed across an interface.
- Exact event boundaries for render-ready, capture, pre/post encode, sender queue/
  send, receive, decode, render and display proxy, marking each available,
  estimated or unavailable for each producer. Polls are not per-frame events.
- Duration formulas and legal same-domain pairs, queue occupancy versus sojourn,
  frame-age reference points, and negative/duplicate/out-of-order handling.
- Clock-domain and synchronization evidence, error bounds and feedback delays.
  GStreamer timestamps, Python monotonic time, browser performance time and UTC
  require explicit relationships; a shared label alone does not synchronize them.
- Declared deadline budget and versioned derivation, if any. Without an explicit
  budget/reference, slack and deadline-hit status remain unavailable.
- Sampling, capacity, drop/overflow accounting, privacy allowlists, byte/row/depth
  bounds, artifact hashes, version rejection and canonical serialization.
- Additive trace/summary root names, producer artifact/bundle versioning, local
  CLI inputs/outputs and unchanged N2/N3 boundaries. No silent v2 reinterpretation.

Gate: every proposed number has a reviewed measurement meaning and independent
example; capability gaps and the minimum real producer acceptance case are fixed
before implementation. Do not promise a browser frame ID or hardware hook that
the inspected producer cannot supply.

## Step 2 — Implement strict additive trace contracts

Add focused observability models/modules and schemas using Step 1 definitions.
Validate finite strict numbers, method versions, ordered unique identities,
clock references, event/state consistency, loss accounting and bounded containers.
Revalidate copied instances and detach mutable inputs. Unsupported/unknown methods
fail closed; unavailable evidence has null values and an explicit reason.

Add independently authored clock/identity/order/range/privacy/resource regressions.
Do not modify frozen N2 stage records, registry outputs or N3 feature policy.

Gate: accepted evidence has a reconstructable meaning; existing ten schemas,
approved releases and reproduction pins remain byte-identical.

## Step 3 — Add bounded host capture and encoder instrumentation

Implement opt-in hooks at the approved engine boundaries. Use producer-local
monotonic timestamps and explicitly scoped IDs; retain restart/reset boundaries.
Keep callbacks short with bounded buffering, sampled collection where specified,
loss counters and teardown. Avoid synchronous export or Python-core calls in
frame callbacks. Report queue occupancy and waiting separately.

Test disabled mode, enabled ordering/correlation, dropped events, overflow,
shutdown and restarts with the producer's established test tooling. Software
hook tests do not establish measured timing or real hardware availability.

Gate: bounded trace collection preserves the disabled path and identifies every
instrumented event's actual location and clock domain.

## Step 4 — Add browser and transport capability evidence

Implement only hooks/API evidence approved in Step 1. Keep existing WebRTC
cumulative decode/buffer means and RTT separate from per-frame timing. Declare
receiver, decode, render/display-proxy and sender support individually. Do not
invent sender-to-browser frame correlation or one-way delay from unrelated clocks.
Retain clock resolution, sampling and feedback-delay limitations.

Gate: supported stages carry method evidence; inaccessible stages and missing
correlation remain explicit rather than becoming fabricated timestamps or zeros.

## Step 5 — Export and adopt bounded trace artifacts

Implement the reviewed producer artifact/version contract, then an additive Python
reader and CLI. Keep old bundle versions and their existing ingestion outputs
unchanged. Reuse bounded, duplicate-safe, no-follow input handling where compatible;
add trace-specific row/event limits, identity/privacy checks and version rejection.
Include support/loss declarations and hashes in the same validated read.

Document producer export and Python commands together. Wrong versions, malformed
records, unsafe links, oversized inputs and mismatched artifacts fail without
partial output. No supplied record can resolve a remote URL or change method meaning.

Gate: the approved new producer export is consumable deterministically; legacy
directory/TAR outputs and all existing pinned fixtures still reproduce exactly.

## Step 6 — Reconstruct stage-local timing and inspect evidence

Implement pure derivation from validated trace evidence. Retain event pairing,
clock/method references, counts, exclusions, dropped/missing evidence and declared
sampling. Derive only approved same-domain durations, frame-age references and
deadline quantities. Reject impossible/nonfinite/unrepresentable arithmetic;
never bridge restarts, unmatched frames or unsupported cross-domain intervals.

Expose a read-only inspection result with independently reconstructable statistics
and observed/estimated/unavailable distinctions. Keep results separate from N3
normalization, fingerprints and match decisions.

Gate: independent positive/zero/missing/out-of-order/reset/clock-domain cases prove
the published durations and coverage, with no one-way latency claim.

## Step 7 — Verify producer integration, overhead and close out

Add separately pinned synthetic trace fixtures and read-only reproduction. Exercise
export-to-inspection across producer and Python boundaries. Run applicable tests
in both repositories, old preservation gates, documentation/link checks and CI
configuration checks, distinguishing local from actual hosted execution.

Execute the minimum real capture acceptance case specified in Step 1. Record
producer versions, instrumentation locations, runtime/hardware, bounded-buffer
behavior and overhead with/without instrumentation under a documented procedure.
Set an overhead acceptance criterion before measurement; do not call an unmeasured
hook software-validated real timing. Capture at least the approved stage-local
boundary pair and show explicit unavailability for the rest.

If runtime/hardware is unavailable, retain implemented software and the concrete
pending integration/overhead gate; do not mark full N4 observability complete.
Publish `N4_SOFTWARE_CLOSEOUT.md` with separate software, real-capture and hosted
results. Archive its progress/audits and plan on the following transition.

Gate: a sanitized real trace reconstructs the approved stage-local timing, explains
unavailable stages and meets the measured overhead criterion. Remaining Phase 1.3
scenario/held-out experiment work stays separate.

## Exit checklist

- [x] Both repository baselines and existing reproduction gates are recorded.
- [x] Timing/identity/method/capability/version and privacy/resource meanings are frozen.
- [ ] Strict additive models/schemas preserve all existing contract bytes.
- [ ] Host instrumentation is opt-in, bounded and handles restarts/loss/teardown.
- [ ] Browser/transport evidence exposes actual capabilities and correlation limits.
- [ ] Versioned producer export and Python adoption agree without changing old outputs.
- [ ] Offline timing reconstruction retains clocks, methods, pairing and exclusions.
- [ ] Independent fixtures, pins and cross-repository tests reproduce.
- [ ] Real stage-local capture and instrumentation overhead acceptance are recorded.
- [ ] Actual minimum-version/hosted results or explicit outstanding items are recorded.
- [ ] Current docs, commands, archive navigation and closeout match delivered behavior.

**Next implementation action:** Step 2 strict additive trace models/schemas. Steps
0–1 are complete locally; runtime instrumentation has not started. Phase 1 also needs the subsequent
scenario harness; the roadmap's seven phases are not a fixed N1–N7 slice count.
