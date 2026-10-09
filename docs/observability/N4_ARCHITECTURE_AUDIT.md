# N4 cross-repository health audit

**Date:** 2026-10-09. **Scope:** core and Pixelated testbed, with focused review of
all N4 contracts, collectors, lifecycle integration, exporters, I/O, reconstruction,
fixtures, CLI commands, documentation and configured verification. Full local
suites/lint cover the surrounding repositories; they do not prove real runtime or
hosted behavior.

Starting checkouts were clean:

- Core `616dabb663d268d871956c401214b6f787e8ae34`.
- Producer `0cc67fd5b542f957be4e22267c8d16af98c93224`.

Results below include this audit's local changes; no deployment, commit or archive
transition was performed.

## Findings patched

1. Browser regex end anchors admitted trailing line terminators in decimal knobs
   and forty-hex producer commits. Such commits exported evidence the strict core
   rejects. Decimal parsing now excludes every nondigit and enforces length;
   snapshot/export commit guards enforce exactly forty characters. Thirteen new
   web cases cover LF/CRLF/Unicode line separators and invalid provenance. Export
   rejects invalid provenance/version before stopping collection.
2. Core directory adoption and both repositories' atomic trace writers could leak
   opened descriptors if `fdopen` failed. A failed temporary-file unlink could
   also bypass directory close. Explicit ownership/finally blocks close both
   descriptors on these failure paths. Three new core I/O tests and one host
   test with two subcases inject failures, verify closed descriptors and preserve
   existing output. If the filesystem refuses deletion, a private temporary file
   can remain; the target is not replaced and the error is reported.
3. The architecture, active-plan index, archive-plan navigation and quality guide
   retained preimplementation N4 claims; the testbed root README still said trace
   export was pending. Those claims now reflect software delivery and real gates.
   Architecture/module/schema maps now include N4. Repeated producer integration
   paragraphs are consolidated into the export guide; web/engine READMEs and
   disabled environment defaults point to it.
4. Optional producer reproduction lacked regression coverage for success, a
   missing archive and the wrong producer's valid record. Three new core cases
   ensure every archive is checked and cannot silently report integration success.

No trace field, schema, method, fixture, metric/policy release, matcher threshold,
or legacy CLI behavior was changed. Six added core cases harden resource cleanup
and optional integration verification; published independent numerical fixtures
remain unchanged.

## Architecture and retention review

Runtime hooks stay in the testbed. Clock/frame/epoch ownership is local; no
cross-producer subtraction or heuristic frame alignment was introduced. Prefix
sampling, global bounds, loss accounting, ambiguity filtering, callback cancellation,
shutdown export and atomic no-follow adoption remain distinct, covered surfaces.
The core reconstructs only validated integer endpoint pairs and retains explicit
unavailability/exclusions. Export and snapshot work remain outside callbacks.

New production N4 modules remain small and cohesive (the largest core module is
249 lines); no large-module split is justified by this review. Existing larger
legacy models/adapters, player telemetry and test harnesses have active consumers
and separate established responsibilities. Import/reference searches, whole-tree
lint/builds and tests found no safely removable orphan in the reviewed tracing
surfaces. Duplicate documentation was removed; current contracts, guides, fixtures
and historical milestone records remain useful and are retained. Deleting those
records would discard reproduction meaning and provenance.

## Verification

Full core suite: **1745 pass / 93.69% branch-inclusive coverage**, unchanged 85% floor.
Local results and coverage are recorded in [quality gates](../measurement/QUALITY_GATES.md).
Core focused observability suite: 206 cases pass. Both full suites and preservation
checks are rerun for the final changes. Producer: 185 API, 133 engine, 245 web,
90 desktop and 61 smoke/security/contract tests pass (714 total); one existing
external mirror-artifact engine test is skipped. All 42 nested Python trace cases
pass. Whole-workspace lint, API TypeScript checks and production web build pass. These tests ran on
Node 26.4.0/npm 11.17.0 and producer Python 3.14.4; they are not Node 24 deployment
or hosted verification.

Actual synthetic host/browser/unsupported-API collectors → exporters → core API
and CLI adoption/inspection reproduce all nine independently pinned JSON files.
The original P0 fixtures/controlled artifacts, run-001 seed, exact run-002 match,
N1/N2/N3 reproduction, twelve schemas, registry and feature policy remain current.
Both Python CI jobs include N4 pin reproduction. Documentation and whitespace
checks cover both repositories after the final edits: 693 core and 29 producer
local documentation targets resolve, including the roadmap anchor; whitespace
checks pass in both trees.

## Next step and remaining evidence

The [active N4 plan](../plans/NEXT_IMPLEMENTATION_PLAN.md) remains at real acceptance,
not another software implementation step. Follow the [integration procedure](N4_INTEGRATION_VERIFICATION.md)
and frozen [capability/overhead criteria](N4_PRODUCER_CAPABILITIES.md): actual Linux
X11→leaky queue→VP8 capture with a draining receiver, unique PTS evidence, nominal
and interrupted/tiny-capacity/two-peer/browser cases, all five paired CPU/FPS
trials, ≥1000-probe diagnostic and export timing. The acceptance runner must start
a fresh recording after warm-up; the current camera collects from pipeline start
and supplies no interactive recording reset control. Do not count warm-up frames
as the nominal case or silently substitute a different source. Implement that
runner/control in the required runtime before claiming acceptance.

Docker/Linux capture, real callback/picker interaction, actual Python 3.11,
producer Node 24 and hosted runs remain unverified locally. No measured overhead,
scientific calibration or hardware certification is claimed. Phase 1.3 scenario
work remains subsequent; archive the N4 plan/progress/closeout/audit together at
that transition, retaining concrete pending gates if still outstanding.
