# Pre-Phase 2 cross-repository audit — 2026-10-17

The reviewed software gaps are fixed. Verification passes **2,035 core tests with
93.56% branch-inclusive coverage** and **800 Node tests** across Pixelated's API,
engine, web, desktop and smoke tooling. One existing engine test skips unavailable
local curated-game mirror artifacts. This is a software audit, not new live
acquisition or final Phase 1 acceptance.

[Structured results](results.json) record baselines, source/log hashes, verification
and remaining gates. Raw logs are retained in ignored
`local/pre-phase-2-audit-20261017/`.

## Findings fixed

| Area | Gap | Change and regression evidence |
| --- | --- | --- |
| Campaign integrity | A positive, nonoverlapping acquisition interval could be shorter than the execution in its linked bundle. | Require the acquisition duration to cover the final phase and cleanup endpoint. A one-nanosecond acquisition now rejects and preserves an existing CLI output. |
| Overhead acceptance | Endpoint presence counted as a usable queue/encode pair even when the end preceded the start. | Count only exact-correlated pairs with nonnegative elapsed time. Separate queue and encode regressions cannot pass nominal capture or overhead acceptance. |
| Cloud downloads | The exclusive file stream's error listener was installed only after an HTTP response, allowing an early file-open error to go unhandled. Failure cleanup could remove a destination the download did not create. | Wait for exclusive file ownership before transport, install file listeners immediately, preserve an existing destination, close before removing partial files, and clean up synchronous transport failures. |
| Download watchdog | DNS resolution preceded the transport deadline and could stall indefinitely. | Bound DNS resolution and spend the remaining monotonic deadline on transport. A stalled DNS regression rejects without creating an artifact. |
| Process telemetry | Health and interval sampling duplicated Linux counter parsing; health parsing assumed single spaces and could return malformed numeric readings. | Share one whitespace-safe, nonnegative safe-integer parser. Exercise parenthesized process names, repeated whitespace, invalid counters, missing processes and invalid uptime. Remove the unused `readNumberFile` export. |

The three core evidence regressions were also run against temporary copies of the
original modules: all three fail before the changes. All pass on the edited tree.
Download tests additionally cover successful completion and artifact validation.
No original schema, fixture pin, feature meaning, scoring policy or effect
threshold was changed. The README reading-order numbering was corrected.

## Audit coverage

Review covered the core's bounded file/JSON/archive inputs, campaign and overhead
evidence linkage, timing reconstruction, measurement aggregation, compatibility
and matching decisions; producer download/cleanup and telemetry lifecycle; API
authorization/CORS and rate-limit boundaries; web research recording/export;
and repository test/build/security workflow wiring. Full suites exercise the
broader API, web, desktop, engine and maintenance scripts.

The process-counter implementation was consolidated where the semantics overlap.
Frozen legacy/v2 contracts and independent producer/consumer recomputation remain
separate because they protect compatibility and detect drift. Historical failed
captures and versioned fixtures remain useful evidence. This pass does not claim
that every module received an exhaustive line-by-line review.

## Verification

- Core full suite, Ruff lint/format, dependency consistency, all 25 schemas and
  canonical registry checks pass.
- Pinned N1/N2/N3/N4/browser/N5 reproduction and the controlled-run seed check pass.
  The installed wheel imports outside the checkout and exports identical schemas.
- The retained 18-trial campaign-8 and selected-workload overhead-9 reports
  reproduce byte-for-byte under the hardened inspectors.
- Pixelated full workspace suites, lint/tooling typechecks and builds pass.
  The final engine suite passes 147 tests, with one existing artifact skip;
  API/web/desktop/smoke pass 210/267/92/84 tests.
- API verification and hosted contracts pass, including actual browser interactions
  and the two-certificate TLS isolation test.
- Fresh full-dependency npm audits report zero vulnerabilities for all five
  lockfiles; the packaged desktop build-chain audit passes.

Current execution uses macOS, core Python 3.13.13 and Node 26.4.0. A fresh Linux,
minimum-Python 3.11 or pinned-Node-24 run, CodeQL/image scans, release packaging and
production smoke were not performed here. Those remain normal hosted/platform
checks for these changes. No remote state or Git history was changed.

## Remaining acceptance and manual checks

Before closing Phase 1, record normal desktop/game-picker, input/reconnect and
trace export/cancel/retry outcomes in the
[acceptance ledger](../../docs/scenarios/N5_RUNTIME_ACCEPTANCE.md), and obtain the
normal hosted checks for both edited trees. Existing campaign/overhead evidence
does not establish diagnosis accuracy, generalization or recovery benefit.

For the changed producer behavior, download a normal approved cloud game and
confirm it boots; simulate an unreachable artifact host and confirm the attempt
fails within its deadline and can be retried. Check engine health and research
telemetry while playing: valid memory/CPU readings remain available and exited
processes become unavailable. Automated tests cover destination collisions and
malformed `/proc` input without modifying live game files.
