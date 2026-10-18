# Browser timestamp method review

See the [execution contract](N4_BROWSER_EXECUTION_CONTRACT.md),
[browser instrumentation](N4_BROWSER_INSTRUMENTATION.md) and [frozen v1 contract](N4_TRACE_CONTRACT.md).

## Timestamp limitation

Frozen v1 pairs the API-supplied `now` argument with
`metadata.presentationTime`. The first timestamp may precede the second, yielding
negative durations that reconstruction excludes. Replacing timestamps or clamping
negative values inside v1 would change the method and hide this limitation.

The [rvfc procedures](https://wicg.github.io/video-rvfc/#procedures) pass the
rendering-update timestamp into callbacks. It is distinct from reading the
performance clock inside the JavaScript callback. A rendering-update timestamp
preceding compositor submission is consistent with this timestamp distinction; it does not establish a specific
browser implementation cause.

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

| Same callback, milliseconds | Frozen v1 result | Additional method result |
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
