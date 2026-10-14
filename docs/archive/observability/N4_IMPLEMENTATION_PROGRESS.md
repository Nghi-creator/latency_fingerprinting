# N4 implementation progress

**Archived:** 2026-10-10 at the transition to [N5](../../plans/NEXT_IMPLEMENTATION_PLAN.md). Software results remain historical; pending real/minimum-version/hosted gates are not cleared.

**Slice:** Stage-level observability
**Started locally:** 2026-10-09
**Status:** Steps 0–6 and Step 7 software complete locally; real acceptance pending
**Plan:** [N4 implementation plan](../../plans/archive/N4_STAGE_LEVEL_OBSERVABILITY_PLAN.md)

## Step 0 — Preserve and reproduce the post-N3 baseline

Both repositories started with clean working trees:

| Repository | Starting commit | Local environment |
| --- | --- | --- |
| `latency_fingerprinting` | `f7028e489346db681042d82d4df3e25610f5f117` | macOS arm64, Python 3.13.13 |
| `Pixelated-Studio-Edition` | `37e50fb7ef919564aba5796af35dbcdc1fc70f3b` | macOS arm64, Node 26.4.0, npm 11.17.0 |

No production source, tests, dependencies, schemas, policy content, fixtures or
controlled artifacts changed in this step. Producer build outputs/cache files
are ignored; its tracked working tree remains clean. The only changes are this
baseline record and current documentation/status/ownership clarifications in the core.

### Python core verification

The full suite passes **1,539 tests with 93.58% branch-inclusive coverage** at the
unchanged 85% floor. Ruff lint/format and installed dependency checks pass.
All ten schema exports and the canonical metric registry reproduce. Exact
approved policy content equals the normative N3 specification. Four fixture
families have no drift; all three N1/N2/N3 reproduction modules pass without
refreshing artifacts or pins. Five controlled P0 artifacts validate; run-001 seed
and the exact run-002 match bytes reproduce.

Preserved identities include:

| Artifact | SHA-256 |
| --- | --- |
| N1 registry | `50329d193303c271194b28e9164ae8627dd257d7620174c5ab136ba209864884` |
| N1 shadow report | `295f57a6f0e0ab80f64c7323be3cd5fc4e278aac712825f0173955594513c423` |
| N2 adopted browser | `50fd2ff8cb013a1d52564b5a21bbe210a25e810e0e55e036da5ca25c15911b81` |
| N2 adopted engine | `f92e1fe241200609a8133be233053a79c7bbb3dca179ffd6ab3e1bbba09ab179` |
| N2 synthetic pair | `d6b96c18e0104fcd62ea2525b5637c6aadf7a033ac30d3b4e918be3ff8088954` |
| N3 policy self-excluding content hash | `96457b318cc714f3d9d0d63a35b12548f6e030b10057b2c8e5a3a77e352fe1af` |
| Controlled run-002 match bytes | `b432121296621cb9bcba1f0ca01bfc5edc0c5d1e7fbaeebfd36396a481cc6b37` |

The N3 reproduction module also checks all 19 full-file analytical snapshot pins;
the policy's full-file pin remains distinct from its self-excluding content hash.

```bash
.venv/bin/pytest --cov=latency_fingerprinting --cov-branch \
  --cov-report=term-missing --cov-fail-under=85
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m pip check
.venv/bin/python -m latency_fingerprinting export-schemas --check
.venv/bin/python -m latency_fingerprinting export-metric-registry --check
.venv/bin/python -m tests.measurement.check_reproduction
.venv/bin/python -m tests.observation_v2.check_reproduction
.venv/bin/python -m tests.analytical.check_reproduction
.venv/bin/python experiments/controlled-run-001/record_seed_fingerprint.py --check
```

### Pixelated producer verification

Existing installed dependencies were used without install/lockfile changes.
The producer declares Node `>=24 <27`; this local check used Node 26.4.0.

