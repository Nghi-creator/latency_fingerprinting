# N3 v2 compatibility, scoring and matching

**Delivered:** Step 5, 2026-10-08
**Contract:** [Analytical field contract](N3_ANALYTICAL_CONTRACT.md)
**References:** [V2 fingerprints and repositories](N3_FINGERPRINTS.md)

`match_response_v2(response, policy, repository)` is a pure, separate v2 API.
It revalidates the query, explicit policy and every full fingerprint before making
any decision, including when the query is analytically invalid. Unknown releases,
malformed records, duplicate IDs and arithmetic/resource failures raise errors.
Incomplete evidence and conservative decisions remain typed analytical results.
The P0 matcher, its defaults and its reproduction bytes remain unchanged.

```python
from pathlib import Path
from latency_fingerprinting.analytical.matching import (
    match_response_v2,
    verify_match_repository_v2,
)
from latency_fingerprinting.analytical.repository import load_fingerprint_repository_v2

repository = load_fingerprint_repository_v2(Path("references-v2"))
result = match_response_v2(response, response.policy, repository)
verify_match_repository_v2(result, repository)
```

## Compatibility and eligibility

Ordered compatibility rejections cover audit status, registry, policy, provenance,
capture method, clock meaning, structural context, probe and effective settings.
Only `software_checked` references can become candidates. Context comparison ignores
contextId, nodeId and networkScenario; structural workload/classes/versions remain
required. Concrete run/window/artifact IDs and clock domain identifiers do not
establish compatibility. JSON comparisons distinguish booleans from numbers.

After compatibility, the sorted shared eligible feature intersection must meet
both policy thresholds: at least four features and coverage >=0.75 of all 22
policy features. Thus scoring needs at least 17 shared features. Failure retains
`shared_feature_count` and/or `feature_coverage` in order. Every unshared policy
feature retains ordered `query_excluded` and/or `reference_excluded` evidence.

## Scoring and conservative decisions

Residuals are query normalized value minus reference normalized value. Positive
weights come exclusively from the approved policy. Sorted-feature `math.fsum`
reconstructs weighted squared residuals and shared weight. Distance is weighted
RMS; match strength is `1 / (1 + distance)`. A residual is conflicting only when
its absolute value exceeds 0.5. Conflict contribution is its weighted squared
residual share, or zero for an entirely zero residual sum. These are software
similarity diagnostics, without calibrated causal confidence.

All scored comparisons remain in the audit map. Ranking uses distance then
fingerprint ID, and retains only the first five summaries. The top-two strength
margin uses all scored candidates; a singleton has null margin. Same-label
candidates still compete. Decisions use this exact priority:

1. invalid_response;
2. no_fingerprints;
3. no_compatible_fingerprints;
4. insufficient_features;
5. weak_match when best strength <0.8;
6. ambiguous_margin when a present margin <0.1;
7. conflicting_evidence when best conflict contribution >=0.5;
8. matched, accepting the best caller-declared label.

Unknown results have no accepted label. Threshold comparisons use reconstructed
floating-point values without an epsilon adjustment. Arithmetic overflow fails
explicitly. No current time, random IDs or file writes enter matching.

## Result validation and repository verification

`MatchResultV2` is exported from `latency_fingerprinting.models`. It embeds the
query, sorted unique fingerprint IDs/content hashes, partitioned comparisons and
rejections, complete comparison evidence, ranking, decision and a fixed
`software_similarity_not_causal_confidence` notice. Its deterministic ID hashes
query response ID, policy hash and sorted repository references.

Runtime root validation reconstructs comparison calculations, exclusions, ranking
and decisions. Evidence query/reference values and policy weights are exact;
computed arithmetic uses the contract's 1e-12 relative/absolute tolerance. Both
input and output maps are detached and immutable, and supplied model instances
are revalidated. Limits are 128 repository/comparison entries, 22 feature entries
per comparison, five ranked summaries and 10 MiB canonical output.

Retained vectors and reference hashes cannot authenticate external fingerprints
by themselves. `verify_match_repository_v2` reproduces the entire result against
full fingerprints, checking hashes, vectors, labels and compatibility rejections.
Use it when verifying a stored result against a supplied repository. Producer
provenance and bottleneck labels remain declared evidence.

The additive [match-result-v2 schema](../../schemas/match-result-v2.schema.json)
brings schema exports to ten roots; generic `validate` accepts the result. The
existing `match` command remains v1. Step 6 will add `build-response-v2`,
`build-fingerprint-v2` and `match-v2` commands. Separate synthetic snapshots and
pins belong to Step 7.

76 new matching/model tests cover independent numerical expectations, unknown
priorities, compatibility, strict JSON equality, coverage, threshold boundaries,
conflicts, ties/truncation, finite arithmetic, forged results, immutable inputs,
repository-backed verification, resource limits and fresh interpreter imports.
[Progress](N3_IMPLEMENTATION_PROGRESS.md) records local results and separately
pending Python 3.11/hosted verification.
