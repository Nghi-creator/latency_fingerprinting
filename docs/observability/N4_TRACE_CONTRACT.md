# N4 trace contract, version 1

**Status:** Step 1 specification frozen, 2026-10-09; software Steps 2–7 delivered locally.
**Implementation:** [Models/validation](N4_TRACE_MODELS.md), [host hooks](N4_HOST_INSTRUMENTATION.md),
[browser hooks](N4_BROWSER_INSTRUMENTATION.md), [export/adoption](N4_TRACE_ADOPTION.md),
[reconstruction](N4_TIMING_RECONSTRUCTION.md), [integration](N4_INTEGRATION_VERIFICATION.md);
real capture/overhead validation remains pending.
**Plan:** [N4](../plans/archive/N4_STAGE_LEVEL_OBSERVABILITY_PLAN.md).
**Producer inventory and acceptance:** [Capability matrix](N4_PRODUCER_CAPABILITIES.md).
**Independent arithmetic cases:** [Examples](N4_TRACE_EXAMPLES.md).

This is the normative software contract for Steps 2–6. Changes to a field,
boundary, formula, approved method or limit require a reviewed version change.
Values describe observed software boundaries, not calibrated physical latency.
Existing N2 `StageTiming`, ten schemas, producer research bundle v2, N3 registry,
policy, normalization and matching remain unchanged. Nothing here enables N4
values as N3 features.

## Roots and release

Add `StageTraceRecord` (`schema_version: "stage-trace-record-v1"`) and
`StageTraceSummary` (`schema_version: "stage-trace-summary-v1"`). Schema filenames
are `stage-trace-record-v1.schema.json` and `stage-trace-summary-v1.schema.json`.
All objects reject extra keys, missing required keys, duplicate JSON keys,
nonfinite numbers, booleans as numbers and coercion from strings. Containers
are immutable snapshots; reused/copied model instances are revalidated.
Optional values below are required keys with null when absent.

The approved release is `method_release: "n4-stage-local-v1"`. Its methods are
compiled allowlists in both implementations, not supplied executable policy.
Unknown releases, sources, events, methods or versions fail closed. A record
cannot select a remote resource or replace method definitions. Version 1 has
no synchronization or estimated-duration method.

## Record fields

| Field | Exact meaning / allowed value |
| --- | --- |
| `schema_version`, `method_release` | Literals above |
| `trace_id`, `session_id`, `run_id` | Export-local aliases `trace-N`, `session-N`, `run-N`; N is a positive decimal integer without leading zeros |
| `provenance` | `producer_capture` or `synthetic`; synthetic never establishes runtime acceptance |
| `producer` | `pixelated_engine` or `pixelated_browser` |
| `producer_version` | Lowercase 40-character Git commit SHA; not a path, environment dump or arbitrary string |
| `streams` | 1–16 stream records, ascending numeric alias order |

A trace contains one producer. Session/run aliases convey user-declared grouping,
not proof of clock synchronization or frame correlation between files. IDs are
renumbered on each export; no raw session, peer, game, user or device identifiers
and no stable hashes of private identities are exported. Content hashes identify
artifact bytes, not people. Live aliases need not equal export aliases.

Each stream has exactly these fields:

| Field | Exact meaning / allowed value |
| --- | --- |
| `stream_id`, `epoch_id`, `clock_id` | Local aliases `stream-N`, `epoch-N`, `clock-N`; each unique within its category in this trace |
| `clock` | Clock object below; `clock_id` identifies this object's scope |
| `capabilities` | Exactly one declaration for each of the eleven boundaries below, in listed order |
| `sampling` | `{ "every_nth_frame": N }`, integer 1–1000 |
| `limits` | `{ "max_frames": F, "max_events": E }`, integers 1–2000 and 1–10000 |
| `deadline` | Null or `{ "method_id": "capture-output-budget", "method_version": 1, "budget_ns": B }`, positive safe integer; engine only |
| `frames` | At most F ledger entries, increasing `source_sequence` |
| `events` | At most E events, increasing `sequence` |
| `loss` | Exact counters below |
| `stop_reason` | `completed`, `disabled`, `capacity`, `shutdown`, `source_error` |

A stream represents a single pipeline or browser video-element lifetime. Restart,
seek/segment discontinuity, clock reset, peer replacement or element replacement
starts a new epoch AND a new stream/clock alias; never pair across these scopes.
At most sixteen such lifetimes fit one trace. Further lifetimes require a new
trace; overflow cannot overwrite an earlier lifetime. Engine peers have separate
capture pipelines and separate frame sequences. Shared content is not identity.

### Clock object

