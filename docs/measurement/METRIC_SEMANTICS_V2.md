# N1 metric semantics and naming inventory

**Status:** Step 1 inventory frozen; registry implementation is pending.
**Reviewed:** 2026-10-06
**Planned registry version:** `latency-metrics-v2.0.0`
**Definition semantic version:** `1.0.0` for each initial definition.

This is the authoritative naming map for the N1 shadow measurement path.
It covers all 23 P0 adapter features and specifies 31 proposed registry outputs.
The P0 adapter, normalization configuration, schemas, fixtures and matcher remain
unchanged. Proposed outputs are not production matcher inputs.

## Shared rules

- Every listed measurement accepts a finite zero. Negative raw values are
  rejected for this inventory. Blank/unavailable/rejected input never becomes zero.
- Gauge definitions expose `median`, `nearest_rank_p95`, `minimum`, and `maximum`;
  the primary value is the sample median. These are statistics of exported values,
  including producer-computed interval means/rates, not per-frame percentiles.
- Counter rate definitions expose only `time_weighted_rate`; total definitions
  expose only `window_total`. Both read the same cumulative raw field. The kind
  describes the raw input (`cumulative_counter`), while canonical units describe
  the derived output. Interval deltas are retained as derivation evidence, not
  registered analytical features. P95 of interval rates is deferred because it
  depends on how intervals are split.
- Rates use seconds, except freeze event frequency, which uses minutes.
  `frames/s` is FPS; `kbps` means decimal kilobits/s; `MiB` means binary mebibytes.
  Freeze duration rate is milliseconds of accumulated freeze per observed second,
  not a bounded percentage. No clipping or implied maximum is introduced.
- Rates are sum(delta) / sum(accepted elapsed seconds), multiplied by 60 for
  freezes/min. Totals are sum(delta) across accepted contiguous intervals.
  Rates are proposed analytical outputs; totals are audit-only in N1. Neither is
  adopted by the matcher. Never extrapolate totals to unobserved time.
- Gauges use `omit_missing_samples`; rejected values remain explicit evidence.
  Counters use `break_counter_continuity` at every missing, unavailable or rejected
  row, and `reject_segment` on reset: discard the negative transition and establish
  the current usable sample as a new baseline. No declared width or wraparound.
- For every definition `expectedCadenceMs` and `cadenceToleranceRatio` are null.
  Cadence is measured and reported, not assumed from a global fixed poll interval.
  Future source-declared cadence is advisory provenance, not a denominator override.
- `clockBasis = source_elapsed_ms`: use strictly increasing exported `elapsed_ms`
  for interval math, convert milliseconds to seconds explicitly, and retain UTC
  `captured_at` for audit/alignment only. Never substitute UTC differences for missing
  elapsed samples. Duplicate/decreasing elapsed times reject the affected series.
- Legacy producer clock provenance must remain visible: browser elapsed is
  `Date.now() - recordingStartedAt`; engine CSV elapsed is derived from the engine
  `capturedAt` and recording start. These exports are wall-clock-derived elapsed,
  not verified monotonic clocks. Their numerical shadow rates must carry that
  limitation; they cannot substantiate a monotonic-clock rate claim. A true
  monotonic capture clock requires a later instrumentation slice. The registry
  clock basis does not erase this source limitation.
- No new normalization epsilon or clipping is assigned in N1. `P0-preserved` means
  the old P0 configuration remains in use for v1 only. `v2-deferred` means the new
  output must not inherit a delta feature's normalization floor or matcher weight.

## P0 mapping

One row per current P0 feature. Counter rows list their two distinct outputs;
each output has exactly one declaration in the output inventory below.
`source_elapsed_ms`, gap policies and reset policies refer to the shared rules.

