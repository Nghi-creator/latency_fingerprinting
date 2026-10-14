# N4 software closeout

**Archived:** 2026-10-10 at the transition to [N5](../../plans/NEXT_IMPLEMENTATION_PLAN.md). Software results remain historical; pending real/minimum-version/hosted gates are not cleared.

**Updated:** 2026-10-09. **Software:** Steps 0–6 and Step 7 synthetic integration
complete locally. **Full N4 acceptance:** pending real capture and overhead.
[Active plan](../../plans/archive/N4_STAGE_LEVEL_OBSERVABILITY_PLAN.md) retains those gates; this
closeout does not advance to the subsequent Phase 1.3 scenario harness.

## Delivered behavior

Pixelated supplies opt-in bounded host source/queue/VP8 probes, browser local
presentation/callback collection and separate sanitized trace exports. The core
supplies strict immutable trace/summary contracts, safe bounded adoption, pure
same-lifetime timing reconstruction and atomic `ingest-trace`/`inspect-trace`
commands. Unsupported stages, correlation gaps and event losses remain explicit;
independent clocks do not produce one-way latency or end-to-end age.

[N4 fixture release 1.0.0](../../../fixtures/observability/README.md) independently
pins three records, three manifests and three expected summaries. Ten new core
checks exercise read-only reproduction, changed/missing/extra fixture failures
and both directory/TAR adoption through inspection. The [integration procedure](../../observability/N4_INTEGRATION_VERIFICATION.md)
feeds fixed inputs through actual producer collectors/exporters, reproducing all
three records/summaries and CLI output bytes. Synthetic placeholder versions and
provenance are explicit; no fixture claims real capture.

## Local evidence

Both trees were clean at this step's start:

- Core: `f0f8090dab809ed643e3209ea454ca25a8ea3dcf`.
- Producer: `b54b47e18cd229c1273c46ff3a78a24676a682d2`.

Results describe those commits plus the uncommitted Step 7 changes. No deployment,
commit, version release or hosted workflow execution was performed.

- Core Python 3.13: **1739 tests pass / 93.69% branch-inclusive coverage**, unchanged 85% floor ([quality gates](../../measurement/QUALITY_GATES.md)).
  Ruff lint/format, dependency consistency, all twelve schema exports and registry
  check pass. N1/N2/N3 pinned reproduction, original P0 fixture drift, controlled
  artifacts, run-001 seed and exact run-002 match pass unchanged.
- Producer: 232 web tests pass; 134 engine tests discovered, 133 pass and one
  pre-existing external mirror-artifact skip. All 41 nested Python tracing cases
  pass. Engine/web lint, lockfile consistency and production web build pass.
- Actual synthetic host/browser/unsupported-API collector → exporter → adoption →
  reconstruction → CLI comparison passes for all three separately pinned cases.
- All 655 local documentation link targets resolve; whitespace checks pass in both repositories.
- Both configured Python 3.13/3.11 CI jobs include N4 read-only reproduction and
  the full suite. This records configuration review, not hosted execution.

Latest checks are local macOS software evidence. Real browser callbacks, export
picker interaction, Linux container capture and performance trials were not run.

## Outstanding gates

Docker and Python 3.11 are absent from the current host's command path; GitHub CLI
is also absent. No Linux/Xvfb/PulseAudio draining receiver is available here.
macOS Gst factory discovery from earlier work does not meet the frozen real case.

The [capability/acceptance specification](../../observability/N4_PRODUCER_CAPABILITIES.md) remains the
authority: nominal 500+ usable queue and encode pairs, ≥95% joint correlation
coverage, zero nominal loss; tiny-capacity, interrupted/restarted, disable/re-enable,
two-peer and browser API cases; five paired overhead trials at the predeclared
CPU/FPS thresholds; separate ≥1000-probe diagnostic and export/write timing.
Save exact versions/configuration and sanitized artifacts with independent integer
reconstruction. No real artifact or measured overhead result is claimed.

Actual minimum-version and hosted CI results must also be attached when run.
Full N4 remains open until the real gates pass. Progress/plan/closeout stay current;
archive them together on the following slice transition. Contracts, fixture and
usage guides remain current references. Scientific calibration, held-out scenarios,
hardware certification and Phase 1.3 remain separate work.

## Subsequent health audit

The [cross-repository audit](N4_ARCHITECTURE_AUDIT.md) fixes browser trailing-line
validation/provenance guards and descriptor cleanup in both repositories, adds
optional integration regressions and corrects stale architecture/index docs.
Latest core result: **1745 pass / 93.69% branch-inclusive coverage**, unchanged 85%
floor. Producer full workspace: 714 pass, one existing artifact skip; all 42 nested
Python trace cases pass. Whole-workspace lint/web build and preservation gates pass.
Original Step 7 counts above remain historical results. Real acceptance still
requires the post-warm-up recording runner and frozen Linux/overhead procedure.
