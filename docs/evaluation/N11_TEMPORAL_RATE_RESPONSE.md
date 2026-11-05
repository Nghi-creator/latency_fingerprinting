# Candidate temporal-rate response

`evaluation.temporal_rate_response` supplies a standalone candidate with release
`n11-temporal-rate-response-candidate-v1`. It retains an engineered healthy
reference in addition to a degraded/relief comparison. This is a different
response contract from N3; it does not add policy features, change the existing
17-of-22 eligibility rule, or provide a classifier. Its specification and content
identity are available through `temporal_rate_response_spec()`.

## Input and validity

`temporal_rate_response(windows)` requires exactly four keys, in logical order:
`healthy`, `degraded`, `relief`, `post`. Each value is the complete preselected
window's sample list. Each sample has exactly these fields:

- `clock_id`: one `worker-monotonic-` identifier followed by 64 hexadecimal digits;
- `read_start_ns`, `read_end_ns`: worker elapsed monotonic read brackets;
- `counter`: cumulative encoded-buffer count;
- `sequence`: worker observation sequence.

Integer fields must be actual integers from zero through 2^63−1; booleans and
coercible strings are invalid. All windows share one declared worker clock.
Across all reads, sequences strictly increase, brackets do not overlap, and the
counter never decreases. Changing clock, resetting a counter, overlapping reads,
malformed fields or extra fields are invalid inputs and raise `ValueError`.

The candidate fixes these engineering eligibility limits before source replay:

| Check | Limit |
| --- | --- |
| Samples per window | 4–64 |
| Last read start minus first read end | At least 2 seconds |
| Last read end minus first read start | At most 5 seconds |
| Adjacent read end minus preceding read start | At most 1.5 seconds |
| Individual read bracket width | At most 100 milliseconds |
| First read start minus preceding window's last read end | At most 15 seconds |

Too few samples or unmet timing limits retain an unavailable window with reason
codes. Oversized input is invalid. Every supplied sample is checked, including
interior counter/sequence continuity; endpoints are never chosen by favorable
values. Callers remain responsible for selecting the complete windows using a
predefined acquisition recipe. The API cannot detect omitted source samples from
an unbound projection.

## Response arithmetic

Each eligible window reuses `contrast_bounds.counter_rate_bounds`: endpoint
counter deltas and read brackets produce exact rational rate bounds with a fixed
one-buffer sensitivity guard. The inherited `guarded_rate_fps` field names refer
to this encoded-buffer rate proxy. They are not physical capture timestamps,
confidence intervals, or authenticated bounds on arbitrary counter lag/bursts.
Read brackets do not establish when the underlying counters updated.

The three response coordinates are interval ratios minus one:

| Coordinate | Numerator rate | Denominator rate |
| --- | --- | --- |
| `degraded_vs_healthy` | degraded | healthy |
| `relief_vs_degraded` | relief | degraded |
| `post_vs_healthy` | post | healthy |

For nonnegative numerator interval `[nL,nU]` and strictly positive denominator
interval `[dL,dU]`, return `[nL/dU−1,nU/dL−1]`. Arithmetic is exact rational, with
numerator/denominator pairs in JSON. No epsilon, midpoint substitution, clipping
or statistical independence assumption is used. A denominator interval including
zero makes that coordinate unavailable. Invalid required windows also make their
coordinates unavailable. Other coordinates remain visible for explanation, but
the complete response is unavailable unless all four windows and all three
coordinates are eligible. There is no subset scoring.

Input and response content identities bind all supplied samples, including
interior reads. Preserve generated JSON bytes or use lossless integer handling:
rational components can exceed JavaScript's exact integer range.

## Read-only source projection

`project_temporal_rate_response(acquisition)` accepts the existing contained
source method `n11-contained-condition-witness-v1`. It invokes no runner, Docker
operation or acquisition. `temporal_rate_projection_spec()` identifies this
adapter separately as `n11-contained-temporal-rate-projection-candidate-v1`.

The adapter first applies the existing native-counter inspector, binding the
worker clock to the declared controller generation. It requires unique healthy
and post reference events and selects all native samples in degraded and relief.
It also validates recovery samples and ordering through recovery into post,
although recovery is not a response coordinate. Configured and negotiated rates
must be 30 except during relief, where both must be 24. These are source validity
checks, not classifier features.

Only encoded counters, sequences and worker read brackets enter the response.
Observer `at_ns`, capture counters, condition labels, configured fault doses and
owned-worker/property witness fields do not enter measured coordinates. The
adapter returns a canonical source payload hash separately from the projected
response identity. Changing ignored witness metadata changes the source hash,
while leaving identical projected measurements unchanged.

This verifies declared source consistency, not physical authenticity. A complete
study still needs raw-file custody, producer source and receipt verification,
independent linked condition bindings, a reviewed prospective acquisition recipe,
and an explicitly versioned fitting/scoring contract. The healthy prefix is a
controlled fixture reference whose availability elsewhere cannot be assumed.
Post restoration follows fault removal; it is not evidence of probe benefit.

Outputs always deny acquisition authority and empirical acceptance, retain zero
independent support/accepted diagnostic groups, and provide no diagnostic label
or confidence. No physical capture-latency or N9 clock acceptance follows.
