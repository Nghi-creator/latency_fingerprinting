# Phase 1 follow-up readiness audit — 2026-10-15–16

This pass starts from core `93ae7b6` and Pixelated `4dfd368`, following the
[pre-manual audit](../phase-1-audit-20261015/README.md). It reviews both repositories
for safe extension, source/test size, unused surfaces, documentation drift and
remaining boundary failures. The [structured results](results.json) record the
final checks and exact source/log hashes.

## Findings and changes

**Legacy compressed research archives:** the adapter previously limited compressed
input and logical TAR members, but the standard TAR decoder could expand compressed
padding/metadata or recursively interpret GNU extension headers before those
limits applied. A focused archive module now bounds expanded bytes, declared
physical contents and physical header count before TAR interpretation. LZMA
also has a decoder memory bound. Plain TAR, gzip, bzip2, XZ, LZMA-alone and ordinary
PAX metadata remain covered; original contract and release bytes are unchanged.
Malformed compression stays a normal bundle error. Existing public member-limit
error wording is preserved.

**Browser save cleanup:** a failed writable `write` or `close` previously fell
through to browser download/cancellation without aborting the temporary write.
The save path now attempts `abort` before continuing, while preserving successful
saves, cancellation and download fallback behavior. Eight regressions cover write,
close and abort failure, cancellation and unsupported/unavailable writers.

**Structure:** the 851-line API fake mixed storage/auth state, table query behavior
and RPC simulation. It is now 181/255/428-line modules with the existing public
fake entry point. The 452-line engine telemetry module now separates response
parsing and CSV encoding from collection/sample creation (289/94/76 lines),
preserving its public exports and serialized output. The 738-line scenario adapter
test file now separates camera hooks, effects, worker lifecycle and reusable fakes.
All 32 original test methods remain, with independent unittest discovery.

**Stale setup and retention:** removed an unused, immediately overwritten manifest
construction from the overhead tests. Source import/reference checks found no
orphan production modules requiring deletion. All existing documentation has an
incoming reference; all repository-local Markdown targets resolve. Versioned
fixtures, useful regression tests, historical plans and failed live runs remain
needed evidence. The 1,020-line archived N1 plan remains historical; the largest
core production module (588 lines) is a cohesive measurement contract. Neither
needs arbitrary splitting to meet a line-count target.

## Verification and boundaries

The structured results contain current core/Node counts, coverage, full workspace
lint/build results, browser interaction smoke, current npm audit counts and release
reproduction. The new archive regressions exercise all supported compression forms,
expanded padding, recursive metadata chains, corrupt streams and excessive LZMA
memory declarations. The refactored scenario suite preserves its test inventory.

All 25 schemas, registry and P0/N1/N2/N3/N4/browser/N5 pins remain current. Actual
producer synthetic archives continue through the independent core checks. Current
inspectors reproduce the retained passing campaign-8 and selected-workload
overhead-9 reports byte-for-byte; this pass does not rerun the long campaigns or
reinterpret their outcomes as diagnosis accuracy.

Current execution is macOS. The Docker application/daemon is unavailable in this
pass; earlier actual Linux Python 3.11, Node 24 and native scenario/trace results
remain historical evidence for their recorded versions. This pass does not claim
a fresh minimum-Python/native Linux run or new hosted image scans. Normal CI must
verify the final patches on the configured supported platforms.

## Next-phase readiness

The reviewed implementation gaps are fixed and the useful module boundaries are
in place for future work. No new matching policy, threshold, feature meaning,
cause family or automatic controller was introduced. Full Phase 1 acceptance still
requires the user's normal desktop/game-picker/input/reconnect and trace
export/cancel/retry checks, plus normal CI for these patches. Record those results
in the [acceptance ledger](../../docs/scenarios/N5_RUNTIME_ACCEPTANCE.md) before
closing N5/Phase 1 and transitioning the [active plan](../../docs/plans/NEXT_IMPLEMENTATION_PLAN.md).

Raw logs are retained in ignored `local/phase-1-readiness-20261015/`; earlier logs
are organized under `local/phase_1/`. This record supersedes the earlier audit's
current software counts, not its exact historical receipts or live measurements.
