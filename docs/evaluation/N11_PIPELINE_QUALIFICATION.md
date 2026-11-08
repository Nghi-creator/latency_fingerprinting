# Engineering pipeline qualification

The pipeline can work even when a recognition method cannot distinguish classes.
Qualification therefore separates valid collection and computation from accuracy.
It does not admit engineering cases to a study or replace held-out evaluation.

The producer's `pipelineQualification.mjs` composes the bounded single-process
condition collector with `experiments/qualify_resource_pipeline.py`. Its fixed
schedule is twelve complete blocks, three conditions each: six fitting blocks
followed by six query blocks. Fitting uses all six condition permutations once;
query order reverses those block orders. Every case has a fresh excluded
engineering ID and a frozen source, plan, dependency set and configuration hash.
One correlated host session is recorded; no independent groups are inferred.

Passing requires all 36 acquisitions to complete without retries, source-bound
restoration and resource inspection, 108 SDK/CLI phase equalities, and complete
nine-coordinate counter-specific responses. Missing or ineligible measurements,
export mismatches, changed source or failed execution stop the remaining suffix.
A new configuration does not resume an old failed attempt.

The separately identified `counter_specific_candidate` uses the recorded getter
projection, retaining exact nine-coordinate interval arithmetic and the original
all-eighteen-fold calibration gate. It accepts zero within-condition dispersion
without dividing by MAD or inventing a denominator. Legacy combined methods and
their frozen results remain unchanged. See the
[counter-specific projection contract](N11_COUNTER_SPECIFIC_PROJECTION.md).

The original Python fitting bytes are saved and hashed before the first query
acquisition. Each query is scored without supplying its expected condition, plan
or control receipt to the scoring command. Original prediction bytes are retained.
Fitting and every prediction must replay byte identically before qualification.
Source and dependency identities are checked through the end of processing.

An unavailable calibration is a valid computational result. In this engineering
drill, all later query acquisitions still exercise export, projection and
abstention. Their predictions must explicitly abstain for unavailable calibration.
This differs from the prospective study rule that leaves queries unstarted; the
engineering route never changes that study rule. Wrong predictions and genuine
ambiguity do not fail pipeline qualification. A fitting/scoring exception does.

The durable supervisor enforces an outer time cap; per-case acquisition, action,
fault and cleanup budgets remain the existing condition recipe. Every terminal
outcome, failed prefix and unstarted suffix is retained. Readonly custody replay
and container cleanup are checked after the run. A successful qualification is
evidence for this exact source and contained fixture, not a guarantee that future
runs cannot fail, nor evidence of diagnostic accuracy or broad N11 acceptance.
