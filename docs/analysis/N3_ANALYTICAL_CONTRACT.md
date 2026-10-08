# N3 analytical features and offline matching contract

**Design version:** 1.0.0
**Specified:** 2026-10-07
**Status:** Step 1 specification complete; Steps 2–3 policy/response models and derivation implemented locally
**Source:** [N3 plan](../plans/NEXT_IMPLEMENTATION_PLAN.md)
**Normative initial policy:** [N3_FEATURE_POLICY_SPEC.json](N3_FEATURE_POLICY_SPEC.json)

This contract connects [N2 observation pairs](../measurement/OBSERVATION_V2_CONTRACT.md)
to separate analytical records. It preserves N1 registry meaning, N2 observation
schemas and the P0 matching path. The JSON policy remains a normative specification
artifact. [Step 2 models](N3_ANALYTICAL_MODELS.md), schema export and `validate`
accept policy and analytical response roots. [Step 3 derivation](N3_RESPONSE_DERIVATION.md)
builds responses from explicit validated inputs. Fingerprint/match roots and the
proposed build/match commands remain pending.

## Versioned roots and trust boundary

| Model | schemaVersion | contractVersion | Schema |
| --- | --- | --- | --- |
| FeaturePolicyV1 | feature-policy-v1 | 1.0.0 | feature-policy-v1.schema.json |
| AnalyticalResponseV2 | analytical-response-v2 | 2.0.0 | analytical-response-v2.schema.json |
| FingerprintV2 | fingerprint-v2 | 2.0.0 | fingerprint-v2.schema.json |
| MatchResultV2 | match-result-v2 | 2.0.0 | match-result-v2.schema.json |

The first two roots are implemented; fingerprint and match roots are planned.

All fields below are required unless explicitly marked default. Nullable fields
must be present as null. Models forbid extra fields, duplicate identities, boolean
numbers, non-finite/unrepresentable arithmetic and unordered sets. Maps/arrays are
detached and immutable; nested model instances are fully revalidated. JSON uses
camelCase aliases, sorted keys, UTF-8, two-space indentation and a final LF.

Registry binding is the existing `latency-metrics-v2.0.0` release/hash:
`sha256:50329d193303c271194b28e9164ae8627dd257d7620174c5ab136ba209864884`.
Resolve only in-package approved definitions/policies. A supplied path/URL or
self-consistent hash does not approve an unknown release. Hashes identify bytes;
they do not authenticate producer evidence or declared bottleneck labels.

Do not edit N2 observations to embed analytical output, resolve remote policy
references, accept v1 roots through renaming, or infer rates from P0 aggregates.

## Initial policy identity and parameters

The only initial approved policy is `n3-offline-conservative / 1.0.0`, with
`parameterProvenance=software_provisional`. Its specification contains every
parameter explicitly; no ambient/P0 defaults are inherited. Its content hash is:

`sha256:96457b318cc714f3d9d0d63a35b12548f6e030b10057b2c8e5a3a77e352fe1af`

Compute `contentHash` by removing that root field, rendering the remaining policy
with the canonical JSON rules above (`allow_nan=False`), and hashing those UTF-8
bytes. Hash presence, identity, known version and exact approved content must all
agree. Step 2 implements an in-package trusted renderer/release check that
reproduces this specification and rejects altered content even with a recomputed hash.

| Policy field/group | Frozen meaning |
| --- | --- |
| policyId, policyVersion, contentHash | Exact approved identity/version/hash above |
| registry | Exact existing RegistryReference |
| parameterProvenance | Literal software_provisional; no scientific calibration claim |
| responseMethod, deltaDirection | signed_relative_primary_v1; relief_minus_degraded |
| normalizationReference | absolute_degraded_with_epsilon_floor |
| confounderHandling | reject_pair |
| compatibilityMethod | structural_context_probe_v1, defined below |
| distanceMethod, strengthMethod | weighted_rms_v1; inverse_one_plus_distance_v1 |
| repositoryFailurePolicy | error; no silent skipping of malformed files |
| maximumRankedCandidates | 5; comparison audit retains all scored candidates |
| features | Exact 22-entry map in the inventory below |
| decision | Exact parameters below, all required |

