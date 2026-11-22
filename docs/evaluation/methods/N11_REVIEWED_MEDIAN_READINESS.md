# Reviewed median training readiness

`evaluation.median_readiness.inspect_reviewed_median_readiness` is an explicit,
read-only bridge from linked N6 inspection to the separate median-response
experiment. Release `n11-reviewed-median-readiness-v1` does not build N7 profiles,
classify a query, set thresholds, promote trust, allocate data or accept N11.

Call it with a directory containing an N6 dataset and its actual artifacts, plus
mandatory `expected_dataset_content_hash` and `expected_split_id` pins. It uses
the existing bounded, private N6 snapshot inspector; a detached caller-supplied
report cannot substitute for linked inspection. Changed bytes, stale pins and
unsupported filesystem inputs fail through the existing inspector.

Only eligible, unique N6 **training responses** enter summaries. Engineering,
retrospective, synthetic, unreviewed, invalid, duplicate, validation and final-test
evidence is excluded. Healthy baseline windows cannot become healthy *response*
profiles. Exclusions retain both N6 and selection reason codes. Mixed labels in
one connected group/partition are excluded under the existing N7 metadata selection
rule. An additional known case/run/source/response origin check rejects artificial
separation across selected N6 groups.

Every candidate is rebuilt from the verified N3 records, grouped by reconstructed
N6 component and exact compatibility partition. The existing median experiment's
five-group, 80% availability and 17/22 feature gates remain. Zero raw MAD stays
descriptive; no floor or MAD divisor is introduced. At most 16 candidate
partition/label combinations are accepted.

The report shows numeric coverage of the existing N6 label vocabulary: `healthy`,
`host_contention`, `render_capture_slowdown`. All three must have computable
summaries in one partition for `reviewed_training_summaries_available`. This is
arithmetic readiness only: even identical class centers can satisfy it. It does
not establish separation, accuracy, a decision rule, threshold calibration or
corrective benefit. Validation/final-test feature values never enter a summary.

The report pins the source dataset, split, N6 report, median method and its own
method specification. Output dictionaries are independent copies. No output is
accepted as a trusted input to a later call; inspection starts from actual files.
Existing N6 external review declarations remain **unauthenticated**; this bridge
cannot independently establish physical truth or reviewer authority.

Keep observed fixture conditions separate from diagnostic labels. An owned delay,
CPU pressure or successful cadence response does not by itself establish a broad
cause label. An absence-of-fault arm also needs independent source/context and
condition review. Never rename an inspected engineering run as prospective data or
reuse inspected calibration/confirmation data as untouched evaluation.
