# N5 implementation progress

**Updated:** 2026-10-10. **Status:** Step 1 complete locally; Step 2 contract next.
**Active plan:** [N5 reproducible scenario harness](../plans/NEXT_IMPLEMENTATION_PLAN.md).
**Inherited gates:** [N4 runtime acceptance](../observability/N4_RUNTIME_ACCEPTANCE.md).

## Step 1 — Baseline and ownership inventory

Both checkouts were clean before this step:

| Repository | Starting commit |
| --- | --- |
| Core | `2a15bbfefba4a76dc5c5f7ed0e76672ecd963287` |
| Pixelated testbed | `b65eeed2fba67987610b957a82ed8a39876c5410` |

No applicable AGENTS.md was found in either repository. N5 changes so far are
plan/progress/transition documentation, not a new runtime harness, fault injection
or a measured scenario. No commit, deployment or hosted workflow was performed.

### Reproduced local software baseline

- Core Python 3.13: **1745 tests pass / 93.69% branch-inclusive coverage**, unchanged
  85% floor. Ruff lint/format, dependency consistency, twelve schemas, canonical
  registry, N1/N2/N3/N4 pinned reproduction and original synthetic fixtures pass.
  Controlled P0 records, run-001 seed and exact run-002 match are preserved.
- Producer Node 26.4.0/npm 11.17.0: 185 API, 133 engine, 245 web, 90 desktop and
  61 smoke/contract/security tests pass: **714 total**, one existing external
  mirror-artifact engine skip. All **42** nested Python trace cases pass under
  Python 3.14.4. Whole-workspace lint, lockfile consistency, API TypeScript checks
  and production web build pass.
- Actual synthetic host/browser/unsupported-API collector exports reproduce all
  pinned N4 record and summary bytes through core adoption and inspection APIs/CLI.
  These artifacts remain synthetic; their placeholder producer versions do not
  identify real captures.

### Inspected starting surfaces

| Owner | Surface | Existing behavior / N5 gap |
| --- | --- | --- |
| Core | `experiments/CONTROLLED_RUN_PROCESSING.md`, controlled-run-001/002 | Manual sanitized healthy/degraded/relief processing and P0 evidence; no N5 scheduler or held-out campaign |
| Core | `experiments/bounded_cpu_pressure.py` | Monitored experiment-only pressure, 30–300 s and 1–8 workers, explicit acknowledgement and cleanup; not a unified adapter or measured-effect verifier |
| Producer | `engine/runtime/src/runtime/processes/` and `launchers/` | Existing process/session ownership and camera launch; inspect cancellation/cleanup before reusing in an experiment runner |
| Producer | `engine/runtime/camera_trace*.py`, `camera.py` | Bounded trace lifecycle and shutdown export; no interactive fresh post-warm-up recording reset |
| Producer | `apps/web/src/features/player/observability/` | Browser callback evidence and explicit finish/export; current recording cannot restart after export without a new collector |
| Producer | `apps/web/src/features/research-mode/researchRunConfig.ts` and player research exporters | Existing healthy/degraded/relief research phases; N5 warm-up/probe/recovery/cooldown need an additive manifest, not v2 enum reinterpretation |
| Producer | `scripts/lan/`, `scripts/hosted/`, `scripts/web/` | Smoke/interaction tools and cleanup helpers; successful smoke/fault startup is not verified scenario ground truth |
| Core | `src/latency_fingerprinting/observability/`, analytical-v2 APIs | Strict offline artifacts/inspection and matching boundaries; experiment phases/actions cannot silently become N3 features |

All producer paths above are in the sibling testbed. The core must not gain a
runtime dependency on that checkout. N5 has no approved fault adapter matrix yet:
network shaping privileges, encoder/render controls and client pressure all need
actual ownership/effect inspection in Step 2. Existing smoke scripts are references,
not authorization to run live hosted calls or alter host networking in this step.

### Contract decisions required next

Freeze separate experiment identity/versioning; phase boundaries and monotonic
clock scope; requested actions versus executed/verified effects; support states;
bounded duration/worker/resource budgets; cancellation/restoration/crash recovery;
seeds and independent repeat/reference/query assignments; sanitized artifact paths,
hashes and byte/row/depth bounds. Author independent arithmetic/lifecycle examples.

N4 traces are capped at 2000 frames/10000 events across lifetimes. A multi-phase
run can exceed those ceilings at full sampling. Step 2 must declare artifact scopes
and sampling/phase budgets; never enlarge frozen N4 limits to hide overflow or
pool independently restarted clocks. Preserve earlier research phase meanings.

### Remaining runtime and verification gates

Docker and Python 3.11 are absent from the current command path. No actual Linux
Xvfb/PulseAudio capture with a draining receiver, real browser callbacks/picker,
paired overhead measurement, producer Node 24 or hosted verification was run.
The [N4 live acceptance ledger](../observability/N4_RUNTIME_ACCEPTANCE.md) retains
all criteria and the recording-control gap. N5 can address the shared runner/control
in Step 4, but its baseline does not pass those gates.

Phase 1.3 still requires at least two real single-bottleneck classes with repeated
runs and held-out queries. Existing controlled artifacts and synthetic fixtures do
not newly establish those results. Mixed/changing scenarios wait for stable single
causes; no scientific calibration or Phase 1 completion is claimed.

Documentation check: 726 core and 32 producer local targets resolve; both trees
pass whitespace checks. N4 plan/progress/closeout/audit were archived with links
updated. Normative N4
contracts, usage/integration guides, schemas and fixtures remain current.

**Next:** Step 2 scenario/phase/evidence/cleanup contract and independent examples.
