# Candidate temporal interval condition experiment

`evaluation.temporal_interval_candidate` defines
`n11-temporal-interval-condition-candidate-v1`, a separate fitting/scoring
candidate over the [temporal-rate response](N11_TEMPORAL_RATE_RESPONSE.md).
It does not alter N3, the rank candidates, any original study protocol, or a live
acquisition path. `temporal_interval_candidate_spec()` returns its identity.

## Inputs and source declarations

`fit_temporal_interval_candidate(blocks, session_id=...)` accepts one through six
planned fitting blocks. Each block maps all three original fixture condition
names to either `None` or `{acquisition, binding}`. Complete calibration requires
exactly six blocks and all three temporal coordinates in every response.
Missing slots and well-formed unavailable responses remain explicitly recorded;
malformed sources raise `ValueError`.

`declare_temporal_condition_binding(acquisition, condition=..., context_hash=...,
inspection_sha256=...)` constructs a caller declaration after external source and
condition witness review. It binds the canonical source payload hash, rebuilt
response identity, condition, context hash and inspection artifact hash. Fitting
recomputes every projection and binding, rejects reused source payloads, worker
clocks and inspection hashes, and requires one common context hash. The context
should bind source/image, source protocol, host/session and compatible setup;
condition-specific fault settings belong in condition declarations, not context.

A declaration does not authenticate context, acquisition or witness inspection.
Raw-byte custody, source qualification and linked producer receipt review remain
external requirements. Clock uniqueness prevents reuse; it does not establish
independent sessions. All blocks belong to one declared correlated session with
zero independent support groups.

## Interval fitting

Each fold holds out a complete block and fits centers from only the other five
blocks. Each condition center is the coordinate-wise median of lower endpoints
and median of upper endpoints, using exact rational arithmetic. No coordinate
selection, epsilon, scale fitting, clipping or interval midpoint is used.

For query interval `[aL,aU]` and center interval `[bL,bU]`, the absolute-distance
enclosure is:

- lower: `max(0, aL−bU, bL−aU)`;
- upper: `max(abs(aL−bU), abs(aU−bL))`.

Average these bounds across all three coordinates. The coordinate box can ignore
shared-rate dependencies and therefore be conservative. These enclosures inherit
the response's declared rate sensitivity assumptions; they are not statistical
confidence or guarantees about arbitrary source lag or counter bursts.

A condition is robustly unique only when its **upper** distance is strictly below
the **lower** distance of every rival. The robust gap is the minimum rival lower
distance minus that upper distance. Overlapping distances abstain, even when
midpoints would favor a condition. There is no requirement that a query lie
inside observed rank support.

All 18 fold responses must robustly select their declared condition. Any failed
or ambiguous fold makes calibration unavailable and thresholds null, retaining
all fold results. Otherwise the per-condition radius is the maximum correct fold
upper distance, and the minimum gap is the minimum positive robust fold gap.
Full-fitting endpoint medians are then reported as centers. Repeated-block folds
are fitting diagnostics, not independent performance estimates.

## Query scoring

`score_temporal_interval_candidate(acquisition, blocks, session_id=...,
query_session_id=..., query_block_id=..., context_hash=...)` rebuilds the entire
training calibration and the query projection. It accepts no truth or cached fit.
It abstains for a different session/context, reused block/source/worker clock,
unavailable calibration or response, ambiguous distance intervals, excessive
upper distance, or a robust gap below the frozen fitting minimum. Queries never
change centers, thresholds or coordinate selection.

Outputs keep diagnostic labels/confidence null, accepted diagnostic groups and
independent support groups zero, and acquisition authority/empirical acceptance
false. A complete software test or retrospective fitting result does not approve
collection or establish prospective recognition, broad diagnosis, probe benefit,
N9 clock authority or physical capture latency. Preserve rational JSON integers
losslessly when storing or transporting artifacts.
