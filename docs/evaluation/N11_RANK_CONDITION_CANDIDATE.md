# Candidate rank-condition folds

`evaluation.rank_condition_candidate` exposes a separately identified numerical
candidate, `n11-within-session-rank-condition-candidate-v1`. It is not integrated
with any acquisition protocol or runner. Existing fixture and within-session
methods keep their original identities and behavior. The candidate has synthetic
software qualification only.

`fit_rank_condition_candidate(blocks, session_id=...)` accepts the same
source-linked condition declarations as the fixture experiment. It retains
missing slots, verifies binding consistency and source uniqueness, and requires
one compatible partition, six complete blocks, and the fixed training eligibility
intersection with at least 17 of 22 policy features. Caller declarations do not
establish physical authenticity or independent support.

Each fold holds out all three conditions in one block. Its rank support is fitted
from only the other five blocks' 15 responses, without labels in the geometry.
Each training response is transformed to pooled midranks. Per-condition centers
are coordinate medians of those transformed responses. Distances are equally
weighted mean absolute coordinate differences. Exact rational rank and median
arithmetic is converted to binary64 distances before ranking and gap decisions.
The full training eligibility mask is fixed before these folds; held-out numeric
values do not contribute to fold support or centers.

A held-out value outside any frozen feature's closed fold support is unavailable;
there is no clipping, extrapolation or mask adaptation. Every fold must recognize
all three responses uniquely with positive gap. Any failed or unavailable fold
makes calibration unavailable and thresholds null, while retaining all fold
results. Otherwise full-fitting support/centers are rebuilt and reported, with
per-condition maximum correct fold radius and the minimum positive fold gap.

`score_rank_condition_candidate(query, blocks, session_id=...,
query_session_id=..., query_block_id=...)` rebuilds calibration from the original
training inputs. It accepts no truth or cached calibration. Queries abstain for
session/block/source overlap, incompatible partition, unavailable calibration,
missing frozen features, values outside full-training support, ties, excessive
radius or insufficient gap. Queries cannot update geometry or thresholds.
Output centers/support are explanatory artifacts; scoring does not trust them
as a substitute for original training data.

All outputs retain one declared correlated session and zero independent support
groups; empirical acceptance and acquisition authority are false. Condition
predictions are candidate outputs only. Diagnostic labels and confidence remain
null. Repeated folds do not estimate independent-session performance.

## Structural limitation

For every selected feature, its global minimum and maximum must each occur in
at least two distinct training blocks for all folds to remain inside support.
Otherwise the sole block containing that extreme necessarily has an unavailable
held-out response. A continuously varying feature with a unique minimum or maximum
therefore prevents calibration, even if class centers are well separated. This
is a consequence of strict support, not a software defect or evidence that more
runs would pass. The candidate needs design review before prospective use.

Rank scaling also discards magnitude and can magnify the importance of tiny
fluctuations. It cannot make equal-valued features informative or restore a
signal absent from the underlying response. See the
[geometry contract](N11_RANK_GEOMETRY.md) for numerical details and limitations.
