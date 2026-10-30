# Qualification and activation requirements

N10 distinguishes selecting an implementation candidate, exercising it in a
contained engineering fixture, qualifying a bounded operation for a supported
context, and enabling that operation in a producer. Passing one stage does not
grant the next stage. N9 proposals and offline evidence cannot authorize actions.

The [capability inventory](N10_CAPABILITY_INVENTORY.md) defines candidate selection:
investigate bitrate first, then capture cadence if justified by observed runtime
behavior. The owned cadence controller is an engineering implementation candidate.
Its isolated synthetic and owned-game sources permit explicit contained dispatch.
Normal production sources reject that configuration and dispatch. A project may
retain an unavailable family when qualification requirements are unmet.

## Evidence required for a supported context

| Requirement | Evidence and acceptance boundary |
| --- | --- |
| Exact context | Pin the image, actual runtime/source/receiver versions, profile, codec settings, capture source, dimensions and relevant platform. Read back settings; an intended configuration or matching method name is insufficient. |
| Isolated operation | Observe the requested control, unrelated settings, source output and independent receiver progress before, during and after the action. Profile switches and pipeline restarts are different operations. |
| Owned lifecycle | Exercise local authorization, exact worker/source binding, durable reservation, idempotence, cancellation, deadlines, watchdog, foreign state, receiver/source loss, replacement and restart. Unknown restoration remains unknown and dirty state blocks further actions. |
| Temporal and visual continuity | Apply predeclared window, gap, drop/freeze and coverage rules, including transitions outside measured windows. Nonblank and varying pixels establish only limited visual proxies. |
| Read-only observation cost | Use a complete, context-matched off/on cohort with fixed budgets, original case order and all paired comparisons. This measures the observation/admission path without a relief action. |
| Action disturbance and resource cost | Compare the actual bounded action with an unchanged control using a separately frozen, comparable acquisition protocol and explicit cost limits. Baseline/during/restoration point estimates alone do not isolate the action from changing content or scheduling. |
| Quality and user acceptance | Define and assess the permitted cadence/quality loss, audio continuity, perceptual quality and supported desktop workflows. A successful video setting change or negotiated audio track does not establish these requirements. |
| Limits and activation | Bind qualified contexts and reviewed limits to an explicit capability/policy revision. Enable only the qualified local operation, with defaults and unsupported contexts remaining unavailable. |

Qualification rules and limits must precede qualification acquisition. Existing
engineering durations, cadence tolerances, CPU/RSS budgets and synthetic design
vectors are scoped test criteria; they are not automatically approved live
safety limits. Keep acquisition failure, unavailable measurements, measured limit
violations and acceptance not yet performed distinct.

Hashes identify supplied records and context. Reproducible owned acquisition,
source provenance and the recorded observations support their interpretation;
hashes alone do not authenticate execution. The
[integrated cohort reconstruction](N10_INTEGRATED_GAME_RECORD.md) recomputes
supplied measurement and hashed lifetime/journal consistency. Its result cannot
create a qualified capability or override producer source guards.

## Comparing cost evidence

The producer's
[moving observer procedure](../../../Pixelated-Studio-Edition/docs/n10-observer-disturbance.md)
compares read-only observation off/on with fixed paired budgets. Its resource
scope excludes the cadence controller's active action and restoration. A passing
observer screen cannot fill the action-disturbance requirement.

The
[contained control procedure](../../../Pixelated-Studio-Edition/docs/n10-contained-game-control.md)
retains phase-specific native and browser resource observations. These are useful
descriptive costs under instrumentation. Successive windows have changing game
content, and their independent clock domains are not aligned. They cannot become
matched unchanged/action repetitions, a CPU benefit estimate or a perceptual
quality decision by subtraction or averaging.

