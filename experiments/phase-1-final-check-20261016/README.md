# Final Phase 1 cross-repository check — 2026-10-16

Reviewed clean baselines core `a82bbaf` and Pixelated `6d17e98` after the
[script/CI pass](../phase-1-script-ci-20261016/README.md).
[Structured results](results.json) identify the exact baselines, changed source,
verification logs and remaining gates.

## Findings and fixes

Two hosted smoke defects were reproduced before fixing them. A game with several
native builds could pass catalog selection but return an earlier unsupported build
or one without a launch manifest. Selection now returns the same build that meets
the supported-runtime and manifest criteria, including across catalog pages.
Navigation errors and console text could retain magic-link credentials embedded
in a URL. Text redaction now removes URL user information, query and fragment,
matching the existing network-log policy. Three new regressions cover these cases.

No core implementation change or further structural split was warranted. The
tracked Python/TypeScript/JavaScript source and test inventory has no files at
600+ lines; the largest are the cohesive core measurement contract (588) and
producer scenario test module (543). No unused-file deletion was justified by this
pass. Historical plans, contracts, fixtures and failed trials remain evidence.
Current handoff documents now link this result and distinguish historical Docker
captures from current availability.

## Verification and limits

- Core: **2,032 tests**, **93.55% branch-inclusive coverage**, Ruff and formatting.
- Pixelated: **783 Node tests**, one existing external-artifact skip; all workspace
  lint/typechecks/builds, browser interaction harness and offline CLI wiring pass.
- All five current npm audit scopes report **zero vulnerabilities**; the desktop
  build-chain advisory gate passes.
- All 25 schemas, registry and P0/N1/N2/N3/N4/browser/N5 release checks pass.
  A freshly built wheel installs outside the checkout and reproduces all schemas.
- Both repositories' workflow YAML parses; local Markdown file targets resolve.
  This is configuration validation, not an actual hosted workflow result.

These are macOS Python 3.13 / Node 26 results; nested producer Python tests use
host Python 3.14. The Docker 29.0.1 client is present at its bundled path, but its
configured daemon socket is unavailable. Python 3.11 is absent from PATH. No new
Linux/minimum-version run, live campaign, hosted mutation or deployment occurred.
Prior exact-build live and hosted receipts retain their original scope.

The remaining acceptance work is final hosted CI and the user's desktop/game-picker,
input/reconnect and trace export/cancel/retry sign-off, recorded in the
[acceptance ledger](../../docs/scenarios/N5_RUNTIME_ACCEPTANCE.md).
N5/Phase 1 remains open until those results are supplied. Raw logs are under
ignored `local/phase-1-final-check-20261016/`.
