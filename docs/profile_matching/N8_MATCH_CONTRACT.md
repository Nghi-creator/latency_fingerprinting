# Provisional profile matching contract

This freezes `n8-profile-matching-v1`, its
[software-provisional policy](N8_MATCH_POLICY_SPEC.json),
[independent examples](N8_MATCH_EXAMPLES.md) and
[design vectors](N8_DESIGN_VECTORS.json). Standalone immutable models, exact pure scoring and reconstruction, generic
validation and three additive schemas are implemented; see the [model guide](N8_MODELS.md).
Linked matching/evaluation APIs and commands remain separate, unimplemented interfaces.
P0, `match-v2`, N2–N7 formats, policies, schemas and fixture releases retain their
existing behavior. N8 performs offline provisional comparison and evaluation;
it neither promotes N7 snapshots nor authenticates acquisition/review evidence.
Distances and margins are not probabilities. The numerical gates are explicit
software parameters, without a claim of empirical calibration or sample adequacy.
Distance 3 and margin 0.25 are round-number boundaries frozen for reproducible
software behavior; no supplied dataset was used to fit or validate them. They
do not imply Gaussian coverage or confidence levels.

## Roots and identities

The public model module is `latency_fingerprinting.profile_matching`, with roots:

| Model | Schema version | ID prefix |
| --- | --- | --- |
| `ProfileMatchPolicy` | `profile-match-policy-v1` | `profile-match-policy-` |
| `ProfileMatchResult` | `profile-match-result-v1` | `profile-match-` |
| `ProfileEvaluationResult` | `profile-evaluation-result-v1` | `profile-evaluation-` |

All roots use snake_case, required nullable fields, closed objects, detached
immutable tuples/maps and strict counts/booleans. Ordered collections require
lists/tuples, not generators or sets. Numbers are finite binary64; booleans and
strings cannot become numbers. Copied/nested model instances are revalidated.
JSON rejects duplicate keys, nonfinite values, more than 10 MiB or depth 32.
Canonical bytes use sorted keys, two-space indentation, UTF-8, no ASCII escaping,
finite numbers and one final LF. Hashes are `sha256:` plus 64 lowercase hex digits.

Each root has `schema_version`, `method_release`, its identity field (`policy_id`
or `result_id`) and `content_hash`. Hash the complete root excluding only its own
identity and `content_hash`; append the digest without `sha256:` to the ID prefix.
Only the exact published policy content and hash are approved. Rehashing changed
parameters does not approve a new policy. The policy pins the existing N3 response
policy, registry, N7 method and N7 policy and contains exactly the fields in its
JSON specification. New thresholds require a separately reviewed policy release.

A match result's other fields are exactly `policy`, `evidence`, `decision`,
`assurance`. `evidence` has exactly `dataset`, `report`, `snapshot`: the complete
N6 dataset declaration, N6 inspection report and supplied N7 snapshot. `assurance`
is `software_provisional_external_reviews_not_authenticated`. These objects retain
all excluded/baseline/missing entries and original identities, not just winners.
Standalone validation reconstructs declared arithmetic and references, not source
file inspection, physical truth, original query features or unseen revision history.
Evaluation adds the fields in the [evaluation contract](N8_EVALUATION_CONTRACT.md).

## Linked input and revision boundary

Consume **one explicitly supplied N7 snapshot and one N6 dataset directory**.
Inspect actual bounded N6 files once, with the existing optional trusted split
and dataset-hash anchors. Query entry IDs resolve in that same dataset. Cross-dataset
matching, lists of snapshot revisions and implicit latest/default discovery are
unsupported inputs. Unequal source aliases in different namespaces cannot establish
independence; this release avoids that ambiguity by requiring one inspected scope.

