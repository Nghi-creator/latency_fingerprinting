# N4 inherited runtime acceptance

**Updated:** 2026-10-14. **Status:** nominal capture, overhead and host lifecycle
cases and opt-in browser execution method verified locally; desktop/final hosted gates open.
[Software closeout](../archive/observability/N4_SOFTWARE_CLOSEOUT.md),
[frozen criteria](N4_PRODUCER_CAPABILITIES.md),
[execution record](../../experiments/n5-runtime-20261013/README.md),
[N5 runtime ledger](../scenarios/N5_RUNTIME_ACCEPTANCE.md).

## Verified actual Linux evidence

These are actual Pixelated X11→queue→VP8 recordings, using the seed-7 animated
1280×720/30 scene, PulseAudio and a draining Chromium receiver in Docker Desktop's
Linux VM. Producer commit `ae0059384cf29609fa9c6233ddf9606002eae35e`, image identity,
versions, allocations, public archive receipts and every retained failed cohort
are recorded in the execution ledger. Synthetic fixtures remain separate.

| Gate | Observed result |
| --- | --- |
| Fresh nominal recordings | Four 30 s measured phases after 10 s warm-up; each has 900 queue and 900 encode pairs, 100% joint coverage and zero drops |
| Five paired overhead trials | All disabled baselines ≥29.995 FPS; median CPU increase 0.46058 percentage points; median FPS change +0.004712%; fixed thresholds pass |
| Enabled coverage/export | Every enabled overhead trace has 900 joint pairs and zero drops; writes take 0.899–1.580 ms outside frame callbacks |
| Separate callback diagnostic | 4,501 probes retained; mean 40.842 µs, min 8 µs, max 1.333 ms; diagnostic CPU increase 0.14366 percentage points |
| Deliberately tiny capacity | Each recording stays within two frames/five events, with 63 accounted capacity drops and one incomplete pair; detached validation passes |
| Disable/re-enable | Disabled 2.00165 s interval encodes 60 frames with zero trace probes; fresh phase collectors restart and owned cleanup succeeds |
| Interruption/restart | Old pipeline reaches NULL and removes its probes; partial stream excludes six queue/seven encode endpoints; new generation supplies 603 complete pairs in a distinct stream/epoch/clock |
| Two peers | Two fresh scopes each supply 600 queue/encode pairs, with distinct stream, epoch and clock IDs and verified probe cleanup |
| API-unavailable browser branch | Controlled API absence on an actual HTMLVideoElement exports explicit `api_unavailable`; this is not a claim of a natively unsupported Chromium build |

The two-second toggle smoke has one missing encode endpoint in its probe phase;
it is excluded, not paired across a collector rotation. This short smoke does not
substitute for the separate nominal coverage case. All real traces are adopted
and reconstructed from hash-verified integer evidence by the detached core.

## Remaining gates and limitations

The supported Chromium 151 recording captures 900 callbacks, but 681 API-reported
pairs have negative durations and are excluded. The remaining 219 pairs yield
zero lag. API collection/export and exclusion arithmetic work; useful callback-lag
acceptance for that original method remains limited. See the [browser timestamp limitation](N4_BROWSER_INSTRUMENTATION.md#live-api-timestamp-limitation).
Frozen v1 API timestamps are not clamped or replaced with a different clock.
The [additive method review](N4_BROWSER_TIMING_REVIEW.md) records a concrete
rationale and independent verification cases; the additive
[execution contract](N4_BROWSER_EXECUTION_CONTRACT.md) is implemented and locally validated.

Python 3.11.17 passes all 2,003 core tests at 93.60% coverage, Ruff, all 25
schemas and every frozen reproduction check. The standard native image now builds and passes two bounded native-package
smoke cases and its actual Node 24.18.1 engine suite (135 passed/one artifact skip).
Core hosted quality/minimum-Python jobs are verified for `bc6f42b`; Pixelated
hosted CI and normal picker/desktop interaction remain unverified. The core hosted
result also predates the new browser changes; those require final hosted verification.
The research capture and standard game image identities are recorded separately. No clock synchronization, physical
scan-out, end-to-end latency or hardware encoder claim follows from these results.

Full N4 and Phase 1.2 acceptance remain open. The [N5 ledger](../scenarios/N5_RUNTIME_ACCEPTANCE.md)
separately records the now-passing complete 18-trial repeated-fault cohort;
these results do not close the remaining browser/desktop gates or Phase 1.

## Selected workload confirmation

After calibration, `workload-4` (512 moving 32-pixel rectangles, seed 7) is used
in the complete passing `campaign-8`, producer `7e78d48`. Its healthy trial also
supplies [four fresh nominal recordings](../../experiments/n5-runtime-20261013/workload-4-nominal.json),
each with 900 queue/encode joint pairs and zero collector drops. Selected-scene
[five-pair overhead `campaign-9`](../../experiments/n5-runtime-20261013/workload-4-overhead-report.json)
also passes: median CPU +0.37238 percentage points, FPS −0.000517%, each enabled
trace 900 joint pairs/zero drops, exports 1.165–1.982 ms. Its separate 4,500-probe
diagnostic averages 19.830 µs with a 399.542 µs maximum. The lighter-scene overhead
above remains retained separately. Hosted core quality/minimum-Python
jobs are verified for `bc6f42b`; final core/Pixelated hosted checks and normal player/picker interaction
remain separate gates.

The [180-callback live entry diagnostic](../../experiments/n5-runtime-20261013/browser-entry-diagnostic.json)
reproduces 170 negative API deltas and ten zero deltas. Reading the performance
clock at callback entry gives 180 positive deltas, median 0.2 ms. This is
noncontract research evidence, with no callback-cost or new-method acceptance
claim. It is superseded for method validation by the versioned recordings below.

## Browser execution method validation, 2026-10-14

The opt-in [method release](N4_BROWSER_EXECUTION_CONTRACT.md) now passes local
[versioned live checks](../../experiments/n5-browser-execution-20261014/README.md).
All five nominal traces have 899–901 execution pairs, 100% coverage, zero trace
drops and zero missed presentations. Median Chromium CPU increase is +0.07918
percentage points; median FPS change is +0.002943%. A retained CPU transient of
+16.06054 percentage points and concurrent early software checks limit any causal
cost claim; the predeclared median criteria pass without replacing a pair.
The separate 1,200-probe diagnostic averages 39.583 µs (0–200 µs), including wrapper
and clock-read cost at unknown effective precision. Browser archive materialization
is 14.4–19.1 ms outside callbacks. Actual HTMLVideoElement API absence exports the
explicit v2 unavailable result. Original API timestamps/exclusions remain intact.

These artifacts identify base commits plus hashed working-tree browser changes,
not an exact final committed release. Normal desktop/picker interaction and hosted
checks of final changes in both repos remain pending. The inherited browser
coding/method issue is resolved locally; full N4, N5 and Phase 1 acceptance remain
open for the final execution gates.
