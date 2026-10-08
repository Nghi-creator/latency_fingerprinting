# N2 offline raw-bundle adoption

[`ingest_pixelated_v2`](../../src/latency_fingerprinting/adapters/pixelated_observation_v2.py)
adopts one bounded directory/TAR bundle into a strict `ObservationWindowV2`.
It uses the frozen registry and pure N1 aggregation. It does not call P0 aggregation,
convert a frozen P0 window, normalize features, build a response or invoke matching.

```bash
latency-fingerprint ingest-pixelated-v2 path/to/bundle.tar \
  --context path/to/context.json --phase degraded \
  --comparison-case-id example-001 > window-v2.json
latency-fingerprint validate window-v2.json
```

The command writes complete canonical JSON to stdout only after validation.
Input bundles/context are read-only; output redirection is an explicit caller
choice. Default provenance is `controlled_real`; `organic_real` is also accepted.
Pixelated adoption rejects synthetic provenance. Optional repeated
`--confounder-code` values use the closed v2 vocabulary, never producer free text.
Phases retain baseline/degraded/relief/recovery meanings; manifest phase/case
agreement and explicit context version/workload checks remain required.

## One validated read

N1's raw loader adds the optional `include_adoption_metadata=True` flag. The
default remains false. A frozen [metadata snapshot](../../src/latency_fingerprinting/adapters/pixelated_adoption_metadata.py)
retains only run ID, bundle version, reviewed settings, source support/counts,
per-definition declarations, optional producer version and typed invalidity codes.
It is built from the same validated files/rows as samples and checksum, without
another archive read or raw payload dictionaries. Settings contain only validated
flat stream/engine scalars. Context is copied before I/O; later caller mutation
cannot change the adopted record.

Shared bundle reads now pin ancestors, root and members through no-follow file
descriptors, reject nonregular files without blocking, and bound TAR bytes before
decoding even if the file grows. See [safe extraction](SAMPLE_EXTRACTION.md) and
the [post-N3 health audit](../archive/analysis/N3_ARCHITECTURE_AUDIT.md). Valid adopted bytes
and source hashes remain unchanged.

Producer version is taken only from an explicitly supplied, non-empty string
`bundle-manifest.json.producerVersion`, otherwise null. This optional declaration
is not inferred from a current checkout/date and is not an instrumentation audit.
Malformed declarations fail in N2's opt-in path; legacy N1 behavior is preserved.
V1 legacy notes/private fields are not copied into the snapshot; v2 retains its
existing envelope privacy validators. Research identifier values remain the
caller's responsibility to sanitize, as specified by the [field contract](OBSERVATION_V2_CONTRACT.md).

Source capability and currently available row counts are distinct. Source/metric
declarations control typed support, with unsupported then unavailable precedence.
Unsupported/unavailable sources or quantities discard stale numeric evidence by
creating missing samples at the same original row/time. Rate/total pairs share the
masked tuple and publish equal accepted interval evidence. N1 raw samples/reports
retain their existing behavior; source suppression is applied in N2 adoption.

Each registered summary uses elapsed bounds and N1 gap/reset policies. Diagnostics
are reduced to the fixed v2 vocabulary, preserving status, counts, usable rows,
intervals and missing/rejected/warning presence. A numeric zero stays zero; absent
or rejected measurements have no fabricated value. All 31 outputs are required,
including explicit missing engine/encoder summaries for v1/browser-only bundles.

## Identity and validity

The source hash is N1's checksum of readable bundle contents, independent of
directory/TAR packaging. Window ID is `pixelated-v2-<checksum hex>-<phase>` and
clock-domain ID is `pixelated-<checksum hex>`. UTC bounds come from the source;
no random ID or ambient timestamp is added. The capture method is explicitly
`pixelated_bundle_offline / 1.0.0`, with wall-clock-derived elapsed provenance.
Increasing elapsed values are not verified monotonic capture or synchronization.

Producer invalidity maps to `producer_invalid`; required missing sources and
partial availability use the v2 source reason codes. Browser support is required;
engine/encoder support is required for v2 except declared browser-only baselines.
V1 absent engine sources remain optional. Invalid windows can be retained for
audit; their pair construction remains prohibited. Numeric metric rejection alone
does not invent a whole-window invalidity rule beyond the reviewed contract.

## Explicit unavailable stage timings

The [pure timing helper](../../src/latency_fingerprinting/measurement/stage_timing.py)
now emits capture, encode, decode and render records in that order. Capture is
associated with engine runtime, encode with encoder pipeline, and decode/render
with browser WebRTC. These associations identify potential evidence sources;
they do not establish instrumentation or clock synchronization.

| Typed source state | Timing state | Reason |
| --- | --- | --- |
| supported | unavailable | not_instrumented |
| unsupported | unavailable | unsupported_source |
| unavailable | unavailable | source_unavailable |

Each record has unit `ms`, zero samples and null value, statistic, method ID/version
and clock domain. Source capability, stale numeric values, metric declarations and
window clock metadata cannot supply direct stage durations. Existing decode/buffer
interval means remain gauges; pipeline-delay proxies and P0 median deltas are never
relabeled as direct timing evidence. No measured/estimated method is approved.

The root model still permits empty or partial unavailable tuples for other callers;
the four-record population guarantee belongs to this Pixelated adopter.

## Verification and next gate

[35 adoption cases](../../tests/pixelated/test_observation_v2_adoption.py) cover
directory/TAR/repeated-output equality, unchanged input bytes, one read, caller
context isolation, immutable opt-in metadata, declarations over stale values,
zero/reset/gap arithmetic, partial/absent sources, producer versions, fixed
diagnostics, CLI validation and repeatable bounded failure handling.

Local Step 3 result: **1,127 tests pass; 92.91% branch-inclusive coverage** on
Python 3.13.13. Existing P0 match bytes, N1 registry/report pins, all schema/fixture
checks and controlled artifacts pass. No bound, frozen artifact or arithmetic
policy is changed. Python 3.11/hosted verification remains pending. Adopted-record
fixtures and broader N2 reproduction gates were subsequently completed in Step 5
([fixture guide](OBSERVATION_V2_FIXTURES.md)).

Local Step 4 result: **1,140 tests pass; 92.93% branch-inclusive coverage**.
[13 timing helper cases](../../tests/measurement/test_stage_timing.py) cover all
source/support combinations, missing support records and immutability. Expanded
adoption assertions cover positive decode means, metric versus source declarations,
v1 absent engines and browser-only unsupported encoders. All local preservation
gates pass; Python 3.11/hosted verification remains pending.

Step 5 final result: **1,162 tests pass; 93.04% branch-inclusive coverage**.
Both configured Python CI jobs reproduce the adopted snapshots with fixed pins.
[N2 software closeout](../archive/measurement/N2_SOFTWARE_CLOSEOUT.md) records remaining hosted verification
and the separate feature/normalization/fingerprint/matcher-v2 boundary.
