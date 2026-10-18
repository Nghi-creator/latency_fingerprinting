# N5 real runtime execution, 2026-10-13

**Current outcome:** complete fresh campaign-8 passes all 18 trials and repeated
effect criteria after the workload calibration below. Full N5 acceptance remains
open for normal desktop/picker and final hosted gates; the browser execution
method now passes [separate local validation](../n5-browser-execution-20261014/README.md). Selected-workload
overhead passes separately. Earlier cohort failures and lighter-workload overhead are
historical evidence retained below.
This record does not mark Phase 1 complete.

[Execution ledger](execution-ledger.json) contains sanitized actual receipts,
per-trial measured effects, retained failures and compact lifecycle/browser
summaries. [Overhead report](overhead-report.json) is the actual canonical core
`n4-overhead-report-v1` output, not a hand-authored expectation. The execution
ledger is research metadata, not a new core artifact schema or synthetic fixture.

## Environment and retained outcomes

Docker Desktop 29.0.1 supplies an aarch64 Linux 6.12.54 VM with 10 CPUs and
8,217,448,448 bytes RAM. The research capture image is
`sha256:cd62376e7c362e085be29e75ecc5150ca209374787a1b30eafe6aca553479bb5`,
with producer `ae0059384cf29609fa9c6233ddf9606002eae35e`, Node 24.18.1,
Python 3.13.5 and Gst 1.26.2. Chromium is 151.0.7922.34. The seed-7 nonprivate X11
scene animates 24 colored rectangles at 1280×720/30; VP8 and PulseAudio use the
frozen producer settings. Full N4 criteria are in the [runtime criteria](../../docs/observability/N4_PRODUCER_CAPABILITIES.md).

| Cohort | Allocation/order | Outcome retained |
| --- | --- | --- |
| campaign-3 | One-CPU quota, 1 s period; interleaved; older producer `08a4732` | 16 verified, one aborted/unavailable; trial 18 not executed. Counter sampling fix followed this failure |
| campaign-4 | One-CPU quota, 1 s period; grouped; corrected `ae00593` | Three healthy verified; contention failed at 28.53184 FPS versus 29.99773 healthy; fifth trial canceled and retained |
| campaign-5 | One-CPU quota, 100 ms period; interleaved; corrected `ae00593` | Healthy verified; contention failed near 30 FPS despite 85.26% worker CPU; partial pacing acquisition retained |
| campaign-6 | Same quota plus CPU 0 affinity; interleaved | Healthy baseline about 4 FPS with too few intervals; unavailable result and partial next trial retained |
| campaign-7 | Restored unpinned one-CPU quota/1 s period; separate engineering overhead request | All five pairs, enabled coverage and separate diagnostic pass |

All attempted fault schedules were declared before measurement. Each retained
receipt has a unique source ID and positive, nonoverlapping acquisition window;
those checks do not alone prove scientific independence or causality. Failed
cohorts are not combined into a successful cohort, and effect/CPU/FPS thresholds
were not changed. Earlier setup and interrupted acquisitions also remain locally
retained outside these four summarized fault cohorts.

The core Python 3.13 suite passes 1,978 tests with 93.48% coverage. Producer Linux
scenario and trace suites pass 78 and 58 tests respectively, with no Linux skip.
Python 3.11.17 also passes 1,978 tests at 93.48% coverage, all 23 schemas, Ruff
and frozen pins. Actual Node 24.18.1 engine verification passes 135 tests with one
existing external-artifact skip. Core hosted quality/minimum-Python CI is verified
for `bc6f42b`; Pixelated hosted CI remains unverified.

## Inspect retained public evidence on this host

Raw public archives and full reports remain under ignored
`local/phase_1/n5-acceptance-20261012/` in the core checkout. Private ownership journals,
leases, native identities and diagnostic PTS are not published. This directory
also retains the trusted research scene/relay/receiver/lifecycle helpers, with
hashes in the execution ledger. The runtime is stopped after measurement.

From the core checkout:

```sh
.venv/bin/python -m latency_fingerprinting inspect-campaign \
  --directory local/phase_1/n5-acceptance-20261012/campaign-4 \
  --output /private/tmp/n5-campaign-4-report.json
.venv/bin/python -m latency_fingerprinting inspect-overhead \
  --directory local/phase_1/n5-acceptance-20261012/overhead-7 \
  --output /private/tmp/n5-overhead-7-report.json
.venv/bin/python -m latency_fingerprinting ingest-trace \
  --bundle local/phase_1/n5-acceptance-20261012/two-peers.tar.gz \
  --output /private/tmp/n5-two-peers-trace.json
.venv/bin/python -m latency_fingerprinting inspect-trace \
  --trace /private/tmp/n5-two-peers-trace.json \
  --output /private/tmp/n5-two-peers-summary.json
```

These commands adopt existing evidence; they do not repeat a live acquisition.
A fresh clone contains the sanitized ledger/reports but not the ignored raw
archives or cached research base image. The standard native image also builds and passes Gst imports plus bounded
Frozen Bubble/Neverball package smoke. Its image identity/lock hash are in the
ledger. Normal desktop/picker interaction and Pixelated hosted CI remain unverified. Use the producer's [live test procedure](../../../Pixelated-Studio-Edition/docs/n5-live-test-procedure.md)
for a new run, selecting new campaign/output/volume IDs and freezing versions,
workload, allocation and schedule before measurements. Start Docker Desktop;
this host's working CLI is `/Applications/Docker.app/Contents/Resources/bin/docker`.
Do not restart retained containers with old inbox files or overwrite their evidence.

Campaign-8 below now supplies the complete passing cohort after declared workload
calibration. Future reruns require a declared adequate workload/allocation and
entirely fresh source acquisitions. The API-reported browser timing limitation
requires method review before changing timestamp meaning. Current failures remain
part of the execution record.

## Commit message correction

The three local producer fix commits were reworded to the existing `[fix]`
convention on 2026-10-13. Current producer HEAD is `7e78d483ec3c1c5bf9e6977048591e19415b1ac1`;
its code tree matches the recorded `ae00593` tree exactly. The ledger records all
three old/new hash mappings. Original commits remain reachable in Pixelated via
`refs/archive/n5-acceptance-ae00593`, so frozen runtime evidence retains its actual
original commit IDs. No source, measurement or archive receipt was rewritten.

## Subsequent calibration and hosted verification

[Calibration screen](calibration-screen.json) retains all six short engineering
trials and the selected 512-rectangle scene. These runs do not pass the 30-second
acceptance predicates and are not reused as references or queries. Fresh full `campaign-8` on `workload-4`, pushed producer `7e78d48`, finishes with
18/18 verified, three references/three queries per class and nonoverlapping
receipt windows. [Plan](campaign-8-plan.json), [index](campaign-8-index.json) and
[canonical report](campaign-8-report.json) retain every result. A separate
selected-scene overhead request `campaign-9` also passes all fixed thresholds.
Its [canonical report](workload-4-overhead-report.json) records median CPU +0.37238
percentage points, FPS −0.000517%, and five enabled traces each with 900 joint
pairs/zero drops. All 4,500 separate diagnostic probes are retained (mean 19.830 µs,
maximum 399.542 µs). Raw evidence is under ignored
`local/phase_1/n5-calibration-20261013/overhead-9/`; the execution ledger includes file
checksums and clean ownership state. Docker stopped after measurement; completed
outputs were copied without restarting the old inbox.

[Core CI job record](core-hosted-ci.json) verifies successful quality and minimum
Python jobs for exact core commit `bc6f42b`; [GitHub run](https://github.com/Nghi-creator/latency_fingerprinting/actions/runs/38198471685).
No Pixelated Actions run was found for its pushed `7e78d48` at verification. Earlier
execution snapshots above predate this hosted check; full runtime/browser gates
remain separate from CI.

## Browser timing diagnostic, 2026-10-14

The [bounded research diagnostic](browser-entry-diagnostic.json) reads both API
`now` and `performance.now()` at callback entry on Pixelated’s actual draining
video element, Chromium 151, selected workload and producer `7e78d48`. Of 180
callbacks, 170 API deltas are negative and ten zero; all entry deltas are positive
(0.1–0.6 ms, median 0.2 ms). Only relative deltas are published. This supports the
[additive method proposal](../../docs/observability/N4_BROWSER_TIMING_REVIEW.md);
it is not a released trace method or acceptance test, and does not measure the
additional callback cost. Frozen v1 timestamps and exclusions remain unchanged.
The owned diagnostic receiver and container are stopped; retained evidence
volumes and earlier failures are preserved.