| P0 feature | raw source file/source kind | raw field(s) | current P0 meaning | problem or ambiguity | proposed v2 feature | physical quantity | canonical unit | metric kind | primary aggregation | clock basis | gap policy | reset policy | normalization status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| client.available_incoming_bitrate_kbps | stream-telemetry.csv/browser_webrtc | available_incoming_bitrate_kbps | Median exported gauge samples | Exported sample statistic; not per-frame or time-weighted | client.available_incoming_bitrate_kbps | Selected candidate-pair incoming bandwidth estimate | kbps | gauge | median | source_elapsed_ms | omit_missing_samples | none | P0-preserved; v2-deferred |
| client.decode_time_mean_ms | stream-telemetry.csv/browser_webrtc | decode_time_mean_ms | Median exported gauge samples | Exported sample statistic; not per-frame or time-weighted | client.decode_time_mean_ms | Producer interval decode-time delta divided by decoded-frame delta across supported video streams | ms | gauge | median | source_elapsed_ms | omit_missing_samples | none | P0-preserved; v2-deferred |
| client.frames_decoded_delta | stream-telemetry.csv/browser_webrtc | frames_decoded | Median consecutive usable counter deltas | Cadence-dependent delta; aggregate lacks interval durations | client.frames_decoded_rate_fps, client.frames_decoded_window_total | Supported video-inbound decoded-frame count | frames/s, frames | cumulative_counter | time_weighted_rate, window_total | source_elapsed_ms | break_counter_continuity | reject_segment | v2-deferred |
| client.frames_dropped_delta | stream-telemetry.csv/browser_webrtc | frames_dropped | Median consecutive usable counter deltas | Cadence-dependent delta; aggregate lacks interval durations | client.frames_dropped_rate_fps, client.frames_dropped_window_total | Supported video-inbound dropped-frame count | frames/s, frames | cumulative_counter | time_weighted_rate, window_total | source_elapsed_ms | break_counter_continuity | reject_segment | v2-deferred |
| client.freeze_count_delta | stream-telemetry.csv/browser_webrtc | freeze_count | Median consecutive usable counter deltas | Cadence-dependent delta; aggregate lacks interval durations | client.freeze_count_rate_per_min, client.freeze_count_window_total | Supported video-inbound freeze event count | freezes/min, freezes | cumulative_counter | time_weighted_rate, window_total | source_elapsed_ms | break_counter_continuity | reject_segment | v2-deferred |
| client.freeze_duration_ms_delta | stream-telemetry.csv/browser_webrtc | freeze_duration_total_ms | Median consecutive usable counter deltas | Cadence-dependent delta; aggregate lacks interval durations | client.freeze_duration_rate_ms_per_s, client.freeze_duration_window_total_ms | Supported video-inbound accumulated freeze duration | ms/s, ms | cumulative_counter | time_weighted_rate, window_total | source_elapsed_ms | break_counter_continuity | reject_segment | v2-deferred |
| client.jitter_buffer_delay_mean_ms | stream-telemetry.csv/browser_webrtc | jitter_buffer_delay_mean_ms | Median exported gauge samples | Exported sample statistic; not per-frame or time-weighted | client.jitter_buffer_delay_mean_ms | Producer interval buffer-delay delta divided by emitted-count delta across supported video streams | ms | gauge | median | source_elapsed_ms | omit_missing_samples | none | P0-preserved; v2-deferred |
| client.received_bitrate_kbps | stream-telemetry.csv/browser_webrtc | bitrate_kbps | Median exported gauge samples | Exported sample statistic; not per-frame or time-weighted | client.received_bitrate_kbps | Sum of supported inbound byte-counter rates already derived by the producer | kbps | gauge | median | source_elapsed_ms | omit_missing_samples | none | P0-preserved; v2-deferred |
| client.received_fps | stream-telemetry.csv/browser_webrtc | fps | Median exported gauge samples | Exported sample statistic; not per-frame or time-weighted | client.received_fps | Maximum reported video-inbound framesPerSecond across supported streams | fps | gauge | median | source_elapsed_ms | omit_missing_samples | none | P0-preserved; v2-deferred |
| encoder.frames_dropped_delta | engine-telemetry.csv/encoder_pipeline | frames_dropped_total | Median consecutive usable counter deltas | Cadence-dependent delta; aggregate lacks interval durations | encoder.frames_dropped_rate_fps, encoder.frames_dropped_window_total | Encoder drop count summed across active peers | frames/s, frames | cumulative_counter | time_weighted_rate, window_total | source_elapsed_ms | break_counter_continuity | reject_segment | v2-deferred |
| encoder.frames_in_delta | engine-telemetry.csv/encoder_pipeline | frames_in_total | Median consecutive usable counter deltas | Cadence-dependent delta; aggregate lacks interval durations | encoder.frames_in_rate_fps, encoder.frames_in_window_total | Encoder input count summed across active peers | frames/s, frames | cumulative_counter | time_weighted_rate, window_total | source_elapsed_ms | break_counter_continuity | reject_segment | v2-deferred |
| encoder.frames_out_delta | engine-telemetry.csv/encoder_pipeline | frames_out_total | Median consecutive usable counter deltas | Cadence-dependent delta; aggregate lacks interval durations | encoder.frames_out_rate_fps, encoder.frames_out_window_total | Encoder output count summed across active peers | frames/s, frames | cumulative_counter | time_weighted_rate, window_total | source_elapsed_ms | break_counter_continuity | reject_segment | v2-deferred |
| encoder.pipeline_delay_proxy_ms | engine-telemetry.csv/encoder_pipeline | pipeline_delay_proxy_ms | Median exported gauge samples | Current producer exports null; synthetic fixture is not real duration evidence | encoder.pipeline_delay_proxy_ms | Exported pipeline delay proxy; not a direct encoder processing duration | ms | gauge | median | source_elapsed_ms | omit_missing_samples | none | P0-preserved; v2-deferred |
| encoder.queue_level_buffers | engine-telemetry.csv/encoder_pipeline | queue_level_buffers | Median exported gauge samples | Exported sample statistic; not per-frame or time-weighted | encoder.queue_level_buffers | Maximum observed pre/post encoder queue occupancy across active peers | buffers | gauge | median | source_elapsed_ms | omit_missing_samples | none | P0-preserved; v2-deferred |
| host.camera_cpu_percent | engine-telemetry.csv/engine_runtime | camera_cpu_percent | Median exported gauge samples | Exported sample statistic; not per-frame or time-weighted | host.camera_cpu_percent | camera bridge process CPU time per elapsed interval; 100 percent is one core | percent | gauge | median | source_elapsed_ms | omit_missing_samples | none | P0-preserved; v2-deferred |
| host.camera_rss_mb | engine-telemetry.csv/engine_runtime | camera_rss_mb | Median exported gauge samples | mb suffix actually means MiB | host.camera_rss_mib | camera bridge resident memory in binary mebibytes | MiB | gauge | median | source_elapsed_ms | omit_missing_samples | none | P0-preserved; v2-deferred |
| host.game_cpu_percent | engine-telemetry.csv/engine_runtime | emulator_cpu_percent | Median exported gauge samples | Exported sample statistic; not per-frame or time-weighted | host.game_cpu_percent | emulator process CPU time per elapsed interval; 100 percent is one core | percent | gauge | median | source_elapsed_ms | omit_missing_samples | none | P0-preserved; v2-deferred |
| host.game_rss_mb | engine-telemetry.csv/engine_runtime | emulator_rss_mb | Median exported gauge samples | mb suffix actually means MiB | host.game_rss_mib | emulator resident memory in binary mebibytes | MiB | gauge | median | source_elapsed_ms | omit_missing_samples | none | P0-preserved; v2-deferred |
| host.node_cpu_percent | engine-telemetry.csv/engine_runtime | node_cpu_percent | Median exported gauge samples | Exported sample statistic; not per-frame or time-weighted | host.node_cpu_percent | Node runtime process CPU time per elapsed interval; 100 percent is one core | percent | gauge | median | source_elapsed_ms | omit_missing_samples | none | P0-preserved; v2-deferred |
| host.node_rss_mb | engine-telemetry.csv/engine_runtime | node_rss_mb | Median exported gauge samples | mb suffix actually means MiB | host.node_rss_mib | Node runtime resident memory in binary mebibytes | MiB | gauge | median | source_elapsed_ms | omit_missing_samples | none | P0-preserved; v2-deferred |
| transport.jitter_ms | stream-telemetry.csv/browser_webrtc | jitter_ms | Median exported gauge samples | Exported sample statistic; not per-frame or time-weighted | transport.jitter_ms | Maximum supported inbound RTP jitter across audio and video streams | ms | gauge | median | source_elapsed_ms | omit_missing_samples | none | P0-preserved; v2-deferred |
| transport.packets_lost_delta | stream-telemetry.csv/browser_webrtc | packets_lost_total | Median exported interval deltas including first-row zero | Cadence-dependent delta; aggregate lacks interval durations | transport.packets_lost_rate_per_s, transport.packets_lost_window_total | Producer rounded non-negative packet-loss count summed across inbound streams | packets/s, packets | cumulative_counter | time_weighted_rate, window_total | source_elapsed_ms | break_counter_continuity | reject_segment | v2-deferred |
| transport.round_trip_time_ms | stream-telemetry.csv/browser_webrtc | round_trip_time_ms | Median exported gauge samples | Exported sample statistic; not per-frame or time-weighted | transport.round_trip_time_ms | Selected candidate-pair current RTT | ms | gauge | median | source_elapsed_ms | omit_missing_samples | none | P0-preserved; v2-deferred |

