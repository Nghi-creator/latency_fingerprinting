# N5 experiment contract v1

**Frozen:** 2026-10-10, Step 2 specification; implementation begins in Step 3.
**Method release:** `n5-single-cause-v1`.
**Plan:** [N5](../plans/NEXT_IMPLEMENTATION_PLAN.md).
**Adapter inventory:** [Capabilities](N5_ADAPTER_CAPABILITIES.md).
**Independent expectations:** [Examples](N5_EXPERIMENT_EXAMPLES.md).

N5 records requested plans, observed execution and bounded experiment evidence.
They do not label scientific diagnoses, promote fingerprints or alter P0/N1–N4.
Unsupported cases and failed effects remain visible. This specification is not
an implemented API or evidence of a live trial. Field/method/limit changes require
reviewed version changes; existing schemas and policy/fixture bytes stay frozen.

## Roots and serialization

| Model | `schema_version` | Schema filename |
| --- | --- | --- |
| ExperimentManifest | `experiment-manifest-v1` | `experiment-manifest-v1.schema.json` |
| ExperimentPhaseEvidence | `experiment-phase-evidence-v1` | `experiment-phase-evidence-v1.schema.json` |
| ExperimentResult | `experiment-result-v1` | `experiment-result-v1.schema.json` |

All roots require `method_release: n5-single-cause-v1`. Strict required fields,
extra-field rejection, duplicate-safe UTF-8 JSON, immutable tuples/copies and
revalidation follow N4. Booleans/strings cannot coerce to numbers. All integers
are 0–2^53−1 unless a tighter bound is specified; every float must be finite.
Canonical JSON is sorted keys, two-space indentation, UTF-8, one trailing LF,
normalized positive zero. SHA-256 hashes those exact canonical bytes.

Every JSON ≤10 MiB, depth ≤32. At most six phases, six actions, eighteen evidence
artifacts and 1200 intervals per phase; input containers reject overflow before
validating elements. These are engineering bounds, not measured scaling claims.
No paths, arbitrary command/URL, PIDs, credentials, game/title, raw PTS, hostnames,
free-text notes or private stdout/stderr enter exported roots.

## Identity and frozen manifest

Manifest exact fields:

| Field | Meaning |
| --- | --- |
| `schema_version`, `method_release` | Constants above |
| `experiment_id`, `run_id`, `node_id`, `workload_id`, `clock_id` | `experiment-N`, `run-N`, `node-N`, `workload-N`, `clock-N` sanitized aliases |
| `provenance` | `synthetic` or `producer_capture` |
| `scenario` | Closed scenario vocabulary in capability inventory |
| `seed` | Strict unsigned 32-bit integer; deterministic run ordering/workload only |
| `repeat_index` | Integer 1–100; distinct actual runs, never duplicated evidence |
| `assignment` | `engineering`, `reference` or `held_out_query` |
| `core_version`, `producer_version` | Exact lowercase forty-hex commits, no trailing whitespace |
| `runtime` | Object specified below |
| `adapter` | Capability object specified below |
| `phases` | Six planned phase objects, fixed order below |
| `actions` | Zero or one requested CPU action in approved v1 cases; max six container cap |
| `trace_policy` | Recording policy below |

Aliases have positive no-leading-zero suffix ≤2^31−1. Aliases are export-local;
source-run identity also requires the manifest hash and run evidence, not a reused
`run-1` alone. Manifest freezes before warm-up; it contains no measured values,
artifact hashes or result fields. Evidence/result reference its hash, preventing
circular checksums. No UTC clock appears in v1; private acquisition metadata may
retain UTC outside this contract and cannot define durations.

Runtime exact fields: `kind` (`synthetic` or `linux_x11`), `python_version`,
`node_version`, `gst_version` (numeric `major.minor.patch`, no leading zeros, each component 0–999),
`cpu_allocation` (integer 1–64), `width` (1280), `height` (720), `fps` (30),
`codec` (`vp8`), `clock_source` (`python_monotonic_ns`), `clock_resolution_ns`
(positive safe integer). Synthetic provenance requires synthetic runtime; capture
requires linux_x11. Versions/config are declarations to verify against runtime,
not proof of availability or hardware certification.

Adapter exact fields: `adapter_id` (`none`, `bounded_cpu_pressure` or null),
`state` (`available` or `unavailable`), `reason` (null when available; otherwise
`adapter_not_implemented`, `runtime_unavailable`, `permission_denied`,
`clock_unavailable` or `source_unavailable`). Healthy maps to `none`, host
contention to `bounded_cpu_pressure`; remaining scenarios require null/unavailable.
Available is a preflight declaration; it is not executed or effect-verified.

