# Robust profile policy and snapshot contract

This specification freezes `n7-profile-statistics-v1`. The additive policy and
snapshot models, exact arithmetic and standalone validate/schema dispatch are
implemented; see the [model guide](N7_MODELS.md). Linked building and immutable
lifecycle operations are available through the [API and CLI](N7_COMMANDS.md).
The [policy specification](N7_PROFILE_POLICY_SPEC.json) and
[independent examples](N7_PROFILE_EXAMPLES.md) define the first release's exact
software-provisional behavior. Existing P0 and N2–N6 formats, releases, fixture
pins and `match-v2` remain unchanged.

N7 summarizes evidence-qualified **training** responses within exact N6
compatibility partitions. It does not implement profile matching, diagnosis
probabilities, live probes, covariance, automatic trust promotion or a database.
Its numerical thresholds are software gates, not scientific sample-size or
accuracy claims. No supplied real calibration set is asserted adequate.

## Roots, canonical identities and validation

The public module is `latency_fingerprinting.profiles`, with immutable
`ProfilePolicy` (`profile-policy-v1`) and `ProfileSnapshot`
(`profile-snapshot-v1`) roots. Both use snake_case and require every listed field,
including nullable fields. Unknown fields, duplicate JSON keys, nonfinite values,
boolean-to-number coercion, generators/sets in ordered containers and oversized
collections fail. Revalidate copied and nested model instances at public boundaries.

Canonical JSON uses sorted keys, two-space indentation, UTF-8, no ASCII escaping,
finite numbers and one final LF, as in N6. Hashes are `sha256:` plus 64 lowercase
hex characters. IDs append that digest without the `sha256:` prefix:

| Identity | Exact canonical hash input |
| --- | --- |
| `policy_id = profile-policy-<digest>`; `content_hash` | Full policy except `policy_id`, `content_hash` |
| `snapshot_id = profile-snapshot-<digest>`; `content_hash` | Full snapshot except `snapshot_id`, `content_hash` |
| Nested `profile_id = profile-<digest>` | Object with exactly `policy_content_hash`, `source_report_id`, `profile`; `profile` is the full candidate except `profile_id` |

Nested profile identity uses the containing policy hash and N6 source report ID.
A new policy or evidence report cannot silently reuse an old profile identity.
Administrative lifecycle revisions retain candidate IDs when their policy,
source report and statistical content are unchanged. Changing a full snapshot's
lifecycle always changes its snapshot identity. Hashes prove content identity,
not physical truth or authenticated authority.

Only the exact repository-approved policy content/version/hash is accepted;
recomputing a hash after changing thresholds does not create an approved policy.
Standalone snapshot validation reconstructs selection, all statistics, counts,
profile identities and allowed lifecycle shape from retained input values. It
cannot verify source artifact bytes or the physical truth of reviews. Linked
building must run the actual [N6 inspector](../calibration/N6_INSPECTION.md).

## Profile policy fields

The JSON policy specification is normative and contains exactly:

| Field | Meaning |
| --- | --- |
| `schema_version`, `method_release` | `profile-policy-v1`, `n7-profile-statistics-v1` |
| `policy_id`, `content_hash`, `policy_version` | Content identity and `1.0.0` |
| `parameter_provenance` | `software_provisional` |
| `calibration_method_release` | `n6-calibration-evidence-v1` |
| `registry` | Exact existing `registry_version`, `content_hash` reference |
| `response_policy_hash` | Exact existing approved N3 feature-policy hash |
| `feature_names` | Exactly the 22 N3 feature names, unique and lexically ordered |
| `selection` | Fixed input kind/role, N6 eligibility, duplicate and mixed-label rules |
| `statistics` | Fixed two-level median, raw MAD, rounding, zero and failure conventions |
| `gates` | Exact count and rational availability/coverage gates |
| `weights` | Supported `1.0`, excluded `0.0`; no learned weights |

There is no caller-controlled feature subset, covariance, scale multiplier,
imputation, clipping, scale floor, tuning rule or default policy lookup.

## Selection and source groups

Start from a complete fresh N6 linked inspection. Keep its full report, including
excluded, missing and baseline entries; never accept a caller-supplied standalone
report as proof that source files were inspected. Trusted split/dataset anchors
have N6's existing optional replay semantics and limitations.

The linked builder also checks that selected responses use the policy
registry and N3 response-policy hash; a known mismatch fails the build.