| Command, from producer root | Result |
| --- | --- |
| `npm run test:engine` | Build succeeds; 132 tests discovered, 131 pass, one skip, zero failures |
| `npm run test:web` | 182 tests pass, zero failures/skips |
| `npm run lint:engine` | Pass |
| `npm run lint:web` | Pass |
| `npm run check:lockfiles` | Workspace direct dependency resolutions consistent |
| `./node_modules/.bin/tsc -b apps/web/tsconfig.json` | Web TypeScript projects compile |

The existing engine skip is the curated local-mirror artifact checksum test:
its external artifact mirrors are absent. It is not counted as a pass and was
not removed or replaced. The initial engine invocation could not bind its test
listeners to `127.0.0.1` within the sandbox; the same existing suite passed after
an approved rerun with local socket access. No producer test or code was patched.

These are engine/web software gates. No hosted/API/desktop deployment or browser
interaction/live capture was run. TypeScript compilation is not a production
Vite build or proof of browser timing availability. Engine tests exercise camera
bridge source/telemetry behavior; they do not validate a running GStreamer stream.

### Runtime availability and clock boundary

Docker is unavailable on this host, so the documented Ubuntu/Xvfb/PulseAudio
engine container was not launched. Host Python GI and GStreamer 1.28.2 initialize,
and factory lookup finds `ximagesrc`, `vp8enc`, `webrtcbin`, `queue` and `appsink`.
The plugin scanner also emits shared-library/GTK loader warnings. Factory discovery
does not establish a working Pixelated capture pipeline, real frame correlation,
hardware support, timing accuracy or acceptable instrumentation overhead.

No real capture, synchronization/error measurement, overhead comparison or
hardware-encoder validation was performed. Those gates remain open for N4 Step 7.
Actual Python 3.11 and hosted Python 3.13 checks remain pending: `python3.11` and
the GitHub CLI are unavailable here. The inspected core CI configuration retains
both Python jobs, coverage and pinned reproduction, but is not execution evidence.

The engine has a monotonic interval resource sampler; that does not make exported
observation elapsed time or camera snapshots approved stage-local trace evidence.
N2 unavailable timing and N3 policy/matching meanings remain frozen. Step 1 must
inspect producer clocks and frame attribution before defining any new methods.

### Step 0 handoff (historical)

Step 1 specifies the timing/identity/clock/capability contract and minimum real
acceptance case. Current producer locations are `engine/runtime/camera.py` for the
pipeline and `engine/runtime/camera_state.py` for atomic telemetry snapshots.
The plan's camera-state path was already correct; the table now explicitly names
the pipeline owner as well. No N4 trace contract,
schema, instrumentation hook, adoption command or timing result is implemented
by this baseline step.

## Step 1 — Timing/identity/capability specification

Completed locally, 2026-10-09, from core commit
`8ef1b5fe5cd1e93bed97945a949f7ee36361c9cc` and unchanged producer commit
`37e50fb7ef919564aba5796af35dbcdc1fc70f3b`. Both trees were clean at this step's start.

- [Normative trace contract](../../observability/N4_TRACE_CONTRACT.md): two additive v1 roots, closed
  release/methods, safe export-local identities, separate lifetime clocks, exact
  boundary/correlation meanings, bounded sampling/loss, canonical hash-verified
  artifact layout and proposed offline commands.
- [Producer capability matrix](../../observability/N4_PRODUCER_CAPABILITIES.md): inspected actual
  host queue/VP8 boundaries, per-peer pipelines, browser polling/getStats and v2
  export. No synchronized engine/browser identity, capture-start, wire-send or
  physical-display evidence is assumed.
- [Independent examples](../../observability/N4_TRACE_EXAMPLES.md): same-clock positive/zero/missing/
  negative pairs, budget equality/negative slack, browser callback lag, sampling
  and loss accounting, plus rejection cases.