Each feature binds semanticVersion `1.0.0`, source/unit/aggregation from its registry
definition, epsilon **1.0 in its canonical unit**, weight **1.0**, null clipMinimum/
clipMaximum, minimumCoverage **1.0**, minimumUsableSamples **2**,
minimumAcceptedIntervals **1**, and allowedStatuses `["complete"]`.

Floors are explicit numerical guards, not noise estimates. Full coverage and
complete status are deliberately conservative software requirements. These settings
have not been experimentally calibrated. Changing inventory, parameters, methods
or clipping requires a separately reviewed policy version/content hash; editing
this approved release in place is forbidden. The first release does not clip.

| Decision parameter | Value |
| --- | --- |
| minimumSharedFeatures | 4 |
| minimumFeatureCoverage | 0.75 |
| minimumMatchStrength | 0.8 |
| minimumScoreMargin | 0.1 |
| conflictingResidualThreshold | 0.5 |
| maximumConflictContribution | 0.5 |

## Feature inventory

Names identify the feature and its sole source metric. All are analytical-candidate
outputs. Read only their registered primary aggregation. This is a signed response
inventory: it does not declare higher/lower values universally beneficial, or
interpret intentional throughput reduction as diagnosis evidence by itself.

| Metric/feature | Unit | Primary aggregation |
| --- | --- | --- |
| client.available_incoming_bitrate_kbps | kbps | median |
| client.decode_time_mean_ms | ms | median |
| client.frames_decoded_rate_fps | frames/s | time_weighted_rate |
| client.frames_dropped_rate_fps | frames/s | time_weighted_rate |
| client.freeze_count_rate_per_min | freezes/min | time_weighted_rate |
| client.freeze_duration_rate_ms_per_s | ms/s | time_weighted_rate |
| client.jitter_buffer_delay_mean_ms | ms | median |
| client.received_bitrate_kbps | kbps | median |
| client.received_fps | fps | median |
| encoder.frames_dropped_rate_fps | frames/s | time_weighted_rate |
| encoder.frames_in_rate_fps | frames/s | time_weighted_rate |
| encoder.frames_out_rate_fps | frames/s | time_weighted_rate |
| encoder.queue_level_buffers | buffers | median |
| host.camera_cpu_percent | percent | median |
| host.camera_rss_mib | MiB | median |
| host.game_cpu_percent | percent | median |
| host.game_rss_mib | MiB | median |
| host.node_cpu_percent | percent | median |
| host.node_rss_mib | MiB | median |
| transport.jitter_ms | ms | median |
| transport.packets_lost_rate_per_s | packets/s | time_weighted_rate |
| transport.round_trip_time_ms | ms | median |

The eight `*_window_total` outputs remain audit-only; the unsupported
`encoder.pipeline_delay_proxy_ms` is excluded. Unavailable stage timings, gauge
P95/min/max alternatives, raw timestamps and P0 delta names are not features.
The policy must not accept a feature merely because a supplied record calls it
analytical_candidate: registry membership/meaning and this exact inventory control.

## AnalyticalResponseV2

| Root field | Type/rule |
| --- | --- |
| schemaVersion, contractVersion | Literals from the root table |
| responseId | Deterministic identifier defined below |
| observation | Full validated ObservationRecordV2; retains both summaries and intervention |
| policy | Full approved FeaturePolicyV1; no implicit lookup defaults |
| features | Exact policy-keyed map of FeatureResponseV2, including excluded entries |
| isValid | Strict boolean; true iff at least one feature is eligible and no confounder |
| invalidReasonCodes | Unique ordered tuple: confounded_pair, no_eligible_features |

`responseId` is `response-v2-<sha256 hex>` of canonical JSON
`{"observation": <full observation>, "policy": <full policy>}`. No current time,
random ID or absolute path participates. Root validation recomputes the ID,
feature evidence, eligibility and response arithmetic from embedded inputs.

