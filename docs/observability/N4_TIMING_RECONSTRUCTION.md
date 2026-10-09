# N4 timing reconstruction and inspection

**Delivered:** Step 6 software, 2026-10-09.
**Meaning:** [Frozen trace/method contract](N4_TRACE_CONTRACT.md).
**Input:** [Standalone export and adoption](N4_TRACE_ADOPTION.md).

The core now reconstructs a `StageTraceSummary` from a revalidated
`StageTraceRecord` through `observability.reconstruct_trace`. The operation is
pure: it changes neither the input nor producer state, runs no probes or network
requests and does not feed N3 normalization, fingerprints or matching.
It accepts a validated trace model; copied/forged nested instances are revalidated
before pairing. Invalid versions, clocks, references, duplicates, loss or bounds
fail rather than producing a partial summary.

## Methods and pairing

Every stream receives all four ordered v1 results:

| Method | Producer | End minus start |
| --- | --- | --- |
| pre-encode-queue-sojourn | Engine | queue exit minus queue entry |
| encode-boundary-elapsed | Engine | encoder output minus encoder input |
| capture-output-age-at-encode-output | Engine | encoder output minus capture output |
| presentation-callback-lag | Browser | callback now minus compositor submission |

Pairing keys are the frame alias and approved boundary within one stream. No
stream/epoch/clock boundary is crossed, even when frame aliases match. Source
sequence orders samples; event arrival order does not replace endpoint timestamps.
Negative durations are excluded, never made positive or repaired by sorting.
Zero durations remain measured samples. Queue waiting is not queue occupancy;
encoder boundary elapsed is not CPU execution; browser callback lag is not decode
execution, display completion, feedback-free timing or one-way network latency.

Each retained frame contributes a usable sample or exactly one exclusion in
priority order: unsupported capability/producer, missing correlation, ambiguous
correlation, missing endpoint, negative duration. All methods belonging to the
other producer are explicitly unavailable. Unavailable result reasons follow
unsupported_source, capability_unavailable, no_frames, no_usable_pairs precedence.
When no usable sample exists, min/mean/max are null rather than fabricated zeros.

Timestamp subtraction and sums use exact Python integer arithmetic, including sums
larger than 2^53−1. Each approved nonnegative delta stays a safe integer because
its endpoints are bounded. Milliseconds use delta_ns / 1000000; mean uses the
integer sum / (usable count * 1000000), with one final floating division.
Summary validators independently recompute the statistics and coverage. No
percentile, tolerance-based repair, confidence interval or unsampled extrapolation
is added. Effective clock resolution stays as declared; numeric formatting does
not imply that accuracy or synchronization has been assessed.

Clock/capability/sampling/loss declarations and lifetime aliases are copied without
reinterpretation. Eligible count is the retained ledger size; usable plus excluded
equals eligible. Offered, unsampled, capacity loss, event loss and browser missed
presentations remain visible separately. Coverage usable/eligible describes this
retained sample only; it is not population coverage across lost/unsampled frames.

## Declared budget and identity

A host deadline budget reuses only usable capture-output-age pairs. Slack is
(budget_ns - delta_ns) / 1000000; equality is a hit, negative slack is valid and
hit fraction uses usable pairs only. No budget yields budget_not_declared with
empty samples and null fraction. A declared budget without usable age pairs yields
no_usable_pairs. Browser traces cannot declare a host budget. This is a declared
software budget relative to capture output, not an end-to-end deadline guarantee
or scheduling decision.

The summary hash is SHA-256 of the validated input model's canonical UTF-8 bytes,
including its trailing LF. It is not a hash of the summary or a supplied hash.
Provenance and producer commit are retained. An internally valid summary alone
cannot authenticate its claimed input; inspect-trace always takes the trace and
recomputes the result. No supplied summary is adopted as inspection evidence.

## Offline command

```bash
.venv/bin/python -m latency_fingerprinting ingest-trace \
  --bundle /absolute/trace.tar.gz --output /absolute/trace-record.json
.venv/bin/python -m latency_fingerprinting inspect-trace \
  --trace /absolute/trace-record.json --output /absolute/trace-summary.json
.venv/bin/python -m latency_fingerprinting validate /absolute/trace-summary.json
```

Input reads pin no-follow ancestors/leaf, require a regular file, bound JSON to
10 MiB/depth 32 and reject duplicate keys before strict trace validation. Standalone
trace JSON may use different whitespace/key order; its identity is still the
canonical model hash. The Step 5 producer bundle remains stricter and requires
canonical record bytes plus matching manifest hash/length.

inspect-trace atomically writes canonical summary JSON through the Step 5 output
helper after complete validation. Parent output directories must exist. Success
returns 0 and no stdout. Failure returns 1 with the fixed
`error: inspect-trace: invalid_input_or_output` message, no source/path/private
value echo and no partial output or replacement of a previous destination.
Symlink/special inputs and outputs fail; no remote resource is resolved.

## Software verification and remaining gate

46 independent cases cover the hand-authored complete Step 1 example, all methods'
positive/zero/negative pairs, exclusion precedence, capability absence, sampling/
loss, out-of-order arrival, reset isolation, optional/equal/negative-slack budgets,
immutable repeatability, canonical hash identity and forged copy rejection. A
2000-frame safe-limit case checks exact large integer sums with an independent
rational expectation. Fresh imports check that public models and reconstruction
avoid a serialization dependency cycle. CLI cases cover bounded/duplicate/deep
JSON, no-follow paths/special files, fixed failures and preserved output.

The actual Step 5 synthetic host/browser exporter artifacts also pass inspect-trace
and strict summary validation. Host means reproduce 0.0001 ms queue waiting,
0.0001 ms encoder boundary elapsed and 0.0004 ms capture-output age. Browser
callback mean reproduces 1.5 ms; foreign-producer results are explicitly unavailable.
Those synthetic clocks are arithmetic/interoperability evidence, not real timing.

Step 7 [pinned integrated reproduction](N4_INTEGRATION_VERIFICATION.md) is delivered. Remaining gates are real Linux/X11/VP8
acceptance and measured overhead. Live browser/picker interaction, synchronized
one-way latency, hosted/minimum-version execution and real capture are not
established by this software. N4 remains incomplete until its acceptance gates
are met or explicitly retained as pending in a software closeout.
