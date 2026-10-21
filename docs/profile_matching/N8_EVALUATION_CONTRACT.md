# Offline evaluation and source-group refits

This is part of the [N8 design contract](N8_MATCH_CONTRACT.md), with the same
policy, arithmetic, trust boundary and design-only implementation status.
`ProfileEvaluationResult` has exactly `schema_version`, `method_release`,
`result_id`, `content_hash`, `policy`, `evidence`, `mode`, `refits`, `decisions`,
`group_outcomes`, `confusion_matrix`, `counts`, `metrics`, `assurance`.
Root identities and assurance follow the match contract. Embed dataset, report
and original snapshot once in `evidence`; do not embed a full match root per query.

## Fixed evaluation modes

`mode` is required; there is no default or automatic threshold selection:

| Mode | Evaluated entry inventory | Training basis |
| --- | --- | --- |
| `validation` | Every measured N6 entry with role validation | Original verified N7 snapshot |
| `final_test` | Every measured N6 entry with role final_test | Original verified N7 snapshot |
| `leave_training_group_out` | Every measured N6 entry with role training | A separate refit for each connected response source group |

Include baselines, duplicates, failed/ineligible entries and unknown outcomes in
the ordered decision inventory; do not retain only successful classifications.
N6 missing-measurement entries have no role/group: retain them in full evidence
and `global_missing_entries`, without fabricating an evaluation assignment.
`decisions` is sorted by query entry ID and uses exactly the match decision shape.
Held-out modes have an empty `refits` list, query mode `held_out`, null excluded
and refit IDs. A training query is never accepted by ordinary held-out matching.

Never fit from validation/final-test values or adapt the frozen policy during an
evaluation call. Validation can inform a separately reviewed future policy release.
After examining final-test results, a redesign needs a fresh untouched cohort or
an explicitly exploratory account. This API neither tunes nor promotes trust.

## Leave one whole connected group out

Enumerate one fold for every training source group containing a response entry,
including groups whose queries cannot be scored. N6 components already join known
sources, sessions, acquisitions, aliases, hashes and derivations. Remove the
**whole** component, not one window, entry or export. All query windows in that
component share one refit. Training baseline-only groups have decision rows but
no classification fold. Cross-dataset leave-out is unsupported.

A refit row has exactly `refit_id`, `excluded_group_id`, `state`, `reason_codes`,
`inputs`, `profiles`, `counts`. State is `computed` or `skipped`. If the original
snapshot is unavailable, or no eligible self-representative response query exists
in the group, collect reasons in order `snapshot_unavailable`, `no_eligible_queries`.
Skipped rows retain their ID/group/reasons, with null inputs/profiles/counts; the
associated decisions remain unknown. Do not resurrect a withdrawn N7 revision.

For a computed fold:

1. Start with N7's exact metadata selection and every original input row. Append
   `leave_source_group_out` after existing N7 reasons for every input in the removed
   group. Removed feature maps are null, including otherwise selected responses.
   Other rows keep their original selection/reasons/maps. Refit from retained
   selected values only. Keep removed values in the original evidence snapshot
   solely as historical evidence, never as fitting inputs.
2. Use the original N7 training `(partition, label)` candidate inventory. Do not
   invent candidates from query labels or drop a label when its last group leaves.
3. Recompute within-group medians, centers, raw MAD, contributing groups,
   availability denominators, weights, active coverage and candidate support from
   scratch under the exact existing N7 policy. Removing a group can make support
   insufficient or MAD zero; retain those rejected candidates and failed folds.
   Share N7 statistic/fitting primitives, not a second approximate implementation.
4. Fold candidates have exactly N7's candidate fields, except their `profile_id`
   uses `profile-fold-<digest>` and the identity envelope below. They are nested
   N8 evidence, **not** N7 snapshots or promoted revisions. N7's fixed selection
   reasons and schema must not be extended to disguise a fold as a normal build.
5. Score each training query against that fold with query mode
   `leave_training_group_out`, its actual `excluded_group_id`, and the computed
   `refit_id`. Apply the ordinary gates except that training is the permitted role.
   Group overlap checks use the refitted contributing groups. Baselines/ineligible
   queries still fail their metadata gates; no fold statistics are imputed.

Refit input rows have the N7 InputSelection fields, with the one additive fold
reason described above, scoped only to N8. Their `selected` flag equals empty
reason list, and values are null exactly when unselected. Counts have exactly
`retained_entries`, `base_selected_entries`, `removed_entries`, `selected_entries`,
`excluded_entries`, `selected_groups`. Retained is all N6 entries; base selected
is original N7 selected count; removed counts every entry in the excluded group;
selected/excluded and groups reconstruct from fold rows. A removed entry may
already have been excluded; removed is not subtracted blindly from base selected.

