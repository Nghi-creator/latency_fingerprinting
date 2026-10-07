# N1 synthetic arithmetic fixtures

Every JSON file here is explicitly **synthetic offline regression evidence**.
These values are authored examples, not sanitized runtime captures,
controlled-real experiments or evidence of diagnostic accuracy.
Each file includes provenance, input samples, window bounds, a hand-auditable
explanation and expected numerical/audit summary projections. These fixtures are
not engine measurements. No live runtime action or instrumentation occurred.

| Case | Expected result |
| --- | --- |
| `gauge-regular` | Median 20, P95 30, min 10, max 30; full coverage |
| `gauge-missing` | Median 30, P95 50; four usable values and 0.5 coverage |
| `gauge-rejected` | Same numeric subset; rejected cell remains explicit |
| `counter-1s-cadence` | 11 samples over 10s: total 600, rate 60 frames/s |
| `counter-5s-equivalent-cadence` | Three samples over the same 10s: total 600, rate 60 frames/s |
| `counter-irregular-cadence` | 100/1s and 100/4s: total 200, weighted rate 40 frames/s |
| `counter-gap` | No delta crosses the gap; total 120, rate 60, coverage 0.5 |
| `counter-unavailable` | Same accepted pairs; unavailable flag stays explicit |
| `counter-malformed` | Same accepted pairs; malformed-cell rejection stays explicit |
| `counter-reset` | Reject 60-to-5 transition; total 120, rate 60, coverage 2/3 |
| `counter-overflow` | Finite deltas sum beyond float range; no partial results |
| `counter-single` | One baseline, no rate/total, zero coverage, incomplete |
| `empty-optional-source` | No samples or numeric aggregates; missing with source reason |

`sourceRow` is a synthetic CSV-style row ordinal; UTC timestamps have a fixed
synthetic origin. They do not assert runtime capture or monotonic clock provenance.
`registryVersion` pins the existing canonical definitions. Counter cases test
both rate and audit-total definitions against the same sample tuple.

The expected projection includes every computed statistic/value, count, usable
row list, interval/delta/rate record, cadence statistic, coverage, state, reset/gap
list, missing reason and warning. Fixed definition metadata and elapsed window
bounds are checked separately against the registry and input. Rejection prefixes
are authored rather than freezing platform-specific suffixes from math exceptions;
reason counts and prefixes must still match exactly.

Authored inputs and expectations are in
[`fixture_cases.py`](../../tests/measurement/fixture_cases.py). That module imports
no aggregation implementation and supplies expected results independently.
[`test_fixture_cases.py`](../../tests/measurement/test_fixture_cases.py) loads the
checked-in JSON with the bounded reader, validates sample contracts and compares
actual aggregation with the authored expectations. Exact-byte drift checks run
in both existing CI test suites and never rewrite files.

Run the checks without writing:

```bash
.venv/bin/python -c \
  'from tests.measurement.fixture_cases import fixture_drift; assert fixture_drift() == {}'
.venv/bin/pytest tests/measurement/test_fixture_cases.py
```

For an intentional reviewed fixture update, regenerate deterministically:

```bash
.venv/bin/python - <<'PY'
from tests.measurement.fixture_cases import DEFAULT_FIXTURE_DIRECTORY, rendered_fixture_files
DEFAULT_FIXTURE_DIRECTORY.mkdir(parents=True, exist_ok=True)
for relative, content in rendered_fixture_files().items():
    (DEFAULT_FIXTURE_DIRECTORY / relative).write_bytes(content)
PY
```

Generation has no ambient timestamps, randomness, runtime data or aggregation
calls. Existing P0 fixtures and controlled-run artifacts are independent and unchanged.
The [N1 fixture guide](../../docs/measurement/ARITHMETIC_FIXTURES.md) records the
verification boundary and next step.
