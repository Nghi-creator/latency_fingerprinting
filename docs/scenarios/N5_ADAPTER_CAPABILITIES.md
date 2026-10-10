# N5 adapter capabilities and real gates

**Inspected/frozen:** 2026-10-10, Step 2 specification. Nothing below claims a
new implemented harness or a measured fault. [Contract](N5_EXPERIMENT_CONTRACT.md)
defines the exact v1 meaning; [examples](N5_EXPERIMENT_EXAMPLES.md) are synthetic.

Producer paths are relative to Pixelated-Studio-Edition. This is ownership
inventory, not a runtime dependency or authorization to execute live actions.

| Scenario enum | Inspected surface | V1 approval/support |
| --- | --- | --- |
| `healthy` | Camera draining peer, encoder counters, player trace/research collectors | Approved `none` adapter; new runner/phase evidence still unimplemented |
| `host_contention` | Core bounded CPU-pressure helper; producer runtime process ownership and resource telemetry | Approved `bounded_cpu_pressure`, 1–8 owned workers; producer adapter, worker CPU evidence and bounded crash/cleanup control still unimplemented |
| `render_capture_slowdown` | camera.py source is X11; no inspected render/capture delay controller | Unavailable/adapter_not_implemented; do not fabricate from CPU pressure |
| `encoder_overload` | VP8 stream profiles affect several settings/capture cadence | Unavailable/adapter_not_implemented; profile change alone is not isolated encoder ground truth |
| `network_delay` | Existing signaling/transport smoke tests | Unavailable/adapter_not_implemented; no dedicated owned shaping namespace inspected |
| `network_jitter` | Same transport surfaces | Unavailable/adapter_not_implemented |
| `network_loss` | Same transport surfaces | Unavailable/adapter_not_implemented |
| `bandwidth_pressure` | Same transport surfaces | Unavailable/adapter_not_implemented |
| `client_decode_pressure` | Browser getStats cumulative means and rvfc callback evidence | Unavailable/adapter_not_implemented; no approved bounded client workload/effect control |
| `mixed` | No stable single-cause campaign yet | Unavailable/adapter_not_implemented; versioned approval follows stable singles |
| `changing` | No stable single-cause campaign yet | Unavailable/adapter_not_implemented; cannot silently switch cause inside v1 |

Only healthy and host contention may declare an available adapter in v1, after
actual preflight or in explicitly synthetic tests. Approving implementation is
not claiming the adapter is implemented or usable on this host.

## Runtime ownership gaps to implement

- `engine/runtime/src/runtime/processes/processLifecycle.ts` binds existing
  child error/exit events to session cleanup. It is not a crash-safe experiment
  lease/journal or bounded reap proof; private output tails must not be exported.
- `launchers/cameraLauncher.ts` launches Python under runtime session/environment
  ownership. A harness must keep normal user process control separate and must
  not export tokens, ICE credentials, addresses or raw session identifiers.
- `scripts/shared/smokeCleanup.mjs` attempts all registered cleanup actions and
  records failures. It does not itself impose deadlines or verify restoration.
- `experiments/bounded_cpu_pressure.py` in the core has 30–300 s and 1–8 worker
  limits and an experiment-only acknowledgement. Its joins are not bounded and
  it lacks crash recovery or phase worker-CPU measurement. Do not directly launch
  it and claim N5 cleanup/effect verification; reuse/adapt the approach under
  producer ownership with deadline, exact handles and measured CPU durations.
- Camera tracing starts at pipeline creation; browser collection ends on explicit
  export. N5 needs new fresh post-warm-up/per-phase recording control with old
  callbacks and queued frames excluded. N4 contract and limits remain unchanged.
- Existing research configuration also has `custom` alongside healthy/degraded/
  relief. None is silently remapped into N5's six-phase lifecycle.
- Camera counter snapshots aggregate peers and can regress on peer removal. V1
  evidence needs one observed peer/encoder generation; a reset is partial/unavailable,
  not a negative or clamped throughput measurement.

## Effect and restoration criteria frozen before trials

Use the contract's independent interval arithmetic. Healthy requires ≥27 fps
in healthy/degraded/recovery. Host contention requires adequate healthy FPS,
observed pressure workers consuming ≥50% of one core during degraded, degraded
FPS ≤95% of healthy and recovery FPS ≥95% of healthy, with no remaining owned
workers in recovery. Every evaluated phase needs ≥30 complete intervals and ≥30 s.
These are provisional engineering predicates, not an isolated-cause diagnosis,
calibrated probability or hardware guarantee. Save failures, insufficient evidence
and actual action timing; never relabel after inspecting results.

Preflight requires a draining actual Linux/Xvfb/PulseAudio VP8 peer, known workload,
fixed configuration, monotonic source and measurable worker/frame counters. Missing
runtime/clock/source fails closed. V1 never mutates host-global networking, launches
arbitrary shell commands or kills unrelated processes. Future network support must
first approve namespace/lease ownership, privilege requirements, effect evidence
and exact restoration in a new reviewed release.

## Real acceptance remains separate

N5 v1's two approved scenarios contain only one fault class. The roadmap requires
at least two real single-bottleneck classes with independent repetitions and
held-out queries; healthy does not count as a bottleneck class. That Phase 1.3 gate
stays open until additional controls are approved/implemented and real evidence
exists. V1 cannot claim completion from synthetic runs or one host pressure case.

[N4 runtime acceptance](../observability/N4_RUNTIME_ACCEPTANCE.md) still requires
its ≥500 pairs, ≥95% correlation, nominal/loss/restart/two-peer/browser trials,
five paired overhead trials and diagnostic/export measurements. N5 effect thresholds
do not replace or relax those separate gates. Docker/Linux runtime, actual Node 24,
Python 3.11 and hosted verification remain unavailable/unverified in local evidence.