## Phases, actions and clocks

Fixed phase order: `warmup`, `healthy`, `degraded`, `probe`, `recovery`, `cooldown`.
Each planned object has exactly `phase` and `duration_ns`; duration is an integer
1–300 seconds in ns, and total planned duration ≤1200 seconds. Nominal schedule is
10/30/30/30/30/10 seconds. These durations are engineering defaults, not calibration.
Host contention requires degraded+probe duration 30–290 seconds, leaving a
predeclared ten-second action startup/scheduling allowance within the inspected
pressure helper's 300-second ceiling. Healthy requests no fault; its degraded/probe
phases are control windows, not manufactured degradation.

A CPU action has exactly `action_id` (`action-N`), `kind` (`cpu_pressure`),
`start_phase` (`degraded`), `stop_phase` (`recovery`), `workers` (1–8 and no more
than cpu_allocation), `max_duration_ns` (equals degraded+probe durations plus ten seconds). Host
contention requests exactly one action even when preflight is unavailable;
healthy and unapproved scenarios request none. No arbitrary shell parameters.
Action startup precedes the first degraded interval; stop/restoration precedes
recovery measurement. The probe window sustains the same requested fault in v1;
there is no automatic diagnostic intervention or runtime stream-profile change.

Runner origin is monotonic time at warm-up start. Actual phase boundaries are
nonnegative offsets in this one runner/engine clock. Planned time does not replace
actual time; delays are recorded, never backdated. A completed run has all six
nonoverlapping actual phases, each lasting planned duration through planned+2 s,
bounded by the 1200-second run watchdog. Transition gaps are explicit in actual
offsets and ≤5 s; warmup.start_ns is 0, and degraded→probe is contiguous while the same action runs. No
interval or phase may fill a gap with fabricated measurements. Partial runs have an ordered prefix, at most one
incomplete final phase. No phase reordering, skipped middle or restarted-clock
subtraction. Deadline/watchdog expiry aborts work and starts bounded cleanup.

Browser performance, Gst media time and each N4 recording clock remain independent.
Do not subtract N5 boundaries from N4 event timestamps or invent browser/host
frame alignment. Artifact ownership assigns recordings to phases without asserting
clock synchronization. Runtime monotonic regression aborts with `clock_error`.

## Fresh recording and resource ownership

Producer runner owns a single local experiment lease, exact child handles and
recording bindings. It refuses concurrent ownership of the same experimental
runtime. Starting a fresh post-warm-up N4 recording is an explicit producer control,
not a reinterpretation of old events or a generic socket command. Old callbacks
are retired; queued pre-start buffers cannot acquire new frame/epoch association.
Normal playback with tracing disabled preserves its path. No synchronous export,
core call or filesystem I/O occurs in frame callbacks.

Use a separate bounded N4 record per measured phase (`healthy`, `degraded`, `probe`,
`recovery`); fresh collector and clock origin each time. Warm-up/cooldown need no
trace. Default every_nth_frame=1, max_frames=2000, max_events=10000; declared trace
policy has exactly those four fields including `scope: per_phase`. Policy may use
N=1–1000 and smaller caps within N4 ceilings. Phase-budget preflight must show
ceil(duration_seconds * fps / N) ≤ max_frames and five events per admitted host
frame ≤ max_events; longer phases require explicit sampling or fail preflight.
Actual loss remains observable; a nominal accepted trace cannot hide overflow.
N4 budget remains optional in the N4 record; N5 declares no new deadline budget.

## Phase evidence and raw intervals

Evidence exact root fields: `schema_version`, `method_release`, `manifest_sha256`,
`run_id`, `phase`, `clock_id`, `start_ns`, `end_ns`, `state`, `reason`, `intervals`.
State: `complete`, `partial`, `unavailable`; reason null only for complete;
otherwise `source_unavailable`, `counter_reset`, `clock_error`, `collection_gap`,
`cancelled` or `timeout`. End ≥ start; complete requires end > start and full
interval coverage. Unavailable has zero intervals; partial retains only actual
covered prefix (possibly empty), never fabricated zero measurements.

