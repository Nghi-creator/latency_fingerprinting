# Within-session fixture-condition experiment

`evaluation.within_session` is an opt-in method with release
`n11-within-session-condition-experiment-v1`. It evaluates recognition of later
condition blocks in the **same host research session**. Six repeated fitting
blocks remain one correlated session component and zero independent support
groups. This is not separate-session validation, broad causal diagnosis, physical
capture latency, or activation/benefit acceptance.

`fit_within_session(blocks, session_id=...)` reuses the frozen median/RMS arithmetic
of the original fixture-condition experiment while reporting the narrower scope
under its own method hash and experiment ID. There are exactly six planned fitting
blocks (partial inputs remain unavailable). All three conditions leave each
descriptive fold together. The fixed training eligibility intersection requires
17 of 22 features; failed folds are retained. All folds must uniquely recognize
their declared condition with positive gap, otherwise calibration is unavailable.
Radii are maximum correct fold distances per condition, and the minimum accepted
gap is the minimum positive training-fold gap. Repeated-block fold checks do not
estimate performance on independent sessions.

`score_within_session(query, blocks, session_id=..., query_session_id=...,
query_block_id=...)` rebuilds training, accepts no query truth, and abstains for a
different session, reused blocks/sources, incompatible partition, missing frozen
features, ties or radius/gap failures. Independent performance is always
`not_estimated_same_session_only`; diagnostic labels remain null.

`evaluation.within_session_protocol` separately validates a prospective 6 fitting
plus 6 untouched later query block protocol: all twelve declare the same host and
session, fitting precedes query, all six arm permutations appear once in fitting
and in reverse sequence for query. IDs, exclusions, method/source/image pins and
exact review subjects are checked. Drafts remain pending; declarations never
authenticate review or grant acquisition authority. Changing proposal content
changes its identity and requires a new review. The original independent-session
protocol continues to reject correlated cross-role declarations.

The producer's `withinSessionStudy.mjs` allocates all 36 plans before acquisition,
records one actual session/context and executes conditions sequentially. Source,
processor, policy, dependency and runner pins are checked. Acquisition, ownership,
cleanup, processing or pin failures retain the failed prefix and stop the entire
remaining suffix without retries/replacements. After 18 fitting acquisitions,
`experiments/within_session_study.py fit` opens only the fitting cases. The resulting
training inputs and calibration are frozen before query collection. Unavailable
calibration leaves all 18 query acquisitions unstarted. Each query score is saved
before condition truth is joined for descriptive counts. Report condition and
whole-block correct/error/abstained/unavailable counts without independent-sample
confidence intervals or generalization claims.

Frozen historical studies stay unchanged and excluded. Neither implementing this
method nor completing a same-session run closes the original separate-session or
broad N11 empirical acceptance gates.