Select only entries that are all of: `response`, role `training`, N6-eligible,
nonnull label and their own duplicate representative. Candidate keys are the
unique `(partition_id, label)` pairs found in retained **training response** entries
with a nonnull label, including excluded ones. Sort keys lexically by partition
then label. Held-out labels cannot add candidates. Baselines never form response
candidates; a healthy-labelled *response* may form a healthy response candidate.

Before extracting any feature values, find `(partition_id, group_id)` pairs with
more than one label among otherwise selectable entries. Exclude every otherwise
selectable entry in that pair as `mixed_group_labels`. Labels from N6-excluded,
duplicate or nontraining entries cannot poison a selectable group. Preserve all
such exclusions and candidate keys; do not silently delete conflicting evidence.

Labels retain N6's exact closed vocabulary: `healthy`, `host_contention`,
`render_capture_slowdown`. No extra label is introduced.

One entry can contribute to exactly one candidate. Different partitions never
pool votes, even if labels or some observed settings happen to agree. Group IDs
come directly from N6 components, not window, frame, run-export or entry counts.

N7 selection reasons have this closed order; retain all applicable reasons:

1. `missing_measurements`: missing input; its sole N7 reason, values null.
2. `baseline_only`: healthy-window input; never a response vector.
3. `not_training`: measured entry's role is not training.
4. `n6_excluded`: measured entry is not N6-eligible; N6's exact reasons remain in the source report.
5. `duplicate_evidence`: measured entry has another representative.
6. `unknown_label`: response label is null.
7. `mixed_group_labels`: otherwise selectable training group/partition has conflicting labels.

An input is selected iff its N7 reason list is empty. Baseline entries may retain
`not_training`, `n6_excluded` and `duplicate_evidence` in addition to `baseline_only`.

N6 still validates all supplied artifacts, including held-out responses. N7 may
inspect all entry metadata for selection, but feature-value extraction and fitting
must access selected training responses only. Validation/final-test feature values
must not influence centers, scales, availability, weights, feature support or
candidate selection. Modifying held-out measurements can change receipt/root IDs;
it must leave fitted numerical statistics and selected source groups unchanged.

## Exact arithmetic and feature support

For each candidate/feature, take the median of eligible finite N3 normalized
values within each selected source group. Different windows with the same numeric
feature may participate; N6 duplicate exports have already been excluded. Each
nonempty group then supplies one median vote, independent of its window count.
No feature value is extracted from an excluded N3 feature; missing remains null.

Across those group medians, center is the median. Dispersion is the **raw MAD**:
median of their absolute deviations from that center. No normal-consistency
multiplier is applied. Both numbers retain N3 normalized units.

For any median: sort finite binary64 inputs; an odd count selects its middle value;
an even count takes the exact rational midpoint of the two binary64 values and
rounds once to binary64, nearest with ties to even. Absolute deviations likewise
use the exact rational difference of the stored binary64 value and rounded center,
then round once. MAD takes the median of those rounded deviations. Evaluate all
contributing deviations; do not hide an overflowing outlier because its rank would
not change the median. Bounded stdlib rational arithmetic avoids an overflowing
intermediate sum or underflow from separately halving subnormal operands.

Reject overflow/nonfinite results. Also reject when an exact nonzero midpoint or
deviation rounds to zero. Exact cancellation may produce zero; canonical computed
zeros are `0.0`. This release never clamps values or substitutes an epsilon. Raw
input signed zero may be retained for source correspondence; computed statistics
normalize its sign. With no observations, center/dispersion are null, not zero.

A feature is supported only when:

- At least 5 independent source groups contribute a value.
- Availability is at least 4/5: contributing groups divided by **all selected
  training groups in that candidate**, including groups missing this feature.
- Raw MAD is strictly positive.

Keep diagnostic center/MAD whenever there is at least one observation, even if
support gates fail. A feature's ordered reasons are `missing_measurements` (zero
observations), `insufficient_group_support` (<5), `insufficient_availability`
(<4/5, including denominator zero), `zero_dispersion` (nonnull MAD equals zero).
Retain every applicable reason. Supported means no reasons and weight `1.0`;
otherwise state is `excluded`, weight `0.0`. No scale floor is allowed (`null`).

Availability/coverage records have exactly `numerator`, `denominator`, `value`.
Value is the once-rounded rational quotient when denominator is positive, else
null. Threshold comparisons use integer cross-multiplication, not rounded ratios.

A candidate is `provisional` only with at least 5 selected training groups and
at least 17 active features out of exactly 22, also meeting active coverage >=3/4.
Otherwise it is `rejected`. Candidate reasons, in order, are
`insufficient_training_groups`, `insufficient_active_features`,
`insufficient_active_coverage`; retain all applicable reasons. These support
states do not make a candidate match-eligible or scientifically trusted.

