# Independent N4 trace examples

**Status:** Hand-authored Step 1 arithmetic/acceptance oracle, not runtime fixtures.
**Definition:** [Contract](N4_TRACE_CONTRACT.md).

All times below are relative integer nanoseconds in a single engine stream/epoch/
clock. They are invented inputs, independent of future producer/derivation code.
For the nominal case all five engine capabilities are supported, all remaining
boundaries unavailable. Sampling N=1; limits F=2000/E=10000. Four ledger frames
have source sequences 1–4 and exact correlation. All events have distinct,
increasing collector sequences 1–17 in the row order below (frame 4 lacks three
endpoints). Other loss counters are zero: offered=sampled=4, attempted=retained=17.

| Frame | Capture output | Queue enter | Queue exit | Encode input | Encode output |
| --- | ---: | ---: | ---: | ---: | ---: |
| frame-1 | 0 | 1000000 | 4000000 | 5000000 | 9000000 |
| frame-2 | 20000000 | 21000000 | 21000000 | 22000000 | 32000000 |
| frame-3 | 40000000 | 41000000 | 46000000 | 47000000 | 57000000 |
| frame-4 | 60000000 | 61000000 | absent | absent | absent |

Expected samples (ms) and statistics:

| Method | Values, in frame order | Eligible / usable / excluded | min / mean / max |
| --- | --- | --- | --- |
| Queue sojourn | 3, 0, 5 | 4 / 3 / 1 | 0 / 8÷3 / 5 |
| Encode elapsed | 4, 10, 10 | 4 / 3 / 1 | 4 / 8 / 10 |
| Capture-output age | 9, 12, 17 | 4 / 3 / 1 | 9 / 38÷3 / 17 |
| Browser callback lag | none | 4 / 0 / 4 | null / null / null |

First three results are measured with one `missing_endpoint` exclusion each;
callback lag is unavailable/unsupported_source with four `unsupported` exclusions.
Coverage is 3/4 for the three engine methods, not 100% and not extrapolated to
frames before/after this trace. With declared budget 12,000,000 ns, slack samples
are 3, 0, −5 ms; hits true, true, false, hit count 2, fraction 2/3. With null budget,
all deadline samples disappear and reason is budget_not_declared; do not assume
12 ms from any observed percentile.

## Distinguish validation errors from pair exclusions

| Independent change | Required outcome |
| --- | --- |
| frame-1 queue exit becomes 500000 ns | Queue method excludes frame-1 for negative_duration; remaining values 0,5, mean 2.5; other methods unchanged |
| frame-1 queue exit equals enter | Valid zero-duration measured queue sample |
| Collector sequences increase but timestamps for unrelated frames interleave | Accept; do not impose global timestamp sorting |
| Repeat frame-1/encode_output with a new event sequence | Reject whole record for duplicate endpoint; no first/last match heuristic |
| Event refers to frame-99 with no ledger entry | Reject whole record |
| Copy frame-1 endpoints into a different stream/epoch | No cross-scope pairing; each lifetime derives only its own frames |
| Frame correlation becomes missing and downstream events are removed | Keep capture output only; all three engine methods exclude for correlation_missing, not missing_endpoint |
| Missing correlation but downstream event remains | Reject inconsistent record |
| Browser timestamp offered as engine endpoint | Reject producer/boundary/clock combination |
| Negative timestamp, float timestamp, bool counter or unknown method release | Reject whole record |
| Unsupported method capabilities, zero ledger frames | Unavailable with capability/producer reason taking precedence over no_frames |
| Supported engine capabilities, zero frames | Engine methods unavailable/no_frames with null statistics |

## Independent browser case

One browser callback ledger frame uses same-domain presentation_proxy=10000000
and presentation_callback=14000000. Events sequences 1,2; offered=sampled=1,
attempted=retained=2. Callback lag is measured 4 ms with min=mean=max=4. All engine
methods are unavailable. No budget is permitted; deadline is budget_not_declared.
Presentation at 14 ms with callback at 10 ms excludes for negative_duration, not
−4 ms of display latency. Two observed presented-frame counts 7 and 10 imply
browser_missed_presentations=2; they do not imply two network-dropped frames.

## Independent sampling / loss case

Engine offered_frames=10, every_nth_frame=3; eligible source sequences are 1,4,7,10.
With max_frames=3, retain frame-1/frame-4/frame-7, sampled_frames=3,
unsampled_frames=6 and frame_capacity_dropped=1. Do not renumber these as frames
1,2,3. Suppose attempted_events=8, retained sequences=[1,2,4,7,8]. Then retained=5,
event_capacity_dropped=2 and event_shutdown_dropped=1 (others zero); total loss=3
matches the three gaps. Which frame endpoint is absent is determined by retained
events, not loss counters. Changing retained=6 without a sixth event rejects.
Sampling is not producer frame loss; queue overrun is not collector event loss.

## Hash / version / resource cases

Canonical record-byte SHA-256 must equal manifest trace_sha256 AND summary
trace_sha256; manifest trace_bytes equals actual UTF-8 byte length. A trailing
space changes bytes and violates canonical input even if parsed data is equal.
A modified event with an old manifest hash rejects before output. Research v2
manifests, unknown trace versions, a third archive member, symlink record files,
duplicate JSON keys, depth 33 or a 10001st event reject without partial output.
These cases are covered by Step 2/5/6 regressions and [Step 7 synthetic fixture](N4_INTEGRATION_VERIFICATION.md)
pins; this document neither refreshes existing fixtures nor establishes a live
producer measurement.