The minimum real acceptance is fixed to a draining Linux/X11/VP8 Pixelated stream,
with independently reconstructed queue/encode pairs and explicit unavailable
stages. Five paired disabled/enabled overhead trials have predeclared CPU/FPS
criteria. These are provisional engineering requirements, not measured results.
Docker/Linux capture and overhead remain pending.

This step changes documentation only in the core. No production source, tests,
schema/fixture/policy bytes or producer files change. N2 unavailable timing and
N3 matching remain frozen. Numeric example checks, all 555 local documentation-link targets, whitespace
checks and all ten schema/registry/N1–N3 pinned reproduction checks pass locally.
The nine changed/new files are Markdown; the producer tree remains clean. The
Step 0 full-suite result remains 1539 tests / 93.58% coverage; the unchanged suite
was not rerun for this specification-only step.

**Step 1 handoff (historical):** Step 2 implements strict, immutable, revalidated trace/summary models
and two additive schemas with independent rejection/consistency regressions.
Hooks, CLI commands, producer artifacts and timing reconstruction remain pending.

## Step 2 — Strict additive models/schemas

Completed locally, 2026-10-09. [Trace models/validation](../../observability/N4_TRACE_MODELS.md) are
delivered in a focused observability package and exported through the existing
model API. Generic validate recognizes snake_case trace roots; existing roots
keep their aliases and outputs. Schema exports add record-v1 and summary-v1,
bringing the total to twelve with the original ten bytes unchanged.

Validation covers closed methods/versions, clock/producer agreement, source-local
aliases/lifetimes, complete capabilities, sampled frame prefixes, event ordering/
references/endpoints, exact loss conservation and total/declared capacity. It
rejects false correlation, copied invalid nested instances, private/unknown fields,
nonfinite/unsafe numbers, booleans as numeric values and unordered/iterator inputs.
Bounded duplicate-safe text decoding enforces 10 MiB/depth 32 before model loading.
Summary validation recomputes integer-delta statistics, coverage, exclusion
counts and declared-budget slack/hits; negative pair evidence remains input for
Step 6 classification. Supplied summary hashes alone do not prove trace provenance.

Local results:

- **1,625 tests pass / 93.59% branch-inclusive coverage**, unchanged 85% floor.
  This includes **86 new independent N4 regressions**; focused N4/schema/CLI
  invocation passes 109 tests. Full run: 102.61 s, Python 3.13.13.
- Ruff lint/format, installed dependencies, twelve schema exports and canonical
  registry pass. Original ten checked-in schema files equal their starting bytes.
- N1/N2/N3 pinned reproduction passes without refresh; frozen policy/fixtures and
  controlled artifacts remain unchanged. Producer working tree remains clean.
- Documentation/status links and whitespace checks pass. No CI thresholds or
  workflow changes: the existing full-suite/schema jobs include these additions.

No producer hooks, new trace bundle reader, ingest-trace/inspect-trace command or
trace-to-summary derivation is implemented in this step. No real capture,
synchronization, overhead or hosted/minimum-version execution was performed.
Step 0 runtime limitations and Step 1 real/overhead acceptance criteria remain open.

**Step 2 handoff (historical):** Step 3 adds opt-in, bounded capture-output/queue/VP8 encoder hooks in
Pixelated Studio Edition, with correlation, teardown and exact loss tests.

## Step 3 — Bounded host capture/queue/encoder hooks

Completed software locally, 2026-10-09. Starting core commit
`012fc03c3786aef2822970508b9ba2266759392a`; producer base remains
`37e50fb7ef919564aba5796af35dbcdc1fc70f3b`. Both trees were clean before this step.
[Host integration guide](../../observability/N4_HOST_INSTRUMENTATION.md) records enablement and limits.

Producer changes: three focused stdlib helper modules, camera integration, runtime
image COPY lists, automatic Python regression invocation in the existing engine
runner and producer documentation. No dependency/lockfile, codec/playback setting,
v2 research export or legacy telemetry meaning changes. Tracing is off by default
and installs no new probes/per-frame trace objects on that path.