The report's dataset ID/hash, split, entries, artifacts and lineage must bind to
the supplied dataset and actual N6 inspection. For a built snapshot, its entire
source report must equal that inspection report. Refit N7's full training evidence
from the same inspected records and approved N7 policy; compare policy, source,
inputs, profiles, counts and assurance exactly with the supplied snapshot. This
comparison ignores only administrative lifecycle and root identity fields.
A mismatched built snapshot is invalid input, not a relaxed compatibility result.
An unbuilt draft may produce `snapshot_unavailable` without inventing a source.

Reuse N6 inspection and N7 fitting/arithmetic; share the inspected object rather
than reopening a directory separately for training and query extraction. A pure
model/scoring kernel is not a source-inspection shortcut. Linked inspection verifies
the actual N3 registry, response policy and source/window bindings for the query
as well as training records. Broken hashes, missing referenced files, invalid
models, false counts, changed anchors or binding contradictions fail the operation.

Only a snapshot whose current lifecycle is `provisional` may supply scores. Created,
rejected, stale or superseded revisions give an explicit unknown outcome. Candidate
support must independently be N7 `provisional`. No `trusted` state is introduced.
Selecting a snapshot never changes its state, training data or policy.

## Query and candidate selection

Ordinary matching accepts a response query with N6 role `validation` or `final_test`,
N6 eligibility and self duplicate representation. Query label is never an input to
candidate selection, features, distance, ranking, thresholds or chosen label.
N6 eligibility still requires its existing label evidence: this is an offline
labelled-cohort method, not an online unlabelled diagnostic API. Evaluation reads
truth only after producing label-blind decisions. A label-only change that preserves
eligibility/partition must leave fitted values and decisions unchanged, although
report/result content IDs change.

Missing queries have only the query reason `missing_measurements`. For measured
queries collect applicable reasons in order: `baseline_only`, `not_held_out`,
`n6_excluded`, `duplicate_evidence`. N6's exact reasons remain in `evidence.report`.
Training queries are allowed only in an explicit leave-group-out evaluation fold.
No query feature values are extracted/exported when the snapshot or query is
unavailable. Never fit training statistics from any held-out query.

Retain one candidate row for **every** N7 candidate, ordered by
`(partition_id, label, profile_id)`. Prequalification collects these ordered reasons:
`snapshot_unavailable`, `query_unavailable`, `partition_mismatch`, `profile_rejected`,
`source_overlap`. Partition equality means N6's exact existing response partition:
registry/N3 policy, provenance, capture/clock method, structural context, intervention
and both effective settings. Different partitions are never pooled or normalized
into compatibility. No cross-clock feature subtraction is introduced.

For each candidate, compare the query's entire connected N6 group with every
contributing training group. Reject overlap by group ID, group source IDs, source
content hashes or primary response/observation artifact byte hashes. Inspect all
members of those groups, including excluded/derived members. Receipt namespaces
are tagged `source` and `artifact`; shared label-support experiment bundles alone
are not primary-response alias receipts. The actual N6 graph already rejects known
cross-role components; this check is additional defense. Intrinsically contradictory
N6 declarations remain invalid inputs, not acceptable unknown results. Abstract
selection vectors need not be valid full N6 roots. External independence remains
an unauthenticated declaration even when all software checks pass.

`query_unavailable` applies exactly when the query has metadata exclusion reasons;
snapshot state has its separate reason. Compare partitions even for an unavailable
query (a null query partition differs from every candidate partition). Compute
source overlap only when the query has a group. These are metadata checks and
must not access an excluded query's feature values.

Within one exact partition, N7 permits at most one candidate per label. Use that
single candidate; do not load repeated historical revisions or count same-label
profiles as competing classes. An invalid duplicate `(partition, label)` inventory
fails model validation. Rank scored rows by `(distance, label, profile_id)`;
lexical tie breaking determines display order only, never a confident decision.

## Common evidence and numerical method

Before scoring, form one common feature mask across **all prequalified labels**:
the query has an eligible nonnull N3 normalized value, and every prequalified
candidate has the N7 feature supported with weight 1 and strictly positive raw MAD.
Only the exact 22 pinned feature names exist. An otherwise usable feature missing
from another label is excluded from every score. Candidate-specific missing-feature
subsets must not make scores artificially easier for one label.

