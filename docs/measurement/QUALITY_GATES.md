# N1/N2 quality and CI gates

[`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) preserves the existing
P0 checks and extends both Python 3.13 and 3.11 jobs with explicit branch-inclusive
coverage at the unchanged 85% floor, N1 fixture drift and pinned registry/report
reproduction. N2 adds [three pinned observation fixtures](OBSERVATION_V2_FIXTURES.md)
and read-only reproduction in both jobs. Python 3.11 also checks schemas,
canonical registry and installed dependencies. The quality job retains Ruff,
P0 fixture drift, controlled-artifact
validation, seed drift and exact run-002 match reproduction.

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
.venv/bin/python -c \
  'from latency_fingerprinting.synthetic_fixtures import fixture_drift; assert fixture_drift() == {}'
.venv/bin/python -c \
  'from tests.measurement.fixture_cases import fixture_drift; assert fixture_drift() == {}'
.venv/bin/python experiments/controlled-run-001/record_seed_fingerprint.py --check
```

Final Step 9 local result: **892 tests passed; 91.53% branch-inclusive coverage**
on Python 3.13.13. N1 registry, raw extraction and inspection modules have 100%
branch-inclusive coverage; aggregation and measurement models have 99% (rounded
by the coverage report). The CI YAML parses and both jobs include the intended
coverage/reproduction commands. Five controlled P0 artifacts validate, and run
002 reproduces exact frozen match bytes. Registry/report pins, schemas, fixtures,
seed, Ruff and installed dependencies all pass.

Python 3.11 and GitHub-hosted CI execution have not been run locally. The workflow
configuration and local checks are verified; remote job results remain pending.
[Step 10 software closeout](N1_SOFTWARE_CLOSEOUT.md) is complete. P0 behavior
and artifacts are unchanged, and proposed v2 features remain outside the matcher.
N2 observation-v2 contracts/offline adoption are now [closed out locally](N2_SOFTWARE_CLOSEOUT.md).
Final N2 result: **1,162 tests pass; 93.04% branch-inclusive coverage**. Its
[public CLI boundary cases](../../tests/observation_v2/test_cli_boundaries.py)
exercise context bytes/depth, total bundle bytes, TAR size/member count/traversal,
CSV headers/row limits, deterministic errors and acceptance at the exact row limit.
All legacy preservation gates and new fixture pins pass locally; configured
Python 3.11/3.13 CI execution evidence remains pending.

The [post-N2 health audit](N2_ARCHITECTURE_AUDIT.md) verifies the complete tree with
**1,166 passing tests and 93.05% branch-inclusive coverage**, including four new
instance-boundary regressions and corrected fixture documentation-test scope.
