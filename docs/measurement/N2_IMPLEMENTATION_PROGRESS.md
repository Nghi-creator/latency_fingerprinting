# N2 implementation progress

**Slice:** Additive observation-v2 contracts and offline adoption
**Started locally:** 2026-10-06
**Starting commit:** `6b185f5ff8f12a1b50e91e1d99c371d6e9725c9b`

## Step 0 — Preserve the N1 baseline

The starting checkout was clean. Reproduced the existing N1 quality gates on
macOS/Python 3.13.13: **924 tests pass, 91.89% branch-inclusive coverage** at the
unchanged 85% floor. Ruff lint/format, dependency consistency, four generated
schemas, canonical registry, both fixture sets, five controlled P0 artifacts,
run-001 seed and exact run-002 match bytes pass without regenerating artifacts.

Frozen SHA-256 pins remain:

| Artifact | SHA-256 |
| --- | --- |
| N1 registry v2.0.0 | `50329d193303c271194b28e9164ae8627dd257d7620174c5ab136ba209864884` |
| N1 sanitized shadow report | `295f57a6f0e0ab80f64c7323be3cd5fc4e278aac712825f0173955594513c423` |

Neither Python 3.11 nor the GitHub CLI is installed in this environment. Hosted CI
results were not retrieved in this session; cross-version/hosted verification
remains pending, separately from the passing local baseline. Reproduction commands
remain in [QUALITY_GATES.md](QUALITY_GATES.md).

## Step 1 — Freeze the observation-v2 field contract

The [field contract](OBSERVATION_V2_CONTRACT.md), design version 1.0.0, specifies:

- Independent `observation-window-v2` and `observation-v2` roots with contract 2.0.0.
- Trusted registry version/content-hash references and exact per-definition binding.
- Immutable context/settings, capture-method versions, local clocks and typed support.
- All 31 outputs with N1 summaries, analytical-candidate versus audit-only roles,
  null/zero distinctions and equal paired counter evidence.
- Explicit degraded/relief and recorded-intervention compatibility/rejection rules.
- Optional stage-local timing with no approved value-bearing methods yet;
  existing interval means and unsupported proxies are not relabeled as direct timings.
- Safe diagnostics, privacy/resource boundaries, deterministic identities and the
  Step 2/3 verification obligations.

This step is specification work. No v2 runtime model, generated schema, ingestion
command, response calculation or matcher was implemented. P0/N1 source and frozen
artifacts are unchanged. The first exit item is specified and locally reviewed;
runtime validation and adoption gates remain open. Markdown links and diff
whitespace checks pass.

## Next action

All N2 software steps are implemented below and [closed out locally](N2_SOFTWARE_CLOSEOUT.md).
The active [N3 plan](../plans/NEXT_IMPLEMENTATION_PLAN.md) now specifies the
v2 feature-policy/normalization and fingerprint/matcher slice; runtime
implementation has not started. The completed
[N2 plan is archived](../plans/archive/N2_OBSERVATION_V2_ADOPTION_PLAN.md).
Keep cross-version hosted verification pending until actual CI evidence is available.

## Step 2 — Additive strict models and schemas

**Starting commit:** `e98f228d14343ffc7e3f5c5903c7f821f5056f81`

Implemented [strict v2 models](OBSERVATION_V2_MODELS.md) in separate common/support,
window and pair modules. Two new schema roots and additive `validate` dispatch
enforce trusted registry binding, exact output inventory/meaning, immutable nested
context/settings, typed support, clock bounds, counter rate/total evidence,
recorded-intervention compatibility, safe diagnostics and unavailable-only timing.
The field specification's design revision 1.0.1 makes the implemented cross-field
clarifications explicit without altering registry meaning or P0/N1 contracts.

The 168 new synthetic contract cases include root/file/CLI round trips, schema
conformance, duplicate keys, missing/null/zero distinctions, strict finite numbers,
privacy, counter reconstruction, incompatible pairs and P0 command isolation.
Final local result: **1,092 tests pass; 92.60% branch-inclusive coverage** on
Python 3.13.13 at the unchanged 85% floor. Ruff lint/format, all six schema checks,
canonical registry, both fixture sets, registry/report pins, five controlled P0
artifacts, run-001 seed and exact run-002 match reproduction pass. Installed
dependencies, local Markdown links and diff whitespace checks pass.

Protected P0/N1 artifacts and numerical source are unchanged against the starting
commit. Schema generation wrote only the two new schema files. No raw-bundle v2
importer, normalized response, matcher adoption or new experiment is included.
Python 3.11/hosted CI verification remains pending.

## Step 3 — Offline raw-bundle adoption

**Completed locally:** 2026-10-07
**Starting commit:** `e312c6a83400baf61d541c36f7df1abb74060e5d`

Added the separate [v2 importer/command](OBSERVATION_V2_ADOPTION.md). It uses one
validated raw read plus opt-in immutable metadata, masks unsupported/unavailable
evidence, aggregates from raw rows, preserves typed support, snapshots context,
derives deterministic checksum IDs and emits privacy-limited validated v2 windows.
No P0 aggregation/conversion or matching is invoked. Existing N1 raw callers keep
their default samples/report behavior; the additive metadata path is opt-in.

