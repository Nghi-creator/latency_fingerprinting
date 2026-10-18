# N5 runtime acceptance ledger

**Updated:** 2026-10-17. **Status:** complete repeated-fault cohort and browser method checks pass; merged-baseline hosted gates verified. Manual desktop/picker sign-off remains pending; audit fixes require their normal hosted run.
[Software closeout](N5_SOFTWARE_CLOSEOUT.md), [active plan](../plans/NEXT_IMPLEMENTATION_PLAN.md),
[frozen contract](N5_EXPERIMENT_CONTRACT.md), [execution record](../../experiments/n5-runtime-20261013/README.md).

## Actual environment

The recorded acceptance runs used Docker Desktop as the Linux camera testbed on
this macOS host; a separate Linux machine is optional. The initial PATH check missed Docker because its
symlink pointed to an absent OrbStack installation. The bundled CLI used for those runs is
`/Applications/Docker.app/Contents/Resources/bin/docker`. The final 2026-10-16
check finds this client present but its configured daemon socket unavailable.
The versions and captures below describe the recorded acceptance environment;
start Docker Desktop and repeat preflight before any new live acquisition.

Observed Docker is 29.0.1, VM Linux 6.12.54-linuxkit/aarch64, 10 CPUs and
8,217,448,448 bytes RAM. The research capture image is
`sha256:cd62376e7c362e085be29e75ecc5150ca209374787a1b30eafe6aca553479bb5`,
with exact producer `ae0059384cf29609fa9c6233ddf9606002eae35e`, Node 24.18.1,
Python 3.13.5 and Gst 1.26.2. The original capture core source is `bc6f42b0668f3d1edd7d3365da9fea70629455ca`.
Chromium 151.0.7922.34 drains VP8 from the fixed seed-7 animated X11 scene at
1280×720/30, with PulseAudio `auto_null.monitor`. Containers have a 2 GiB memory
limit, no new privileges, bounded PIDs and loopback-only receiver signaling.

The accepted nominal/overhead setup has a one-CPU aggregate quota with a
1,000,000/1,000,000 µs period and no affinity pin. A 100 ms quota-period retry
and subsequent CPU-0 affinity retry are retained separately; they are not the
accepted overhead allocation. The research image and standard native image both build. The standard image
`sha256:26dfdb1bac8c34e2efa3930d7d9f2dcb4f2a43b3ce0a1d1bb10d1c58f8d7b25e`
passes the native Gst import and bounded Frozen Bubble/Neverball package smoke.
Its Node 24.18.1 engine suite passes 135 tests with one existing external-artifact
skip. Normal desktop/picker interaction remains unverified. Both merged baselines
now have successful hosted verification; [exact CI receipts](../../experiments/phase-1-audit-20261015/hosted-ci.json)
supersede the earlier pending entries. The subsequent audit fixes are locally
verified and need their normal hosted run after merge.

## Runtime fixes and retained failures

Actual tests exposed borrowed Gst caps access, four-component Gst version
formatting, and VP8 replacement initial SEGMENT identifiers. Commits `eac8e58`
and `08a4732` fixed those cases. Initial segment normalization is limited to
verified fresh NULL pipelines with matching segment descriptors; frame PTS is
not transformed and seek/reset association is not widened.

The older `campaign-3` verified sixteen acquisitions, then aborted the seventeenth
on a CPU-counter sampling issue; the eighteenth did not execute. Commit `ae00593`
takes timestamps after counter reads and preserves abort cleanup offsets when the
original clock remains trustworthy. Strict physical/effect bounds are unchanged.
Its Linux regressions pass. The subsequent selected-workload cohort below now
passes every repeated-effect criterion; earlier failures remain retained.

