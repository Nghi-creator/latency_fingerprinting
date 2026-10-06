# N2 observation-v2 field contract

**Design version:** 1.0.1
**Frozen for Step 2:** 2026-10-06
**Status:** Strict models and additive schemas implemented in Step 2; adoption is Step 3

This specifies additive offline measurement records using the unchanged
[N1 registry](CANONICAL_REGISTRY.md), [gauge](GAUGE_AGGREGATION.md) and
[counter](COUNTER_AGGREGATION.md) semantics. V2 records retain evidence and
compatibility metadata. They contain no response vector, normalization, match
result, diagnosis probability or runtime action. P0 contracts and the N1 shadow
report remain unchanged.

## Roots and version ownership

| Root/model | JSON schemaVersion | New schema file | Purpose |
| --- | --- | --- | --- |
| ObservationWindowV2 | `observation-window-v2` | `observation-window-v2.schema.json` | One independently validated measurement window |
| ObservationRecordV2 | `observation-v2` | `observation-v2.schema.json` | Comparable degraded/relief windows and recorded intervention metadata |

Both roots require `contractVersion: "2.0.0"`. These constants belong in new v2
modules; do not change P0's `CONTRACT_VERSION` or existing schema dispatch values.
An embedded window retains its own root/version fields. Unknown fields and root
versions fail validation. The existing P0 matcher and response builder must reject
v2 inputs rather than converting them. Step 2 adds root validation/schema exports;
Step 3 adds a separate `ingest-pixelated-v2` command for standalone windows.
Pair assembly is an in-memory validated constructor in N2; a new pair-building CLI
is not required by this slice.

All fields below are required unless marked **default**. A required nullable field
must appear explicitly as null when evidence is absent. Numbers are strict finite
scalars, booleans are strict, counts/row ordinals are strict integers, and strings
are trimmed and non-empty. No numeric-string/bool coercion is allowed. Ordered
collections become tuples; maps detach from callers and become read-only. Context
and settings are deeply immutable, including nested JSON values. Serialize camelCase
aliases, sorted keys, finite JSON and a final newline, with no ambient timestamps.

## Registry binding

Windows reference a separately verified snapshot; they do **not** embed definitions.

| RegistryReference field | Type and rule |
| --- | --- |
| registryVersion | `latency-metrics-v2.0.0` for the initial N2 release |
| contentHash | `sha256:<64 lowercase hex digits>`; exact trusted release hash below |

The trusted snapshot is [metric-registry-v1.json](../../schemas/metric-registry-v1.json).
Its hash is SHA-256 of the UTF-8 bytes emitted by `render_metric_registry`, including
the final newline, rather than arbitrary JSON reformatting or the input TAR bytes:

```text
sha256:50329d193303c271194b28e9164ae8627dd257d7620174c5ab136ba209864884
```

Validation resolves a version/hash pair against the in-package trusted canonical
registry. It never loads a path/URL from a record, trusts an embedded definition,
or accepts a same-version modified registry. Unknown versions/hashes fail closed.
Future registry releases require an explicit resolver extension and new fixtures;
this specification does not silently enable arbitrary registries.

Every metric map key must equal `summary.metricName`. Its semantic version, source,
raw fields, kind, unit, primary/available aggregations and clock basis must exactly
match its resolved definition; summary registryVersion must match the window.
Require all 31 canonical outputs exactly once, including explicit missing summaries
for absent sources. Unknown names, omitted outputs and duplicate JSON keys fail.
For non-negative definitions every published aggregate must be non-negative;
gauge min/median/P95/max values must be ordered where present. Retain N1 internal
count, coverage, interval, rate and aggregate reconstruction checks.
Canonical `reject_segment` transitions cannot appear as accepted reset/wrap
intervals. Rate/total pairs must also agree on status and missing/rejected evidence.

## Standalone window

| ObservationWindowV2 field | Type and rule |
| --- | --- |
| schemaVersion, contractVersion | Root/version literals above |
| runId, windowId, comparisonCaseId | Non-empty sanitized research identifiers; comparison case is required |
| context | Immutable V2ContextSnapshot described below |
| phase | Existing `baseline`, `degraded`, `relief`, `recovery` meanings |
| provenance | `synthetic`, `controlled_real`, `organic_real` |
| registry | RegistryReference |
| captureMethod | CaptureMethodReference |
| clock | WindowClock |
| sourceArtifact | SourceArtifactV2 |
| sources | Map with exactly `browser_webrtc`, `engine_runtime`, `encoder_pipeline` SourceSupport records |
| effectiveSettings | Non-empty immutable finite JSON map of stable window settings |
| measurements | Canonically ordered map of all 31 MetricMeasurement records |
| validity | Strict `isValid` plus ordered unique closed-enum `reasonCodes`; valid iff reasons are empty |
| confounderCodes | **default:** empty tuple; closed enum `composite_profile_change`, `other_setting_change`, `operator_declared` |
| stageTimings | **default:** empty tuple of StageTiming records; omission explicitly means no supplied stage-local timing evidence |

