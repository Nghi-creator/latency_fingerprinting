# Post-N1 architecture audit

> Archived milestone record, retained with its original results and limitations.
> The [active N4 plan](../../plans/NEXT_IMPLEMENTATION_PLAN.md) now covers stage-level observability.

This report preserves the original post-N1 findings and verification. Subsequent
[N2 closeout](N2_SOFTWARE_CLOSEOUT.md) and [health audit](N2_ARCHITECTURE_AUDIT.md)
deliver the registry binding and typed support that were pending here. The
[archived N3 plan](../../plans/archive/N3_ANALYTICAL_FEATURES_AND_MATCHING_PLAN.md) now covers analytical adoption
and offline fingerprint/matching. Strict policy/response models are delivered;
pure response derivation, v2 fingerprints and bounded repositories are implemented;
v2 compatibility, scoring and conservative matching are implemented. Additive
v2 commands and [N3 synthetic fixtures/closeout](../analysis/N3_SOFTWARE_CLOSEOUT.md)
are complete locally; actual hosted/minimum-version execution remains pending.

**Reviewed:** 2026-10-06, after N1 software closeout
**Local environment:** macOS, Python 3.13.13

The reviewed offline architecture remains coherent: bounded adapters feed strict
contracts; P0 comparability, normalization, evidence and matching remain separate
from N1 registry-driven raw aggregation. The shadow report joins the paths only
for diagnostic comparison. No major package restructuring is justified by this
review. This is a software audit, not a diagnosis-accuracy evaluation or proof
that every defect has been eliminated.

## Findings and fixes

| Finding | Consequence | Resolution |
| --- | --- | --- |
| Summary construction lacked the definition-level gauge kind restrictions | A hand-authored summary could claim a counter unit/aggregation or a reserved kind | Reject reserved kinds and incompatible gauge units/aggregations |
| Counter summaries checked numerical reconstruction but not consistent row identity | Two accepted intervals could assign different timestamps to one source row, reverse source evidence or claim an unaudited wrap | Require ordered adjacent usable endpoints, one timestamp per row and reset audit entries for wraps |
| Counter endpoint/reset/gap membership repeatedly scanned a tuple | Validation cost grew quadratically with source rows | Index rows once and use dictionary/set lookups throughout |
| Some engine envelope rejection branches lacked public-path regression tests | P0 and N1 could diverge in rejecting malformed producer envelopes without detection | Add 24 cases across both public loaders for identity, availability, clocks, schema and settings contradictions |
| Architecture tree and fixture description predated completed N1 | Readers could miss aggregation/inspection and mistake arithmetic fixtures for paired matcher cases | Update module/fixture entries, clarify fixture roles, and add an editable Mermaid view of implemented dependencies |

Eight new summary regression cases were first run against the previous code;
all eight failed because contradictory inputs were accepted. They pass with the
validation fixes. Valid summary serialization and arithmetic remain unchanged.
Tests live in [summary contracts](../../../tests/models/test_measurement_summary.py)
and [source boundaries](../../../tests/pixelated/test_source_boundary.py).

## Files and dependency boundaries

- The largest runtime module is `models/measurement.py` at 588 lines after the
  fixes; `pixelated_bundle_v2.py` is 531 and `measurement/aggregation.py` is 453.
  They have cohesive responsibilities. Keep future observation-v2 roots in new
  modules rather than expanding this shared measurement contract indefinitely.
- Aggregation repeats some chronology/cadence scanning between gauge and counter
  paths. Their missing/reset semantics differ; a shared scanner is optional
  maintenance work if another consumer needs it, not a current blocker.
- The 1,016-line N1 plan is already archived; the 445-line progress document
  preserves milestone evidence. The active N2 plan is 132 lines. Retain historical
  test counts as historical records and link subsequent audits separately.
- The largest tracked artifact is the 444 KB architecture PNG. No outsized raw
  capture or generated-code file was found among tracked files. The target PNG
  still lacks its original editable source; the implemented-path Mermaid is
  maintained in [ARCHITECTURE.md](../../ARCHITECTURE.md).
- The runtime remains standard library plus Pydantic. CLI orchestration, bounded
  I/O, adapter validation, pure arithmetic and matcher policy remain separated;
  N1 does not import the matcher into its aggregation layer.

## Verification

**924 tests pass; 91.89% branch-inclusive coverage** at the unchanged 85% floor.
Ruff lint/format, dependency consistency, all generated schemas, canonical
registry, both fixture sets, registry/report pins, five controlled P0 artifacts,
run-001 seed and exact run-002 match bytes pass. Protected P0 files remain
unchanged against baseline `b1cd7aa07eebf39629572c22cdd20428a78de826`.

The registry/report pins remain those in [QUALITY_GATES.md](../../measurement/QUALITY_GATES.md).
Cross-field validation changes introduce no schema/artifact drift. Local Markdown
file links and diff whitespace checks pass.

A non-gating local probe validated 10,000-row and 20,000-row counter summaries in
approximately 0.039 s and 0.099 s respectively, retaining the expected 60 frames/s.
This checks practical scaling after indexing; it is not a full-limit memory or
latency guarantee for a 31-output inspection report.

## Remaining gaps and next boundaries

1. Python 3.11 and hosted CI results remain unverified in this session. Both jobs
   are configured; review their actual results before claiming release coverage.
2. Global coverage does not imply complete coverage of every boundary. The legacy
   v2 bundle validator improved from 77% to 81%; remaining privacy/manifest/summary
   rejection branches are useful targets for future focused tests.
3. N2 must bind summaries to the exact registry version/hash and definition
   metadata. Standalone N1 summaries enforce internal consistency but do not
   establish registry membership or authenticate their producer evidence.
4. The shadow report currently classifies unsupported sources using extraction's
   reason strings. N2 should carry typed support states independently of rendered
   prose, as required by the [archived N2 plan](../../plans/archive/N2_OBSERVATION_V2_ADOPTION_PLAN.md).
5. Bundle byte/row limits are tested, but full-limit report memory and throughput
   are not characterized. Measure those before adopting large captures as a
   supported workload; this audit only removes the verified quadratic lookup.
6. Monotonic clock capture, unavailable stage timings, legacy zero fallbacks,
   live mutation/rollback, v2 normalization/matching and cause discrimination
   remain the documented producer/research boundaries. They require later slices
   and controlled evidence, not a package reorganization.

The historical [N1 closeout](N1_SOFTWARE_CLOSEOUT.md) remains the milestone record;
this audit records subsequent hardening without rewriting its original results.
