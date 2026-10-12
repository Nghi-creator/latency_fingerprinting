# N5 runtime acceptance ledger

**Updated:** 2026-10-12. **Status:** pending; no real N5 trial is claimed.
[Software closeout](N5_SOFTWARE_CLOSEOUT.md), [active plan](../plans/NEXT_IMPLEMENTATION_PLAN.md),
[frozen contract](N5_EXPERIMENT_CONTRACT.md), [adapter matrix](N5_ADAPTER_CAPABILITIES.md).

## Observed environment and availability

The available execution host is Darwin/macOS. Docker is absent from PATH; no Linux
connection/testbed was supplied and no N5 real campaign artifacts exist in either
checkout. Existing `controlled-run-001/002` artifacts predate N5 and cannot be
relabeled as N5 repetitions. Installed Node reports 26.4.0 and producer Python
reports 3.14.4; these do not demonstrate minimum-version execution. A local
`gst-launch-1.0 --version` probe did not finish because of macOS service errors;
no fresh local GStreamer version or pipeline availability is established by it.

The actual `LinuxCameraRuntime.preflight` was invoked with a bounded healthy plan
on this host. It returned `unavailable / runtime_unavailable`, no runtime fields,
no acquired resources and no prepared plan. The platform check runs before camera
access. No camera, workload, process worker or pressure was started. This proves
local unavailability, not behavior of the adapter on Linux.

## Required evidence and dependencies

| Gate | Current outcome | Evidence required to close |
| --- | --- | --- |
| Linux runtime and actual native ownership | Pending: unavailable locally | Explicit testbed connection, trusted checkouts, observed CPU allocation/cgroup visibility, pidfd/worker lifecycle and exact versions |
| Real healthy and host contention | Pending: zero N5 real trials | Warm running X11→queue→VP8 peer with draining receiver, frozen workload/seed/config, integer intervals, fresh phase traces and bounded owned cleanup |
| Second real fault class | Capture-pacing extension implemented; live validation pending | Run the additive pacing method alongside host contention; retain measured delay/FPS, restoration and independent repetitions; healthy is not a fault class |
| Repetitions and held-out separation | Pending: no assignment ledger | Freeze acquisition identities/assignments before analysis, distinct actual source runs, repeated trials per real fault class and all failed/unsupported outcomes |
| Inherited N4 capture and correlation | Pending | [Exact N4 runtime gates](../observability/N4_RUNTIME_ACCEPTANCE.md), including ≥500 usable queue/encode pairs, ≥95% joint coverage and zero nominal drops |
| Inherited N4 overhead | Pending | All five paired disabled/enabled trials, every baseline ≥27 fps, median CPU increase ≤5 percentage points and FPS change ≥−5%, diagnostic/export measurements |
| Browser, minimum versions, containers and hosted CI | Unverified | Actual execution records; configured jobs, installed tools and synthetic fixtures do not close these gates |

N5 method `n5-single-cause-v1` still approves healthy and host contention only.
The [capture-pacing/campaign extension](N5_CAMPAIGN_WORKFLOW.md) delivers a second
control through additive v2 roots and method `n5-capture-pacing-v1`, plus live-entry
and overhead/reporting tools. Old contract/policy/schema/pin bytes are preserved.
Both causes still require actual trials; mixed/changing runs remain unsupported.

## Campaign handoff

1. Supply an actual Linux testbed and draining local receiver, not only an installed
   GStreamer binary. Verify the fixed Xvfb `:99`, PulseAudio `auto_null.monitor`,
   one peer, 1280×720/30 fps, VP8 and stable encoder/profile properties required by
   producer preflight. Preserve exact commits, commands, versions and CPU allocation.
2. Freeze workload identity/seed, phase durations, worker count and action bound,
   full tracing policy, independent repetition schedule and source-run assignments
   before measurements. Record the private acquisition identity ledger separately
   from sanitized export aliases. Reexports and phase subsets cannot serve as new
   references or held-out queries. Do not infer independence from hashes.
3. Use the trusted producer control thread and opted-in existing camera peer through
   the [lifecycle](N5_RUN_LIFECYCLE.md) and [supported adapters](N5_SUPPORTED_ADAPTERS.md).
   The library is not a standalone scene launcher or remote testbed provisioner.
   Obtain fresh frozen healthy/degraded/probe/recovery collectors, retain raw integer
   evidence and truthful failed cleanup. Do not substitute shutdown/warm-up traces.
4. Export after cleanup using [experiment export/inspection](N5_EXPERIMENT_INSPECTION.md).
   Inspect each real bundle with `inspect-experiment`. Retain every result, including
   unavailable and failed effects; report measured degradation and recovery without
   changing thresholds after seeing results. Keep private diagnostics out of exports.
5. Validate the implemented capture-pacing second class and repeated/held-out evidence, as well
   as every N4 capture/correlation/overhead case. Sparse Step 7 fixture traces cannot
   satisfy real coverage. Publish per-trial values and independent source assignments
   before asserting Phase 1.3 or promotion into downstream analysis.

No repetition count or second-adapter predicate is invented by this ledger; the
campaign protocol must predeclare them before execution. Update this ledger only
with actual evidence and keep failed trials. The coding workflow is available for a Linux engine inside Docker Desktop on macOS
or on a separate Linux machine. Record the actual environment/allocation; source
checkout alone and macOS preflight do not establish a running Linux engine.
Step 8 runtime acceptance, Phase 1.2,
Phase 1.3 and Phase 1 overall remain open.