## Snapshot fields and reconstruction

A snapshot has exactly:

| Field | Meaning |
| --- | --- |
| `schema_version`, `method_release` | `profile-snapshot-v1`, `n7-profile-statistics-v1` |
| `snapshot_id`, `content_hash` | Full snapshot identity |
| `policy` | Full approved ProfilePolicy |
| `source_report` | Full immutable N6 CalibrationReport; null for an unbuilt draft or its rejection |
| `inputs` | One ordered InputSelection per source-report entry, or empty for a draft |
| `profiles` | Ordered candidates, including rejected candidates |
| `counts` | Exact reconstruction of selection denominators below |
| `lifecycle` | Explicit current revision metadata below |
| `assurance` | `software_provisional_external_reviews_not_authenticated` |

InputSelection has exactly `entry_id`, `selected` (strict boolean), `reason_codes`
and `feature_values`. `feature_values` is null for unselected entries; selected
entries have exactly the 22 feature names mapped to finite N3 normalized floats
or null for excluded N3 features. No values from unselected entries are exported.
Retain corresponding N6 feature counts; selected maps must agree with those counts.

A candidate has exactly `profile_id`, `partition_id`, `label`, `state`,
`reason_codes`, `training_group_ids`, `selected_entry_ids`, `features`,
`active_feature_count`, `active_feature_coverage`. Group/entry lists are unique
and sorted. They must reconstruct exactly from selected inputs and source-report
metadata. `features` contains exactly the 22 approved feature names, ordered.

Each feature has exactly `state`, `reason_codes`, `weight`, `group_values`,
`contributing_groups`, `availability`, `center`, `dispersion`. Group-value records are unique and ordered by group ID. Each group value
has exactly `group_id`, `entry_ids`, `median`. Its entry list consists of exactly
the selected entries in that group with a nonnull value for this feature.
Reconstruct group medians, center, MAD, reasons, weights and all counts from the
retained input maps; no supplied summary is authoritative.

`counts` has exactly `retained_entries`, `selected_entries`, `excluded_entries`,
`selected_groups`, `baseline_entries`, `missing_entries`, `heldout_response_entries`,
`mixed_label_groups`. Excluded = retained minus selected. Selected groups count
unique N6 group IDs across selected inputs, not a sum across partitions/profiles.
Heldout response entries count validation/final-test response entries, regardless
of N6 eligibility. Mixed-label groups count conflicting `(partition_id, group_id)`
pairs, not their individual labels/windows. Draft counts are all zero.

A built snapshot with no candidates is a valid rejected build with empty
profiles; missing/baseline-only and synthetic-only datasets do not become errors
or fabricated profiles. Any numerical overflow/underflow violation is instead a
failed build with no partial accepted snapshot.

## Lifecycle and operations

Lifecycle has exactly `state`, `operation`, `parent_snapshot_id`,
`replacement_snapshot_id`, `reason_code`, `review`. IDs are required nullable
fields. A review has exactly `actor_id`, `subject_snapshot_id`,
`replacement_snapshot_id`, `reason_code`, `evidence_sha256`.
Actor uses the N6 safe-alias rule; reviews are unauthenticated declarations.
Subject must equal the actual parent's ID; replacement/reason must exactly agree
with the operation. No path is followed and no hash alone supplies authority.

Candidate `provisional`/`rejected` support facts remain unchanged during
administrative withdrawal of their containing snapshot. All revisions are immutable;
parent IDs reference history without embedding it. Never modify old files in place.

| Parent state | Operation | New state and required evidence |
| --- | --- | --- |
| None | `create` | `created`; policy only, source_report null, inputs/profiles empty, counts zero; reason `draft`, parent/replacement/review null |
| None, created, provisional, rejected, stale | `build` | Fresh N6 linked inspection; provisional iff any candidate is provisional, else rejected; reason `supported_profiles` or `no_supported_profiles`; optional parent ID, replacement/review null |
| provisional, rejected | `mark_stale` | `stale`; review and parent required; reason `method_changed`, `context_changed`, `policy_changed` or `external_review`; no replacement |
| created, provisional, stale | `reject` | `rejected`; review and parent required; reason `operator_rejected` or `evidence_rejected`; preserve original evidence/statistics |
| provisional, rejected, stale | `supersede` | `superseded`; review, parent and full validated replacement required; reason `replacement_selected`; replacement must be a different provisional snapshot |
| superseded | Any | Rejected operation; terminal historical revision |
| Any | Promote to trusted | Rejected operation; unsupported in this release |

