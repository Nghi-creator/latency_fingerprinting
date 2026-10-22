# Profile-match models and standalone validation

`ProfileMatchPolicy`, `ProfileMatchResult` and `ProfileEvaluationResult` are
available from both `latency_fingerprinting.profile_matching` and
`latency_fingerprinting.models`. The [matching contract](N8_MATCH_CONTRACT.md),
[evaluation contract](N8_EVALUATION_CONTRACT.md) and exact
[approved provisional policy](N8_MATCH_POLICY_SPEC.json) define their behavior.

```python
from latency_fingerprinting.profile_matching import (
    ProfileMatchPolicy,
    ProfileMatchResult,
    ProfileEvaluationResult,
)

policy = ProfileMatchPolicy.model_validate_json(policy_json)
match = ProfileMatchResult.model_validate_json(result_json)
evaluation = ProfileEvaluationResult.model_validate(evaluation_payload)
```

Structured payloads must already come from an appropriate bounded reader. JSON
entry points reject duplicate keys, nonfinite numbers, invalid encoding, depth
over 32 and input over 10 MiB. Containers are detached and immutable; copied and
nested models are revalidated. Global candidate, feature, refit and reference
budgets are enforced before nested construction. Actual refit work is bounded
independently of supplied counts or claimed skipped-fold summaries. Complete
canonical output must also fit the byte limit; no record/fold is silently dropped.

## What reconstructs

- Exact policy approval, source dataset/report/snapshot bindings, declared N6
  lineage, roles, review-dependent exclusion flags, receipts and all content IDs.
- Total query/candidate inventories, query metadata gates, lifecycle availability,
  exact partitions, whole-component/source/receipt overlap and feature counts.
- One common feature mask across prequalified labels, every per-feature exclusion,
  absolute and standardized deviation, applied weight, exact distance and ranking.
- Absolute margin, provisional/unknown decision, ordered reasons and chosen-label
  semantics. Single-label, tied, insufficient or excessive-distance evidence stays
  unknown with diagnostics. Raw signed query zero is retained; computed zeros are
  positive. Overflow and nonzero-to-zero rounding fail rather than yielding scores.
- Complete leave-source-group-out refits using N7's existing fitting/statistic
  primitives, separate fold identities, full removed-input reasons and support
  recomputation. Original N7 snapshots and schemas remain unchanged.
- All group votes, truth/prediction exclusions, the full confusion matrix, unknown
  outcomes, failed folds, baseline/missing inventory and exact metric denominators.

Production arithmetic uses bounded exact rational binary64 operations and rounds
once per specified stage. The frozen design examples use an independent Decimal
oracle. Model-only positive test declarations are artificial; they do not represent
inspected real acquisitions. Actual frozen synthetic N6 inputs remain excluded
and produce unknown N8 declarations.

## Generic CLI and schemas

```sh
latency-fingerprint validate docs/profile_matching/N8_MATCH_POLICY_SPEC.json
latency-fingerprint validate PROFILE_MATCH.json
latency-fingerprint validate PROFILE_EVALUATION.json
latency-fingerprint export-schemas --output schemas --check
```

Validation prints the canonical validated root. Three additive schemas describe
[policy](../../schemas/profile-match-policy-v1.schema.json),
[match](../../schemas/profile-match-result-v1.schema.json) and
[evaluation](../../schemas/profile-evaluation-result-v1.schema.json). The earlier
29 schema files retain their exact bytes and behavior. JSON Schema checks shape
and local bounds; runtime models additionally reconstruct arithmetic, references,
policy approval and content identities.

## Inspection and assurance boundary

Standalone validation checks **declared retained values**. It cannot verify original
query features, original artifact bytes, physical independence, review authenticity
or unseen revision history. Embedded source metadata is not proof of fresh file
inspection. Scores remain software-provisional; accuracy/unknown-rate ratios are
reconstructed evaluation accounting, not a claim of scientific generalization.

The linked `match_profile_snapshot` / `evaluate_profile_snapshot` operations and
`match-profiles` / `evaluate-profiles` commands perform fresh N6 inspection and
verify training/query bindings from one pinned inspection; see the
[command guide](N8_COMMANDS.md). There is no trust promotion, probability
calibration or producer call.