V2ContextSnapshot preserves the exact field meanings of
[ContextKey](../../src/latency_fingerprinting/models/context.py): contextId,
compatibilityGroup, edgeNodeClass, nodeId, operatingSystem, runtimeClass, workloadId,
captureImplementation, encoderFamily, encoderProfile, transportImplementation,
connectionMode, clientClass, nominalStreamProfile, nullable networkScenario and
versions. Match context identities using finite JSON-aware equality, preserving
the distinction between booleans and numbers. Copy into a new immutable snapshot;
do not relax or mutate P0's model. Identity labels must be sanitized research aliases.
The explicit context's `versions.pixelatedBundleSchema` must match a Pixelated input.

CaptureMethodReference contains `methodId`, semantic `methodVersion` and required
nullable `producerVersion`. Initial allowed method pairs are
`pixelated_bundle_offline / 1.0.0` and `synthetic_series / 1.0.0`.
The first versions the offline extraction/adoption meaning; it does not identify
a proven instrumentation revision. Producer version is null unless declared by
the producer; never infer it from a checkout, file date or current software.
Synthetic method requires synthetic provenance. Real provenance requires the
Pixelated method in this slice. Future methods require an explicit extension.

SourceArtifactV2 contains `sourceType` (`pixelated_bundle` or `synthetic_series`),
required `contentHash` with the SHA-256 syntax above, and `bundleSchemaVersion`
(`"1"`, `"2"` or null). Pixelated windows require the declared bundle version;
synthetic windows require null. Pixelated contentHash uses N1's checksum over
readable bundle contents, independent of directory/TAR packaging. Synthetic hashes
identify deterministic fixture input bytes. No source path or arbitrary producer
text is included. Derive Pixelated windowId as `pixelated-v2-<checksum hex>-<phase>`; take
runId from validated sanitized metadata and comparisonCaseId from the explicit
caller/manifest agreement. Do not mint random IDs during adoption.

Validity reason codes are `producer_invalid`, `required_source_unavailable` and
`source_samples_unavailable`. V2 retains invalid windows for audit; pair construction
requires valid windows. Numeric metric rejection alone does not invalidate the
entire window when registered policies yield incomplete evidence. Envelope,
identity, privacy and invalid-clock errors still reject the import outright.

## Clocks and typed support

| WindowClock field | Type and rule |
| --- | --- |
| basis | `source_elapsed_ms`, matching every summary |
| provenance | `wall_clock_derived_elapsed` or `synthetic_elapsed`; monotonic is not an N2 claim |
| domainId | Non-empty sanitized capture-local domain identifier; independent runs may have different domains |
| elapsedStartMs, elapsedEndMs | Non-negative finite bounds with end > start |
| durationMs | Positive finite; equals end minus start |
| startedAt, endedAt | Required nullable UTC timestamps; both present or both null |

Pixelated windows require wall-clock-derived provenance and both UTC bounds;
synthetic windows require synthetic provenance and null UTC bounds. The UTC and
elapsed durations must agree with `math.isclose(durationMs / 1000, utcDurationS,
rel_tol=1e-6, abs_tol=0.001)`, after N1 envelope validation; UTC never
replaces missing elapsed evidence. Summaries must have exactly the window's elapsed
bounds/duration. Clock domains are local: no cross-domain timestamp subtraction,
one-way transit measurement or producer synchronization is inferred. Derive the
Pixelated domainId as `pixelated-<checksum hex>`; synthetic fixtures declare theirs.

SourceSupport contains `state`, nullable `declaredState`, `basis`, `sourceFile`,
`rowCount` and `availableRowCount`. State is `supported`, `unsupported` or
`unavailable`; basis is `source_declaration`, `source_rows` or `source_absent`.
Source file is a closed basename: browser uses `stream-telemetry.csv`, engine and
encoder use `engine-telemetry.csv`; synthetic sources use null. Counts are
non-negative, available <= total, and every corresponding summary's source count
equals rowCount. Available rows count active/error-free rows after applying source
support declarations, independently of metric numeric-cell validity.