An unbuilt draft has null source_report, empty inputs/profiles and zero counts.
It may be created or rejected by explicit review; a rejected unbuilt draft may
only be rebuilt. `mark_stale` and `supersede` require a nonnull source report.

All omitted transitions fail. Fresh build may use a new explicitly approved policy;
a draft parent must have the same policy as its build. Withdrawal/supersession
must preserve the parent's policy, source report, inputs, profiles and counts
exactly. Replacement need not share policy/context; selecting it never transfers
trust or merges incompatible profiles. Validate its full model, identity and
provisional lifecycle before recording its ID. No self-reference is allowed.

Accepted snapshot-state vocabulary is exactly `created`, `provisional`, `rejected`,
`stale`, `superseded`. `trusted` is deliberately not an accepted value. Trust needs
a separately frozen held-out validation method and explicit evidence-aware
promotion operation in a later release. N7 defines neither, so opaque receipts,
matching success, admin review or state strings cannot enable matching/trust.
Rebuilding creates a new revision; it never revives or overwrites a terminal one.

Standalone validation checks current lifecycle shape/reconstruction. Operations
also revalidate the supplied parent/replacement and verify exact preservation.
A standalone file cannot authenticate unseen history or physical acquisitions.
No ambient clock, automatic expiry/promotion or implicit current-context lookup.

## Planned APIs, commands and failure behavior

These names are frozen for implementation, not currently callable:

```python
create_profile_snapshot(policy)
build_profile_snapshot(directory, policy, *, parent=None,
                       expected_split_id=None, expected_dataset_content_hash=None)
transition_profile_snapshot(snapshot, *, operation, reason_code, review,
                            replacement=None)
```

All return immutable ProfileSnapshot. Build always re-inspects actual N6 files;
transition revalidates snapshot models and preservation but does not manufacture
new acquisition evidence. Pure numerical helpers are internal, bounded and do not
read files. No report-only shortcut or ambient policy path.

```sh
latency-fingerprint create-profile-snapshot --policy POLICY.json --output DRAFT.json
latency-fingerprint build-profiles --directory DATASET --policy POLICY.json --output SNAPSHOT.json
latency-fingerprint transition-profile-snapshot --snapshot SNAPSHOT.json \
  --operation mark_stale --reason external_review --review REVIEW.json --output REVISION.json
```

Build also accepts `--parent`, `--expected-split-id`,
`--expected-dataset-content-hash`. Transition operation choices are `mark_stale`,
`reject`, `supersede`; `--replacement` is required only for supersede and forbidden
otherwise. Create has no source dataset. Generic validate/schema export recognize
only the two new profile roots. Review is a closed nested object, not a third root.

Linked public function failures are fixed `ValueError("invalid_profile_snapshot")`
for create/transition and `ValueError("invalid_profile_build")` for build. Internal
numerical helper failure is `ValueError("invalid_profile_arithmetic")`. Model
validation retains the repository's usual ValidationError behavior.
CLI success is silent exit 0, canonical atomic private mode-0600 output. Failure
is exit 1, empty stdout and exactly `error: <command>: invalid_input_or_output`
on stderr, without supplied paths/values. Argument errors retain argparse exit 2.
Old output survives all failures. Input files and N6 dataset members cannot be
output targets; output parent must exist outside the N6 directory. Retain parent
and replacement files at distinct paths for history; there is no managed history
store or implicit discovery of other revisions. An explicit unrelated output file
may be atomically replaced on success. Reuse existing
no-follow, nonblocking bounded readers and atomic writer.

## Resource and ordering limits

JSON input/output <=10 MiB UTF-8 including LF; depth <=32. Review JSON has the same
bounded decoder but only its five fields. The approved policy has exactly 22
features. Snapshot inputs/profiles and each sorted entry/group list <=256;
features per candidate exactly 22; group_values per feature <=256. Across the
snapshot, group-value records and feature entry references are each <=22 times
the number of selected entries (<=5632). Counts are strict nonnegative integers
<=256; feature counts <=22. Rational denominators in the approved policy are
positive strict integers; observation ratio denominator may be zero only with
numerator zero and value null. Numeric feature/stat fields are finite binary64.

Use N6's exact directory/artifact/aggregate bounds for linked input. A valid N6
input whose expanded output cannot fit the snapshot limit fails atomically;
never truncate profiles, retained evidence or reasons. Rational work is bounded
by binary64 operands and these collection limits; arbitrary-precision external
numeric payloads are not admitted. All IDs, references and identities reconstruct.
Use N6 safe aliases for review actor IDs and N6 exact hashes/IDs for source links.
