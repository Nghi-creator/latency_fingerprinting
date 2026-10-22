# Linked profile matching and evaluation

The N8 operations inspect one explicit [N6 dataset directory](../calibration/N6_INSPECTION.md)
and verify one supplied [N7 snapshot](../profiles/N7_COMMANDS.md) against those
actual records. Training reconstruction and query extraction share the same
inspection; neither reads a second copy of the directory. A built snapshot must
match the fresh policy, source report, selected values, profiles and counts.
Administrative lifecycle revisions may withdraw scores but cannot change a fit.

```python
from pathlib import Path
from latency_fingerprinting.profile_matching import (
    match_profile_snapshot,
    evaluate_profile_snapshot,
)

result = match_profile_snapshot(
    Path("calibration-dataset"),
    snapshot,
    policy,
    query_entry_id="validation-response",
    expected_split_id=trusted_split_id,
    expected_dataset_content_hash=trusted_dataset_hash,
)
evaluation = evaluate_profile_snapshot(
    Path("calibration-dataset"),
    snapshot,
    policy,
    mode="validation",
    expected_split_id=trusted_split_id,
    expected_dataset_content_hash=trusted_dataset_hash,
)
```

`policy` is the exact [approved provisional match policy](N8_MATCH_POLICY_SPEC.json).
Policy and snapshot accept validated models or structured payloads; copied/nested
models are revalidated. Both anchors are optional, explicit caller expectations.
No latest snapshot, external review path, producer or network source is discovered.
Failures raise `ValueError("invalid_profile_match")` or
`ValueError("invalid_profile_evaluation")` without source paths or partial scores.

## Commands

```sh
latency-fingerprint match-profiles \
  --directory calibration-dataset --snapshot built.json \
  --policy docs/profile_matching/N8_MATCH_POLICY_SPEC.json \
  --query-entry-id validation-response --output match.json
latency-fingerprint evaluate-profiles \
  --directory calibration-dataset --snapshot built.json \
  --policy docs/profile_matching/N8_MATCH_POLICY_SPEC.json \
  --mode validation --output evaluation.json
```

Both commands accept `--expected-split-id` and `--expected-dataset-content-hash`.
Evaluation requires an explicit `validation`, `final_test` or
`leave_training_group_out` mode. Ordinary matching accepts held-out response
queries; missing, baseline, training, excluded and duplicate entries produce
explicit unknown outcomes. Only a provisional snapshot can supply scores.

Success writes canonical UTF-8 JSON atomically with mode 0600 and returns 0 with
empty stdout/stderr. An unrelated regular output may be replaced. Invalid input
or output returns 1, empty stdout and exactly
`error: <command>: invalid_input_or_output` on stderr. Argument syntax errors return
2. Output parents must exist. Symlink inputs/parents and nonregular operands are
rejected. Pinned directory/file identities protect the snapshot, policy, every
inspected dataset member and their hard-link aliases from output replacement.
Failed writes preserve prior output and clean temporary files.

## Reading results

Results retain the complete dataset, inspection report and original snapshot once,
plus every candidate and score exclusion. Evaluation retains every measured entry
in the selected role. Missing records stay in global evidence/counts. Training
refits remove an entire connected source group, recompute N7 statistics and retain
unsupported candidates. Unknown predictions remain in accuracy denominators;
zero-denominator metrics are null. Resource limits fail the request rather than
truncating a cohort or silently skipping folds.

The [matching contract](N8_MATCH_CONTRACT.md),
[evaluation contract](N8_EVALUATION_CONTRACT.md) and
[standalone model guide](N8_MODELS.md) define the exact gates and retained fields.
Linked operations verify source bytes and bindings, not physical independence or
external review authenticity. Scores remain software-provisional. Synthetic N6
fixtures remain excluded and produce unknown outcomes; positive model-only tests
do not establish real acquisition quality, calibration or diagnostic accuracy.

The [runtime fixture release](N8_FIXTURES.md) exercises all commands and evaluation
modes through both the checkout and an isolated installed wheel.
