# Browser execution method validation, 2026-10-14

**Outcome:** implementation and local live method checks pass. Normal desktop/picker
interaction and hosted verification of final committed changes remain pending.
[Method contract](../../docs/observability/N4_BROWSER_EXECUTION_CONTRACT.md),
[research report](report.json), [runtime criteria](../../docs/observability/N4_PRODUCER_CAPABILITIES.md).

This is real Pixelated VP8 playback on a draining Chromium 151.0.7922.34 video
element. The same seed-7 `workload-4` scene animates 512 rectangles of size 32 pixels
at 1280×720/30. The Linux capture runtime uses the existing image
`sha256:995a464082209b07664b5e92b27d8fd408c366defe8df3ce7667a3571bbbfdf1`,
one-CPU quota/one-second period, no CPU affinity and 2 GiB memory. Chromium runs
on the macOS host. Browser CPU is the delta of CDP CPU times over the same owned
Chromium process set, expressed as a percentage of one logical core; it is not
the Linux camera CPU metric used by the earlier host-overhead report.

The browser source is base producer `7e78d48` plus explicitly hashed working-tree
changes; the record's commit label is that base. The report retains individual
source/bundle/helper hashes and explicitly identifies this limitation. It does
not claim an exact committed browser release or hosted verification. Final build
commits and desktop outcomes must be recorded separately after commit/push.

## Predeclared paired measurements

Five disabled/enabled pairs each have 10 seconds warm-up and 30 seconds measured
collection. A separate disabled/enabled diagnostic uses 40-second measurements.
Thresholds were frozen before acquisition: disabled FPS ≥27, median CPU increase
≤5 percentage points, median FPS change ≥−5%, each nominal trace ≥500 usable pairs
and ≥95% coverage with zero trace drops, and ≥1,000 diagnostic probes.

All fixed thresholds pass. Median CPU increase is **0.07918 percentage points**;
median FPS change is **+0.002943%**. Every nominal trace has 899–901 frames and
complete execution pairs, zero trace drops and zero missed presentations.
All five raw archives are detached-adopted and reconstructed. Original API
callback negative exclusions remain visible independently of the new result.
The [published nominal record](nominal-record.json) and its
[canonical summary](nominal-summary.json) preserve the first actual recording.

Individual CPU deltas range from −0.34651 to +16.06054 percentage points; the
transient increase remains in the report. Earlier software verification also ran
during initial acquisition windows. These results satisfy the predeclared median
criteria under the recorded conditions; they do not establish an isolated-machine
or causal CPU cost. No failed pair is discarded or replaced.

The separate diagnostic retains all 1,200 observed callbacks: mean 39.583 µs,
minimum 0 and maximum 200 µs, including wrapper/clock-read cost. Effective clock
precision is unknown; quantized zeros are not a claim of zero execution cost.
Its CPU change is +0.80388 percentage points. Archive materialization outside
callbacks takes 14.4–19.1 ms in the five nominal windows; this measures browser
serialization/gzip/blob materialization, not a disk write or picker interaction.

A separate actual HTMLVideoElement case deliberately removes callback/cancellation
methods during attachment. Its [record](api-absent-record.json) and
[summary](api-absent-summary.json) explicitly report both capabilities unavailable
and no invented samples. This is controlled API absence, not a claim that native
Chromium lacks support.

## Reproduce detached inspection

From the core checkout:

```sh
.venv/bin/python -m latency_fingerprinting validate \
  experiments/n5-browser-execution-20261014/nominal-record.json
.venv/bin/python -m latency_fingerprinting inspect-trace \
  --trace experiments/n5-browser-execution-20261014/nominal-record.json \
  --output /private/tmp/n4-execution-summary.json
cmp experiments/n5-browser-execution-20261014/nominal-summary.json \
  /private/tmp/n4-execution-summary.json
```

All seven actual raw archives, frozen acquisition plan, helper scripts, receipts
and full test logs remain under ignored `local/phase_1/n5-browser-execution-20261014/` on
this host. Private process IDs/getStats diagnostics are not published. The report
is research metadata, not a new core artifact schema. The trace/summary files are
actual versioned artifacts, separate from the
[independent synthetic release](../../fixtures/browser-execution-v1/README.md).
The owned receiver processes and scene container are stopped; evidence volumes
and earlier failed cohorts remain retained.

Use the producer's [manual handoff](../../../Pixelated-Studio-Edition/docs/n5-live-test-procedure.md#final-manual-desktop-and-hosted-checks)
for normal desktop, export-picker and final hosted checks. This method does not
change N5 host/capture-pacing evidence or close Phase 1 by itself.

## Software verification

[Local verification record](verification.json) records the actual final checks:
Python 3.13.13 passes 2,003 tests/93.52% coverage; actual Linux Python 3.11.17
passes 2,003 tests/93.60%, all 25 schemas, registry and frozen reproductions.
All 259 web tests pass on Node 24.18.1 Linux and Node 26.4.0 macOS, without skips.
Web lint and default/opt-in production builds pass. Original schema bytes and
N4/N5 fixture releases remain unchanged. The new independent fixture release
also reproduces actual producer archives through the core API and CLI.