A fold candidate hash covers exactly `policy_content_hash` (N8),
`profile_policy_content_hash` (N7), `source_report_id`, `snapshot_id`,
`excluded_group_id`, `profile` (candidate without profile_id). A refit hash covers
exactly `policy_content_hash`, `source_report_id`, `snapshot_id`, `refit` (complete
row without refit_id). Prefix the digest with `profile-fold-` or `profile-refit-`.
No identity references itself. Refit rows are ordered by excluded group ID and
candidate/input inventories use N7's ordering. Baseline-only training decisions
have null refit ID; skipped response-fold decisions also have null refit ID.
Their excluded group is still the actual group. Other training decisions refer
to their group's computed refit even if that individual query is unavailable.

## One group, one outcome

Classification units are unique N6 groups containing response entries in the
requested mode. Do not count windows, repeated exports, partitions or labels as
independent repetitions. Baseline-only groups are counted separately. Within a
unit retain all response entry IDs and use only self-representative response rows
for truth and prediction votes; N6 guarantees their representatives stay in the
same group/role/kind. Duplicate rows still appear in `decisions` and group entry IDs.

A group outcome has exactly `group_id`, `entry_ids`, `representative_entry_ids`,
`truth_label`, `truth_reason_codes`, `predicted_label`, `prediction_reason_codes`.
Group rows and both ID lists are sorted and total. Truth is a declared evaluation
label, not authenticated physical truth. Collect truth reasons `label_unverified`
if any representative has a null label or one of the policy's N6 label/effect/
binding reasons, then `mixed_labels` if nonnull representative labels differ.
With no truth reason, truth is their common label; otherwise it is null. Feature
support failure alone must not erase an otherwise declared truth label.

Prediction is their common chosen label only if **every** representative decision
is `provisional_match` with that label. Otherwise prediction is null. Collect
`entry_unknown` if any decision is unknown, then `entry_disagreement` if two or
more nonnull chosen labels differ. A repeated matching window cannot outvote an
unknown or conflicting window. All constituent scores and unknown reasons remain
inspectable. No majority vote or arbitrary tie breaking is permitted.

## Denominators and metrics

`confusion_matrix` is a closed 4-by-4 count map: truth keys are `healthy`,
`host_contention`, `render_capture_slowdown`, `unverified_truth`; prediction keys
are the three labels and `unknown`. Include every classification group exactly
once, including unavailable truths and unknown predictions. Every count is a
strict integer from 0 through 256.

`counts` has exactly `retained_entries`, `global_missing_entries`,
`evaluated_entries`, `response_entries`, `baseline_entries`, `n6_excluded_entries`,
`duplicate_entries`, `classification_groups`, `baseline_only_groups`,
`known_truth_groups`, `unverified_truth_groups`, `provisional_match_groups`,
`unknown_groups`, `correct_groups`, `incorrect_groups`, `computed_refits`,
`skipped_refits`. Entry counts except retained/global missing refer to the
mode's inventory. N6-excluded and duplicate counts may overlap. Correct/incorrect
require known truth and a nonnull prediction; unknown known-truth groups remain
in the accuracy denominator. Computed plus skipped refits equals the response
classification-group count only in leave-group-out mode; both are zero otherwise.

`metrics` has exactly `accuracy`, `unknown_rate`, `truth_coverage`, each an object
with strict integer `numerator`, `denominator` and nullable finite `value`:

| Metric | Numerator | Denominator |
| --- | --- | --- |
| accuracy | correct_groups | known_truth_groups, including unknown predictions |
| unknown_rate | unknown_groups | classification_groups, including unverified truths |
| truth_coverage | known_truth_groups | classification_groups |

Zero denominator gives null value, never zero or one. Otherwise round the exact
ratio once to binary64. No success-only accuracy or confidence percentage is
reported. Counts, matrix, ratios, refit identities, masks and every decision must
fully reconstruct from retained evidence. Review the accuracy together with
truth coverage and unknown rate; no ratio certifies diagnosis accuracy on new data.

All match-policy resource limits apply before materialization and nested parsing,
including skipped/excluded rows. Do not truncate folds or pool incompatible data
to meet a budget. Synthetic linked data remains excluded, and artificial positive
kernel vectors are not real N6 acquisitions. There is no trust-promotion receipt,
probability calibration, live probe, producer execution or automatic policy update.
