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

Step 2 is implemented below; the next action is Step 3 offline bundle adoption.
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