An explicit source declaration controls state, records that declaration and uses
`source_declaration`. Unsupported/unavailable declarations suppress usable source
rows, including stale cells. Without a declaration, available rows yield supported;
otherwise state is unavailable, with source_rows or source_absent according to
rowCount. Supported declarations can have zero currently available rows: capability
and current evidence are different. Missing source counts are zero; no denominator
or row is manufactured. Use typed extraction metadata, never parse diagnostic prose.

MetricMeasurement contains `role`, `support` and `summary`:

- Role is `analytical_candidate` for the 15 gauges/eight rates, `audit_only` for
  the eight window totals, derived from the definition. Candidate is not matcher adoption.
- MetricSupport contains `state`, nullable `declaredState` and `basis`:
  `measurement_declaration`, `source_support` or `source_rows`. Unsupported source
  or metric declarations dominate; otherwise unavailable declarations/source state
  dominate; otherwise supported. The selected controlling declaration determines
  basis, with metric declaration winning ties. Without one, use source_support
  for a source declaration and source_rows for inferred source availability.
- Summary is the existing immutable MetricSeriesSummary shape, validated internally
  and bound to the registry/window above. The primary value is read from aggregates;
  no duplicate outer value field or renamed P0 aggregate is stored.

Unsupported/unavailable metric support requires missing status, zero usable samples,
empty aggregates/intervals and zero observed duration/coverage. Its source count may
be positive because stale/unavailable rows still exist. Supported means the source
can supply the quantity: it permits complete, incomplete, missing or rejected
summary states. Blank/malformed values do not change capability to unsupported.
Rates and audit totals reading the same raw field must have identical support,
counts, usable rows, intervals, reset/gap rows and observed duration/coverage.

| Evidence | Support | Summary/value |
| --- | --- | --- |
| Valid zero gauge or zero counter delta | supported | Numeric zero; never missing |
| One usable gauge sample | supported | incomplete; statistics present, coverage zero |
| One usable counter sample | supported | incomplete; no primary value, coverage zero |
| All cells blank in an available browser source | supported | missing, no value |
| Malformed/negative-only numeric cells | supported | rejected, no value |
| Some missing cells or rejected reset transitions | supported | N1 policy selects incomplete/rejected; no gap bridging |
| Declared unsupported proxy, even with stale cells | unsupported | missing, no value |
| Absent engine source or source declared unavailable | unavailable | missing, no value |

N2 serializes safe fixed summary diagnostics: `Missing source evidence.`,
`Rejected source evidence.` and `Measurement provenance requires review.` for
the respective non-empty N1 missing/rejected/warning categories. Keep their presence
and structured counts/rows; do not copy arbitrary producer exception strings.
Untrusted v2 summary reason/warning strings must belong to this vocabulary.
Detailed N1 diagnostics remain in the separate shadow report. Typed support,
summary state and row/interval evidence carry semantics independently of prose.

## Paired observation and compatibility

ObservationRecordV2 contains only `schemaVersion`, `contractVersion`,
`observationId`, `comparisonCaseId`, `degradedWindow`, `reliefWindow` and
`intervention`. The nested windows carry context, registry and provenance; do not
duplicate potentially divergent copies at the observation root. observationId is
an explicit sanitized caller identifier, not a current-time-generated UUID.

InterventionV2 contains required `probeId`, `probeType` (initially
`stream_profile_relief`), semantic `probeVersion`, non-empty immutable
`requestedSettings`, nullable `observedSettings`, positive finite `intensity`,
`applicationMethod` (`paired_run` or `simulated_pair`), `executionStatus`
(`not_executed`, `executed`, `failed`), `restorationStatus` (existing P0 meanings),
`degradedWindowId`, `reliefWindowId`, `pairedWindowOrder` (exactly
`["degraded", "relief"]`) and **default** empty `confounderCodes` with the window
vocabulary. No live method, action execution, quality-cost model or free-text safety
notes are added. Retain P0 simulated/executed/restoration consistency rules in new
v2 validators rather than changing P0 Probe.

Pair construction fails with validation errors when:

1. IDs, comparison cases, phases or intervention window references disagree, or
   window IDs are equal. Different runIds/artifact hashes are allowed for paired runs.
2. Context identities, registry version/hash, capture method ID/version/producer
   version, provenance, clock basis/provenance or metric definition meanings differ.
   Domain IDs/UTC bounds need not match across independent runs; they are not
   synchronized by pairing. Synthetic and real evidence cannot be mixed.
3. Either window is invalid, or durations differ by more than the frozen P0 10%
   relative duration rule. This is a duration comparability rule, not a gauge or
   counter coverage threshold. Partial/missing metric evidence remains explicit.