Each interval exact fields: `start_ns`, `end_ns`, `frames_start`, `frames_end`,
`active_workers`, `worker_cpu_ns`. End > start, duration 0.5–5 s; adjacent intervals
have equal boundary offsets and equal frame counter endpoints. No counter reset,
gap interpolation or pooling across peers/process generations. Frame counters
come from one draining camera peer/encoder, not rvfc or sampled trace frame count.
Active_workers is 0–8; worker_cpu_ns is the sum of process CPU-time deltas of only
owned pressure workers over this interval. It is a duration, not a wall timestamp;
0 workers implies zero worker CPU, and worker_cpu_ns ≤ duration * active_workers.
Worker count is stable within an interval; align action transitions at boundaries.
Missing CPU/count evidence is unavailable/partial, never a successful zero sample.
Linked validation requires zero workers for healthy controls and all nonfault
phases; completed contention degraded/probe rows require exactly the requested
worker count. An unexpected worker exit aborts the action/run and retains partial
evidence. Owned live workers consuming too little CPU may still produce complete
evidence with a failed pressure predicate.

Evidence methods are fixed: encoded throughput = sum frame differences / covered
wall seconds; pressure CPU = summed worker CPU duration / covered wall duration,
expressed as percent of one core, which may exceed 100 for multiple workers.
Use integer totals/cross multiplication for thresholds, convert only final outputs.
Do not use camera CPU as proof that pressure workers consumed CPU. The existing
engine telemetry sampler does not supply worker CPU; the runner must collect it.

## Execution result and effect classification

Result exact root fields: `schema_version`, `method_release`, `manifest_sha256`,
`run_id`, `status`, `reason`, `phases`, `actions`, `artifacts`, `effect`, `cleanup`.
Status `completed`, `aborted`, `unsupported`; completed reason null, aborted reason
`cancelled`, `timeout`, `clock_error`, `source_error`, `action_failed` or
`cleanup_failed`; unsupported reason equals manifest adapter reason. Unsupported
has no executed phases/actions/artifacts, effect unavailable and cleanup not_required.

Actual phase object exact fields: `phase`, `start_ns`, `end_ns`, `state`
(`complete`/`partial`). Bounds/clock agree with phase evidence. Completed phases
follow the six-phase rule; aborted retain prefix only. Run duration excludes the
separate cleanup allowance. Completion is execution status, not a verified effect.

Action result exact fields: `action_id`, `state` (`not_started`, `started`, `stopped`,
`failed`), `started_ns`, `stopped_ns`, `reason`. Not_started has null timestamps;
started has start only; stopped has both ordered timestamps and null reason;
failed retains available ordered timestamps and reason `start_failed`,
`exit_failed`, `stop_failed`, `cancelled` or `timeout`. Completed host contention
requires stopped action: started_ns lies between healthy.end_ns and
degraded.start_ns inclusive, stopped_ns lies between probe.end_ns and
recovery.start_ns inclusive, and stopped_ns-started_ns ≤ max_duration_ns. Cleanup
must be restored.
Healthy has no action results. Aborted runs never lose the requested action's state.

Effect exact fields: `state` (`verified`, `failed`, `unavailable`), `reason`,
`healthy_fps`, `degraded_fps`, `recovery_fps`, `pressure_cpu_percent`. Values are
finite nonnegative floats or null. This is a reproducible engineering predicate,
not ground-truth scientific causality. Unavailable reasons are `adapter_unavailable`, `incomplete_run`,
`cleanup_unverified`, `insufficient_evidence` in that precedence order. Unsupported
results have all effect values null. Aborted or unverified-cleanup results cannot
have verified effects. Available values derive from complete,
hash-verified phase evidence with ≥30 intervals and ≥30 s each for healthy,
degraded and recovery. Inadequate/missing input yields unavailable with reason
`insufficient_evidence`; valid evidence failing a threshold yields failed with
`baseline_inadequate`, `pressure_not_observed`, `degradation_not_observed` or
`recovery_not_observed` in that order. Verified has null reason.

Healthy verifies healthy/degraded/recovery FPS ≥27, no owned workers in any phase and
restored/not_required cleanup; pressure_cpu_percent is null. Host contention
requires healthy FPS ≥27, degraded pressure CPU ≥50% of one core, degraded FPS
≤95% of healthy, recovery FPS ≥95% of healthy and zero workers in recovery with
restored cleanup. Equality passes each inclusive criterion. These fixed provisional
criteria cannot be relaxed after trials. Queue/encode timing is retained separately
in N4 artifacts; verified host pressure does not identify an isolated bottleneck
or guarantee a diagnosis. Probe/cooldown are retained, not omitted to cherry-pick.

## Cleanup, cancellation and crash recovery