## Proposed output inventory

Each row declares one initial semantic version `1.0.0`. Gauge available
aggregations and counter derivations are fixed by the shared rules above.

| proposed v2 feature | P0 feature | source | raw field | metric kind | canonical unit | primary aggregation | role |
| --- | --- | --- | --- | --- | --- | --- | --- |
| client.available_incoming_bitrate_kbps | client.available_incoming_bitrate_kbps | browser_webrtc | available_incoming_bitrate_kbps | gauge | kbps | median | analytical-shadow |
| client.decode_time_mean_ms | client.decode_time_mean_ms | browser_webrtc | decode_time_mean_ms | gauge | ms | median | analytical-shadow |
| client.frames_decoded_rate_fps | client.frames_decoded_delta | browser_webrtc | frames_decoded | cumulative_counter | frames/s | time_weighted_rate | analytical-shadow |
| client.frames_decoded_window_total | client.frames_decoded_delta | browser_webrtc | frames_decoded | cumulative_counter | frames | window_total | audit-only |
| client.frames_dropped_rate_fps | client.frames_dropped_delta | browser_webrtc | frames_dropped | cumulative_counter | frames/s | time_weighted_rate | analytical-shadow |
| client.frames_dropped_window_total | client.frames_dropped_delta | browser_webrtc | frames_dropped | cumulative_counter | frames | window_total | audit-only |
| client.freeze_count_rate_per_min | client.freeze_count_delta | browser_webrtc | freeze_count | cumulative_counter | freezes/min | time_weighted_rate | analytical-shadow |
| client.freeze_count_window_total | client.freeze_count_delta | browser_webrtc | freeze_count | cumulative_counter | freezes | window_total | audit-only |
| client.freeze_duration_rate_ms_per_s | client.freeze_duration_ms_delta | browser_webrtc | freeze_duration_total_ms | cumulative_counter | ms/s | time_weighted_rate | analytical-shadow |
| client.freeze_duration_window_total_ms | client.freeze_duration_ms_delta | browser_webrtc | freeze_duration_total_ms | cumulative_counter | ms | window_total | audit-only |
| client.jitter_buffer_delay_mean_ms | client.jitter_buffer_delay_mean_ms | browser_webrtc | jitter_buffer_delay_mean_ms | gauge | ms | median | analytical-shadow |
| client.received_bitrate_kbps | client.received_bitrate_kbps | browser_webrtc | bitrate_kbps | gauge | kbps | median | analytical-shadow |
| client.received_fps | client.received_fps | browser_webrtc | fps | gauge | fps | median | analytical-shadow |
| encoder.frames_dropped_rate_fps | encoder.frames_dropped_delta | encoder_pipeline | frames_dropped_total | cumulative_counter | frames/s | time_weighted_rate | analytical-shadow |
| encoder.frames_dropped_window_total | encoder.frames_dropped_delta | encoder_pipeline | frames_dropped_total | cumulative_counter | frames | window_total | audit-only |
| encoder.frames_in_rate_fps | encoder.frames_in_delta | encoder_pipeline | frames_in_total | cumulative_counter | frames/s | time_weighted_rate | analytical-shadow |
| encoder.frames_in_window_total | encoder.frames_in_delta | encoder_pipeline | frames_in_total | cumulative_counter | frames | window_total | audit-only |
| encoder.frames_out_rate_fps | encoder.frames_out_delta | encoder_pipeline | frames_out_total | cumulative_counter | frames/s | time_weighted_rate | analytical-shadow |
| encoder.frames_out_window_total | encoder.frames_out_delta | encoder_pipeline | frames_out_total | cumulative_counter | frames | window_total | audit-only |
| encoder.pipeline_delay_proxy_ms | encoder.pipeline_delay_proxy_ms | encoder_pipeline | pipeline_delay_proxy_ms | gauge | ms | median | analytical-shadow |
| encoder.queue_level_buffers | encoder.queue_level_buffers | encoder_pipeline | queue_level_buffers | gauge | buffers | median | analytical-shadow |
| host.camera_cpu_percent | host.camera_cpu_percent | engine_runtime | camera_cpu_percent | gauge | percent | median | analytical-shadow |
| host.camera_rss_mib | host.camera_rss_mb | engine_runtime | camera_rss_mb | gauge | MiB | median | analytical-shadow |
| host.game_cpu_percent | host.game_cpu_percent | engine_runtime | emulator_cpu_percent | gauge | percent | median | analytical-shadow |
| host.game_rss_mib | host.game_rss_mb | engine_runtime | emulator_rss_mb | gauge | MiB | median | analytical-shadow |
| host.node_cpu_percent | host.node_cpu_percent | engine_runtime | node_cpu_percent | gauge | percent | median | analytical-shadow |
| host.node_rss_mib | host.node_rss_mb | engine_runtime | node_rss_mb | gauge | MiB | median | analytical-shadow |
| transport.jitter_ms | transport.jitter_ms | browser_webrtc | jitter_ms | gauge | ms | median | analytical-shadow |
| transport.packets_lost_rate_per_s | transport.packets_lost_delta | browser_webrtc | packets_lost_total | cumulative_counter | packets/s | time_weighted_rate | analytical-shadow |
| transport.packets_lost_window_total | transport.packets_lost_delta | browser_webrtc | packets_lost_total | cumulative_counter | packets | window_total | audit-only |
| transport.round_trip_time_ms | transport.round_trip_time_ms | browser_webrtc | round_trip_time_ms | gauge | ms | median | analytical-shadow |