4. A requested relief setting was not applied or did not change; declared observed
   settings disagree with relief; or other setting changes lack a confounder code
   on a window/intervention. JSON equality distinguishes booleans from numbers.
5. The probe is failed, simulated metadata claims runtime execution/restoration,
   or real paired-run metadata does not declare executed status, observed settings
   and an applicable restoration outcome. Simulated pairs require synthetic windows.

Source/metric support and coverage can differ between the windows and must not be
discarded to force comparability. No normalized vector or raw response delta is
created by these contracts. A future analytical adoption contract must set minimum
support, feature normalization/direction and probe compatibility before scoring.

## Optional stage-local timing

StageTiming is a separate evidence record, not a canonical registry extension or
an additional analytical metric. It is not populated from existing interval means.

| StageTiming field | Type and rule |
| --- | --- |
| stage | `capture`, `encode`, `decode`, `render`; unique per window |
| state | `measured`, `estimated`, `unavailable` |
| source | One of the three source enums |
| methodId, methodVersion | Required nullable non-empty ID/semantic version; both present for values, both null for unavailable |
| clockDomainId | Required nullable capture-local identifier; present for values, null for unavailable |
| unit | Literal `ms` |
| statistic | Required nullable `sample_mean`; null for unavailable |
| value | Required nullable non-negative finite number; null for unavailable |
| sampleCount | Non-negative integer; positive for values, zero for unavailable |
| reasonCode | Required nullable `not_instrumented`, `unsupported_source`, `source_unavailable`; present only for unavailable |

The statistic is explicitly a mean of direct stage-local duration samples; it is
not a per-frame latency distribution or end-to-end delay. Estimated values require
a documented estimation method with the same stage meaning, never an unlabeled proxy.
Value-bearing records require an explicitly allowlisted method/version and its
documented local clock domain/source; no such methods are approved in initial N2.
Consequently only unavailable records or an empty tuple can be adopted now.
An unavailable timing reason of unsupported_source/source_unavailable must agree
with the typed support state of its declared source.
Future measured/estimated methods require producer evidence, reviewed meaning,
validation fixtures and a contract-method allowlist extension before population.

Existing decode/buffer producer interval means remain registered gauges; the
unsupported pipeline-delay proxy remains missing. Neither becomes direct capture,
encode, decode or render duration. No registry hash changes are needed for the
empty/unavailable representation. A new analytical timing meaning requires a new
registry release, never an edit to latency-metrics-v2.0.0.

## Privacy, resources and implementation gates

No arbitrary metadata bag, raw rows, hostnames, usernames, tokens, peer IDs, URLs,
absolute paths or producer notes are part of v2 records. Context/run/artifact/domain
identifiers are explicit sanitized research aliases; substring scanning cannot
prove sanitization, so callers remain responsible for pseudonymizing label values.
Reject known forbidden private keys recursively in context/settings input, retaining
existing producer-envelope privacy checks. Export only fixed diagnostic vocabulary,
typed states and reviewed fields. Never interpolate raw exception text into records.

Untrusted file loading reuses bounded duplicate-safe JSON I/O. Bundle adoption
reuses the bounded directory/TAR reader and N1 pure arithmetic. Additional support
metadata must come from the same read/validated envelope as samples and checksum;
do not reread mutable files independently to infer support. Add typed extraction
metadata additively and preserve N1 report/sample behavior and pins. Freeze source
state before aggregation; declarations cannot be overridden by stale numeric cells.
Respect existing byte/row bounds; do not raise them to accommodate larger reports.

Step 2 must test both roots, immutable nested maps, strict finite/null/zero states,
registry hash/version/definition mismatches, duplicate/unknown/omitted metrics,
typed support contradictions, summary/window bounds, rate/total evidence equality,
counter reconstruction, safe diagnostics, all pair rejection rules and unavailable
timing. Step 3 must additionally prove directory/TAR equality, unchanged inputs,
deterministic IDs, declaration precedence and explicit legacy-clock limitations.
Step 4 may populate unavailable timing only until a reviewed producer method exists.
Existing P0/N1 schema, fixture, registry/report and exact match gates remain required.

Specification changes during Step 2 must be explicit revisions to this document;
do not resolve field ambiguity by silently changing a frozen v1/N1 meaning.

Design 1.0.1 records Step 2's explicit cross-validation clarifications for canonical
reset rejection, rate/total status/reasons and unavailable timing/source agreement.
It adds no fields or registry meanings. Runtime behavior and construction are in
the [model guide](OBSERVATION_V2_MODELS.md).
