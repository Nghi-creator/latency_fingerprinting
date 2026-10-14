# Browser timestamp method review

**Status:** implemented opt-in additive method, release 1.0.0; local live validation passes; final desktop/hosted acceptance remains separate.
[Exact execution contract](N4_BROWSER_EXECUTION_CONTRACT.md).
[Observed limitation](N4_BROWSER_INSTRUMENTATION.md#live-api-timestamp-limitation),
[frozen v1 contract](N4_TRACE_CONTRACT.md), [runtime ledger](N4_RUNTIME_ACCEPTANCE.md).

## Problem and evidence

The actual Chromium 151 recording has 900 callbacks. Frozen v1 pairs the
API-supplied `now` argument with `metadata.presentationTime`; 681 negative deltas
are excluded and 219 pairs produce zero lag. The collector and detached exclusion
arithmetic agree. Replacing those timestamps or clamping negatives inside v1
would change a frozen method and hide the observed limitation.

The [rvfc procedures](https://wicg.github.io/video-rvfc/#procedures) pass the
rendering-update timestamp into callbacks. It is distinct from reading the
performance clock inside the JavaScript callback. A rendering-update timestamp
preceding compositor submission is a plausible explanation for the observed
pairs; the particular Chromium cause has not been independently established.

## Implemented additional measurement

The implementation keeps both original endpoints and their v1 meaning. In an explicitly selected new
browser mode, take one additional `performance.now()` reading at callback entry,
before collector work. Record it as `presentation_callback_execution` for the
same callback-local frame and independent browser clock scope.

Use a distinct `presentation-execution-lag` method for compositor submission to
observed JavaScript callback entry. It remains API-reported, local and subject to
browser precision; it does not measure physical display, network transit or an
engine-to-browser frame age. Negative/missing/invalid endpoints remain explicit
exclusions, with no clamping, heuristics or replacement of old evidence.

The implementation introduces additive browser `stage-trace-record-v2` and `stage-trace-summary-v2`
roots with an explicit method release, rather than adding an unversioned endpoint
to the closed v1 schema. The new record retains the original API endpoints so the
observed discrepancy can be compared directly. Default v1 collection/export,
all original pins and the N5 host/capture-pacing artifact contracts stay unchanged.
Browser v2 traces remain standalone; they are not silently adopted into N2/N3
features or N5 v1/v2 experiments.

## Concrete review and verification cases

| Same callback, milliseconds | Frozen v1 result | Proposed additional result |
| --- | --- | --- |
| API `now` 10.00, submission 10.05, observed entry 10.40 | −50,000 ns, excluded | 350,000 ns, usable |
| Entry precedes API-reported submission | Existing exclusions unchanged | Negative duration excluded |
| Missing/nonfinite/throwing entry clock | Existing endpoint evidence retained | Explicit missing/invalid evidence; no fabricated sample |
| Counter/reset/clock regression | Existing lifetime closure rules | Independent new scope required; no cross-lifetime pairing |
| Capacity/sampling/cancellation | Existing limits and loss counts unchanged | Additional events accounted within the same bounded global capacity |

The [execution contract](N4_BROWSER_EXECUTION_CONTRACT.md) specifies exact fields,
capabilities, versioned export and failure/loss accounting. Independent pinned
integer fixtures and actual producer-to-core archive/API/CLI reproduction cover
paired, partial-capacity and API-unavailable cases. Tests exercise failed entry
clock reads, regressions including unsampled callbacks, coarse-clock zeros and
late callbacks after failed cancellation. Original v1 pins remain unchanged.

The [bounded live diagnostic](../../experiments/n5-runtime-20261013/browser-entry-diagnostic.json)
on 2026-10-14 collects 180 actual paired API-argument/entry timestamps on
Pixelated's draining video element, Chromium 151 and selected `workload-4`.
API deltas are negative in 170 callbacks and zero in ten (median −0.1 ms).
Entry deltas are all positive, 0.1–0.6 ms (median 0.2 ms); entry-minus-API is
0.2–0.8 ms (median 0.4 ms). These observations support the implemented distinction;
they do not establish Chromium's internal cause or validate a released method.
The diagnostic publishes only relative deltas and does not measure callback cost.

The [versioned live validation](../../experiments/n5-browser-execution-20261014/README.md)
now passes all five paired overhead/coverage checks and the separate 1,200-probe
diagnostic using the production v2 collector on Pixelated's video element. It
retains every original API exclusion, the CPU transient and working-tree source
hashes. Normal player/picker interaction and hosted checks for final committed
changes remain open. Local method validation does not close Phase 1.