Enabled collection records five actual host pad locations with local monotonic
time. Shared frame/event capacity, prefix sampling, bounded PTS/endpoint metadata
and sixteen lifetime aliases limit the entire recording, including closed peers.
Missing/regressing/duplicate PTS and repeated endpoints never get guessed pairing;
correlation filtering conserves exact event loss without refilling capacity.
Source/downstream segment routing prevents old queued buffers joining new epochs.
Clock failure/reset closes its scope. Partial installation rolls back, teardown
is idempotent, existing telemetry probes survive removal, and callbacks preserve
media flow even when tracing fails. Enabled SIGTERM routes through GLib cleanup;
state-write failures cannot skip the other trace scopes/finalization.

Local verification:

- Producer engine build and complete Node suite: **134 discovered, 133 pass,
  one existing curated-mirror artifact skip, zero failures**. Two new Node cases
  run **31 nested Python 3.14.4 collector/fake-pad/actual-teardown-code tests**
  and check integration locations; those are not 31 extra Node results.
- Engine lint, workspace lockfile consistency, new Python-helper/test Ruff checks
  and camera/trace compilation pass. Both Dockerfile helper COPY lists are checked;
  no container image was built or launched.
- All **25 synthetic snapshots** generated by the producer cases pass strict core
  N4 validation. Core focused N4/schema/CLI suite passes **109 tests**. Twelve
  schemas, canonical registry and N1/N2/N3 reproduction pass without refresh.
- A local GLib loop receives self-SIGTERM, quits and permits recording finalization.
  This is signal-loop verification, not a live Pixelated capture pipeline.
- Core production source/tests/schemas/fixtures remain unchanged. Its latest full
  result remains Step 2's **1625 tests / 93.59% coverage**; the full core suite was
  not repeated for producer-only implementation. Current docs and links are checked.

The sandbox initially blocked existing engine test listeners at 127.0.0.1. The
same suite passes with approved local-socket access; no signaling tests were
weakened. No hosted/minimum-runtime, browser interaction or Linux/X11/VP8 capture
was performed. Docker remains unavailable. No real correlation or measured
instrumentation overhead is claimed. Snapshots are in-memory only; persistence,
artifact adoption and trace-to-summary reconstruction remain Steps 5–6.

**Step 3 handoff (historical):** Step 4 adds bounded optional browser presentation/callback collection
and explicit sender/receive/decode/display capability limits, retaining cumulative
WebRTC metrics and unavailable cross-producer latency.

## Step 4 — Bounded browser presentation/callback evidence

Completed software locally, 2026-10-09, from core commit
`ba9e559fe836b31f69e20d83ca7ffcdc24ee412d`. The core started clean; producer base
remains `37e50fb7ef919564aba5796af35dbcdc1fc70f3b`, with the Step 3 host changes
already present and preserved. [Browser integration guide](../../observability/N4_BROWSER_INSTRUMENTATION.md)
records build-time opt-in configuration, approved endpoints and capability limits.

Producer implementation adds closed configuration, a bounded recorder/rvfc adapter,
a focused lifecycle hook wired into actual playback, and independent unit cases.
The disabled path allocates no recorder or native callback. Enabled collection
reads only callback now, presentationTime and presentedFrames; snapshots retain
relative integer ns, exact callback-local pairing and all eleven capabilities.
Receiver/decode/render-ready/sender stages remain explicitly unsupported. Cumulative
WebRTC metrics, v2 export and N2/N3 meanings are unchanged.

