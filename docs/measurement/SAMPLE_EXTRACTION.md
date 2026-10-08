# N1 timestamped sample extraction guide

[`adapters/pixelated_measurement_samples.py`](../../src/latency_fingerprinting/adapters/pixelated_measurement_samples.py)
provides `load_pixelated_measurement_samples(bundle_path, *, phase,
comparison_case_id, context, include_adoption_metadata=False)`. It reads one directory/TAR bundle and returns
`PixelatedMeasurementSamples` containing one `MetricSampleSeries` for every
canonical output. The API is exported from the adapters package. This extraction
boundary computes no metric rate, total, delta, percentile, normalization or
matcher feature. The optional N2 flag retains a typed immutable metadata snapshot
from the same validated read; default callers receive `adoption=None` and unchanged
sample/report behavior. See [N2 adoption](OBSERVATION_V2_ADOPTION.md).

## Safe input and clock validation

The loader reuses `pixelated_bundle_io.read_bundle`, `json_object` and `csv_rows`,
retaining TAR/member/file/row limits, duplicate-key and duplicate-column checks,
UTF-8/nesting checks and rejection of links. It reuses existing metadata,
manifest/privacy, cross-file identity, engine-source, settings, window-alignment,
summary-count and declared-source-support validators. No second archive reader
is introduced; P0 ingestion/aggregation is not invoked.

The shared reader pins every ancestor and the bundle root through no-follow
descriptors. Directory members are opened relative to that root with nonblocking
no-follow flags and must be regular files. TAR inputs are likewise pinned regular
files; compressed input bytes are bounded before decoding, including file growth
after the size check. Ancestor links and replacement links/FIFOs fail closed.
The [post-N3 health audit](../analysis/N3_ARCHITECTURE_AUDIT.md) records these repairs
and preservation checks across P0/N1/N2.

Context must explicitly declare bundle schema version and workload identity.
Mixed session/source identities reject input. Every source is separately checked
for non-negative and strictly increasing `elapsed_ms`, increasing UTC
`captured_at`, and elapsed/wall-clock alignment. Invalid clocks fail closed for
the bundle, with the source filename and original row in the error; they cannot
safely locate missing/rejected metric values within a window. Engine/encoder poll
identities and browser-window alignment retain their existing checks.

The first/last browser timestamps and elapsed values define the positive-duration
capture window. The result's checksum identifies bundle bytes independently of
directory/TAR packaging. No private run/session identity, hostname or absolute
path is retained in the result object.

N1 selects `packets_lost_total` instead of the legacy packet interval-delta field.
It does not run P0's delta consistency validator or compute deltas. Counter
decreases remain raw values; the registered reset policy is applied in Step 6.
P0 continues using its original validator and aggregation path.

## Sample states

`MeasurementSample` in
[`models/measurement.py`](../../src/latency_fingerprinting/models/measurement.py)
is a strict frozen model with `elapsedMs`, `capturedAt`, `value`, `available`,
`sourceRow`, `missingReason` and `rejectionReason`. UTC capture time and separate
missing/rejection reasons extend the planned internal sample shape to preserve
audit provenance and distinguish unusable states.

- Usable samples have a finite value, are available and have no reasons.
  Legitimate zero and finite extreme values remain raw evidence.
- Browser blanks/absent optional fields are missing. Inactive playback,
  disconnected/failed connection states or an engine error make the row
  unavailable, discarding stale numeric cells.
- Engine unavailable rows are missing; stale cells are discarded. Contradictory
  availability/error envelopes reject input through the existing validator.
- Manifest `measurementSupport` declarations match source plus the raw field's
  camelCase producer name. Unsupported/unavailable metrics stay missing even if
  a stale cell exists. This keeps the current pipeline-delay proxy missing.
- Available engine rows lacking required numeric cells are rejected. Malformed,
  non-finite, overflow-range and definition-forbidden negative values are rejected
  with source filename, original row and raw field. No unusable state becomes zero.
  Rejection messages do not echo malformed cell contents.
- Every source row remains in its sample tuple. `sourceRow` is the CSV record
  ordinal used by the existing parser, with the header counted as row 1; it is
  not a physical line offset for multiline CSV cells.

V1 absent engine sources and the allowed header-only optional engine source in
v2 return empty tuples with explicit series missing reasons. Other missing/rejected
values keep elapsed/UTC time and row identity, exposing continuity breaks for the
[counter engine](COUNTER_AGGREGATION.md). Extraction does not bridge gaps or
choose reset behavior.

Clock provenance is `wall_clock_derived_elapsed`, with an explicit warning that
monotonic capture is unverified. Increasing exported elapsed values do not prove
a monotonic producer clock.

## Immutability and reuse

The bundle is read once and each CSV is parsed once. Source row references and
clock metadata are reused. Samples are parsed once per
`(source, rawFields, nonNegative)`; each rate/total pair shares an immutable tuple.
Series records are frozen dataclasses and the name-to-series mapping is read-only.
The result contains no raw payload bytes or row dictionaries.

[`test_measurement_samples.py`](../../tests/pixelated/test_measurement_samples.py)
checks all source categories, directory/TAR equality, original rows, malformed and
missing values, stale cells, reset values retained without derivation, one-read
reuse, clocks/identities, input immutability and inherited security/resource bounds.
Sample-state tests are in
[`tests/models/test_measurement_samples.py`](../../tests/models/test_measurement_samples.py).
[`Gauge aggregation`](GAUGE_AGGREGATION.md) is implemented in Step 5; counter
derivation is implemented in [Step 6](COUNTER_AGGREGATION.md); the deterministic
[shadow report/CLI](MEASUREMENT_INSPECTION.md) is implemented in Step 7.