Exactly `source`, `unit`, `origin`, `resolution_ns`, `synchronization`:

- Engine source `python_monotonic_ns`, browser source `browser_performance`;
  `unit: "ns"`, `origin: "stream_start"`, `synchronization: "none"`.
- `resolution_ns`: positive safe integer or null when not established. Engine
  reports ceil(`time.get_clock_info('monotonic').resolution * 1e9`), at least 1.
  Browser reports null unless effective timestamp quantization was actually
  assessed; representation in nanoseconds does not imply nanosecond accuracy.
- Engine timestamps subtract an origin read from the same `time.monotonic_ns()`
  clock. Browser subtracts an origin from the same document performance timeline,
  then rounds milliseconds times 1e6 to the nearest integer, ties upward.
  Negative, nonfinite or unsafe results cannot be exported as events.
- Origins, UTC dates, `performance.timeOrigin`, machine uptime and absolute Gst
  timestamps are not exported. No clock offset, uncertainty or feedback-delay
  estimate is fabricated; absent synchronization forbids cross-clock subtraction.

Python's monotonic clock has an unspecified reference point; only differences
are meaningful. [Python time reference](https://docs.python.org/3/library/time.html#time.monotonic_ns).
Gst buffer PTS may be absent and represents media timing; it is not this clock
or a guaranteed globally unique frame ID. [GstBuffer reference](https://gstreamer.freedesktop.org/documentation/gstreamer/gstbuffer.html).

### Boundary declarations

Each capability is exactly `{ "boundary": NAME, "state": STATE, "reason": REASON }`.
State is `supported` with null reason, or `unavailable` with one closed reason:
`not_instrumented`, `unsupported_source`, `api_unavailable`, `disabled`,
`source_unavailable`. Supported means the hook/API is active, not that every
frame has evidence. Disabled streams have no frames/events and all boundaries
unavailable with `disabled`; all loss counters are zero. Engine frames require
supported capture_output; browser frames require supported presentation_proxy. Supported boundaries must belong to this producer's
allowlist; events require supported declarations. A boundary outside the producer
allowlist uses unsupported_source, except disabled mode. Browser frames always
have exact callback-local correlation; engine missing/ambiguous frames have no
downstream events.

| Boundary name, in declaration order | Exact observation permitted in v1 |
| --- | --- |
| `render_ready` | Unavailable: game/render completion not exposed |
| `capture_begin` | Unavailable: no approved source start hook |
| `capture_output` | Engine: source `ximagesrc` src-pad buffer probe, after capture output is produced |
| `pre_encode_queue_enter` | Engine: `pre_encoder_queue` sink-pad buffer probe |
| `pre_encode_queue_exit` | Engine: same queue src-pad buffer probe |
| `encode_input` | Engine: `video_encoder` sink-pad buffer probe |
| `encode_output` | Engine: same VP8 encoder src-pad buffer probe |
| `wire_send` | Unavailable: enqueueing RTP does not observe actual wire send |
| `receive` | Unavailable in this release: no approved receive hook/correlation |
| `decode_ready` | Unavailable in this release: cumulative getStats means are separate |
| `presentation_proxy` | Browser: rvfc `metadata.presentationTime`, paired with callback `now` |

The last API reports compositor submission, not physical scan-out. Browser event
`presentation_callback` additionally records rvfc's callback `now`; it uses the
`presentation_proxy` capability. This is delivery lag, not render duration.
`expectedDisplayTime` is predictive; remote `captureTime` is estimated. Neither
is accepted as synchronized capture/display evidence. Callbacks can skip frames.
[Video frame callback specification](https://wicg.github.io/video-rvfc/).

### Frame ledger and events

Every admitted sampled frame has exactly `frame_id`, `source_sequence`,
`correlation`. `frame_id` is `frame-N`, where N equals `source_sequence`.
Source sequences are integers 1–2^31-1; the sampled set satisfies `(N-1) % every_nth_frame == 0`.
`correlation` is `exact`, `missing`, or `ambiguous`.

Engine source sequence advances at every capture-output probe. A bounded internal
PTS map associates downstream raw/encoded buffers only when PTS is present,
unique within this epoch, and preserved at the observed boundaries. Never assume
those conditions from plugin names. Duplicate PTS invalidates all implicated
sampled frames as `ambiguous`; omit their downstream events at finalization.
Missing PTS is `missing`. For either case, only `capture_output` may remain.
Evicting an unresolved mapping must mark it missing, not reuse its alias. Do not
export raw PTS or buffer offsets. PTS is an internal correlation key only;
queue passage and encode output pairing require real-case verification.

Browser sequence advances on each observed rvfc callback, not each received
network frame. The two callback metadata events belong to that same callback
(`exact`). No engine-to-browser frame mapping is approved. Gaps in rvfc
`presentedFrames` are recorded separately below, not invented ledger entries.

Each event has exactly `sequence`, `frame_id`, `boundary`, `timestamp_ns`.
`sequence` starts at 1 for attempted events per stream and increases even when
an event is lost; retained gaps account for lost events. A frame/boundary pair
is unique. Engine events use the five supported engine names above; browser uses
`presentation_proxy` and `presentation_callback`. Events reference ledger frames.
Timestamps are nonnegative safe integers. Sequence describes collector order;
clock values may tie or arrive out of temporal order. Do not sort timestamps to
repair an impossible duration or silently pair a duplicate endpoint. Duplicate
identity/endpoints, missing references or illegal boundary/source combinations
reject the trace. Negative pair durations exclude that frame for that method.

### Sampling and loss

Keep the earliest admitted frame ledger and event prefix (subject to correlation filtering); never a rolling buffer
that hides lost beginnings. Sampling is selected once at capture output/callback
and applied consistently to every endpoint. Stops freeze all counters and tables.
Counts are nonnegative safe integers; no guessed zeros when counters are unavailable.
Exact accounting is required for this release, including shutdown and contention.

`loss` has exactly:
`offered_frames`, `sampled_frames`, `unsampled_frames`, `frame_capacity_dropped`,
`attempted_events`, `retained_events`, `event_capacity_dropped`,
`event_invalid_timestamp_dropped`, `event_contention_dropped`,
`event_shutdown_dropped`, `event_correlation_dropped`, `browser_missed_presentations`.

`offered_frames = sampled_frames + unsampled_frames + frame_capacity_dropped`;
`sampled_frames = len(frames)`; unsampled counts only ineligible source sequences.
Frame capacity drops count eligible frames that cannot enter the ledger.
Sampled plus frame-capacity-dropped must equal ceil(offered_frames / N).
Retained source sequences are within offered_frames and match the sampling rule.
`attempted_events = retained_events +` the five event-drop counters;
`retained_events = len(events)`. Last sequence is at most attempted_events;
sequence gaps plus omitted suffix equal the sum of dropped events. Correlation
filtering of previously admitted downstream events increments
`event_correlation_dropped`, retaining their sequence gaps. Downstream buffers
that cannot be assigned a sampled frame are not attempted events. Do not refill
slots freed by correlation filtering or count removed candidates as retained. `browser_missed_presentations` is zero
for engine, otherwise the sum of positive gaps minus one in adjacent rvfc
presented-frame counts within the epoch. It measures missed callbacks, not
network/decoder drops. Endpoints not reached are missing evidence, not event loss.

## Approved derivation and summary

Method version is integer 1 for each approved method. All differences use the
same frame, stream, epoch and clock. Engine methods require `exact` correlation.
Timestamp delta is calculated in integer nanoseconds before division by 1e6.

| `method_id` | Producer | Start → end | Meaning |
| --- | --- | --- | --- |
| `pre-encode-queue-sojourn` | engine | queue enter → queue exit | Observed queue residence including scheduling, not occupancy or CPU work |
| `encode-boundary-elapsed` | engine | encode input → encode output | Encoder boundary elapsed including scheduling/buffering, not pure encode execution |
| `capture-output-age-at-encode-output` | engine | capture output → encode output | Age since observed capture output, excludes source capture duration |
| `presentation-callback-lag` | browser | presentation proxy → callback | API-reported compositor submission to callback delivery |

Summary fields exactly: `schema_version`, `method_release`, `trace_sha256`,
`provenance`, `producer`, `producer_version`, `streams`. Hash is SHA-256 of canonical input record
bytes, not a self-referential record ID. Each summary stream has `stream_id`,
`epoch_id`, `clock_id`, `clock`, `capabilities`, `sampling`, `loss`, `results`,
`deadline_result`. Clock/capabilities/sampling/loss are copied unchanged; stream order equals input. Results contain
all four methods in table order, even when unsupported for this producer.

Each result has exactly `method_id`, `method_version`, `state`, `reason`,
`eligible_frames`, `usable_frames`, `excluded_frames`, `exclusions`,
`samples`, `min_ms`, `mean_ms`, `max_ms`. Samples are ordered by source sequence,
each `{ "frame_id": ID, "delta_ns": DELTA, "value_ms": VALUE }`; count equals
usable_frames. DELTA is the nonnegative safe integer endpoint difference; VALUE
must equal DELTA / 1e6. Sample frame IDs are unique within each result.
Eligible frames equal the stream ledger size. Excluded = eligible - usable.
`exclusions` has counters `unsupported`, `correlation_missing`,
`correlation_ambiguous`, `missing_endpoint`, `negative_duration`, applied in that
priority order, exactly one per excluded frame. Missing/disabled capability
counts as unsupported. Their sum equals excluded_frames.

State is `measured` iff usable_frames > 0, else `unavailable`. Measured reason
is null; unavailable reason is `unsupported_source`, `capability_unavailable`,
`no_frames`, or `no_usable_pairs`, in that precedence. Empty samples have all
three statistics null. Otherwise min/max are extrema and mean is arithmetic
sample mean (integer delta sum / (count * 1000000)); zeros are valid measured values.
Coverage is usable/eligible when eligible > 0, derivable from counts; it is not
an estimate for unsampled or lost frames. No percentile or confidence interval
is approved. Intermediate sums use exact integer arithmetic (including BigInt
where necessary), followed by one floating division. Summary statistics must
equal recomputation from deltas, not loosely agree within an arbitrary tolerance.
Overflow or nonfinite/unrepresentable arithmetic fails closed.

`deadline_result` has exactly `state`, `reason`, `method_id`, `method_version`,
`budget_ns`, `samples`, `usable_frames`, `hit_frames`, `hit_fraction`.
Method literal `capture-output-budget`, version 1. With null input budget it is
unavailable / `budget_not_declared`, null budget, empty samples, counts zero,
null fraction. Otherwise reuse only usable capture-output-age pairs; no pairs
means unavailable / `no_usable_pairs`. Each sample is `{ "frame_id": ID,
"slack_ms": (B-delta_ns)/1e6, "hit": delta_ns <= B }`. Negative slack is valid;
boundary equality is a hit. Measured reason null; hit count and fraction use
usable pairs only. This is a declared software budget referenced to capture
output, not an end-to-end deadline guarantee or a scheduling decision.

Summary validation must check internal arithmetic and counts; when produced
from a trace it is recomputed, not trusted from a supplied summary. Summary
alone proves no input identity; inspection requires the corresponding trace.

## Bounded I/O, privacy and proposed commands

Limits: 10 MiB per JSON, nesting depth 32, 16 streams, 2000 frames and 10000
events per stream AND per trace; positive counters/times at most 2^53-1. Alias
suffixes at most 2^31-1. Total input archive/readable bundle at most 32 MiB,
exactly two regular files; directories, links, devices, duplicate members,
unknown members, absolute/traversal names and compressed/declared oversize fail.
Collection limits may be lower than hard limits, never higher. These are
provisional software resource limits, not validated full-limit throughput.

No arbitrary metadata maps or diagnostic strings. No pixels/audio, SDP, ICE,
network addresses, credentials, URLs, paths, titles, hardware IDs or raw PTS.
Only listed fields/enums, local aliases, a producer commit and finite bounded
numbers are permitted. Byte/depth caps apply before model validation; frame/event
caps apply before allocating unbounded intermediate collections.

Canonical JSON: UTF-8, sorted keys, two-space indentation, non-ASCII unescaped,
finite numbers only, one trailing LF. Arrays preserve contractual order. Integer
fields serialize as integers; derived ms/fraction fields as floats, normalize
negative zero to positive zero. Python canonical rendering is the hash authority;
producers emit this representation (including float spelling where relevant).
Record contains only integer numeric fields, simplifying cross-language hashing.

Standalone producer bundle is **not research bundle v2**: `trace-manifest.json`
plus `trace-record.json`, optional uncompressed directory or gzip TAR container.
Manifest exactly `{ "schema_version": 1, "bundle_type": "pixelated_stage_trace",
"trace_schema_version": "stage-trace-record-v1", "trace_sha256": HEX,
"trace_bytes": INTEGER }`; HEX is lowercase 64-character SHA-256 of the canonical
record bytes; bytes equal actual length. Reject noncanonical record serialization,
hash/length mismatch or unsupported version before returning any output.
Summary is generated offline, not an accepted third input bundle member.

[Step 5 delivers](N4_TRACE_ADOPTION.md) `ingest-trace --bundle PATH --output PATH` (validated canonical
record) and [Step 6 delivers](N4_TIMING_RECONSTRUCTION.md) `inspect-trace --trace PATH --output PATH` (canonical summary).
Both commands are implemented, are offline and use duplicate-safe/no-follow
regular-file reads and atomic output after complete validation. Existing CLI and
legacy ingestion do not discover or reinterpret these artifacts. Generic schema
export/validation now includes the two roots delivered in Step 2.
