# Counter-specific resource projection candidate

`evaluation.counter_specific_projection.project_counter_specific_resource(source)`
is a separate offline projection, identified by
`n11-counter-specific-combined-projection-candidate-v1` and its content hash.
It produces the same nine coordinate definitions as the original combined
resource projection: three encoded-rate interval responses and six CPU resource
responses. It does not fit or score a classifier, authorize acquisition, or
establish empirical acceptance.

The encoded counter is read within a larger native snapshot that also reads
unrelated metadata. The candidate uses the actually recorded
`encoded_counter_read` bounds for the reported encoded value. Each point must
carry method `native-encoded-counter-read-brackets-v1`, the original worker clock
and basis, the identical reported counter value, and bounds wholly inside the
original snapshot. Its declared scope is
`reported_encoded_counter_only_not_other_snapshot_fields`; underlying counter
freshness remains `not_authenticated_by_read_brackets`, with no live authority.
These bounds measure the getter call, not physical capture or counter freshness.

All five phases require recorded point evidence. Missing, malformed, foreign,
out-of-envelope or differently valued points are rejected. There is no fallback
to estimated timestamps or conversion of older captures. The raw acquisition
bytes remain SHA-256 bound to the identical CPU artifact. Original snapshot,
phase, generation, ownership and runtime-context checks remain required.

The encoded read-width limit remains **100 ms**, now applied to the recorded
encoded getter. The CPU read-width limit remains **50 ms** on its own recorded
CPU reads. Duration, sample-count, sequence, gap, counter-monotonicity and
missingness checks remain unchanged. Both complete components are required;
an unavailable component yields no nine-coordinate response. No samples are
trimmed or dropped to rescue eligibility.

The original `project_combined_resource` continues to use whole-snapshot bounds
and its original identity. Existing combined-candidate fitting, scoring and study
protocols continue to select that original projection. This candidate has no
automatic adoption path. A prospective classifier/study using these new timing
semantics needs a separately identified contract and declared source; old failed
cohorts remain closed and cannot supply the unrecorded point timestamps.