| Corrected cohort | Retained result |
| --- | --- |
| campaign-4, 1 s quota period, grouped order | Three healthy verified; contention measured 28.53184 FPS versus 29.99773 healthy, with 86.05% worker CPU, failing the fixed ≤95% FPS predicate. Fifth trial canceled/retained; journal clean |
| campaign-5, 100 ms period, interleaved order | Healthy verified; contention stayed near 30 FPS despite 85.26% worker CPU. Partial pacing trial retained after cancellation; journal clean |
| campaign-6, 100 ms period plus CPU-0 affinity | Healthy baseline about 4 FPS and fewer than thirty intervals per evaluated phase; correctly unavailable/insufficient_evidence. Partial next trial retained; journal clean |

Every attempted schedule/source assignment was frozen before measurement. No
threshold was changed, no acquisition was overwritten, and prior successes are
not combined into a successful new cohort. Positive nonoverlapping receipt windows
and unique source IDs are checked; hashes/aliases alone do not prove scientific
independence or causality. Earlier setup failures and interrupted executions remain
locally retained. Old `controlled-run-001/002` artifacts are not N5 repetitions.

## Verified checks and remaining gates

| Gate | Current actual outcome | Remaining action |
| --- | --- | --- |
| Linux/native ownership | Preflight, owned worker sampling and clean restoration observed | Preserve exact environment and every failure in future acquisitions |
| Healthy and host contention | Pass: all six healthy and six contention trials in complete campaign-8 verify; contention 23.74–24.67 FPS, with healthy/recovery near 30 | Passing fresh cohort retained; earlier lightweight-scene failures are separate |
| Capture-pacing second class | Pass: all six fresh pacing trials verify, degraded 16.90–17.17 FPS and recovery near 30 | Actual additive v2 timing/cleanup receipts retained |
| Repetitions/held-out separation | Complete 18/18 verified; three references and three held-out queries per class, unique source IDs and nonoverlapping receipt windows | Receipt/code review establishes fresh disjoint acquisitions, not general statistical independence or scientific validity |
| N4 nominal/correlation | Current corrected commit has 900 queue/encode pairs per phase, 100% joint coverage, zero drops | Recorded in [N4 runtime ledger](../observability/N4_RUNTIME_ACCEPTANCE.md) |
| N4 five-pair overhead | Selected workload passes: baselines ≥29.997 FPS, median CPU +0.37238 percentage points, median FPS −0.000517%, five enabled traces each 900 joint pairs/zero drops; 4,500 diagnostic probes | [Canonical report](../../experiments/n5-runtime-20261013/workload-4-overhead-report.json); earlier lighter-scene result retained separately |
| N4 host lifecycle/isolation | Tiny capacity, disabled/re-enabled, interruption/restart and two-peer cases pass detached validation and owned cleanup | Short-smoke partial endpoints remain explicitly excluded |
| Browser | Opt-in execution v2 passes five live paired overhead/coverage checks and 1,200-probe diagnostic; original v1 API limitations remain recorded | Normal desktop/picker and exact final committed build checks remain separate; [new method evidence](../../experiments/n5-browser-execution-20261014/README.md) |
| Minimum Python | Pass: Python 3.11.17, 2,015 tests, 93.61% coverage, 25 schemas, Ruff and frozen reproduction | Local Linux result and separate hosted core CI both verified |
| Standard native image | Build and two native-package smoke tests pass; actual Node 24 engine suite 135 passed/one artifact skip | Image identity and lock hash recorded separately from research image |
| Hosted core CI | Quality and Python 3.11 jobs pass at merged `3313139`; [CI receipts](../../experiments/phase-1-audit-20261015/hosted-ci.json) | Subsequent local audit fixes need normal CI after merge |
| Pixelated hosted CI | npm audits, both engine image scans, three-platform desktop builds, hosted web/API checks, deployment and auth/pairing smoke pass at merged `31d675a` | Subsequent local audit fixes need normal CI after merge |
| Normal desktop/picker interaction | Manual sign-off unverified | User checks game launch/input/reconnect and trace export/cancel/retry on the final build |

Prior native verification passed all 79 producer scenario tests and 58 trace/control tests on Linux, including
the previously skipped parked-child integration case. Current readiness verification
passes 2,032 core Python 3.13 tests at 93.55% coverage and 788 Pixelated Node tests
with one existing external-artifact skip. The earlier actual Node 24 baseline passed
all 259 web tests. New patch minimum-version/native reruns remain CI work. These are software results, separate from real
fault effects, scientific validation and hosted CI.

