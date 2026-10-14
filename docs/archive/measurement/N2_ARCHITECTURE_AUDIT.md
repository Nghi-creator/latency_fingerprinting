# Post-N2 architecture and health audit

> Archived milestone record, retained with its original results and limitations.
> The [archived N4 plan](../../plans/archive/N4_STAGE_LEVEL_OBSERVABILITY_PLAN.md) now covers stage-level observability.

This report preserves the original post-N2 findings, counts and then-pending
analytical work. [N3 closeout](../analysis/N3_SOFTWARE_CLOSEOUT.md) now delivers
those v2 analytical/fingerprint/matching contracts. The subsequent
[post-N3 health audit](../analysis/N3_ARCHITECTURE_AUDIT.md) records current whole-tree
verification and shared bundle-reader hardening; stage instrumentation and
scientific evaluation remain pending.

**Reviewed locally:** 2026-10-07
**Starting commit:** `1554a7cd7f7af2e5b9d68d71934929bfb9f902a0`
**Scope:** Completed N2 code, models, raw adoption, fixtures, CI and current guides

N2's separation is sound: frozen P0 matching, N1 extraction/aggregation and N2
record validation/adoption have distinct responsibilities. The audit found and
fixed one N2 instance-validation boundary bug, a fixture identity gap, an outdated
test scope and stale module-guide wording. No major restructuring is justified.
This is local software verification, not proof that every possible defect or
scientific validity gap has been eliminated.

## Findings and fixes

| Finding | Consequence | Resolution |
| --- | --- | --- |
| N1 summary instances reused in N2 did not revalidate all fields | Unchecked `model_copy()` updates could admit boolean/string aggregates or retain a caller-mutable aggregate dictionary inside a frozen N2 record | Snapshot instance data and fully revalidate it at `MetricMeasurement.summary`, including nested counter intervals and map freezing |
| Synthetic pair artifact hashes were all-zero placeholders | Fixture identity did not identify its deterministic series inputs as the contract specifies | Hash canonical artificial input bytes; independently assert those bytes in fixture tests and deliberately revise only the synthetic-pair pin |
| A P0 truthfulness test recursively scanned every fixture README | Addition of the N2 README broke the complete suite because the test imposed P0-specific phrases on other fixture families | Scope the test to P0 generator-owned README files; assert N2's software/provenance notice separately |
| N2 reproduction reconstructed all records twice | CI repeated raw adoption and model validation unnecessarily | Reconstruct once for exact-byte drift, then hash the checked fixture files |
| N1 registry/arithmetic/inspection guides still called N2 adoption future work | Current readers received an outdated implementation boundary | Link delivered N2 adoption and distinguish pending v2 analytical/matcher contracts; document extraction's opt-in metadata argument |

The summary bug was reproduced before the fix: a boolean minimum was accepted,
and mutation of the supplied aggregate dictionary changed the retained record.
Four new cases reject boolean/string aggregates, detach/refreeze reused summaries
and reject an unchecked integer in a nested strict-boolean counter interval.
Tests are in [window validation](../../../tests/models/test_observation_v2.py).

The full-suite failure in the README test also exposed an original closeout
verification omission: the Step 5 run preceded creation of the new README. The
final audit reran the complete tree after the documentation scope fix. Historical
milestone counts remain recorded as historical evidence, with this correction
linked from the closeout.

## File sizes and dependency boundaries

- N2 runtime modules range from 46 to 245 lines: stage timing, adoption metadata,
  importer, common/support models and window/pair roots. They remain cohesive;
  splitting them further would add indirection without resolving a current issue.
- Shared legacy modules remain unchanged: measurement models (588 lines), producer
  v2 envelope validation (531) and aggregation (453). Future feature/normalization
  or matcher-v2 code should have separate modules instead of expanding those files.
- The largest N2 test module is 511 lines of related window-validation cases. Its
  shared builders are separate; no production code depends on test support.
- The three JSON snapshots total about 242 KB. Their size reflects full required
  summaries and interval audit evidence, including both windows in a pair. They
  are bounded test artifacts, not inflated runtime files; reducing their fields
  would weaken exact record reproduction.
- Progress and closeout documents preserve milestone history. Current guides link
  this audit rather than rewriting historical results as current test counts.

## Verification and preservation

Final macOS/Python **3.13.13** result: **1,166 tests pass; 93.05% branch-inclusive
coverage**, above the unchanged 85% floor. Ruff lint/format, installed dependencies,
six generated schemas, canonical registry, all three fixture families, N1 registry/
report pins, N2 fixture pins and five controlled P0 artifact validations pass.
Run-001 seed and exact run-002 match bytes reproduce. Both configured Python jobs
retain branch coverage and N1/N2 reproduction commands. Local Markdown links and
diff whitespace checks pass.

P0 models/adapter/arithmetic, N1 numerical source, schemas, existing raw fixtures,
reference/query fixtures and controlled artifacts remain unchanged. Adopted N2
browser/engine snapshots retain their original pins. The synthetic pair changes
only its two source-artifact hashes; summaries, support, clocks, settings and
intervention data are unchanged. Its reviewed new snapshot pin is:

`d6b96c18e0104fcd62ea2525b5637c6aadf7a033ac30d3b4e918be3ff8088954`

The [fixture guide](../../measurement/OBSERVATION_V2_FIXTURES.md) records all current pins and their
software provenance limits. Schema/contract/registry versions and valid production
adoption bytes are unchanged by the instance-validation repair.

## Remaining boundaries

No additional concrete N2 implementation blocker was found in this audit.
The remaining known work is explicitly outside the completed local slice:

- Actual Python 3.11 and hosted CI execution evidence remains pending; inspected
  workflow configuration and local Python 3.13 checks do not establish that result.
- Full-limit memory/scaling characterization and cross-producer clock evidence
  remain unverified. Existing caps and rejection regressions remain intact.
- Measured/estimated direct timing still requires reviewed producer methods and
  clock evidence. Current stages remain unavailable, with no one-way latency claim.
- V2 feature selection, coverage eligibility, normalization and fingerprint/matcher
  contracts remain separate implementation work. Scientific diagnosis validation
  still requires experiments beyond these software fixtures.