FeatureResponseV2 has required fields `unit`, `aggregation`, `state` (eligible or
excluded), `degraded`, `relief`, `exclusionCodes`, `rawDelta`, `referenceValue`,
`denominator`, `normalizedValue`, `wasClipped`, `unclippedValue`.
Each window evidence record contains `windowId`, metric `supportState`,
`summaryStatus`, `primaryValue`, `sourceSampleCount`, `usableSampleCount`,
`acceptedIntervalCount`, `observedDurationMs`, `coverage`. Copy these exactly from
the corresponding trusted summary/support; finite primary values may be null.
Raw interval/source evidence remains in the embedded observation, not discarded.

For each window, select the first applicable feature exclusion in this order:

1. support is unsupported: `<phase>_unsupported`;
2. support is unavailable: `<phase>_unavailable`;
3. status missing, rejected or incomplete: `<phase>_missing`, `<phase>_rejected`,
   `<phase>_incomplete`, respectively;
4. coverage below policy minimum: `<phase>_coverage`;
5. usable samples or intervals below minimum: `<phase>_samples`, `<phase>_intervals`;
6. absent primary value: `<phase>_no_value`.

Here `<phase>` is degraded or relief. Retain up to two codes in degraded/relief
order. If any window/intervention confounder code is present, override feature
exclusions with `["confounded_pair"]` for all entries and set root invalidity to
`["confounded_pair"]`. Otherwise all excluded entries produce root invalidity
`["no_eligible_features"]`; any eligible entry produces an empty invalidity tuple.
Invalid N2 pairs fail input validation before response construction.

Excluded entries retain window audit evidence but have null rawDelta,
referenceValue, denominator, normalizedValue and unclippedValue, with wasClipped
false. Eligible entries have empty exclusionCodes and:

```text
rawDelta = relief.primaryValue - degraded.primaryValue
referenceValue = degraded.primaryValue
denominator = max(abs(referenceValue), epsilon)
normalizedValue = rawDelta / denominator
wasClipped = false
unclippedValue = null
```

No extrapolation, sample-cadence conversion or cross-domain timestamp subtraction
occurs. A missing value is not zero. Any non-finite/unrepresentable derived result
is a validation/calculation error, not a fabricated exclusion or match. Validate
reconstruction with `math.isclose(rel_tol=1e-12, abs_tol=1e-12)`; identity, units,
support, counts and eligibility remain exact. Known false provenance declarations
fail model consistency rules; the contract cannot independently verify capture truth.

## FingerprintV2

| Root field | Type/rule |
| --- | --- |
| schemaVersion, contractVersion | Literals from the root table |
| fingerprintId | Deterministic identifier defined below |
| bottleneckLabel | Required non-empty sanitized declared label; never inferred by creation |
| provenance | Equals embedded observation provenance |
| validationStatus | unreviewed, software_checked or rejected |
| response | Full validated AnalyticalResponseV2 with isValid=true |
| featureVector | Exactly eligible feature names mapped to normalized finite values |

`fingerprintId` is `fingerprint-v2-<sha256 hex>` of canonical JSON
`{"response": <full response>, "bottleneckLabel": <label>,
"validationStatus": <status>}`. Reconstruct the vector/ID from these fields;
a separately supplied inconsistent vector cannot override the response.
`software_checked` requires at least four eligible features and eligible count/22
>=0.75. Thus initial eligibility requires at least **17** of the 22 features.
Unreviewed/rejected records may retain lesser valid evidence for audit; neither
is a match candidate. Creation defaults to software_checked and errors if its
requirements are not met. Explicit audit status is allowed by the API/CLI.

Software checking means numerical/contract consistency, not experimental cause
validation. Synthetic fingerprints remain synthetic. Real provenance requires
real N2 inputs; labels remain caller-declared references. No field claims calibrated
confidence, verified experimental truth or execution of a new probe.

## Compatibility, repository loading and comparison

Parse/validate query, policy and every repository fingerprint before decisions.
Malformed roots/files, duplicate IDs, unsafe links, unknown releases/policies and
resource failures are errors with no partial result. Initial repository traversal
is sorted and bounded: at most **128 v2 fingerprint JSON files**, **4,096 directory
entries**, depth **16**, existing **10 MiB JSON** / depth **128** per-file limits.
Do not raise P0 limits or change its loader. Local paths are inputs, never record
fields. Empty valid repositories produce an analytical unknown, not a load error.

