# N5 producer lifecycle and recording control

**Contract:** [Experiment contract](N5_EXPERIMENT_CONTRACT.md)
**Producer guide:** [Pixelated lifecycle](../../../Pixelated-Studio-Edition/docs/n5-lifecycle.md)

The producer now implements a stdlib-only `scenario_harness` package with strict
immutable local plans, a single-use six-phase runner, monotonic deadlines,
contiguous covered counter prefixes, action attempts and restoration checkpoints.
Its private mode-0700 lease directory contains no-follow mode-0600 regular files,
a nonblocking exclusive lock and a durable atomic ownership journal. Mutation
hooks run only after prepared exact resource/generation intent is journalled.
Restart recovery verifies those exact identities; dirty/unknown ownership cannot
be overwritten or restored by guessing a PID.

The runner requires trusted cooperative runtime hooks with explicit budgets. It
cannot preempt arbitrary blocking Python/GI code. [adapters](N5_SUPPORTED_ADAPTERS.md)
now supply concrete draining-peer hooks, parked-child identities, bounded TERM/KILL/reap
and owned worker CPU clocks.
The internal execution object is not a public
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

Warm-up's initial collector is separate; [implementation guide](N5_EXPERIMENT_INSPECTION.md) exports the four frozen phase
collectors explicitly. Existing shutdown export is never relabelled as a fresh
post-warm-up phase. No filesystem/export/core work occurs in frame or barrier
callbacks. Both runtime images include the helper and harness.