## Migration decisions

All 15 gauge mappings are `identity_safe` in physical units and sample-median
meaning when the same usable raw samples and availability policy apply. The three
RSS names change to `_rss_mib` to make the unit explicit; no numerical conversion
is performed. A P0 aggregate cannot reconstruct the original raw gauge series,
row rejections, cadence, or coverage. New row rejection handling may retain valid
samples where P0 rejected the whole feature, so identity-safe is not a promise of
identical values on malformed input.

All eight P0 delta features are `recomputable_from_raw` when suitable raw counters
and elapsed samples exist, and `not_recoverable_from_aggregate` when only frozen P0
records remain. No median interval delta is renamed or numerically reinterpreted
as a rate or total. Unsupported sources and rejected series stay explicit in the
future inspection report. The first packet-loss delta is producer-inserted zero;
N1 derives from `packets_lost_total` and requires two usable samples for an interval.

The supported gauge source values already carry producer assumptions: received
bitrate sums inbound byte rates; received FPS takes the maximum video report;
decode/buffer means are producer interval ratios; jitter takes the maximum inbound
report. N1 preserves these meanings. Exported CSV lacks the per-report byte/time
and buffer-delay counters needed to replace these with pooled window calculations.

Browser frame/freeze counters sum supported video reports; packet loss is rounded
and clamped upstream, with missing per-report counters contributing zero. Encoder
counters sum active peers and may fall when peer membership changes. Membership
and counter identity are not fully reconstructable from sanitized totals; declines
are resets, not inferred wraparound or recovered activity. Counter increases across
an invisible membership change cannot be diagnosed from these CSV fields alone.