## Evidence and remaining acceptance

[Sanitized execution ledger](../../experiments/n5-runtime-20261013/execution-ledger.json)
contains the actual receipts, measured effects, scope/loss summaries and helper
hashes. [Overhead report](../../experiments/n5-runtime-20261013/overhead-report.json)
is the canonical detached inspector output. Raw public archives/full reports and
trusted research helpers remain under ignored `local/phase_1/n5-acceptance-20261012/` and
`local/phase_1/n5-calibration-20261013/`;
private leases, native identities and diagnostic PTS are not published. Completed cohort and calibration runtimes are stopped with clean journals;
the separate selected-scene overhead completed with a clean ownership journal. The bounded browser diagnostic runtime is also stopped.

Follow the producer [live procedure](../../../Pixelated-Studio-Edition/docs/n5-live-test-procedure.md)
and [campaign workflow](N5_CAMPAIGN_WORKFLOW.md) for future reruns. Campaign-8
already satisfies the full repeated-fault gate. For a new environment, verify
≥27 FPS nominal adequacy
and actual contention effect on the chosen workload/allocation before freezing
an entirely fresh acceptance cohort. Keep all results, independent references
and held-out queries, and the six fresh phases. Do not reuse old output IDs,
reexports or phase subsets as new repetitions. Inspect each checksum-bound bundle
after cleanup; a started injector is not verified ground truth.

The supported-browser method uses frozen API-reported timestamps. Changing their
meaning requires an additive method/version; the implemented
[execution release](../observability/N4_BROWSER_EXECUTION_CONTRACT.md) adds a
distinct endpoint and keeps original exclusions intact. N5 Step 8, full N4, Phase 1.2, Phase 1.3 and Phase 1 remain open.
No N6 transition is claimed by these checks.

## Subsequent workload calibration and fresh cohort

Six one-minute engineering trials compare seed-7 scenes of 24/192/512 moving
rectangles on the same unpinned one-CPU/one-second allocation. The predeclared
screen requires both repeats to sustain healthy/recovery ≥27 FPS, degraded
≤90% of healthy, recovery ≥95% of healthy, ≥50% owned worker CPU and restored
cleanup. [Screen results](../../experiments/n5-runtime-20261013/calibration-screen.json)
retain all outcomes. Every detached short-run effect is correctly unavailable /
insufficient_evidence; calibration is not acceptance or held-out evidence.

The 512-rectangle/32-pixel scene (`workload-4`) is selected for its consistent
24.6–24.7 degraded FPS, near-30 healthy/recovery FPS and approximately 75.7%
worker CPU across both repeats. New `campaign-8` freezes eighteen independent
source assignments, repeat/assignment/class interleaving and the normal
10/30/30/30/30/10-second phases before execution. Producer is the pushed
`7e78d483ec3c1c5bf9e6977048591e19415b1ac1`; the labeled calibration image and scene
hash are in the screen record. The fresh full cohort finishes with 18/18 verified and repeated-effect criteria
passed. Public [plan](../../experiments/n5-runtime-20261013/campaign-8-plan.json),
[index](../../experiments/n5-runtime-20261013/campaign-8-index.json) and
[detached report](../../experiments/n5-runtime-20261013/campaign-8-report.json) retain
every acquisition. Selected-scene five-pair overhead (`campaign-9`) also passes
all fixed thresholds. Its [report](../../experiments/n5-runtime-20261013/workload-4-overhead-report.json)
retains the separate result: median CPU +0.37238 percentage points, FPS −0.000517%,
five 900-joint-pair traces with zero drops and 1.165–1.982 ms exports. The separate
4,500-probe diagnostic averages 19.830 µs (5.542–399.542 µs). The earlier overhead
report remains the lighter-workload measurement. No acceptance threshold or
original contract/pin changed.