For each valid fingerprint, collect compatibility rejection codes in this order:
`validation_status`, `registry_mismatch`, `policy_mismatch`, `provenance_mismatch`,
`capture_method_mismatch`, `clock_meaning_mismatch`, `context_mismatch`,
`probe_mismatch`, `settings_mismatch`. Retain all applicable codes, no free text.
Compatibility requires:

- software_checked status and exact registry/policy identity, versions and hashes;
- equal provenance and capture method ID/version/producer version, plus clock
  basis/provenance (domain IDs/UTC bounds may differ);
- JSON-aware equality of all context fields except contextId, nodeId and
  networkScenario; compatibilityGroup, workload, versions and structural classes
  remain equal. Booleans do not compare equal to numbers;
- equal probe type/version/application method/intensity and requestedSettings;
- equal degraded effective settings and equal relief effective settings.

Concrete run/window/observation IDs, artifact hashes and clock domains need not
match across runs. This structural compatibility is a declared software rule,
not evidence of cross-node/scenario transfer. Missing support can differ: feature
eligibility handles it rather than forcing numeric values into the vector.

Shared features are the sorted intersection of eligible query/reference vectors.
Their weight comes only from the exact approved policy; it is positive. Reject
otherwise compatible candidates with `shared_feature_count` if shared count<4,
or `feature_coverage` if shared count/22<0.75. Retain both failing codes in that
order. The coverage denominator is always the full policy inventory, not a
candidate-selected subset. Fewer features cannot artificially improve eligibility.

For each eligible shared feature, compute residual=query-reference,
weightedSquaredResidual=weight*residual*residual. Use sorted-feature `math.fsum`:

```text
sharedWeight = sum(weights of shared features)
residualSum = sum(weightedSquaredResidual)
distance = sqrt(residualSum / sharedWeight)
matchStrength = 1 / (1 + distance)
featureCoverage = sharedFeatureCount / 22
```

All arithmetic must be finite; zero/empty usable weight cannot be scored. A feature
is conflicting iff abs(residual)>0.5; equality is supporting. Conflict contribution
is conflicting weighted residual sum / residualSum, or zero if residualSum is zero.
It is a residual diagnostic, not a causal contradiction detector.

Rank all scored candidates by `(distance ascending, fingerprintId ascending)`.
Only the first five appear in rankedCandidates; all scored comparisons remain in
an audit map so truncation does not change the top-two margin or hide eligibility.
Margin is best strength minus second strength, null when fewer than two are scored.
Same-label candidates still compete for margin; equal distances remain ambiguous.

## MatchResultV2 and decisions

| Root field | Type/rule |
| --- | --- |
| schemaVersion, contractVersion | Literals from the root table |
| matchId | Deterministic identifier defined below |
| queryResponse | Full validated AnalyticalResponseV2, including invalid analytical state |
| repositoryReferences | Sorted unique fingerprintId/contentHash records for all parsed fingerprints |
| candidateRejections | Fingerprint-ID map to ordered closed rejection codes |
| comparisons | Fingerprint-ID map of all scored CandidateComparisonV2 records |
| rankedCandidates | At most five sorted summaries: fingerprintId, bottleneckLabel, distance, matchStrength |
| decision | matched or unknown |
| acceptedLabel | Top label only when matched, otherwise null |
| unknownReason | Closed code below when unknown, otherwise null |
| matchStrength, scoreMargin | Top strength/top-two margin, or null when absent |
| noticeCode | Literal software_similarity_not_causal_confidence |

Each comparison contains fingerprintId, fingerprintContentHash, bottleneckLabel,
referenceVector, sharedFeatures, excludedFeatures, sharedWeight, featureCoverage,
distance, matchStrength, conflictContribution and evidence. referenceVector is the
fingerprint's full eligible vector; evidence maps shared names to queryValue,
referenceValue, residual, weight, weightedSquaredResidual and classification
(supporting/conflicting). excludedFeatures contains all unshared policy names with
ordered codes query_excluded and/or reference_excluded. Root validation reconstructs
all retained comparisons/ranking/decision from query, policy and reference vectors.

