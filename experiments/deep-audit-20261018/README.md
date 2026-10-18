# Deep cross-repository audit — 2026-10-18

This follow-up fixes two core validation gaps, companion HTTP/WebSocket cleanup,
and companion health-probe bounds. It also removes duplicated proxy helpers and
repairs two links to a deleted document.

[Structured results](results.json) bind the baselines, edited sources and local
verification logs. Raw logs are in ignored `local/deep-audit-20261018/`.

## Findings and fixes

| Area | Finding | Fix and regression |
| --- | --- | --- |
| Pacing declarations | `50000.0` was accepted for the fixed integer `delay_us`, although the producer rejects it. | Reuse the existing strict-integer validator before literal validation. Valid schema bytes and fixture pins remain unchanged. |
| Overhead ownership | Evidence could declare producer-capture provenance with a synthetic runtime, or the reverse. | Enforce the runtime/provenance relationship already used by experiment manifests. Test both mismatches and detached rejection. |
| Companion proxy | Upstream errors after headers attempted a second response; response-stream errors were unhandled; HTTP/WebSocket disconnects could leave upstream work open. | Handle both stream directions, cancel abandoned work, return a generic 502 only before headers, and close partial responses otherwise. Preserve buffered output on graceful WebSocket closure. |
| Companion health | The inactivity timeout did not bound the entire probe, bodies had no byte cap, and response-stream errors were unhandled. | Add a total deadline and 64 KiB cap, handle aborted/error responses, and close resources on settlement. |
| Maintenance | Proxy token/header/path helpers duplicated companion utilities. Docs linked a deleted auto-merge guide. | Reuse shared helpers; link the current workflow and enforced policy. No remote setting was changed. |

Before-fix checks show three core failures, seven proxy failures, an unhandled
health-stream error and two health tests timing out. All those regressions pass
after the fixes. A real loopback integration test also sends and receives a complete
128 KiB streamed upload through the HTTP proxy.

## Verification

- **Python 3.13.13:** 2,038 tests pass, with **93.56% branch-inclusive coverage**.
- **Python 3.11.17:** all 2,038 tests pass in a new isolated environment, plus
  N1/N2/N3/N4/browser/N5 reproduction and schema/registry checks. This environment
  resolved Pydantic 2.14.1; the existing 3.13 environment uses Pydantic 2.13.4.
- Ruff lint/format, dependency consistency, original release pins, controlled-run
  seed and isolated installed-wheel checks pass. All 25 schema exports match.
- Retained live campaign-8 and selected-workload overhead-9 reports still
  reproduce byte-for-byte under the edited core.
- **Node 24.18.0 and Node 26.4.0:** workspace tests pass. Final per-workspace counts
  are API 210, engine 147, web 267, desktop 106 and smoke/security 84: **814 passes**,
  plus the existing unavailable curated-game-mirror skip.
- Workspace lint/tooling checks and production-Node builds pass. API verification,
  hosted browser interactions and the actual two-certificate TLS test pass.
- Fresh npm audits across all five lockfiles, packaged desktop build-chain audit
  and the installed core Python advisory audit are clear.

The review also inspected research artifact linkage, trace loss/clock semantics,
matcher compatibility and arithmetic, producer worker ownership, cloud-download
lifecycle, API auth/session boundaries, browser trace collection, IPC trust and
workflow gates. Independent core/producer arithmetic and versioned contracts
remain separate intentionally. This is a focused deep review with whole-repository
verification, not an exhaustive proof for every possible failure.

## Remaining platform and manual gates

Execution here is on macOS. Docker's configured daemon socket is absent. No fresh
Linux image/native-runtime validation, hosted CodeQL/image scan, release packaging
or production mutation was performed. Local Node 24 and Python 3.11 verification
closes those local runtime coverage gaps; hosted Linux/platform lanes still need
to run for these patches.

Manual acceptance remains: desktop/game-picker/input/reconnect flows and trace
export/cancel/retry. For these fixes, restart the engine during companion requests
or streaming: the desktop should remain responsive, health checks should settle,
and reconnection should work. Complete a normal LAN stream and upload as well.
Record outcomes in the [acceptance ledger](../../docs/scenarios/N5_RUNTIME_ACCEPTANCE.md).

Changes are left unstaged. No Git history, remote workflow setting, fixture pin,
measurement threshold, matching policy or live capture was changed by this pass.
