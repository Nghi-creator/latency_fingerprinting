# N2 software closeout

**Slice:** N2 — Additive observation-v2 contracts and offline adoption
**Closed locally:** 2026-10-07
**Software status:** Steps 0–5 implemented and locally verified
**Hosted verification:** Actual Python 3.11 and hosted Python 3.13 execution remains pending

The [post-N2 health audit](N2_ARCHITECTURE_AUDIT.md) records subsequent hardening
and current verification. Results below retain the original Step 5 milestone
evidence; its initial test run preceded addition of the fixture README. The audit
repairs that documentation-test scope and verifies the complete final tree.

N2 preserves the frozen N1 registry in strict additive window/pair records and a
bounded offline raw-bundle importer. Records retain typed support, clock limits,
counter interval evidence, registry binding and explicit unavailable stage timings.
Existing P0 response construction and matching continue to use v1 contracts.

## Delivered boundary

| Deliverable | Verified behavior |
| --- | --- |
| [Field contract](OBSERVATION_V2_CONTRACT.md) | Design 1.0.2; separate v2 roots with contract 2.0.0, pinned registry, provenance, support and pair semantics |
| [Strict models](OBSERVATION_V2_MODELS.md) | Immutable metadata, all 31 registered outputs, finite arithmetic, counter reconstruction and compatible recorded interventions |
| [Offline adoption](OBSERVATION_V2_ADOPTION.md) | One validated directory/TAR read, opt-in metadata, declaration precedence, deterministic IDs, privacy-limited diagnostics and canonical JSON |
| [Stage timing](../../src/latency_fingerprinting/measurement/stage_timing.py) | Four unavailable Pixelated stages with source-aware reasons; no promotion of interval means, proxies or window clocks |
| [Fixtures and reproduction](OBSERVATION_V2_FIXTURES.md) | Browser-only/v2 adoption and synthetic pair snapshots, exact-byte checks and fixed SHA-256 pins |
| [Quality gates](QUALITY_GATES.md) | Both configured Python jobs retain the 85% branch floor and P0/N1 gates, adding pinned N2 reproduction and public resource regression tests |

The public addition is `ingest-pixelated-v2`; `validate` accepts both new roots and
`export-schemas` includes their schemas. Pair assembly is a validated in-memory
constructor; N2 adds no pair-building command. `match` and `build-response` reject
v2 inputs through unchanged v1 loaders.

## Verification and preservation

Final local environment: macOS/Python **3.13.13**. **1,162 tests pass; 93.04%
branch-inclusive coverage**, above the unchanged 85% floor. N2 adds 238 cases
across model validation (168), adoption (35), timing (13) and final fixtures/public
CLI gates (22), retaining the 924-test baseline. Ruff lint/format, installed
dependencies, all six schema checks, registry export and all three fixture sets
pass. N1 registry/report pins and N2 fixture pins reproduce exactly. Five
controlled P0 artifacts validate; run-001 seed and exact run-002 match bytes pass.
Local Markdown links and diff whitespace checks pass.

Frozen N1 SHA-256 pins:

| Artifact | SHA-256 |
| --- | --- |
| Registry v2.0.0 | `50329d193303c271194b28e9164ae8627dd257d7620174c5ab136ba209864884` |
| Sanitized shadow report | `295f57a6f0e0ab80f64c7323be3cd5fc4e278aac712825f0173955594513c423` |

The [N2 fixture guide](OBSERVATION_V2_FIXTURES.md) records its three independent
snapshot pins and software provenance limitations. Fixture arithmetic tests and
the existing N1 hand-authored expectations support numerical verification beyond
snapshot equality. None of these tests establishes scientific diagnosis validity.

The N2 starting baseline is `6b185f5ff8f12a1b50e91e1d99c371d6e9725c9b`.
P0 models/adapter/arithmetic, v1 schemas, existing fixture inputs and controlled
artifacts are unchanged. N1 raw extraction gained opt-in immutable adoption
metadata; its default samples, aggregation and pinned inspection output remain
unchanged. Step 5 itself changes only new fixtures/test support, CI and docs from
`2dcc96fccb5eafcc7dc39cdeecd0c92612979bce`. Milestone evidence is retained in
[N2 progress](N2_IMPLEMENTATION_PROGRESS.md).

Run the [full local gate commands](QUALITY_GATES.md), including:

```bash
.venv/bin/python -m tests.measurement.check_reproduction
.venv/bin/python -m tests.observation_v2.check_reproduction
```

Both configured Python CI jobs include N2 reproduction. Neither Python 3.11 nor
the GitHub CLI is installed here, and hosted results were not retrieved. Workflow
inspection and local execution do not establish hosted/minimum-version success.
The [archived N2 plan](../plans/archive/N2_OBSERVATION_V2_ADOPTION_PLAN.md)
retains that verification item unchecked.

## Remaining boundaries and next work

All N2 software steps are locally complete. Actual Python 3.11/hosted execution
is the outstanding release-verification item. Existing bounded-reader tests and
reduced-cap regression cases exercise resource rejection; full-limit memory and
cross-producer scaling characterization remain future verification work.

Direct measured/estimated stage timing has no approved producer method. Window
clocks retain wall-clock-derived elapsed provenance; there is no synchronized
one-way or per-frame timing claim. New instrumentation requires reviewed meanings,
methods, clock evidence and fixtures before value-bearing timing is permitted.

The successor slice is **N3: v2 feature-policy, normalization and offline
fingerprint/matching**, specified in the [active plan](../plans/NEXT_IMPLEMENTATION_PLAN.md).
Its [Step 1 analytical specification](../analysis/N3_ANALYTICAL_CONTRACT.md) is now
complete, and [strict policy/response models](../analysis/N3_ANALYTICAL_MODELS.md)
are implemented. Pure response derivation is next. The analytical contract selects
features, establishes compatible units/registry versions, defines missing-data and
coverage eligibility, specifies response/normalization behavior, and keeps audit
totals distinct. Separately versioned fingerprint/match roots and explicit v1/v2
rejection rules are specified; their implementation remains pending. N2 supplies records;
it does not choose calibration parameters or change production matching.

No live probe, remediation, runtime instrumentation or new experiment was run.
Scientific validation and diagnosis performance remain separate roadmap work.
