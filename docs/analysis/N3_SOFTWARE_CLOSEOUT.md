# N3 software closeout

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
| [Contract and policy](N3_ANALYTICAL_CONTRACT.md) | 22 registered primary features; exact provisional policy identity/hash, eligibility and compatibility rules |
| [Strict models](N3_ANALYTICAL_MODELS.md) | Separate policy/response/fingerprint/match roots; immutable revalidated evidence; four additive schemas, ten total |
| [Response derivation](N3_RESPONSE_DERIVATION.md) | Signed primary-value changes, explicit floors, retained exclusions/confounders and deterministic IDs |
| [Fingerprints and repositories](N3_FINGERPRINTS.md) | Declared labels/provenance, reconstructable vectors, 17/22 software threshold, bounded fail-closed loading |
| [Matching](N3_MATCHING.md) | Structural compatibility, finite weighted RMS residual evidence, all comparisons, stable top-five ranking and conservative unknowns |
| [Commands](N3_COMMANDS.md) | Three additive read-only commands, explicit policies, privacy-limited failures and bounded complete output |
| [Fixtures](N3_ANALYTICAL_FIXTURES.md) | 19 synthetic snapshots, independent numerical expectations, full-byte hashes and reproduction in both configured CI jobs |

Local Python 3.13.13 verification: **1,520 tests pass; 93.58% branch-inclusive
coverage**, above the unchanged 85% floor. N3 adds 354 tests to the post-N2 baseline
of 1,166: 94 strict models, 30 derivation, 62 fingerprint/repository, 76 matching,
52 commands and 40 closeout cases. Ruff lint/format, installed dependencies, all
ten schemas, registry export, four fixture families and all three reproduction
modules pass. Five controlled P0 artifacts validate; run-001 seed and exact run-002
match bytes reproduce. Whole-tree Markdown links and diff checks pass after adding
fixture READMEs and closeout documentation.

The original N3 baseline is `06e697105e918c0c2f3ae2d25bf75c833f7982ad`.
Step 7 starts at `b5224cb17409ff28640960b060134471a6fd3cfe`. It adds snapshots,
test support, CI gates and docs, and hardens only v2 repository root opening.
Pinned N1 registry/report and N2 browser/engine/synthetic bytes are preserved.
[The fixture README](../../fixtures/analytical-v2/README.md) retains all 19 separate
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

N3 is locally closed out. The [completed implementation plan](../plans/NEXT_IMPLEMENTATION_PLAN.md)
retains its gates and pending hosted item until a successor is selected, then should
be archived. The [broader roadmap](../plans/FULL_IMPLEMENTATION_PLAN.md) still has
Phase 1 observability/experiment-foundation work and later scientific evaluation.
Review a successor's scope against those remaining boundaries before replacing
the completed N3 plan.