The producer also provides a separate
[fixed-schedule unchanged/action acquisition](../../../Pixelated-Studio-Edition/docs/n10-action-cost.md).
Its unchanged condition creates no action or reservation, and both conditions
share fixed script-age windows. A separately versioned fixed-order six-session
measured-phase comparison is also available
with explicit context/timing comparability and null deltas for unavailable pairs.
The separate
[full-span acquisition](../../../Pixelated-Studio-Edition/docs/n10-full-span-cost.md)
captures declared native/browser costs through the phase gaps and retains failed
prefixes. Its matched comparison keeps native, browser and container intervals
separate; a container CPU checkpoint through cleanup callbacks supplies a bounded
cleanup interval while excluding later process/container/browser exit. These
procedures supply descriptive costs for their stated scopes;
they cannot establish total system/failure-cleanup cost, reviewed cost limits or
qualification. The producer also provides a separate
[actual fault-cost acquisition](../../../Pixelated-Studio-Edition/docs/n10-fault-cost.md)
for cancellation, receiver/source loss and reconnect, preserving their restoration
and journal rules. Its bounded cleanup intervals do not establish a cost policy
or parent-death/watchdog-specific cost qualification. A separate
[owned-game controller-thread-exit procedure](../../../Pixelated-Studio-Edition/docs/n10-fault-cost.md#owned-game-controller-thread-exit-cost)
requires observed thread exit and continued media progress before unresolved
worker teardown. It measures its own bounded costs; it does not establish a
blocked controller thread, whole-camera death, which guard won the teardown race,
or acceptance of cost/quality limits. A separate
[blocked-controller procedure](../../../Pixelated-Studio-Edition/docs/n10-fault-cost.md#owned-game-blocked-controller-cost)
requires a live control thread, elapsed post-fault time and advancing media
before unresolved teardown. These records retain separate methods and cannot
be substituted into the earlier fault cohort. A separate
[whole-camera-death procedure](../../../Pixelated-Studio-Edition/docs/n10-fault-cost.md#whole-camera-death-cost)
pins the exact camera and child lifetimes from an external monitor, retains
unresolved intent and measures costs through owned descendant cleanup. Its
interval includes source teardown and differs from camera cleanup-callback
costs. It does not establish automatic desktop disconnect handling, a complete
camera restart/reconnect workflow, or reviewed cost/quality acceptance.

For an action-cost comparison, predeclare the unchanged condition, actual action,
session order, independent repetitions, warmup, measurement/exclusion windows,
comparability rules, scopes, limits and missingness before collection. Retain
settling and restoration costs, including failed attempts. Preserve both
conditions and all original rows; do not substitute a diagnostic or later pass
for an unavailable or failed row. Compare only supported contexts. Matching
script phase does not establish identical pixels or eliminate scheduling noise.

Historical evidence retains its actual bitrate, image and source context. A
new source snapshot requires current-context verification or a documented,
reviewable applicability argument. Do not relabel fallback settings, mix source
versions into one fixed cohort, adjust limits after seeing results or call a
post-fix cohort a replacement for an earlier failure.

## Decision and producer boundary

The producer provides a read-only
[qualification protocol checker](../../../Pixelated-Studio-Edition/docs/n10-qualification-protocol.md)
for exact context, versioned procedures, cost units/intervals, quality criteria,
fault-scope and exclusion decisions. It reports missing declarations without
approving review references or evidence. The separate v2 format declares thread
exit/block and whole-camera costs explicitly, keeps camera descendant cleanup
distinct from cleanup callbacks, and records separate matched-action and fault
request durations. The v1 format and its hashes remain unchanged. Even a complete
draft retains false live
authority and unavailable qualification; no controller consumes it for dispatch.

Record the decision against the complete evidence set and supported context. A
missing required gate yields **unavailable**, with the specific missing evidence
or acceptance. An engineering screen marked `met` remains an engineering screen.
Operator-specific decisions, plans and acquisition receipts belong in ignored
`local/`, not as public project audit writeups.

The current offline evidence roots permanently retain their engineering roles
and `live_authority=false`. A qualification/activation mechanism must be explicit;
it must not repurpose a record hash, producer success flag, receiver capability,
N9 proposal or mutable caller JSON into authorization. Normal production sources
continue to reject engineering control configuration. No LAN/browser mutation
endpoint is implied by these procedures.

N11 diagnostic utility, live-window response derivation and independent held-out
evaluation are separate from qualifying the safety and cost of an operation.
Engineering acquisitions cannot silently become training or final-test evidence.
