# N5 software closeout

**Recorded:** 2026-10-12. **Outcome:** delivered local software; runtime acceptance pending.
[Progress](N5_IMPLEMENTATION_PROGRESS.md), [runtime ledger](N5_RUNTIME_ACCEPTANCE.md),
[active plan](../plans/NEXT_IMPLEMENTATION_PLAN.md).

Steps 1–7 deliver strict additive experiment contracts, bounded producer lifecycle,
fresh recording control, concrete healthy/owned CPU adapters, fixed integer effect
predicates, sanitized deterministic export, independent detached inspection and
read-only fixture reproduction. Step 8's software/runtime/hosted outcomes are
published here. The original snapshot below predates live campaigns; current
[acceptance](N5_RUNTIME_ACCEPTANCE.md) records campaign-8 passing 18/18 trials and
selected-scene overhead passing. The additive browser execution method also passes
local software/live checks; final desktop/hosted gates remain open.

The clean closeout baseline is core commit
`75447e87fca9bee66d7e3bc21001bdb20d3bac9f` and Pixelated commit
`4d3f768d89fe4b2440e0eb8a1d1c4d04e5a18422`. Both trees were clean before this
closeout. These identify the delivered Step 7 implementation, not the subsequent
uncommitted closeout documentation and not a real capture build.

The table records the original software-closeout snapshot. Current live execution
uses Docker Desktop Linux and has retained real acquisitions; consult the
[runtime ledger](N5_RUNTIME_ACCEPTANCE.md) for current outcomes.

| Original closeout outcome | Evidence and limit |
| --- | --- |
| Core local software | Step 7 full suite: 1,950 passed, 93.77% branch-inclusive coverage; Ruff/format and dependency checks pass |
| Producer local software | Step 7 full suite: 716 Node passed; 109 nested Python passed; existing external-artifact and Linux idle-child skips retained |
| Local builds | Step 7 workspace lint/lockfiles, engine build, API typecheck and production web build pass |
| Frozen compatibility | Fifteen schemas, registry, P0/N1/N2/N3/N4 pins and synthetic N4 producer API/CLI reproduction remain unchanged/current |
| N5 synthetic integration | Release 1.0.0: eight independent cases, exact raw producer member parity and canonical API/CLI results; synthetic provenance only |
| Live availability | Step 8 actual preflight on Darwin returns runtime_unavailable, no resources acquired; initial PATH check missed Docker Desktop |
| Real fault campaigns and N4 overhead | Not run; [acceptance ledger](N5_RUNTIME_ACCEPTANCE.md) retains concrete dependencies/gates |
| Actual minimum versions, container and hosted execution | Unverified; configured jobs are not observed results |

This closeout adds documentation and availability evidence, with no new runtime
implementation or changed thresholds. Full regression counts above are the actual
Step 7 run, not a claim that those suites were rerun solely for documentation.
Current schema/pin reproduction and documentation links are checked at closeout.

The normative guides stay current. Progress and the N5 plan remain active while
runtime acceptance is open; the approved plan calls for archival on the subsequent
slice transition. No N6 plan or completed Phase 1 claim is introduced here. Finishing
local software cannot substitute for real measurements or real validation of the
second fault class required by Phase 1.3.

## Coding scope correction and subsequent extension

The initial closeout covered the Step 1–7 libraries and synthetic handoffs. It did
not deliver an end-to-end campaign entry, second fault class or automated overhead
workflow. [Campaign/pacing workflow](N5_CAMPAIGN_WORKFLOW.md) now implements those
missing coding surfaces with additive contracts and independent tests. The latest
results are in [progress](N5_IMPLEMENTATION_PROGRESS.md); the original Step 7
counts above remain historical. Live acceptance still requires actual execution.
