# Phase 1 pre-manual audit, 2026-10-15

**Outcome:** identified input/dependency/documentation gaps fixed; automated checks
pass. User desktop/game-picker and trace-export sign-off remain pending.
[Structured results](results.json), [hosted receipts](hosted-ci.json),
[current acceptance ledger](../../docs/scenarios/N5_RUNTIME_ACCEPTANCE.md).

The audit starts from core `3313139` and Pixelated `31d675a`, with clean working
trees. It reviews measurement/analytical compatibility, finite arithmetic,
strict contracts, archive/file safety, private ownership and cleanup, pacing
watchdogs, browser timing/export, evidence reproduction, dependency security,
tests/builds and current documentation. The local changes after those baselines
require their normal hosted CI after merge; successful baseline runs are not
presented as tests of uncommitted fixes.

## Fixed findings

| Finding | Result |
| --- | --- |
| Non-object experiment manifest | Reject before version dispatch; return the fixed API/CLI error and preserve an existing output. Ten independent root/container cases reproduce the earlier failure and verify the fix |
| Generic JSON special-file input | Open nonblocking where supported, validate the actual descriptor as a regular file, retain size/read bounds, and close it on failures. Named-pipe/device regressions verify bounded rejection |
| Private journal/worker FIFO | Open nonblocking before existing file type, permissions and ownership validation. Regression subprocesses previously timed out; both poisoned paths now fail without a writer |
| Remaining moderate dependency advisory | Update compatible `fast-copy` from 4.0.4 to 4.2.0 in root/API locks; all scopes now have zero full/production npm advisories |
| Stale active docs | Record exact successful CI baselines, fix active-roadmap links and 25-schema counts, update manual handoff, and archive repeated historical quality checkpoints |

The dependency finding is documented in the
[maintainer's advisory](https://github.com/advisories/GHSA-jggr-w7fw-pc2j).
No audit exception, effect threshold, capacity bound or versioned method meaning
was relaxed. Original valid artifact/schema/fixture bytes remain unchanged.

## Verification

- Core Python 3.13 and actual Linux Python 3.11: **2,015 passed, 93.61% coverage**
  each. Ruff/format, dependency check, 25 schemas, registry and all frozen
  P0/N1/N2/N3/N4/browser/N5 reproduction checks pass.
- Pixelated full Node baseline: **732 passed**, one existing external-artifact
  engine skip. Final changed API/engine checks also pass. Full workspace lint and
  API/engine/web/desktop builds pass; automated browser interaction harness passes.
- Actual Linux producer: **79 scenario and 58 trace tests pass, no skips**.
  Node 24 Linux passes all **259 web tests**.
- Actual producer synthetic archives reproduce independent N4 v1, browser v2
  and N5 v1 raw records and API/CLI summaries exactly. These are interoperability
  checks, not new live acquisitions.
- Current core re-inspection of retained campaign-8 and selected-workload
  overhead-9 reproduces both published canonical reports byte-for-byte. The
  passing 18-trial cohort, original failures and browser live evidence are retained.
- Both merged baselines have successful hosted jobs. Pixelated includes npm
  audits, native/libretro image security, three-platform desktop validation,
  hosted API/web contracts and auth/pairing smoke. Core includes quality and
  minimum Python. Full job/commit identities are in the linked CI receipts.

Raw local logs and before/after regressions remain in ignored
`local/phase_1/phase-1-audit-20261015/`; the structured record publishes hashes without
private process identities or runtime journals. Existing live evidence and its
original source labels are not rewritten.

## Structure and remaining scope

The production modules already separate acquisition, validation, arithmetic,
matching, tracing, orchestration and export. No broad source restructure was
warranted in the reviewed Phase 1 surfaces. The active quality guide was condensed
and its step-by-step history moved to the
[explicit archive](../../docs/archive/phase1/QUALITY_GATE_HISTORY.md). Existing
contracts, release fixtures and historical failure evidence remain available.

This audit does not claim that tests prove absence of every defect, that fault
verification is classifier accuracy, or that browser timing is physical display
latency. It adds no new cause family, calibrated confidence, live remediation or
fast frame scheduler. Normal desktop/picker/export checks remain the final user
acceptance task; the audit fixes need ordinary hosted CI after merge. N5 and
Phase 1 remain open until those outcomes are recorded.
