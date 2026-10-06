# N1 focused arithmetic fixtures

[`fixtures/measurement`](../../fixtures/measurement/README.md) contains 13 small,
synthetic JSON cases for the pure N1 aggregation APIs. It implements Step 8's nine
minimum cases plus rejected gauge cells, unavailable/malformed counter rows and a
single counter baseline. It adds no runtime capture, public API or CLI command.

Both regular counter cases cover the same ten-second window and cumulative
activity. One-second deltas of 60 and five-second deltas of 300 produce the same
600-frame total and 60 frames/s rate. Irregular intervals explicitly demonstrate
why time-weighted rate differs from an unweighted average. Gap/reset cases expose
exact accepted pairs and unsupported time. Overflow clears interval evidence and
aggregates rather than publishing a partial value.

Each fixture declares `measurement-arithmetic-fixture-v1`, a case ID, fixed
canonical registry version, synthetic provenance (`controlledReal=false`),
explicit elapsed bounds, timestamped samples, a numerical explanation and expected
summary projections. Samples satisfy the internal `MeasurementSample` contract;
a rejected numeric cell is represented by a null value and rejection reason.
This layer tests aggregation, while malformed raw CSV parsing remains covered by
the extraction tests. Empty optional sources retain their absence reason.

[`fixture_cases.py`](../../tests/measurement/fixture_cases.py) is test support,
not a production module. It authors fresh independent inputs and expected values,
performs deterministic JSON rendering and provides read-only exact-byte drift
checking. It never calls gauge or counter aggregation to generate expectations.
Shared helpers assemble records; expected statistics, interval deltas/rates,
durations and coverage are supplied explicitly. Rejection-prefix checks retain
reason count and meaning without freezing a platform-dependent arithmetic-error
suffix. Each fixture's README table and explanation make its expected arithmetic
reviewable.

[`test_fixture_cases.py`](../../tests/measurement/test_fixture_cases.py) compares
all authored numerical/audit fields with actual summaries, verifies units and
registry/bound metadata, checks provenance, input immutability and equal-window
cadence invariance, and exercises changed/missing/unexpected files, CRLF drift,
format-only changes and no-write checking. Expectations are also tested with both
aggregation entry points disabled, guarding independence of generation.

Drift checks run through the existing Python 3.11/3.13 CI suites without modifying
the workflow in this step. Checks create no directories and write no files:

```bash
.venv/bin/python -c \
  'from tests.measurement.fixture_cases import fixture_drift; assert fixture_drift() == {}'
.venv/bin/pytest tests/measurement/test_fixture_cases.py
```

The [fixture README](../../fixtures/measurement/README.md) gives the intentional
regeneration command. Generated JSON is sorted, indented UTF-8 with LF line endings
and a trailing newline, and disallows non-finite JSON values. Exact bytes, including
formatting, are protected. No P0 schema, fixture, controlled artifact, registry,
adapter, normalization or matcher code is changed. [Step 9](QUALITY_GATES.md)
implements quality, CI and security/resource-bound gates. Hosted CI execution
and N1 software closeout remain outstanding.
