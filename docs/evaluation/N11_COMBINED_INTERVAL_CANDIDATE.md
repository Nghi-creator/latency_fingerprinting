# Candidate combined encoded/resource interval method

`evaluation.combined_interval_candidate` defines the opt-in release
`n11-combined-resource-interval-condition-candidate-v1`. It combines the separate
encoded-rate and CPU-resource response candidates under its own identity.
`combined_interval_candidate_spec()` returns the fixed specification. Neither N3
nor an existing experiment or acquisition protocol adopts this method implicitly.

## Source binding and projection

`evaluation.combined_resource_projection.project_combined_resource(source)`
requires exactly `acquisition_json` (the original UTF-8 JSON text) and
`resource_artifact` (parsed `resource-observation.json`). It enforces a 2 MiB raw
input limit and strict JSON parsing. Raw-byte SHA-256 must match the auxiliary
artifact, whose CPU samples and window summaries must exactly match embedded
raw samples, including integer representations. Altering JSON whitespace without
updating the artifact is rejected. Canonical payload and raw-byte identities are
both recorded.

The source must use the explicit resource method/mode/role. The runtime image,
software hash, platform and architecture are recorded as a compatibility identity.
The projector validates one generation-bound controller clock context before its
samples, the separate worker clock, source-local phase containment and complete
reference/native samples. It rebuilds encoded and CPU responses from those
samples; supplied cached responses are never used. Sample schemas, fixed quota,
file lifetime, counters, ordering and availability rules remain those of the
underlying response contracts. Unknown resource context events are rejected.

The resource source's encoded projection has a separate identity while retaining
the original encoded response arithmetic. The original condition-source public
projector still requires its original source method and keeps its specification.
The new private arithmetic seam does not relabel a resource acquisition as an
ordinary condition source.

This projector is not a substitute for the producer's independent condition and
resource inspector. Before admitting data, replay raw-file custody, frozen source
hashes, producer inspection and the byte-bound auxiliary export through the
operator tools. Python consistency checks cannot authenticate execution or a
caller's claimed witness review. Resource counters and encoded counters retain
different source clocks; no cross-clock subtraction or N9 latency authority is
introduced.

## Fixed coordinates and fitting

Every response requires all nine interval coordinates:

- encoded `degraded_vs_healthy`, `relief_vs_degraded`, `post_vs_healthy`;
- CPU quota-fraction differences for degraded minus healthy, relief minus degraded
  and post minus healthy;
- throttled-seconds-per-wall-second differences for the same three comparisons.

Unavailable component responses make the entire combined vector unavailable.
There is no subset scoring, midpoint replacement, epsilon, clipping, rank support
check, fitted scaling or feature selection. Coordinates are equally weighted;
therefore six resource coordinates contribute two-thirds of the distance and
three encoded coordinates one-third. These are differently interpreted response
units; the fixed weighting is a candidate design choice requiring prospective
assessment, not an empirically optimal scale.

`declare_combined_condition_binding(source, condition=..., context_hash=...,
inspection_sha256=...)` records caller declarations after external inspection.
It binds condition, declared setup context, inspection hash, raw-byte/payload
identity, rebuilt response and measured runtime compatibility. Bindings do not
verify their own authority. The declared setup hash should bind source/image,
recipe, host/session and compatible environment, excluding condition-specific
fault settings. The measured runtime identity is also checked automatically;
using the same declared hash cannot hide an image/software/platform change.

`fit_combined_interval_candidate(blocks, session_id=...)` accepts one through six
planned blocks. Each maps all three original fixture conditions to either `None`
or `{source, binding}`. It rebuilds every source and binding, rejects source,
worker/controller clock or inspection reuse, and requires one declared setup and
measured runtime context. Missing slots and unavailable responses are retained.
Exactly six complete compatible blocks are needed for calibration.

Each fold holds out a whole block and forms condition centers using only the
other five. Centers are exact rational coordinate-wise medians of lower and
upper interval endpoints. For query `[aL,aU]` and center `[bL,bU]`, absolute-distance
bounds are `max(0,aL−bU,bL−aU)` and `max(abs(aL−bU),abs(aU−bL))`. Average these bounds
across all nine coordinates. The box enclosure ignores shared-rate dependencies
and can be conservative; these sensitivity envelopes are not confidence bounds.

A condition is uniquely robust only if its upper distance is strictly below
every rival lower distance. The robust gap is the smallest such separation.
All 18 fold responses must robustly select their declared condition. Any failure
or ambiguity leaves calibration unavailable and thresholds null, retaining all
folds. Otherwise class radii are maximum correct fold upper distances and the
minimum gap is the minimum positive robust fold gap; full-fitting centers are
then reported.

## Query and acceptance boundaries

`score_combined_interval_candidate(source, blocks, session_id=...,
query_session_id=..., query_block_id=..., context_hash=...)` rebuilds original
training calibration and the query source. It accepts no truth or cached fit.
Different session/setup/runtime, reused blocks/payloads/either source clock,
unavailable calibration/response, ambiguous distances, excessive radius or
insufficient gap cause abstention. Queries cannot update centers, coordinates,
weights, support or thresholds.

All outputs retain one declared correlated session, zero independent support and
accepted diagnostic groups, null confidence/diagnostic labels, and false empirical
acceptance/acquisition authority. Engineering sources remain excluded from study
fitting and evaluation. Software and source compatibility do not establish
prospective recognition, broad diagnosis, physical capture latency, probe benefit
or independent-session acceptance. A separately reviewed prospective protocol and
truth-free execution path are still required before study collection.