Queue occupancy is the producer maximum across existing pre/post encoder queues;
the current producer falls back to zero when no queue is present or a property read
fails. N1 cannot retroactively distinguish that fallback from a measured empty queue.
An explicit unavailable row with a stale numeric cell is ignored as unavailable.
The pipeline-delay proxy stays registered for P0 completeness but the current camera
producer emits null; it must remain missing on real captures with no value.
Host CPU percentages are not divided by logical cores or capped at 100.

## Context-only fields

These settings and provenance fields are excluded from the 31 observed outputs.

| raw field | semantic role |
| --- | --- |
| target_fps | Configured output FPS target, not observed frames/s |
| target_bitrate_kbps | Configured bitrate target, not received throughput |
| cpu_used | Encoder configuration knob, not measured CPU utilization |
| max_quantizer | Encoder quantizer limit, not observed quality |
| logical_cpu_count | Host capacity context |
| cpu_capacity_cores | Available/quota CPU capacity context |
| runtime_kind | Runtime compatibility context |
| node_running | Process lifecycle/availability context |
| emulator_running | Process lifecycle/availability context |
| camera_running | Process lifecycle/availability context |
| peer_count | Peer population context; not a fingerprint outcome in N1 |

`key_frames_decoded` is a raw observed counter outside the current P0 inventory;
N1 does not add an unrequested feature for it. `sample_sequence` and
`sample_interval_ms`, where newer exporters provide them, are optional provenance
and not required by the existing sanitized fixture schema. Identity, playback,
connection, error and manifest support states govern validation/availability;
they are not analytical metrics. `stream-events.csv` remains event/probe evidence;
no event-count metric is introduced in this slice.

