# N5 adapter capabilities and real gates

[Contract](N5_EXPERIMENT_CONTRACT.md) defines the exact v1 meaning; [examples](N5_EXPERIMENT_EXAMPLES.md) are synthetic.

Producer paths are relative to Pixelated-Studio-Edition. This is ownership
inventory, not a runtime dependency or authorization to execute live actions.

| Scenario enum | Inspected surface | V1 approval/support |
| --- | --- | --- |
| `healthy` | Camera draining peer, encoder counters, player trace/research collectors | Approved `none` adapter; lifecycle, actual camera hooks and fixed effect checks delivered in software; Linux availability requires preflight |
| `host_contention` | Core bounded CPU-pressure helper; producer runtime process ownership and resource telemetry | Approved `bounded_cpu_pressure`, 1–8 workers within observed allocation; durable parked children, pidfd cleanup/recovery, owned CPU clocks and fixed effects delivered |
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
actual preflight or in explicitly synthetic tests. Software implementation does
not establish Linux availability or a verified live effect on this host.

## Integration boundaries

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
  export. [N5 fresh recording control](N5_RUN_LIFECYCLE.md) now excludes old callbacks
  and queued frames from each measured phase. N4 contract and limits remain unchanged.
- Existing research configuration also has `custom` alongside healthy/degraded/
  relief. None is silently remapped into N5's six-phase lifecycle.
- Camera counter snapshots aggregate peers and can regress on peer removal. [implementation guide](N5_SUPPORTED_ADAPTERS.md) samples one exact peer/encoder generation
  directly and guards retired callbacks; a reset is partial/unavailable,
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

## Additive capture-pacing extension

[Campaign workflow](N5_CAMPAIGN_WORKFLOW.md) implements `render_capture_slowdown`
through experiment-v2 roots and `n5-capture-pacing-v1`, preserving this frozen v1
matrix. The bounded owned identity-element delay has measured integer stage-delay,
FPS and restoration predicates, a watchdog and independent regression checks.
The extension includes campaign entry, frozen source assignments, overhead
collection and detached reports. Source/workload independence requires external
verification.
