# N3 software closeout

> Archived milestone record, retained with its original results and limitations.
> The [archived N4 plan](../../plans/archive/N4_STAGE_LEVEL_OBSERVABILITY_PLAN.md) now covers stage-level observability.

**Slice:** N3 — V2 analytical features and offline fingerprint/matching
**Closed locally:** 2026-10-08
**Software status:** Steps 0–7 implemented and locally verified
**Hosted verification:** Actual Python 3.11 and hosted Python 3.13 execution remains pending

N3 delivers a separate auditable v2 analytical path from immutable N2 observations
through an approved feature policy, responses, declared fingerprints and conservative
matching. Existing P0/N1/N2 meanings, schema bytes, controlled artifacts and pins
remain unchanged. The [final architecture audit](N3_ARCHITECTURE_AUDIT.md) includes
the repository ancestor-replacement fix and the complete fixture documentation.

| Delivered surface | Meaning |
| --- | --- |
| [Contract and policy](../../analysis/N3_ANALYTICAL_CONTRACT.md) | 22 registered primary features; exact provisional policy identity/hash, eligibility and compatibility rules |
| [Strict models](../../analysis/N3_ANALYTICAL_MODELS.md) | Separate policy/response/fingerprint/match roots; immutable revalidated evidence; four additive schemas, ten total |
| [Response derivation](../../analysis/N3_RESPONSE_DERIVATION.md) | Signed primary-value changes, explicit floors, retained exclusions/confounders and deterministic IDs |
| [Fingerprints and repositories](../../analysis/N3_FINGERPRINTS.md) | Declared labels/provenance, reconstructable vectors, 17/22 software threshold, bounded fail-closed loading |
| [Matching](../../analysis/N3_MATCHING.md) | Structural compatibility, finite weighted RMS residual evidence, all comparisons, stable top-five ranking and conservative unknowns |
| [Commands](../../analysis/N3_COMMANDS.md) | Three additive read-only commands, explicit policies, privacy-limited failures and bounded complete output |
| [Fixtures](../../analysis/N3_ANALYTICAL_FIXTURES.md) | 19 synthetic snapshots, independent numerical expectations, full-byte hashes and reproduction in both configured CI jobs |

Local Python 3.13.13 verification: **1,520 tests pass; 93.58% branch-inclusive
coverage**, above the unchanged 85% floor. N3 adds 354 tests to the post-N2 baseline
of 1,166: 94 strict models, 30 derivation, 62 fingerprint/repository, 76 matching,
52 commands and 40 closeout cases. Ruff lint/format, installed dependencies, all
ten schemas, registry export, four fixture families and all three reproduction
modules pass. Five controlled P0 artifacts validate; run-001 seed and exact run-002
match bytes reproduce. Whole-tree Markdown links and diff checks pass after adding
fixture READMEs and closeout documentation.

These counts preserve the original Step 7 milestone. The
[follow-up health audit](N3_ARCHITECTURE_AUDIT.md) records subsequent arithmetic
and shared-reader repairs, added regression cases and current verification.

The original N3 baseline is `06e697105e918c0c2f3ae2d25bf75c833f7982ad`.
Step 7 starts at `b5224cb17409ff28640960b060134471a6fd3cfe`. It adds snapshots,
test support, CI gates and docs, and hardens only v2 repository root opening.
Pinned N1 registry/report and N2 browser/engine/synthetic bytes are preserved.
[The fixture README](../../../fixtures/analytical-v2/README.md) retains all 19 separate
N3 full-file pins. The approved policy's self-excluding hash remains:

`sha256:96457b318cc714f3d9d0d63a35b12548f6e030b10057b2c8e5a3a77e352fe1af`

```bash
.venv/bin/python -m tests.measurement.check_reproduction
.venv/bin/python -m tests.observation_v2.check_reproduction
.venv/bin/python -m tests.analytical.check_reproduction
```

Both configured Python jobs run the full coverage suite and N3 reproduction;
CI never refreshes artifacts/pins to make gates pass. Python 3.11 and the GitHub CLI
are unavailable in this local environment, and no actual hosted results were
retrieved. Minimum-version/hosted verification remains an open release item.

Software checking does not establish diagnosis accuracy, calibrated thresholds,
causal labels, cross-node transfer or actual relief efficacy. Producer evidence and
labels remain declarations; retained vectors/hashes require full-repository
verification to check external references. No new live probe, remediation, direct
stage instrumentation or controlled experiment was run. Stage timings remain
unavailable under N2's explicit timing contract.

N3 is locally closed out. Its [archived implementation plan](../../plans/archive/N3_ANALYTICAL_FEATURES_AND_MATCHING_PLAN.md)
retains completed gates and the pending hosted item. The active
[N4 plan](../../plans/archive/N4_STAGE_LEVEL_OBSERVABILITY_PLAN.md) addresses stage-level observability
without changing N2/N3 meanings. The [broader roadmap](../../plans/FULL_IMPLEMENTATION_PLAN.md)
still has Phase 1 scenario-harness work and later scientific evaluation. N4 is
planned, not implemented.