## Audit sources and implementation boundary

The mappings are checked against
[`pixelated_bundle_metrics.py`](../../src/latency_fingerprinting/adapters/pixelated_bundle_metrics.py),
[`p0_feature_config.py`](../../src/latency_fingerprinting/measurement/p0_feature_config.py),
and the headers in
[`valid-v2`](../../tests/data/pixelated_bundle/valid-v2/stream-telemetry.csv).
P0 packet baseline/reset validation is in
[`pixelated_bundle_validation.py`](../../src/latency_fingerprinting/adapters/pixelated_bundle_validation.py).

Producer audit used Pixelated Studio Edition checkout
`37e50fb7ef919564aba5796af35dbcdc1fc70f3b`, reading
`apps/web/src/lib/webrtc/telemetry/webrtcStatsParser.ts`,
`apps/web/src/features/player/telemetry/streamTelemetryExport.ts`,
`apps/web/src/features/player/telemetry/engineResearchTelemetry.ts`,
`engine/runtime/src/telemetry/intervalResourceSampler.ts`, and
`engine/runtime/camera_state.py`. This records inspected current code, not a claim
that every older captured bundle used that exact producer revision.

[`test_metric_inventory.py`](../../tests/measurement/test_metric_inventory.py)
checks adapter/config completeness, unique output declarations, raw-field coverage,
units, counter source selection, and context exclusion. It reads these tables directly
so documentation drift fails without adding a second runtime registry prematurely.
Step 2 will turn this inventory into strict registry models; Step 3 will compare the
canonical registry's names and definitions to these declarations.

Baseline and milestone verification are recorded in
[`N1_IMPLEMENTATION_PROGRESS.md`](N1_IMPLEMENTATION_PROGRESS.md).