A recording retains an earliest sampled prefix across sixteen media lifetimes
with shared frame/event capacity. Counter gaps include unsampled callbacks;
clock/counter regressions close their scope without joining resets. Bad endpoints,
capacity and partial pairs retain exact loss/event sequences. Callback registration,
metadata and cancellation failures cannot escape into playback. One callback is
outstanding per binding; detach/finish are idempotent and late delivery is ignored.
No per-frame React update, file/export/core-model work or optional/private metadata
read occurs. Clock resolution remains unknown; synthetic checks do not assess it.

Local verification:

- **220 web tests pass**, zero failures/skips, including **38 new collector/config/
  lifecycle cases**. Web lint and production TypeScript/Vite build pass.
- **23 synthetic browser snapshots** emitted by those cases pass strict core N4
  validation, covering supported/unavailable APIs, resets, sampling, timestamp
  loss, global capacity and multiple lifetimes. They are not real browser captures.
- Core focused N4/schema/CLI checks pass **109 tests**. Twelve schemas, canonical
  registry and N1/N2/N3 pinned reproduction remain current without refreshing pins.
- Current docs/navigation and both working-tree whitespace checks pass. Core
  production source/tests/schema/fixtures and producer dependencies/lockfiles are
  unchanged. Engine files/tests are unchanged by Step 4; their latest result remains
  Step 3's 133 passes plus one existing external-artifact skip, not a rerun here.
- Latest full core execution remains **1625 tests / 93.59% coverage** from Step 2;
  it was not repeated for producer browser code and documentation changes.

No live browser interaction/timing, Linux/X11/VP8 capture, measured overhead,
clock synchronization or hosted/minimum-version execution occurred. Docker remains
unavailable. Persistent trace export/adoption and reconstruction remain Steps 5–6;
real acceptance/overhead and pinned integrated reproduction remain Step 7 gates.

**Step 4 handoff (historical):** Step 5 standalone versioned trace artifacts and bounded Python adoption/CLI.

## Step 5 — Standalone producer export and bounded adoption

Completed software locally, 2026-10-09, from core commit
`afa39e002b1125662e930758e42be3c7534551ff` and producer commit
`98f90770a529165b3b7ed0ce426ee3add7afd890`. Both trees started clean; existing
Steps 3–4 producer implementations were preserved. [Export/adoption guide](../../observability/N4_TRACE_ADOPTION.md) documents the exact
standalone layout, producer settings, offline command and failure semantics.

Producer changes add a stdlib host gzip-TAR exporter, both image COPY lists,
post-finish camera shutdown persistence, browser canonical serialization/hashing/
gzip, and an explicit opt-in finish/download control. The lifecycle hook moves
into PlayerExperience after playback's srcObject assignment effect. Export neither
merges with research bundle v2 nor changes its members, CSVs or metrics. Real
exports require an explicit deployed producer commit; synthetic APIs declare
synthetic provenance. No implicit artifact write or network upload is introduced.
Empty/invalid-version browser export leaves future collection available; successful
finish stops it. Picker cancellation is reported and permits re-export. Host output
uses atomic replacement, no-follow ancestor/leaf checks and private 0600 files.

Core changes add a focused standalone reader, atomic output helper and ingest-trace
command. The reader requires exactly two regular members, checks physical TAR
headers before extension parsing, bounds compressed/expanded/JSON resources,
rejects links/path aliases/extra/duplicate/extension members and validates duplicate-
safe JSON. Manifest version/type/hash/byte count and canonical trace bytes must
agree before returning a strict immutable record. No supplied URLs or private
fields are interpreted. CLI failures use a fixed error with no partial output,
source echoes or change to the previous destination. inspect-trace remains Step 6.

Local verification:

- **1683 full core tests pass / 93.58% branch-inclusive coverage**, unchanged 85%
  floor, Python 3.13.13, 109.23 s. **58 new adversarial adoption/output cases** cover
  canonical directory/gzip equality, hostile layouts, a 2000-header TAR extension
  chain, JSON versions/privacy/depth, resource limits and atomic write failures.
- **232 web tests pass**, zero failures/skips, including **12 new export cases**;
  web lint and production TypeScript/Vite build pass.
