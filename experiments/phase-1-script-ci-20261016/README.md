# Script boundaries and CI hardening — 2026-10-16

This pass follows the [readiness audit](../phase-1-readiness-20261015/README.md).
It splits the remaining large utilities and fixes failure/cleanup gaps found while
reviewing them. [Structured results](results.json) retain exact source/log hashes.
No live hosted smoke, storage mutation, artwork upload or deployment was run.

## Module boundaries

The existing four command paths remain available. Staging smoke separates HTTP/auth,
catalog, storage-policy and session checks. Artwork capture separates CLI options,
catalog selection/upload, bounded image acquisition and command lifecycle. LAN smoke
separates options, telemetry, session assertions, ownership cleanup and orchestration.
Hosted pairing separates configuration, HTTP/catalog access, runtime and reporting.
The entry points are now small dispatchers; their helper modules remain focused.

Removed four unused artwork helpers left behind by the earlier upload implementation.
The new tooling TypeScript check rejects unused declarations in these paths, rather
than relying on manual discovery. The test suite checks the real helper behavior;
stale source-text assertions were replaced with behavior checks where appropriate.

## Correctness and resource fixes

- Artwork downloads and file reads have byte bounds; operator requests have deadlines.
  PNG dimensions, checksums, scanline shape and inflation output are checked before
  brightness analysis. Existing JPEG/WebP signature support remains; this is not a
  replacement for a complete image decoder or universal image-quality assessment.
- Capture timeout configuration rejects invalid values. A timed-out owned process
  receives TERM, then KILL, with bounded exit confirmation. POSIX capture process
  groups include descendants; Windows uses direct-child termination. Temporary
  workspaces are removed after success/failure, after use of the captured image.
  If exit cannot be confirmed, the private workspace is retained with a visible
  cleanup failure. Local artwork is never removed. Dry-run reports distinguish
  retained local images from temporary captures.
- LAN guests are registered for cleanup immediately after each acquisition. A later
  join failure cannot lose the earlier guests. Cleanup attempts every guest and the
  telemetry lease; success is written only after telemetry shutdown succeeds.
- Staging catalog checks distinguish permission denial from unrelated auth/network
  failures. Storage policy checks require the removal response to confirm the owned
  probe, including an attempted cleanup after a failed/ambiguous upload acknowledgement. Pairing restoration preserves a known prior pairing without deleting it
  first; failed inventory cannot justify mutation.
- HTTP bodies are bounded through consumption, not just request headers. Smoke
  diagnostics omit raw response bodies and sensitive URL parameters, redact known
  credentials/token fields, cap retained log entries/text and publish drop counts.

## CI changes

Pixelated's new reusable **Repository Quality** workflow runs the complete workspace
lint, tooling typecheck, test and build chain on Ubuntu with the pinned production
Node `24.18.0` and a Node 26 compatibility lane. Producer tests use Python 3.13.
This includes the engine regression suite, previously absent from the full hosted
contract gate. Hosted deployment now waits for that quality workflow before its
existing schema/hosted gates and deploy hooks. Workflow concurrency includes the
caller identity so standalone and reused quality/API-gate runs cannot cancel
each other. The API production dependency audit also runs before deployment.

`typecheck:tooling` also runs through normal lint, API verification and hosted predeploy.
The production Node guard remains pinned; its test explicitly permits the separate
compatibility lane. Existing security audits and desktop release checks remain.
Branch-protection settings were not changed by this local workflow edit.

Core CI builds a wheel and installs it in a clean temporary venv outside the checkout
on both configured Python versions. It verifies import location, the installed
console entry point and exact exports of all 25 frozen schemas, without editable
source-path assistance. Existing v7 checkout/setup-python actions are now pinned to
commits resolved from their published GitHub tag references; the new producer Python
setup uses the same verified pin.

## Verification and remaining acceptance

Current core verification passes **2,032 tests / 93.55% branch-inclusive coverage**.
The isolated installed-wheel check passes, as do Ruff/format and all frozen release
reproduction checks. Pixelated passes **780 Node tests**, with one existing
external-artifact skip: API 209, engine 135, web 267, desktop 92 and smoke/security 77.
The full lint/build chain, final changed API/smoke checks, browser interaction harness,
lockfile consistency, offline CLI wiring and workflow YAML syntax checks pass.

These are local Python 3.13 / Node 26 results. The new hosted workflow and its
production-Node/native Linux/minimum-Python lanes still need actual CI execution.
Earlier actual Linux and live campaign evidence keeps its original source identity.
This pass does not rerun the long fault campaigns or change schemas, fixtures,
matcher policy, thresholds or frame callbacks.

Manual desktop/game-picker/input/reconnect and trace export/cancel/retry sign-off
remain in the [acceptance ledger](../../docs/scenarios/N5_RUNTIME_ACCEPTANCE.md).
N5/Phase 1 remains open until that sign-off and final hosted verification are recorded.
Raw verification logs remain under ignored `local/phase-1-script-ci-20261016/`.
