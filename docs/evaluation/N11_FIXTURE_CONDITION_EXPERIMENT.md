# Blocked fixture-condition recognition experiment

`evaluation.fixture_conditions` implements the separate opt-in
`n11-fixture-condition-block-experiment-v1`. Its predictions name only
`no_injected_fault`, `owned_identity_delay` or `owned_cpu_pressure`. These are
bounded fixture states. They do not mean broad healthy, capture-latency or
host-contention diagnosis. Existing N6/N7/N8/N11 contracts and defaults are unchanged.

## Bound inputs and assurance

A training mapping contains 1–32 declared block aliases. Every block has exactly
the three condition keys. Each slot is `{response, binding}`, or `None` for an
unavailable acquisition. One original validated N3 response contributes per
condition/block; repeated rows cannot add votes. Every condition in the same block
is removed together in a calibration fold. Mixed conditions within a block are
intentional in this version; original N7 mixed-label exclusion remains unchanged.

`declare_fixture_condition_binding(response, condition=..., witness_acquisition_sha256=...,
witness_inspection_sha256=...)` creates an explicit **declaration**, not a truth
inspector. Its closed fields bind the condition, response/comparison case, both
original N2 source hashes and native acquisition/inspection hashes. Callers must
first inspect the actual predeclared assignment, whole-phase owned witnesses,
source/phase links and cleanup using the source-bound producer procedure. A detached
hash or this declaration helper does not authenticate that inspection.

The numerical APIs revalidate N3/policy/binding consistency, one compatibility
partition, unique witness identities and no known source/run/case/response reuse
across slots. Block names, physical independence, session boundaries and witness
reviews remain caller declarations requiring review. Synthetic inputs can exercise
arithmetic; they cannot establish empirical truth or acceptance. Neither API
allocates acquisitions or approves collection counts.

## Calibration and abstention

`fit_fixture_condition_experiment(blocks)` requires at least six complete blocks
for calibration, leaving at least five groups per condition in every fold. Missing
slots retain the block and make calibration unavailable. Six is an arithmetic
prerequisite, not statistical power or collection approval.

Select a single feature mask from eligibility across **all training slots**, in
canonical feature order. It contains only features available in every training
response and must include at least 17/22. This stricter complete mask preserves
query comparability and the existing five-group/80% support gates in every fold;
missing values never become zero. Freeze the mask before distance calculations.
Mask selection uses training eligibility only. These calibration folds do not
provide an unbiased independent performance estimate.

For each held-out block, rebuild all three condition centers from the remaining
blocks using one response per block, median centers and equal-weight RMS in the
existing unscaled N3 normalized units. Raw MAD is descriptive, never a divisor or
floor. Existing staged binary64 arithmetic rejects overflow/nonzero underflow.
Retain all three queries per fold. Every fold must be uniquely correct with a
strictly positive runner-up gap; otherwise retain the failed folds and return
unavailable thresholds. Do not omit failures, change the mask or extend the data
until a fit appears.

When all folds succeed, each class radius is its maximum correct held-out distance,
and minimum gap is the minimum positive runner-up gap over all folds. Refit centers
on all declared training blocks. These empirical extrema are not confidence bounds;
a tiny positive gap or zero-radius fit does not establish practical utility.

`score_fixture_condition_experiment(query_response, blocks, query_block_id=...)`
takes no query truth label and rebuilds calibration from original inputs. It rejects
known training block/source overlap, incompatible partition and missing fixed
features. A unique nearest condition is returned only within its class radius and
at or above the calibrated minimum gap. Otherwise abstain with explicit reasons.
No detached fitted result can substitute for original training inputs. Output
mutation therefore cannot alter a later score. A constant training class can have
radius zero; a small fresh deviation then abstains without adding an epsilon.

## Interpretation and study integration

Reports pin the method/median/N3 specifications, binding receipts, source origins,
feature mask, all folds and thresholds. Conditions sharing a work session stay
correlated; new container IDs do not establish independent blocks. The fixed mask
cannot be adapted using evaluation data. Prospective untouched complete blocks and
frozen counts/targets are needed before any evaluation claim.

All outputs retain `diagnostic_label: null`, zero accepted diagnostic groups and
`acquisition_authority: false`. Prediction confidence is unavailable. A fixture
condition prediction is an experimental numerical result under caller declarations,
not authenticated truth, N6 trust, corrective benefit, independent generalization
or broad N11/Phase 2 empirical acceptance. Current inspected engineering runs must
remain excluded from prospective training/evaluation. Keep original N7 findings as
the original-method comparison, including unavailable results rather than relaxing
its group/dispersion rules.

These APIs rebuild calibration on the offline/slow path. Keep them outside media
callbacks and live dispatch loops.
