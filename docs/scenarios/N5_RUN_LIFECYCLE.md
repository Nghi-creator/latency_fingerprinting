# N5 producer lifecycle and recording control

**Delivered:** Step 4 software, 2026-10-11.
**Contract:** [Frozen experiment v1](N5_EXPERIMENT_CONTRACT.md).
**Producer API/hooks:** [Implementation guide](../../../Pixelated-Studio-Edition/docs/n5-lifecycle.md).
**Progress:** [N5 evidence ledger](N5_IMPLEMENTATION_PROGRESS.md).

The producer now implements a stdlib-only `scenario_harness` package with strict
immutable local plans, a single-use six-phase runner, monotonic deadlines,
contiguous covered counter prefixes, action attempts and restoration checkpoints.
Its private mode-0700 lease directory contains no-follow mode-0600 regular files,
a nonblocking exclusive lock and a durable atomic ownership journal. Mutation
hooks run only after prepared exact resource/generation intent is journalled.
Restart recovery verifies those exact identities; dirty/unknown ownership cannot
be overwritten or restored by guessing a PID.

The runner requires trusted cooperative runtime hooks with explicit budgets. It
cannot preempt arbitrary blocking Python/GI code. [Step 5 adapters](N5_SUPPORTED_ADAPTERS.md)
now supply concrete draining-peer hooks, parked-child identities, bounded TERM/KILL/reap
and owned worker CPU clocks.
The original Step 4 software tests exercised fake runtime dependencies and did
not establish real workers or trials. Subsequent real acquisitions are recorded
in the [runtime ledger](N5_RUNTIME_ACCEPTANCE.md). The internal execution object is not a public
`ExperimentResult`, artifact bundle or verified effect. Private final-release
watchdog timestamps must not be copied into runner-relative exported evidence.

The actual camera exposes an explicit local `create_peer_recording_control` API
for one exact opted-in peer. A bounded source IDLE barrier permits retiring the
old probes and installing a fresh collector, clock and admission floor for each
measured phase. Queued buffers already admitted by the old source and retired
callbacks cannot join the new recording. Source blocking spans collector rotation;
its live cost remains an overhead measurement gate. Missing source/barrier or
incomplete retirement fails closed and retains exact failed handles for cleanup.
Normal tracing-disabled playback and frozen N4 root/schema formats are preserved.

Warm-up's initial collector is separate; [Step 6](N5_EXPERIMENT_INSPECTION.md) exports the four frozen phase
collectors explicitly. Existing shutdown export is never relabelled as a fresh
post-warm-up phase. No filesystem/export/core work occurs in frame or barrier
callbacks. Both runtime images copy the helper and harness; no container build
was run here.

Seventy producer Python regressions cover lifecycle/ownership failures, strict
budgets, setup origin, fractional intervals, cancellation/reset/clock regression,
restart/foreign generation, source barriers, stale frames/callbacks, partial probe
installation, cleanup retry and actual runner→collector integration with fake pads.
Synthetic producer→core N4 exports still reproduce all pinned records/summaries
and API/CLI bytes. Core models/schemas/policies/fixtures are unchanged in Step 4.

**Successor:** [Step 5 adapters/effect checks](N5_SUPPORTED_ADAPTERS.md) delivered.
**Successor:** [Step 6 export/adoption/inspection](N5_EXPERIMENT_INSPECTION.md) delivered.
**Successor:** [Step 7 independent fixtures/pins](N5_EXPERIMENT_FIXTURES.md) delivered.
**Current:** Step 8 remaining desktop/final hosted acceptance.
[Current runtime acceptance](N5_RUNTIME_ACCEPTANCE.md) records verified nominal
capture, selected-workload overhead/lifecycle cases, minimum-version execution
and the complete passing 18-trial cohort. Browser execution method checks also
pass locally. Core hosted baseline CI is verified; normal desktop/picker and
hosted checks of final browser changes in both repos remain open.
