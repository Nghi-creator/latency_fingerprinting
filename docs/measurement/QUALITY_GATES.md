# Phase 1 quality and CI gates

**Updated:** 2026-10-16. [Script/CI hardening](../../experiments/phase-1-script-ci-20261016/README.md),
[readiness audit](../../experiments/phase-1-readiness-20261015/README.md),
[previous audit](../../experiments/phase-1-audit-20261015/README.md),
[acceptance ledger](../scenarios/N5_RUNTIME_ACCEPTANCE.md),
[historical checkpoints](../archive/phase1/QUALITY_GATE_HISTORY.md).

## Latest actual verification

Current full-suite results and exact log hashes are recorded in the
[current verification results](../../experiments/phase-1-script-ci-20261016/results.json).
Earlier minimum-version/native Linux counts belong to their recorded baselines;
the current macOS pass and remaining hosted checks are listed separately.
The core covers P0 compatibility, N1 aggregation, N2 observation adoption,
N3 analytical matching, N4 stage reconstruction and N5 campaign inspection.
Pixelated verification covers API, engine, web, desktop, smoke/security tests,
workspace lint/builds, browser interactions and native Linux scenario/trace tests.
The branch-inclusive coverage floor remains 85%; no threshold or security
allowlist was relaxed during the audit.

## Hosted CI and remaining acceptance

[Verified hosted results](../../experiments/phase-1-audit-20261015/hosted-ci.json)
bind successful runs to exact merged commits: core `3313139` and Pixelated
`31d675a`. Core quality/minimum-Python jobs pass. Pixelated npm audits, both
engine image scans, three-platform desktop builds, hosted contracts/deployment,
auth and signed-in pairing smoke pass. These results supersede the earlier
unverified baseline entries in historical records.

The audit adds bounded-input hardening after those commits; these local changes
need their normal hosted run after merge. Normal desktop/game-picker and trace
export/cancel/retry remain the user's manual acceptance checks. Automated
browser interactions and native package smoke do not replace that sign-off.
N5 and Phase 1 acceptance remain open until the remaining evidence is recorded.

## Read-only reproduction

Run from the core checkout:

```sh
.venv/bin/python -m tests.measurement.check_reproduction
.venv/bin/python -m tests.observation_v2.check_reproduction
.venv/bin/python -m tests.analytical.check_reproduction
.venv/bin/python -m tests.observability.check_reproduction
.venv/bin/python -m tests.observability.check_browser_execution
.venv/bin/python -m tests.scenarios.check_reproduction
.venv/bin/python experiments/controlled-run-001/record_seed_fingerprint.py --check
```

Independent synthetic expectations and original fixture pins are immutable release
evidence. These commands check drift; they do not regenerate expectations or count
synthetic output as live measurements. The separate browser execution fixture
release preserves original browser v1 bytes and exclusion meanings.

## Security and resource regression boundaries

The suites exercise strict versions/fields, duplicate-safe bounded JSON, archive
membership/checksums, path and link safety, regular-file limits, monotonic scopes,
sampling and exact loss accounting, finite arithmetic, compatibility gates,
source-run exclusion and conservative `unknown` decisions. N5 adds bounded
private process ownership, cleanup/recovery, watchdogs, measured fault predicates
and detached recomputation of every retained trial.

The 2026-10-15 audit specifically adds non-object manifest rejection and
nonblocking rejection of special JSON/journal files. Invalid evidence cannot
replace an existing successful output. Valid schemas, methods, arithmetic and
measurement thresholds remain unchanged. The follow-up adds bounded compressed
legacy TAR expansion/physical metadata parsing and browser writable-stream
cleanup on failed export; its regression tests preserve public failure messages.

## Local verification commands

```sh
.venv/bin/python -m pytest --cov=latency_fingerprinting --cov-branch \
  --cov-report=term-missing --cov-fail-under=85
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m pip check
.venv/bin/python -m latency_fingerprinting export-schemas --output schemas --check
.venv/bin/python -m latency_fingerprinting export-metric-registry \
  --output schemas/metric-registry-v1.json --check
```

There are 25 generated schemas. JSON Schema checks shape and primitive bounds;
Python validators and linked inspectors establish cross-field and evidence
consistency. Original P0/N1/N2/N3/N4/N5 schema bytes and release pins are preserved.
Use the producer's [live/manual procedure](../../../Pixelated-Studio-Edition/docs/n5-live-test-procedure.md)
for desktop and exact-build evidence; versioned local research captures remain
separate from final committed-build and scientific-validation claims.


## Installed artifact and full producer CI

Both core jobs also run `python -m tests.packaging.check_wheel`: build a wheel,
install it outside the checkout in a fresh venv, verify its import location/console
entry point and compare all schema exports with the frozen files. It needs normal
package-index access for build/runtime dependencies. Existing v7 action versions
are pinned to their verified commits.

Pixelated's reusable Repository Quality workflow runs all workspaces on the pinned
production Node version and Node 26 compatibility, including engine tests on Linux.
Hosted deployment waits for that workflow. Tooling typechecks are part of normal
lint, API verification and predeploy. New lane execution remains a hosted gate;
local validation does not establish remote success.
