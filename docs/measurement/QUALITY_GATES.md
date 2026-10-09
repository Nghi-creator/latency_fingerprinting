# N1–N4 quality and CI gates

[`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) preserves the existing
P0 checks and extends both Python 3.13 and 3.11 jobs with explicit branch-inclusive
coverage at the unchanged 85% floor, N1 fixture drift and pinned registry/report
reproduction. N2 adds [three pinned observation fixtures](OBSERVATION_V2_FIXTURES.md)
and read-only reproduction in both jobs. Python 3.11 also checks schemas,
canonical registry and installed dependencies. The quality job retains Ruff,
P0 fixture drift, controlled-artifact
validation, seed drift and exact run-002 match reproduction.

N3 Step 2 adds [strict policy/response validation](../analysis/N3_ANALYTICAL_MODELS.md)
and two additive schemas, bringing the schema drift gate to eight roots. Its 94
analytical tests run in the existing full-suite jobs. Step 3 adds 30
[derivation tests](../analysis/N3_RESPONSE_DERIVATION.md). Step 4 adds 62
[fingerprint/repository tests](../analysis/N3_FINGERPRINTS.md) and one schema,
bringing exports to nine roots. Step 5 adds 76 [matching/model tests](../analysis/N3_MATCHING.md)
and one match schema, bringing exports to ten roots.
Step 6 adds 52 [public command tests](../analysis/N3_COMMANDS.md). The post-N3 suite
passed 1,539 tests with 93.58% branch-inclusive coverage after 40 original
fixture/closeout cases and 19 subsequent health-check regressions.
The [post-N3 audit](../archive/analysis/N3_ARCHITECTURE_AUDIT.md) covers scoring underflow,
stored-result/CLI failures, descriptor-pinned bundle reads, replacement links/FIFOs,
TAR growth and unchanged legacy missing-path errors.
[Step 7 fixtures/pins](../analysis/N3_ANALYTICAL_FIXTURES.md)
and reproduction are delivered in both jobs. Actual hosted/minimum-version
execution remains pending; see [N3 closeout](../archive/analysis/N3_SOFTWARE_CLOSEOUT.md).

## Read-only reproduction

[`check_reproduction.py`](../../tests/measurement/check_reproduction.py) is test
support, not a production API or fixture generator. It checks the canonical
registry artifact against source, then checks the pinned registry release and the
sanitized shadow report SHA-256. The shared report pin also guards the inspection
tests in both Python suites. It creates no files or directories and returns an
error exit code with no partial JSON or traceback on drift or missing files.

```bash
.venv/bin/python -m tests.measurement.check_reproduction
.venv/bin/python -m tests.observation_v2.check_reproduction
.venv/bin/python -m tests.analytical.check_reproduction
```

Expected pins:

| Artifact | SHA-256 |
| --- | --- |
| Canonical registry v2.0.0 | `50329d193303c271194b28e9164ae8627dd257d7620174c5ab136ba209864884` |
| Sanitized N1 inspection report | `295f57a6f0e0ab80f64c7323be3cd5fc4e278aac712825f0173955594513c423` |

Changes to registered meanings or rendered report bytes require a deliberate pin
review. Schema/registry checks and fixture drift checks never regenerate artifacts
in CI; the arithmetic fixture generator is separately documented in the
[fixture guide](ARITHMETIC_FIXTURES.md).

## Security and resource regression boundaries

[`test_quality_gates.py`](../../tests/measurement/test_quality_gates.py) adds public
inspection CLI boundary tests on top of the existing bounded-reader, extraction,
registry and arithmetic suites. Pathological envelope errors are invoked twice
and must produce identical error text, an error exit code, empty stdout and no
traceback. Invalid numeric cells remain structured rejection evidence in a valid
report rather than fabricated values or process failures.

| Boundary | Verification |
| --- | --- |
| JSON bytes | Oversized context is rejected before reading; existing bounded-reader tests retain pre/post-read protection |
| Bundle/file bytes | Inspection honors existing per-file and total-bundle caps |
| Duplicate keys | Root/nested bundle keys and context keys fail closed |
| Nesting | Depth beyond the configured JSON nesting limit is rejected before decoding |
| Numeric range | NaN/Infinity, overflow-range floats and pathological integer literals are rejected at their relevant boundaries |
| CSV structure | Field-size overflow, unterminated quoting and duplicate headers fail deterministically |
| Sample count | A reduced configured limit accepts exactly six rows and rejects the next row, exercising the real reader without a huge fixture |
| Archive paths | Relative traversal and absolute TAR member names remain rejected |
| Error handling | No partial report JSON or raw traceback on envelope/resource failure |
| Reproduction | Registry/report pin drift, artifact drift and missing fixtures fail; successful checks perform no writes |

The existing extraction tests also retain UTF-8, links, archives, CSV row limits,
clocks/identities and duplicate-safe JSON protections. Arithmetic tests retain
non-finite/overflow rejection, continuity and immutable inputs. No bound was raised
and no production exception handling or parsing implementation changed in Step 9.

## Local verification commands

```bash
.venv/bin/pytest --cov=latency_fingerprinting --cov-branch \
  --cov-report=term-missing --cov-fail-under=85
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m pip check
.venv/bin/python -m latency_fingerprinting export-schemas --output schemas --check
.venv/bin/python -m latency_fingerprinting export-metric-registry \
  --output schemas/metric-registry-v1.json --check
.venv/bin/python -m tests.measurement.check_reproduction
.venv/bin/python -m tests.observation_v2.check_reproduction
.venv/bin/python -m tests.analytical.check_reproduction
.venv/bin/python -c \
  'from latency_fingerprinting.synthetic_fixtures import fixture_drift; assert fixture_drift() == {}'
.venv/bin/python -c \
  'from tests.measurement.fixture_cases import fixture_drift; assert fixture_drift() == {}'
.venv/bin/python experiments/controlled-run-001/record_seed_fingerprint.py --check
```

## Baseline and next slice

The latest completed post-N3 health check records **1,539 passing tests and 93.58%
branch-inclusive coverage** on Python 3.13.13. All ten schemas, four fixture
families, registry/policy releases, controlled P0 artifacts and pinned reproduction
checks pass locally. Historical milestone counts and audit findings remain in the
[archive](../archive/README.md), including the
[final N3 audit](../archive/analysis/N3_ARCHITECTURE_AUDIT.md).

The active [N4 plan](../plans/NEXT_IMPLEMENTATION_PLAN.md) has reproduced
this baseline and the applicable Pixelated producer gates in
[Step 0](../observability/N4_IMPLEMENTATION_PROGRESS.md). Step 1 freezes the
[additive trace contract](../observability/N4_TRACE_CONTRACT.md) and
[real-capture/overhead criteria](../observability/N4_PRODUCER_CAPABILITIES.md).
N4 Step 2 delivers [strict models and generic validation](../observability/N4_TRACE_MODELS.md),
two additive schemas (twelve total) and 86 independent regressions in the existing
full-suite jobs. Latest local execution passes **1,745 tests with 93.69%
branch-inclusive coverage**, retaining the 85% floor. N4 Step 3 delivers [host hooks](../observability/N4_HOST_INSTRUMENTATION.md):
producer engine build/tests/lint and 31 nested Python collector/pad/teardown
regressions pass locally. Step 4 delivers [browser collection](../observability/N4_BROWSER_INSTRUMENTATION.md):
220 web tests (38 new), lint and production build pass; 23 synthetic browser
snapshots pass strict core validation. Step 5 delivers [standalone export/adoption](../observability/N4_TRACE_ADOPTION.md),
58 core I/O regressions and synthetic producer-to-CLI checks. Step 6 delivers
[offline timing inspection](../observability/N4_TIMING_RECONSTRUCTION.md) with 46
independent arithmetic/exclusion/copy/I/O cases. Step 7 pinned trace fixtures and
synthetic integration are delivered; real acceptance remains pending. Existing N2 timing and N3 policy/match outputs remain frozen.

Actual Python 3.11/hosted execution remains pending. N4 separately requires real
stage-local capture and measured instrumentation overhead; those results cannot
be inferred from synthetic fixtures or this completed software baseline.

## N4 Step 7 software verification

Current local Python 3.13 suite: **1,745 tests / 93.69% branch-inclusive coverage**,
unchanged 85% floor. Ten new tests cover read-only release pins, changed/missing/extra
fixture failures and full directory/TAR adoption → inspection CLI handoffs.

```sh
python -m tests.observability.check_reproduction
```

Both configured Python CI jobs run this independent N4 gate. The optional actual
producer export check and frozen real/overhead procedure are in the
[N4 integration guide](../observability/N4_INTEGRATION_VERIFICATION.md). See the
[software closeout](../observability/N4_SOFTWARE_CLOSEOUT.md) for both repository
results and pending real/minimum-version/hosted gates. N1–N3 pins and controlled
P0 artifacts remain unchanged.

## Post-N4 software health check

[Cross-repository audit](../observability/N4_ARCHITECTURE_AUDIT.md): **1,745 core tests /
93.69% branch-inclusive coverage**. Six new core cases cover descriptor ownership
on stream/cleanup failures and optional producer reproduction success/missing/wrong
archives. Pixelated full workspace: 714 passing Node tests, one existing artifact
skip, and 42 nested Python tracing cases; whole-workspace lint, API TypeScript
checks and production web build pass. Thirteen new browser cases reject line-terminated numeric/commit inputs
and invalid provenance before stopping collection.

All schemas, registry/policy and P0/N1/N2/N3/N4 reproduction pins are preserved.
The active next step remains real N4 acceptance, including a fresh recording after
warm-up and all paired overhead trials. Actual Python 3.11/producer Node 24 and
hosted execution remain pending; local tests ran with core Python 3.13 and Node 26.
