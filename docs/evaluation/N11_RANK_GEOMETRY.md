# Candidate pooled-rank geometry

`evaluation.rank_geometry` provides a numerical design candidate with release
`n11-pooled-midrank-geometry-candidate-v1`. It is not a condition classifier,
calibration method, replacement for the frozen within-session experiment, or
permission to collect data. `rank_geometry_spec()` returns its content identity.

`fit_rank_geometry(samples, feature_names=...)` fits an unlabelled training pool.
Callers supply a frozen eligibility mask; this primitive does not choose features
or authenticate which data belong to training. It accepts 2–96 vectors and 1–22
unique feature names. Additional vector fields are ignored. Every selected field
must contain a finite number; booleans, strings and missing values are rejected.

For each feature and value x, the rank is
`(count(training < x) + count(training == x)/2) / training_count`.
Duplicate values retain their frequency. A constant training feature therefore
has rank one half, without dividing by a MAD, noise estimate or epsilon. Support
is immutable and detached from the caller's input objects.

`rank_distance(left, right, geometry)` computes the mean absolute difference
between the two vectors' feature ranks. Every contribution is bounded by one;
strictly increasing changes of numerical units preserve ranks and distances
when they preserve the observed ordering and ties. Exact rational arithmetic
on the binary64 input values avoids overflow from subtraction of large finite
numbers. Returned distances are binary64.

Both vectors must lie within every feature's closed training support. Missing
fields and values outside that support return `unavailable` with explicit feature
lists and no partial distance. Non-finite or non-numeric values are invalid
inputs. Queries never update support, change the mask, or alter scale. A changed
value on a constant feature is outside support and remains unavailable.

The separate [rank-condition fold candidate](N11_RANK_CONDITION_CANDIDATE.md)
implements a synthetic-qualified wrapper around this primitive. A prospective
recognition method still needs a reviewed specification: fit rank
support inside each fitting fold, transform each training observation before
forming class centers, retain all failed folds, freeze final support and centers
before later queries, and define abstention and threshold calibration explicitly.
This module supplies none of those decisions or condition predictions. A caller
must not pool a held-out fold or query into rank support.

Rank distances discard metric magnitude and may give tiny numerical fluctuations
as much rank spread as a strong physical signal. The support rule can also cause
frequent abstention on later data. Constant features cannot separate conditions.
These limitations require prospective assessment and probe observability review;
synthetic arithmetic checks are not empirical recognition evidence. No original
missingness, provenance, timing, source-overlap or independent-session gate is
relaxed by this candidate.