The 35 new adoption cases include repeated/directory/TAR byte equality, unchanged
inputs, one read, declaration precedence, zero/reset/gap arithmetic, absent sources,
caller isolation, fixed diagnostics and repeatable public CLI boundary failures.
Local Python 3.13.13 result: **1,127 tests pass; 92.91% branch-inclusive coverage**.
Ruff, dependency consistency, six schemas, canonical registry, both fixture sets,
N1 release/report pins, five controlled P0 artifacts, run-001 seed and exact
run-002 match bytes pass. Markdown links and whitespace checks pass.

P0 adapter/model/arithmetic source, all frozen schemas, fixtures and controlled
artifacts are unchanged. N1 extraction gained opt-in metadata only; its numerical
behavior and pinned shadow output are preserved. Stage timings remain empty;
Step 4 will populate explicit unavailable evidence. No new experiment, runtime
instrumentation, normalization or matcher adoption is included. Hosted Python
3.11/3.13 verification remains pending.

## Step 4 — Explicit unavailable stage timing

**Completed locally:** 2026-10-07
**Starting commit:** `837573005014ae1ae5cc03d949a3f64d25925894`

The pure stage timing helper populates four unavailable records in Pixelated
adoption. Typed source support determines not_instrumented, unsupported_source or
source_unavailable reasons; no mean/proxy, metric declaration or window clock is
promoted into stage duration evidence. Values/methods/clock domains/statistics
remain null, samples zero. Design revision 1.0.2 records the adoption policy;
models and generated schemas remain unchanged.

Thirteen new helper cases cover every source/state association, missing support
records and immutable outputs. Existing adoption cases now assert absent engine,
unsupported encoder, source versus metric declarations, positive decode gauges
and deterministic directory/TAR output alongside explicit timing records.
Local Python 3.13.13 result: **1,140 tests pass; 92.93% branch-inclusive coverage**.
Ruff, dependency consistency, six schemas, canonical registry, both fixture sets,
N1 registry/report pins, five controlled artifacts, run-001 seed and exact run-002
match bytes pass. Local Markdown links and whitespace checks pass.

P0/N1 numerical source, models, schemas, fixtures and controlled artifacts are
unchanged. No new runtime instrumentation, value-bearing timing method, experiment,
normalization or matcher adoption is included. Python 3.11/hosted CI evidence
remains pending. Step 5 will add deterministic v2 fixtures/reproduction gates and
record the software closeout with this verification boundary explicit.

## Step 5 — Fixtures, reproduction and software closeout

**Completed locally:** 2026-10-07
**Starting commit:** `2dcc96fccb5eafcc7dc39cdeecd0c92612979bce`

Added three [deterministic software fixtures](OBSERVATION_V2_FIXTURES.md): v1
browser-only adoption, v2 engine-enabled adoption and a synthetic simulated pair.
Read-only gates compare reconstructed bytes and fixed SHA-256 pins, rejecting
missing/changed/unexpected files and pin drift. Both Python CI jobs run the new
N2 reproduction command alongside existing N1/P0 gates. Twenty-two new cases
cover both schema roots, exact CLI bytes, independent counter arithmetic, absent
source/timing evidence, incompatible registries, no-write checks and public N2
resource/CSV/TAR failures with no partial JSON or traceback.

Final local Python 3.13.13 result: **1,162 tests pass; 93.04% branch-inclusive
coverage** at the unchanged 85% floor. Ruff, installed dependencies, six schemas,
canonical registry, all three fixture sets, N1/N2 pins, five controlled P0
artifacts, seed and exact run-002 match bytes pass. Workflow commands were checked
for both jobs. Markdown links and diff whitespace checks pass.

Step 5 changes test support, new fixtures, CI and documentation only. Production
source, models, schemas, existing fixtures and controlled artifacts are unchanged
against the starting commit. [N2 software closeout](N2_SOFTWARE_CLOSEOUT.md) records
all completed software steps and the remaining Python 3.11/hosted execution gap.
The next boundary is a separately reviewed feature/normalization and
fingerprint/matcher-v2 contract. No experiment, direct timing instrumentation or
scientific diagnosis claim is added.

## Post-N2 health audit

**Completed locally:** 2026-10-07
**Starting commit:** `1554a7cd7f7af2e5b9d68d71934929bfb9f902a0`

The [health audit](N2_ARCHITECTURE_AUDIT.md) repairs reused N1 summary validation
at the N2 boundary, detaching mutable maps and revalidating nested strict values.
Four new regression cases pass. Synthetic pair source hashes now identify
canonical artificial input bytes; its snapshot pin is deliberately revised,
with numerical/settings/intervention fields unchanged. Reproduction avoids a
second reconstruction. P0 README truthfulness checks now cover their owned corpus,
with N2 documentation asserted separately. The original Step 5 test run preceded
creation of the new fixture README; the complete final tree is now verified.

Current result: **1,166 tests pass; 93.05% branch-inclusive coverage** on Python
3.13.13. All local schema, registry, fixture/pin, dependency, Ruff, controlled-artifact,
seed, exact match, Markdown-link and whitespace gates pass. Frozen P0/N1 source and
artifacts and adopted N2 snapshot pins remain unchanged. No restructuring is needed;
no additional concrete N2 blocker was found. Actual hosted/minimum-version execution,
full-limit scaling, direct timing instrumentation and v2 analytical/matcher semantics
remain explicitly outside local closeout.

## Plan transition to N3

**Updated:** 2026-10-07. Archived the completed N2 plan, preserving its historical
gates and pending hosted verification. The active next-implementation document
now contains the N3 feature-policy, response/normalization and offline fingerprint/
matcher sequence. Current navigation and historical N2-specific links are aligned;
this documentation transition does not implement N3 runtime code.
