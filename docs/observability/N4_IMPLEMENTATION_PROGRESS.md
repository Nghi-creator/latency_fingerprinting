# N4 implementation progress

**Slice:** Stage-level observability
**Started locally:** 2026-10-09
**Status:** Step 0 complete locally; Step 1 timing/capability specification is next
**Plan:** [N4 implementation plan](../plans/NEXT_IMPLEMENTATION_PLAN.md)

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

### Next action

Step 1 specifies the timing/identity/clock/capability contract and minimum real
acceptance case. Current producer locations are `engine/runtime/camera.py` for the
pipeline and `engine/runtime/camera_state.py` for atomic telemetry snapshots.
The plan's camera-state path was already correct; the table now explicitly names
the pipeline owner as well. No N4 trace contract,
schema, instrumentation hook, adoption command or timing result is implemented
by this baseline step.
