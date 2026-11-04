# Median-response engineering experiment

`n11-median-response-experiment-v1` is a separately versioned, explicit SDK
experiment. It does not replace N7, enter the N11 study runner, accept N6 groups,
classify causes, or promote trust. Existing N7/N8 releases, policies and schemas
retain their original meanings. There is no automatic acquisition or dispatch.

The experiment tests whether robust response centers can remain numerically
usable when within-profile MAD is zero. It retains N3's normalized response units
and uses equal-weight RMS distance without dividing by learned dispersion. This
is a different method, not a successful N7 profile or an epsilon correction.

## Rebuilding engineering summaries

```python
from latency_fingerprinting.evaluation.median_response import (
    median_response_method_spec,
    summarize_engineering_responses,
    compare_engineering_responses,
)

spec = median_response_method_spec()
summary = summarize_engineering_responses(
    {
        "run-group-001": [response_001],  # validated AnalyticalResponseV2 inputs
        "run-group-002": [response_002],
        "run-group-003": [response_003],
        "run-group-004": [response_004],
        "run-group-005": [response_005],
    }
)
```

Every response is revalidated under the existing pinned N3 policy. Invalid or
confounded responses fail. Every profile must have one exact N6 compatibility
partition; different source versions/settings/probes cannot be pooled. Group
aliases are explicit and bounded. Known shared response IDs, comparison cases,
run IDs or source content hashes cannot be split across declared groups. This
conservatively requires globally distinct case/run identities across groups.
It does not authenticate independent acquisitions, labels or original raw files.
Use the original source inspection/adoption procedures for those links.

Repeated responses within one group collapse. Eligible responses contribute one
median per group for each feature. Across group medians, center is the median
and raw MAD is retained as descriptive evidence. A feature needs at least five
contributing groups and 80% availability over all declared groups. A summary needs
five groups and 17/22 numeric features (also at least 3/4 coverage) to be computable.

Unlike N7, positive MAD is not required for numeric evidence. Exact constant
values remain numeric, including zero. A missing/excluded response never becomes
zero. A majority tie can produce zero MAD without all values being equal:
`[-1, 0, 0, 0, 1]` has MAD zero and three unique values. `unique_group_values` makes
that distinction explicit. No dispersion floor or rescaling is introduced.
`computable` describes arithmetic availability, not empirical profile support.

The output includes the complete hash-pinned method specification, response IDs,
source origins, group values, availability, centers and descriptive raw MAD. The
method hash changes when the experimental contract changes. No detached summary
is accepted as a trusted comparison input; every comparison rebuilds its inputs.

## Distance evidence and limits

```python
comparison = compare_engineering_responses(
    query_response,
    {
        "candidate-a": candidate_a_groups,
        "candidate-b": candidate_b_groups,
    },
)
```

Candidate names are aliases, not accepted cause labels. Inputs are limited to 16
candidates and 256 aggregate response rows. Source overlap between candidates
fails, and a query sharing any known training origin cannot be scored. At least
two source-disjoint computable candidates must share the query's exact partition.
All compared candidates use the same feature intersection with the query, requiring
17/22 numeric features and 3/4 coverage. Incompatible/unavailable summaries remain
visible. A lone candidate cannot establish diagnostic contrast.

For each common feature, compute absolute binary64 difference, rounded square,
rounded mean of squares and its square root. Difference/square/mean stages use
exact rational arithmetic followed by one binary64 rounding. Reject nonfinite,
overflow or nonzero-to-zero underflow; do not silently lose a residual. Raw MAD
is never a divisor. Feature contributions and candidate distances are retained.
Identical centers or equal best distances report unavailable contrast.

Even `distances_available` emits no diagnosis, acceptance threshold, confidence or
chosen label. A tiny positive gap is not a scientifically useful gap. Stable
centers, a large gap or successful synthetic tests do not establish held-out
accuracy, causality, independent truth or probe utility. A classifier, governed
N6 selections, prospective calibration/validation and study integration require
separate contracts and evidence.

This is a project-specific experimental combination, rather than a claim to
implement a standard nearest-centroid classifier. For statistical context,
[R documents raw MAD](https://stat.ethz.ch/R-manual/R-patched/RHOME/library/stats/html/mad.html).
The official [nearest-centroid documentation](https://scikit-learn.org/stable/modules/generated/sklearn.neighbors.NearestCentroid.html)
distinguishes mean/Euclidean from median/Manhattan centers; the median/RMS choice
here is explicit and remains subject to prospective evaluation.

## Pacing contrast preflight

```python
from latency_fingerprinting.evaluation.median_response import pacing_contrast_preflight

old = pacing_contrast_preflight(prior_fps=30, target_fps=24, delay_us=50_000)
candidate = pacing_contrast_preflight(prior_fps=30, target_fps=24, delay_us=37_500)
```

This pure check models only the upper throughput ceiling of a serial per-buffer
delay. It uses exact rational arithmetic and requires target/prior within 24–60
FPS and no more than 20% cadence reduction. A modeled crossing requires
`target < 1_000_000 / delay_us < prior`; equality is insufficient.

At 50,000 us, the ceiling is 20 FPS, below both 30 and 24. The period midpoint
37,500 us has a ceiling of 80/3 FPS between them. That candidate is determined
from the cadence periods, not a rate search. It is a proposed new protocol,
not a change to any retained acquisition or the original native pacing fixture.
Native overhead may erase the modeled crossing; measured initial/relief progress,
complete source support, ownership and cleanup must be checked prospectively.
The function always reports measured contrast/utility unavailable and acquisition
authority false. It grants no setter or production capability.

The additive [counter/contrast bounds APIs](N11_COUNTER_CONTRAST_BOUNDS.md) require
explicit extra-period assumptions and preserve worker read brackets for guarded
finite-window analysis. They do not fit overhead from this cohort, revise an old
pilot, substitute for primary N3 clocks or create diagnostic acceptance.
