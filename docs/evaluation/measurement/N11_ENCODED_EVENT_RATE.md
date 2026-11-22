# Encoded event-span rate prototype

The prototype measures completed intervals between consecutive encoded-buffer
observations on one worker clock. If the first and last observations have
ordinals (i) and (j), the span contains exactly (j-i) completed intervals
under the complete-trace contract. Divide this count by the outer and inner
elapsed bounds to obtain the lower and upper rate. The polled-counter rate
continues to use its one-buffer guard.

`evaluation.encoded_event_rate.encoded_event_rate` accepts a bounded sequence
of records with `event_ordinal`, `clock_id`, `read_start_ns`, and
`read_end_ns`. The records must share a worker clock and have consecutive
ordinals and strictly ordered brackets. The sequence includes an observation
entirely before the phase and one at or after its end. A bracket crossing a
phase boundary makes the phase unavailable. The first and last fully included
observations must span at least three seconds, with outer elapsed time at most
five seconds and elapsed half-width at most five milliseconds.

## Producer feasibility

The current producer records the encoded getter and its read brackets. The
candidate would observe buffers at the existing encoded identity before the
RTP payloader. A bounded observer would record each observation with its
ordinal and worker elapsed time, then export the batch through the engineering
path. The observation time describes the callback at that point in the
pipeline. It does not establish encoder completion time, media PTS alignment,
or display latency.

A producer qualification needs explicit evidence of callback coverage,
overflow and generation handling, and reconciliation with an independent
count of buffers at the same boundary over the same covered span. Consecutive
export ordinals by themselves cannot establish callback completeness. Phase
boundaries need worker-clock observations or a verified bounded mapping onto
that clock. Controller-clock timestamps alone cannot select worker events.
Both boundary witnesses and a three-second interior span must fit the
observed phase. A trace that starts late, overflows, or lacks a boundary
witness cannot produce a rate. CPU rate observations retain their guarded
source contract and independent clock.

The prototype exposes numerical bounds for synthetic or separately verified
event records. Producer instrumentation and source custody integration are
open. The existing observer cost, restoration, and control lifetime checks
apply to an engineering qualification of the new observer.