With no prequalified candidate, the mask is empty. Otherwise require at least
17 common features and exact common count/22 >= 3/4. Check the ratio gate using
integers, not its rounded display value. If either gate fails, compute no distances.
Unsupported/zero-MAD features never gain a floor, epsilon or imputed value.

For each included feature of each candidate:

1. `absolute_deviation` = round once to binary64 of the exact rational difference
   `abs(query_value - center)`. Reject an unrepresentable intermediate even if
   later division could have reduced it to a representable number.
2. `standardized_deviation` = round once of the exact binary64 rational ratio
   `absolute_deviation / dispersion`.
3. `weighted_contribution` = standardized deviation times the applied weight.
   This release's included weights are exactly 1, so this is the same binary64.
4. `distance` = round once of the exact rational sum of binary64 contributions
   divided by the exact rational sum of applied weights. Do not round a running
   sum or require its un-divided sum to fit in binary64. `weight_sum` is the
   included feature count as a finite float in this release.

Every rounding is IEEE binary64 round-to-nearest, ties-to-even. Any nonzero exact
result rounding to zero, nonfinite input, overflow or invalid divisor fails the
whole request with a fixed error; do not return a partial ranking. Computed zeros
are positive; raw query-map values and feature-row query_value retain the
original signed zero. Helpers are
bounded before iteration. Exact rational production arithmetic is specified;
the independent design oracle uses high-precision Decimal.

If two or more labels score, `margin` is the exact difference of their **serialized
rounded** runner-up and best distances, rounded once with the same rules. There
is no relative margin, similarity transform, covariance or probability. Retain
per-feature N7 counts/availability/dispersion through the snapshot, common mask,
all score contributions and exclusions. These are support/spread diagnostics;
no confidence interval, calibrated uncertainty or out-of-distribution detector is
claimed. `distance_exceeded` is a software distance gate, not proof of a new cause.

## Decision fields and stage ordering

`decision` has exactly:

| Fields | Meaning |
| --- | --- |
| `query_entry_id`, `query_artifact_id`, `query_record_id` | N6 safe entry alias; nullable primary artifact alias and actual N3 response ID (baseline window ID for a baseline), bound by the linked API |
| `query_mode`, `excluded_group_id`, `refit_id` | `held_out` for ordinary matching, with both IDs null; fold semantics are in the evaluation contract |
| `query_feature_values` | Exact 22-feature float/null map only when query and snapshot are available; otherwise null; nonnull count equals the N6 eligible-feature count |
| `candidates` | Total ordered rows described below |
| `common_feature_names`, `common_coverage` | Sorted shared mask and exact numerator/denominator/value, denominator always 22 |
| `ranked_profile_ids` | Every scored candidate in rank order; never excluded candidates |
| `best_label`, `runner_up_label`, `best_distance`, `runner_up_distance`, `margin` | Nullable diagnostics; runner-up/margin null with fewer than two scored labels |
| `state`, `chosen_label`, `reason_codes` | `provisional_match` with best label and empty reasons, or `unknown`, null chosen label and ordered reasons |

Use N6 Alias for entry/artifact IDs and its existing hash/partition/group ID rules.
For a response, record ID is `response-v2-` plus 64 lowercase hex digits; for a
baseline use N6's bounded OriginalID; missing input has null artifact/record IDs.
The artifact ID must match the dataset entry declaration. Original record content
and feature extraction are checked by the linked API; standalone arithmetic
validation cannot verify the original artifact from a receipt alone. Candidate IDs
must belong to the supplied snapshot, or the referenced computed evaluation refit;
normal and fold candidates cannot be interchanged.