Cleanup exact fields: `state` (`not_required`, `restored`, `failed`, `unverified`),
`reason` (null for restored/not_required; otherwise `stop_failed`,
`restore_failed`, `ownership_lost` or `missing_evidence`), `started_ns`, `ended_ns`,
`owned_workers_remaining` (0–8 or null). Not_required: no started actions, null
times, remaining 0. Restored: ordered nonnull times, remaining 0, every started
owned worker reaped, original runtime settings restored and old callbacks retired.
Failed/unverified may retain null counters/times; neither permits verified effect.
Cleanup duration ≤10 s; expiry records failed, never waits indefinitely. Completed
contention requires cleanup.ended_ns ≤ recovery.start_ns; recovery cannot start
before verified restoration.

Cancellation stops new phases/actions, closes recordings, TERM then bounded wait,
KILL if needed and bounded reap of exact owned child/process-group handles.
Attempt every owned cleanup even if one fails; no kill-by-name, unrelated PID,
foreign process group or host-global network/settings reset. Keep sanitized state
in results; private diagnostic logs stay outside exported artifacts.

A crash-safe private journal and lease must be written before starting children or
mutating settings. On restart, verify ownership/generation before restoring exact
owned resources; unknown/reused identity means ownership_lost, no destructive guess.
SIGKILL cannot promise cleanup. Existing pressure-helper join is not bounded enough
for this contract; adapt under producer ownership rather than assuming it satisfies
crash recovery. Export only after recording has frozen; export failures cannot skip
cleanup. No failed restoration can be called a successful trial.

## Artifact adoption, APIs and bundle

Artifact reference exact fields: `artifact_id` (`artifact-N`), `file_name`
(`artifact-N.json` matching ID), `phase`, `role`, `schema_version`, `bytes`, `sha256`.
Roles and roots: `phase_evidence` → experiment-phase-evidence-v1, `stage_trace` →
stage-trace-record-v1, `observation_window` → observation-window-v2. One role per
phase, sorted ordinal IDs; ≤18 refs; bytes positive ≤10 MiB. All references resolve
inside the supplied bundle; no traversal/remote resolution or third-party file I/O.
Phase evidence is required for all six completed phases and stage_trace for each
of the four measured phases. Trace loss/unavailability is retained and cannot
pass the separate N4 nominal gate even if the N5 FPS/CPU predicate is verified.
Partial/missing phase evidence
cannot produce verified effect. Phase-evidence run/phase/manifest/clock fields must agree. N4 roots retain their
local aliases; provenance and producer_version must agree with the manifest, and
v1 stage_trace artifacts require pixelated_engine (browser traces remain separate
N4 artifacts, not a second same-role phase member).
Observation windows retain their existing fields. N4/observation phase ownership
comes from the hash-verified mapping; these roots gain no N5 phase or manifest
fields. Stage traces are permitted only for the four measured phases.
Manifest/result canonically agree on provenance through the referenced manifest;
result cannot redefine it. Raw N4 hashes/policy fields are preserved.

Standalone experiment bundle v1 is an exact directory or gzip USTAR with
`experiment-manifest.json`, `experiment-result.json` and all referenced artifact
files, no extras. Result bytes bind artifact hashes; result binds manifest hash.
No extra bundle-manifest root. Compressed/expanded ≤64 MiB; each JSON ≤10 MiB;
≤20 regular members. Duplicate keys/files, symlinks/specials/extensions/hidden
nonzero trailers fail closed; no extraction into arbitrary paths. Inputs use
pinned no-follow paths and outputs private atomic writes. Read-only inspection
recomputes derived effect predicates and rejects supplied claims that disagree.

Intended core API `inspect_experiment_bundle(path)` returns validated manifest,
result and recomputed effect evidence; no producer process or remote access.
Intended CLI `inspect-experiment --bundle PATH --output PATH` writes canonical
ExperimentResult only after verification; success is silent. Failure emits exactly
`error: inspect-experiment: invalid_input_or_output` with no input/path echo and
preserves existing output. Generic validate gains three additive roots in Step 3;
inspection is implemented in Step 6. These APIs do not exist at Step 2.

## Campaign separation and real acceptance

Freeze reference/held_out_query assignments before measurements. Repeats require
new actual source runs, not reexports/new hashes of the same run. Neither source
run nor its phase subset can be both reference and query. Seeds make procedure
repeatable, not observations identical; retain all unsuccessful trials. A single
manifest cannot prove campaign disjointness; campaign evidence/manual audit must
verify underlying acquisition ownership. No new matching/promotion API in v1.

N5 v1 starts healthy/host contention only. Unsupported classes cannot supply the
roadmap's two real single-bottleneck classes; Phase 1.3 stays incomplete until
supported real repeated/held-out evidence satisfies that gate. [N4 acceptance](../observability/N4_RUNTIME_ACCEPTANCE.md)
remains separately pending, including all frozen capture/overhead/browser criteria.