A bounded [browser entry diagnostic](../../experiments/n5-runtime-20261013/browser-entry-diagnostic.json)
on the actual draining Pixelated video element records 180 callbacks: 170 API
deltas are negative and ten zero; callback-entry deltas are all positive,
0.1–0.6 ms (median 0.2 ms). This research diagnostic supports the
[additive method review](../observability/N4_BROWSER_TIMING_REVIEW.md), and is retained as noncontract research evidence. Subsequent versioned
[method validation](../../experiments/n5-browser-execution-20261014/README.md) now
passes with five complete enabled traces and a separate 1,200-probe diagnostic.
Merged-baseline hosted verification now passes in both repos. Normal
desktop/picker sign-off and the ordinary hosted run for subsequent audit fixes
remain open; no N6/Phase 1 completion is claimed.

## Pre-manual cross-repository audit, 2026-10-15

[Audit record](../../experiments/phase-1-audit-20261015/README.md) records bounded
malformed-manifest/special-file fixes, regression tests, dependency cleanup and
current hosted receipts. Re-inspection of the retained campaign-8 and selected
workload overhead archives reproduces their original canonical reports exactly;
no live acquisition was replaced or rerun as a new repetition. The
[current quality guide](../measurement/QUALITY_GATES.md) links the final audit
counts. All original schemas, arithmetic/effect thresholds and fixture bytes
remain unchanged. Final manual outcomes are still not supplied.


## Follow-up readiness audit

The [follow-up review](../../experiments/phase-1-readiness-20261015/README.md)
hardens legacy compressed input and browser failed-save cleanup, separates mixed
source/test modules and reproduces both retained live reports exactly. Its
macOS tests do not constitute new native Linux or minimum-version execution.
Manual sign-off and normal hosted verification remain open.


The [script/CI hardening pass](../../experiments/phase-1-script-ci-20261016/README.md)
splits the remaining large utilities, repairs owned cleanup/validation gaps and
adds full producer regression/deploy gating plus isolated core wheel verification.
The current checks pass locally; new hosted execution and manual sign-off remain open.

## Final cross-repository check

The [final review](../../experiments/phase-1-final-check-20261016/README.md) passes
2,032 core tests and 783 Node tests, all workspace checks, frozen release checks,
installed-wheel verification and fresh zero-vulnerability npm audits. It fixes
hosted smoke selection of a nonmatching native build and embedded signed-URL
redaction. Manual sign-off and actual hosted CI for the final patches remain open.

## Focused security follow-up, 2026-10-17

The [security review](../../experiments/phase-1-security-20261017/README.md) removes
the hosted smoke's broad browser TLS bypass, hardens its probe credentials/private
certificate workspace, and closes the Dependabot quality-gate omission. Current
local verification passes 2,032 core tests/93.55% coverage and 788 Node tests
with one existing artifact skip, plus the real two-certificate browser TLS test.
Fresh npm/Python advisory audits are clear. Hosted CodeQL/image/minimum-version
checks and manual acceptance remain separate pending gates.

## Pre-Phase 2 audit, 2026-10-17

The [cross-repository audit](../../experiments/pre-phase-2-audit-20261017/README.md)
closes acquisition-duration and negative-timing acceptance gaps, hardens producer
download ownership/deadlines, and consolidates process-counter parsing. Current
verification passes 2,035 core tests/93.56% coverage and 800 Node tests with one
existing local-artifact skip. Retained campaign-8 and selected-workload overhead-9
reports reproduce byte-for-byte. Manual sign-off and the normal hosted/platform
checks for the edited trees remain open; this record does not close Phase 1.

## Deep follow-up audit, 2026-10-18

The [deep audit](../../experiments/deep-audit-20261018/README.md) enforces pacing
integer and overhead runtime/provenance consistency, handles companion proxy
disconnects and bounds health probes. All 2,038 core tests pass on local Python
3.13 and 3.11; Pixelated passes 814 Node tests across local Node 24/26 checks.
Retained live reports and original pins remain unchanged. Docker's daemon is
unavailable, and hosted Linux/image/CodeQL/platform and manual acceptance remain
separate gates for these changes.