A candidate row has exactly `profile_id`, `partition_id`, `label`, `state`,
`reason_codes`, `features`, `weight_sum`, `distance`. State is `excluded` or `scored`.
Candidate reasons use the prequalification order above, followed by
`insufficient_common_features`, `insufficient_common_coverage`. With any candidate
reason, features/weight_sum/distance are null. Add common-support reasons only to
otherwise prequalified rows. With no candidate reason, features has all 22 keys.
Each feature row has exactly `state` (`included`/`excluded`), `reason_codes`,
`query_value`, `center`, `dispersion`, `profile_weight`, `applied_weight`,
`absolute_deviation`, `standardized_deviation`, `weighted_contribution`.
Collect feature reasons in order: `query_feature_missing`, `profile_feature_excluded`,
`not_common_feature`. The last applies only when this candidate and query could
use the feature but another prequalified candidate cannot. Excluded rows retain
query/profile diagnostics, applied weight zero and null arithmetic. Included rows
have empty reasons and applied weight 1. Every field reconstructs from source
snapshot, retained query map and the policy; supplied summaries are not authoritative.

Apply decision stages in order, stopping scoring after an unsuccessful stage:

1. Collect `snapshot_unavailable` then the query metadata reasons above. If any,
   common mask empty, no ranks/score diagnostics, unknown with those reasons.
2. If no prequalified rows, unknown with `no_compatible_profiles`.
3. If common gates fail, unknown with applicable `insufficient_common_features`
   then `insufficient_common_coverage`, no ranks/score diagnostics.
4. Score every prequalified label. Collect `no_competing_label` if fewer than two,
   `distance_exceeded` if best distance > 3, and `ambiguous_labels` if a runner-up
   exists and absolute margin < 0.25. Boundary equality passes. Preserve ranking
   diagnostics even on unknown. No reasons means `provisional_match`.

A single label is always unknown, even at zero distance. Ties are always unknown.
An unknown may have a best label for inspection but never a chosen label. No other
reason, state, score normalization or hidden gate is part of this release.

## Frozen interfaces and output bounds

```python
match_profile_snapshot(
    directory, snapshot, policy, *, query_entry_id,
    expected_split_id=None, expected_dataset_content_hash=None,
) -> ProfileMatchResult

evaluate_profile_snapshot(
    directory, snapshot, policy, *, mode,
    expected_split_id=None, expected_dataset_content_hash=None,
) -> ProfileEvaluationResult
```

Failures are `ValueError("invalid_profile_match")` or
`ValueError("invalid_profile_evaluation")`. Internal numeric failures use
`invalid_profile_match_arithmetic`; public operations wrap them without data/path
leaks. Structurally valid unsupported evidence produces unknown results rather
than inventing scores. Standalone root validation raises `ValueError` on invalid
declarations; it does not promise the linked API's fixed message.

Future commands are `match-profiles` and `evaluate-profiles`, both with required
`--directory`, `--snapshot`, `--policy`, `--output` and optional
`--expected-split-id`, `--expected-dataset-content-hash`. Match requires
`--query-entry-id`; evaluation requires `--mode` with the three exact policy modes.
Success writes canonical private mode-0600 JSON atomically, empty stdout/stderr,
exit 0. Invalid input/output gives exit 1, empty stdout and exactly
`error: <command>: invalid_input_or_output`; syntax errors give 2. Input operands,
hard-link aliases and every member of the inspected N6 directory are protected
from output replacement through pinned no-follow descriptors. Explicit unrelated
regular output may be replaced; failures preserve it and clean temporary files.
Parents must exist. No producer, network or external review path is followed.

The policy's limits apply globally before nested validation/materialization, not
only per child: 256 entries/candidates, 22 features, 64 refits, 4096 candidate rows,
5632 feature-score rows, 256 refit candidates, and 32768 refit group-value rows
and entry references each. N7's existing snapshot budgets also apply. Each root's
complete canonical bytes must fit 10 MiB; evidence is embedded once per result.
Bounds include excluded rows. An oversized request fails; do not drop entries,
folds, labels, source receipts or unknown outcomes to fit a budget. These limits apply to the implemented standalone models and pure kernels.
The linked match/evaluation operations and commands described above are not callable yet.
