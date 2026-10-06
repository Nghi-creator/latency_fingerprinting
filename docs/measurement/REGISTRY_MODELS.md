# N1 registry model guide

[`models/measurement.py`](../../src/latency_fingerprinting/models/measurement.py)
defines `MetricDefinition` and `MetricRegistry`, exported intentionally through
[`models/__init__.py`](../../src/latency_fingerprinting/models/__init__.py).
They inherit `ContractModel` aliases, whitespace trimming, strict finite scalar
types and rejection of extra fields. They do not alter the P0 root models.

## Representation and validation

Registry schema version is `metric-registry-v1`. Registry identifiers follow
`latency-metrics-vMAJOR.MINOR.PATCH`; definition versions use `MAJOR.MINOR.PATCH`.
The eventual canonical registry identifier remains `latency-metrics-v2.0.0`.
Versions are explicit metadata, not derived from the package version.

Definition names use dotted lowercase identifiers. Sources, units, metric kinds,
aggregations, clocks, missing-data policies and reset policies are closed enums.
`event_count` and `derived` are reserved enum values; constructing definitions
with those kinds is rejected until their derivation contracts are implemented.

Gauge definitions admit median, nearest-rank P95, minimum and maximum and omit
missing samples or reject the series on invalid input. They cannot declare a
counter reset policy/width or use counter continuity rules. The definition's
`nonNegative` flag is a strict boolean; gauges can explicitly support signed data.

Cumulative counter definitions require non-negative input, a reset policy and
continuity-breaking or series-rejecting missing-data policy. One definition has
one canonical output unit, so rates and totals must have separate definitions.
Rates use `frames/s`, `freezes/min`, `ms/s` or `packets/s`; totals use `frames`,
`freezes`, `ms` or `packets`. Gauge units follow the inventory, including `fps`
for producer FPS gauges. Kind describes raw input; unit describes derived output.

`counterWidthBits` is the only added optional field: it is a strict integer from
1 to 64 and is required exclusively for `allow_declared_wraparound`. That policy
can be declared only with a width; no arithmetic or inferred wraparound happens
in these models. N1's canonical inventory uses `reject_segment` without widths.
Optional normalization/clipping/direction metadata is not included because N1
has no consumer for it. Step 4 adds `MeasurementSample` for
[`raw extraction`](SAMPLE_EXTRACTION.md); series summary contracts remain part
of the later aggregation implementation steps.

All required nullable fields must be supplied explicitly. Cadence and tolerance
must be positive finite numbers when present. Tolerance requires expected cadence;
expected cadence can be advisory without a tolerance. Booleans, numeric strings,
non-finite floats and overflow-range integers cannot become cadence values.
`createdAt` accepts a datetime or ISO timestamp string, requires a timezone-aware
zero UTC offset, and rejects epoch-number coercion. Release metadata must be fixed
by the future canonical builder rather than generated from the current time.

`clockBasis` is `source_elapsed_ms`. It identifies the elapsed CSV field without
claiming monotonic provenance. Legacy wall-clock-derived elapsed timestamps and
their limitations remain documented in
[`METRIC_SEMANTICS_V2.md`](METRIC_SEMANTICS_V2.md).

## Immutability and determinism

Both models are frozen. Raw fields, available aggregations and definitions are
tuples detached from caller-owned lists. Validation rejects duplicates and
canonicalizes raw-field/aggregation order and registry definition order by name.
A registry cannot contain two definitions with the same name, even when their
semantic versions differ. The primary aggregation must belong to the available set.

Use validated constructors or `model_validate`. As with all Pydantic contracts,
`model_construct`, unvalidated `model_copy(update=...)` and low-level attribute
mutation are trusted escape hatches, not public validation boundaries.
Cross-field validators enforce model invariants beyond what generated JSON Schema
can express; importing external data always requires model validation.

Serialize with `model_dump_json(by_alias=True)` or
`model_dump(mode="json", by_alias=True)`. For file ingestion, use the existing
`load_model_file(path, MetricRegistry)` in
[`json_io.py`](../../src/latency_fingerprinting/json_io.py), which retains the P0
size, nesting, UTF-8, duplicate-key and finite-number protections. Pydantic's
`model_validate_json` is useful for trusted round trips but cannot serve as a
duplicate-safe untrusted file reader.

[`test_measurement.py`](../../tests/models/test_measurement.py) covers these
invariants, JSON aliases/schema shape, deterministic ordering, immutability,
finite/overflow input and root/nested duplicate-key rejection. Checked-in schema
artifacts and export/drift commands are implemented with the Step 3
[`canonical registry`](CANONICAL_REGISTRY.md).