Fingerprint content hashes identify canonical full fingerprint bytes. Numeric
result validation cannot authenticate those external bytes from a reference hash
alone; repository-backed reproduction must check hashes/vectors/labels against the
full fingerprints. This limit is explicit, just like declared producer provenance.
Comparisons/rejections partition repository IDs. For an invalid query, every
repository ID is rejected with `query_invalid` and comparisons is empty.

`matchId` is `match-v2-<sha256 hex>` of canonical JSON
`{"queryResponseId": <id>, "policyHash": <hash>,
"repositoryReferences": <sorted references>}`. Different directory/TAR packaging
or ambient execution time must not change IDs/output for equal semantic inputs.

Apply unknown reasons in this exact priority:

1. invalid query response: invalid_response;
2. empty repository: no_fingerprints;
3. no candidate passes compatibility: no_compatible_fingerprints;
4. compatibility passed but none has sufficient shared evidence: insufficient_features;
5. best strength<0.8: weak_match;
6. non-null margin<0.1: ambiguous_margin;
7. best conflictContribution>=0.5: conflicting_evidence;
8. otherwise matched, accepting the best declared label.

Threshold equality passes strength/margin; equality fails the conflict cap. Unknown
never includes acceptedLabel. A singleton has no margin requirement. Query invalidity
and candidate exclusions remain explicit. No additional arbitrary tie/epsilon fudge
factor modifies decision boundaries. Output size is capped at **10 MiB**; oversized
results fail before serialization reaches stdout. Models enforce at most 128
repository/comparison entries and 22 feature entries per comparison.

## Independent examples and implementation gates

| Input | Required result |
| --- | --- |
| Median 20 ms ->10 ms, epsilon1 ms | rawDelta=-10 ms; denominator20 ms; normalizedValue=-0.5 |
| Primary zero ->0 | rawDelta0, denominator1, normalizedValue0; eligible if evidence complete |
| Primary zero ->2 units | normalizedValue2, no clipping; not missing or an error |
| Counter rate60 ->30 frames/s, with totals600 ->300 | Rate response=-0.5; totals remain absent from feature vector |
| Coverage0.5, missing cell or rejected series | Explicit phase exclusion; calculations null |
| 16 shared complete features | Coverage16/22<0.75; candidate rejected, even if residuals zero |
| All22 residuals0.25 and weights1 | distance0.25; strength0.8; no conflicts; singleton passes |
| All22 residuals0.3 | distance0.3; strength1/1.3<0.8; weak_match |
| Distances0.1 and0.12 | Strengths1/1.1 and1/1.12; margin<0.1; ambiguous_margin |
| One residual0.6, other21 zero | distance0.6/sqrt(22); strength>0.8; conflict contribution1; conflicting_evidence |
| Two equal-distance fingerprints | Stable ID order, zero margin; unknown regardless of label |

Step 2 must enforce root/policy identities, strict/immutable data, registry binding,
policy pin and response reconstruction without implementing the matcher early.
Steps 3–5 must add independent numerical and repository-backed reconstruction cases,
including invalid/confounded pairs, exact threshold boundaries, policy tampering,
unit/version mismatch, unsupported sources, arithmetic range failures, duplicate
fingerprints and ranking beyond five entries. Unknown releases or changed clipping
bounds fail the initial policy gate; future clipping requires a new approved release.

Step 6 commands are `build-response-v2 --observation --policy`,
`build-fingerprint-v2 --response --policy --bottleneck-label [--validation-status]`,
and `match-v2 --response --policy --fingerprints`, with all path arguments explicit.
The supplied policy must equal the embedded policy. Commands are read-only and emit
canonical JSON only on success. Existing v1 commands stay unchanged. Step 7 adds
separate synthetic fixtures/pins, both CI jobs, privacy/resource regressions and
software closeout. Step 1 delivered specification only; Step 2 now delivers
[policy/response validation and two additive schemas](N3_ANALYTICAL_MODELS.md).