- Complete engine build/Node suite passes **133 tests plus one existing external-
  mirror artifact skip (134 discovered)**. **41 nested host Python cases pass**,
  including ten new export cases and actual shutdown-code ordering checks.
  Engine lint, workspace lockfile consistency and producer Python-helper/test
  Ruff checks pass. Runtime Dockerfiles copy the exporter; no container was built.
- Actual producer export APIs generate synthetic gzip artifacts: one host frame
  with five endpoints and two browser frames with four endpoints. Both core API
  and ingest-trace adopt them with exact canonical output-byte equality. This is
  synthetic producer-to-CLI interoperability, not a running media pipeline.
- Twelve schema exports, metric registry and N1/N2/N3 pinned reproduction pass
  unchanged. Source fixture/policy/schema bytes and dependencies/lockfiles are
  preserved. Current documentation/navigation and both whitespace checks pass.

A full run was repeated after final reader hardening so the result above reflects
final behavior, not the earlier in-progress implementation. No live browser/picker,
Linux/X11/VP8 capture, synchronization, measured overhead, container or hosted/
minimum-version execution occurred. Docker remains unavailable. Resource limits
are software caps, not measured full-limit scaling.

**Step 5 handoff (historical):** Step 6 pure same-domain trace-to-summary reconstruction and inspect-trace.
Step 7 pinned integrated reproduction and real capture/overhead gates remain open.

## Step 6 — Pure timing reconstruction and offline inspection

Completed software locally, 2026-10-09, from core commit
`82fc5b662586bd825cce7858c1e3886e8de0a2de` and unchanged producer commit
`e8f54c77ef3d8f192544e70466e06a826cae18d7`. Both trees started clean.
[Reconstruction/inspection guide](../../observability/N4_TIMING_RECONSTRUCTION.md) records the API,
command, pairing, exclusion precedence, coverage and remaining runtime gates.

Core changes add a focused pure reconstruction module, bounded no-follow trace
reader, public reconstruct_trace API and inspect-trace command. All four methods
retain their frozen versions and meanings. Each stream gets its own endpoint index;
frames, lifetimes, clocks and unsampled/lost observations never get merged. Input
models/copies are revalidated before indexing. Unsupported capability/producer,
missing/ambiguous correlation, missing endpoint and negative delta exclusions
conserve exactly one classification per retained frame. Zero remains a measured
sample, while unavailable statistics remain null.

Integer endpoint subtraction and exact integer sums precede one millisecond
floating division; the returned strict summary independently recomputes statistics,
coverage and budget arithmetic. Declared deadlines reuse only usable age pairs,
with equality hits and valid negative slack. No declared budget means unavailable.
Source clock/capability/sampling/loss and producer/provenance declarations are
preserved. Summary identity hashes canonical validated trace bytes, never a
supplied summary hash. API output is immutable and deterministic; input is unchanged.

inspect-trace accepts bounded duplicate-safe trace JSON through pinned no-follow
regular reads and writes canonical summary JSON atomically through the Step 5
output helper. Input text whitespace does not alter canonical trace identity.
Invalid inputs, unsafe outputs or invalid results produce a fixed public error,
no source/path/input echo and no partial output. A supplied summary cannot be
used as inspection input. Reconstruction is separate from N2/N3 adoption/matching.

Local verification:

- **1729 full core tests pass / 93.69% branch-inclusive coverage**, unchanged 85%
  floor, Python 3.13.13, 106.24 s. **46 new independent cases** cover the complete
  hand-authored Step 1 example, all positive/zero/negative methods, exclusion and
  reason precedence, API absence, sampling/loss, out-of-order arrival, reset
  isolation, optional/equal/negative-slack budgets and immutable/copy/hash behavior.
