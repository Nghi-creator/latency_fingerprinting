# Independent N5 v1 examples

**Frozen:** 2026-10-10. Arithmetic/examples below are hand-authored without a
producer, model or result derivation. They become Step 3/4/6 regressions and Step 7
separately pinned fixtures. They do not run CPU pressure, prove real capture or
refresh existing fixtures. See [contract](N5_EXPERIMENT_CONTRACT.md).

## Nominal host contention

Use synthetic provenance/runtime, placeholder forty-hex `a` core and `b` producer
versions, experiment-1/run-1/node-1/workload-1/clock-1, seed 7, repeat_index 1,
assignment engineering, adapter bounded_cpu_pressure/available/null, allocation 2.
Plan warmup/healthy/degraded/probe/recovery/cooldown durations 10/30/30/30/30/10 s.
One action-1: cpu_pressure, degraded→recovery, workers 1, max duration 70 s
(including the predeclared 10 s allowance). Trace policy per_phase, N=1, 2000 frames/10000 events.
At nominal 30 fps, each 30 s trace plans 900 frames/4500 events, inside N4 ceilings.

Actual phase ranges in seconds are warmup 0–10, healthy 10–40, degraded 40–70,
probe 70–100, recovery 101–131, cooldown 131–141: all six phases complete.
Action starts at 40 s and stops at 100 s; cleanup at 100–101 s is restored with
0 owned workers remaining. The explicit one-second transition gap holds cleanup;
recovery begins only after restoration and retirement of old callbacks.
One peer counter is continuous across phases; its value advances from 2640 to
2670 during the transition gap. No interval/FPS is attributed to that gap. For each evaluated phase, use thirty
contiguous 1-second intervals with constant increments:

| Phase | Frame counter start/end | Frames/interval | Active workers | Worker CPU/interval |
| --- | --- | --- | --- | --- |
| healthy (10–40 s) | 300 → 1200 | 30 | 0 | 0 ns |
| degraded (40–70 s) | 1200 → 1920 | 24 | 1 | 600,000,000 ns |
| probe (70–100 s) | 1920 → 2640 | 24 | 1 | 600,000,000 ns |
| recovery (101–131 s) | 2670 → 3570 | 30 | 0 | 0 ns |

Warm-up has ten 1-second rows 0→300 frames with zero workers; cooldown (131–141 s) has ten
rows 3570→3870 with zero workers. Complete evidence covers each actual phase
exactly. Six phase-evidence artifacts plus four measured-phase N4 records = ten
artifacts, within the eighteen-ref cap. N4 clocks start fresh per record; no N5/N4
offset subtraction or host/browser alignment is performed.

Independent calculations:

- Healthy FPS = 900/30 = 30; degraded = 720/30 = 24; recovery = 900/30 = 30.
- Degraded worker CPU = 30×600,000,000 / 30,000,000,000 ×100 = 60% of one core.
- 24 ≤0.95×30 =28.5 and 30 ≥28.5; adequate healthy FPS and restored cleanup pass.
- Expected effect: verified/null with values 30.0,24.0,30.0,60.0 in field order.
  Expected execution status: completed/null. This proves only the specified
  synthetic engineering predicate, not a scientific bottleneck label.

Manifest SHA is computed only from canonical planned manifest bytes. Each evidence
root carries that hash; result carries the same hash and exact artifact bytes/hashes.
No literal arbitrary hash may substitute for calculating the supplied bytes.

## Boundary and failure examples

| Change from nominal | Independent expected result |
| --- | --- |
| degraded 855 frames/30 s, CPU 15 s/30 s; recovery 855 frames/30 s | Degraded/recovery both 28.5 fps and pressure CPU 50%; all inclusive thresholds pass |
| degraded 900 frames/30 s, worker CPU 18 s | Execution completed but effect failed/degradation_not_observed; injector success cannot pass |
| healthy 780 frames/30 s | 26 fps; failed/baseline_inadequate takes priority over later faults |
| worker CPU 12 s over degraded 30 s | 40%; failed/pressure_not_observed before checking throughput |
| recovery 810 frames/30 s | 27 fps <28.5; failed/recovery_not_observed |
| only 29 one-second degraded intervals | unavailable/insufficient_evidence, not a 30 s measurement or zero FPS |
| one interval frames_end < frames_start | Complete evidence rejects; export actual valid prefix as partial/counter_reset |
| adjacent intervals have a one-second hole | Complete evidence rejects; partial/collection_gap retains covered prefix; no interpolation |
| 0 active workers with positive worker_cpu_ns | Reject inconsistent raw interval evidence |
| cancellation at 65 s during degraded | Aborted/cancelled; warmup/healthy complete, degraded partial; no later phases. Action stopped/failed truthfully, effect unavailable/incomplete_run; cleanup still attempted |
| TERM/KILL/reap cannot establish restoration | Failed/unverified cleanup; never verified effect or completed accepted run; retain partial evidence |
| network_delay request with null/unavailable adapter | Unsupported/adapter_not_implemented; no executed phases/actions/artifacts; effect unavailable/adapter_unavailable with null numbers, cleanup not_required |
| a new warmup clock after runtime restart | Abort/clock_error; never bridge elapsed times or retain old frame association |
| 300 s measured phase at 30 fps, N=1 | 9000 planned frames exceeds N4 cap; preflight rejects, not a larger trace limit |
| same source acquisition reexported as held_out_query | Campaign disjointness fails despite new aliases/hash; it cannot query its reference fingerprint |

## Healthy control

Same six-phase plan with scenario healthy, adapter none/available/null, actions [],
all intervals at 30 fps and zero workers. Cleanup is not_required/null, null times,
remaining 0. Expected effect verified/null with healthy/degraded/recovery 30.0 fps
and pressure_cpu_percent null. The named degraded/probe windows are controls here;
no fault or bottleneck class is implied.

## Serialization, privacy and adoption rejection

Extra fields or supplied commands/URLs/PIDs, duplicate keys, depth 33, bool/string
numbers, NaN/Infinity, clock regression, unknown versions/scenarios, commit ending
in LF/CRLF, unordered phases/aliases, mismatched artifact names/roots/hash/bytes,
special/symlink files, extra archive members and unsupported root versions reject.
A result's verified claim with a recomputed failing effect rejects during inspection.
Standalone shape validation cannot prove file hashes, real measured effects or
campaign separation. Those require the declared linked evidence and acquisition audit.
