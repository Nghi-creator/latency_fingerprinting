# Browser callback execution method, release 1.0.0

**Implemented:** `n4-browser-execution-v1`, opt-in standalone browser trace v2.
[Original v1 contract](N4_TRACE_CONTRACT.md), [method rationale](N4_BROWSER_TIMING_REVIEW.md),
[browser integration](N4_BROWSER_INSTRUMENTATION.md).

## Timestamp meaning and version boundary

`stage-trace-record-v2` and `stage-trace-summary-v2` admit only `pixelated_browser`
and require `method_release: n4-browser-execution-v1`. They retain the original
`presentation_proxy` (`metadata.presentationTime`) and `presentation_callback`
(API callback `now`) endpoints unchanged. They add `presentation_callback_execution`:
one `performance.now()` reading inside the callback before metadata/collector work.
All three endpoints use the attachment's browser performance clock and private
origin, exporting only rounded relative integer nanoseconds. No native frame IDs,
absolute origins, optional metadata or display predictions enter the record.
Clock precision remains unknown (`resolution_ns: null`); no synchronization is implied.

The new method `presentation-execution-lag`, version 1, subtracts compositor
submission from observed callback-entry time. It measures local JavaScript callback
execution relative to the browser's reported submission time. It does not measure
physical presentation, engine-to-browser frame age, transit or end-to-end latency.
The original `presentation-callback-lag` still subtracts the API `now` argument.
Negative durations are retained in raw evidence and excluded during reconstruction.
Zero remains a valid precision-limited sample. Neither method clamps or substitutes
an endpoint to make a pair usable.

V1 remains the default. Its schemas, method release, producer fixture bytes and
N2/N3 semantics are unchanged. N5 experiment v1/v2 and host-overhead artifacts
continue to admit only their existing host trace v1; standalone browser v2 is not
silently adopted into scenario effects, features, fingerprints or matching.

## Exact record and summary shape

V2 inherits all v1 identity, provenance, strict parsing, immutable validation,
stream/epoch/clock, frame-prefix sampling, resource bounds and loss fields.
It makes these explicit changes:

- Record/summary root versions and method release are as above; producer is browser only.
- Capabilities retain the eleven v1 entries in order, then append
  `presentation_callback_execution`. The two browser source entries are supported
  when the callback/cancellation APIs exist; host/receive/decode boundaries remain
  unavailable. A missing entry-clock sample does not fabricate API unavailability.
- Browser events admit exactly `presentation_proxy`, `presentation_callback` and
  `presentation_callback_execution`. The original callback event continues to use
  the proxy capability; execution uses its own capability.
- Summary results retain the four ordered v1 methods and append
  `presentation-execution-lag`. The three host methods are unavailable, and no host
  deadline is allowed. Both browser results independently report eligible/usable
  frames, all exclusion counts, exact integer deltas and checked statistics.

The global limits remain sixteen lifetimes, 2,000 retained frames and 10,000
retained events. Each sampled callback attempts three events, in the endpoint order
above. Sequence gaps and loss accounting expose invalid or capacity-dropped events.
Capacity is shared across attachments and never refilled; a partial last frame is
retained and each method excludes its missing endpoint independently. Sampling and
missed-presentation counts use callback order, including unsampled callbacks.

A throwing, missing or nonfinite entry-clock reading drops only that event via
`event_invalid_timestamp_dropped`; the original API endpoints survive. Invalid
relative integer conversion is handled the same way. A finite entry-clock value
before origin or before the previous finite entry reading closes that lifetime
with `source_error`, before admitting the offending callback. This check includes
unsampled callbacks. Existing API-clock and presentation-counter reset checks
remain active. A new attachment must establish a fresh scope. Detachment/finish
cancels the one outstanding callback; late callbacks cannot read clocks or mutate
finished evidence even if cancellation fails.

## Export, adoption and independent verification

The same two-member archive contains only `trace-manifest.json` and canonical
`trace-record.json`. Browser v2 requires manifest `schema_version: 2` and
`trace_schema_version: stage-trace-record-v2`, with the existing closed bundle type,
SHA-256 and exact byte count. Manifest/record version mismatch is rejected. Existing
bounded no-follow input, duplicate-safe JSON, archive checks and atomic output apply.

`ingest-trace`, `inspect-trace` and `validate` dispatch explicitly on the root
version. Public model APIs export `StageTraceRecordV2` and `StageTraceSummaryV2`;
the v1 model still rejects v2. The generated [record schema](../../schemas/stage-trace-record-v2.schema.json)
and [summary schema](../../schemas/stage-trace-summary-v2.schema.json) are additive.

[Independent release fixtures](../../fixtures/browser-execution-v1/README.md)
cover paired timestamps, partial capacity and API unavailability. Their integer
expectations are authored separately from the producer and reconstruction code.
Both core CI jobs check their read-only pins. Producer tests reproduce the exact
raw record bytes; optional archives exercise the actual producer exporter through
core API/CLI adoption and reconstruction.