- A 2000-frame safe-limit case checks an integer sum beyond 2^53−1 against an
  independently computed rational expectation. Fresh public imports check the
  serialization dependency boundary. CLI cases cover bounded/deep/duplicate JSON,
  links/special files, fixed private errors and preserved output.
- Focused N4/schema/CLI invocation passes **213 tests**. Twelve schema exports,
  metric registry and N1/N2/N3 pinned reproduction pass unchanged. Ruff lint/format,
  installed dependency checks, documentation links and both whitespace checks pass.
- Actual Step 5 producer-generated synthetic records pass inspect-trace and strict
  summary validation. Host queue/encode/age means reproduce 0.0001/0.0001/0.0004 ms;
  browser callback mean reproduces 1.5 ms. Foreign-producer methods are unavailable.
  This is arithmetic/export interoperability, not timing from a running pipeline.
- Producer runtime/source/tests/dependencies remain unchanged in this step; only
  its three N4 guides are updated to reference delivered inspection. Its latest
  recorded gates remain Step 5's **232 web passes**, **133 engine passes plus one
  existing external-artifact skip**, **41 nested host Python passes** and successful
  lint/production web build. Those suites were not rerun for documentation-only
  producer changes.

No fixtures/pins, policy/schema bytes, thresholds, CI/dependency settings or legacy
outputs change. No live browser/picker interaction, Linux/X11/VP8 capture, clock
synchronization, measured overhead, hosted/minimum-version execution or full-limit
throughput measurement occurred. Docker remains unavailable. The maximum-ledger
arithmetic case is a resource/logic test, not a throughput acceptance measurement.

**Step 6 handoff (historical):** Step 7 separately pinned integrated reproduction, minimum real producer
acceptance, measured overhead and a closeout separating software/runtime/hosted
results. N4 is still incomplete; a missing runtime must remain an explicit pending
gate rather than being replaced with synthetic timing claims.

## Step 7 — Synthetic integration and software closeout

Three independent fixture cases pin nine canonical files in release 1.0.0. Ten
new tests verify read-only pins/drift and both directory/TAR CLI handoffs. Actual
producer host/browser collectors and exporters reproduce the same record bytes,
summaries and adoption/inspection CLI outputs. Both CI jobs now run N4 pinned
reproduction without a sibling runtime dependency.

[Software closeout](N4_SOFTWARE_CLOSEOUT.md) records both starting commits, local
checks and the concrete pending real/minimum-version/hosted gates. The
[integration guide](../../observability/N4_INTEGRATION_VERIFICATION.md) contains rerunnable commands.
Producer checks: 232 web pass; 133 engine pass, one existing artifact skip; 41
nested Python trace cases pass; engine/web lint, lockfiles and web build pass.
All legacy preservation checks pass. Docker and Python 3.11 remain unavailable.
No real capture or overhead measurement was performed; full N4 remains open.

Core full suite: **1739 pass / 93.69% branch-inclusive coverage**, unchanged 85%
floor. All twelve schemas, registry, N1/N2/N3 reproduction, original P0 fixtures,
controlled artifacts, seed and exact run-002 match remain current.

Documentation check: all 655 local targets resolve. Both repository whitespace
checks pass. N4 remains the active slice while real acceptance is pending; no
progress/plan archival or subsequent-slice transition was performed.

## Post-N4 software health audit

[Cross-repository audit](N4_ARCHITECTURE_AUDIT.md) patches strict browser inputs,
pre-finish provenance guards and descriptor cleanup; adds six core and thirteen
web regressions; removes duplicate integration prose and stale preimplementation
claims from current architecture/indexes. Full local result: **1745 core tests /
93.69% coverage**; 714 producer Node tests pass with one existing artifact skip;
42 nested Python trace cases pass. Whole-workspace lint/web build and all
preservation/synthetic integration gates pass. Real post-warm-up recording runner,
Linux capture, measured overhead and actual minimum-version/hosted results remain
concrete pending work. No slice transition or historical evidence deletion occurred.
