# N1/N2/N3 quality and CI gates

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
Step 6 adds 52 [public command tests](../analysis/N3_COMMANDS.md). The local suite
passes 1,539 tests with 93.58% branch-inclusive coverage after 40 original
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
Next is strict model/schema implementation before instrumentation. N4 models, hooks, commands and fixtures
are not implemented. Existing N2 timing and N3 policy/match outputs remain frozen.

Actual Python 3.11/hosted execution remains pending. N4 separately requires real
stage-local capture and measured instrumentation overhead; those results cannot
be inferred from synthetic fixtures or this completed software baseline.
