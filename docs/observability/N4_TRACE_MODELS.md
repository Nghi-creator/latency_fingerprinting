# N4 trace models and schema validation

**Meaning:** [Normative contract](N4_TRACE_CONTRACT.md).
See [host instrumentation](N4_HOST_INSTRUMENTATION.md),
[browser instrumentation](N4_BROWSER_INSTRUMENTATION.md),
[adoption](N4_TRACE_ADOPTION.md) and [reconstruction](N4_TIMING_RECONSTRUCTION.md).

`StageTraceRecord` and `StageTraceSummary` are available from
`latency_fingerprinting.observability` and `latency_fingerprinting.models`.
They use the specified snake_case JSON fields; legacy roots retain their existing
camelCase aliases. Both roots and every nested model are frozen, forbid extra
fields, snapshot list inputs into tuples and revalidate reused/copied instances.
All required nullable keys remain required. No free-form metadata or diagnostics
are accepted.

Implementation is split into [closed vocabulary/shared constraints](../../src/latency_fingerprinting/observability/contracts.py),
[record validation](../../src/latency_fingerprinting/observability/trace.py),
[summary validation](../../src/latency_fingerprinting/observability/summary.py) and
[bounded text decoding](../../src/latency_fingerprinting/observability/json.py).

```python
from latency_fingerprinting.observability import StageTraceRecord, StageTraceSummary

trace = StageTraceRecord.model_validate(payload)  # detached structured input
trace = StageTraceRecord.model_validate_json(json_text)  # bounded, duplicate-safe
summary = StageTraceSummary.model_validate(summary_payload)
```

The JSON entry point enforces 10 MiB/depth 32 before decoding, rejects duplicate
keys/nonfinite numbers and understands brackets inside escaped strings. Structured
input is already decoded: use the bounded JSON entry point at text boundaries,
not native Pydantic TypeAdapter decoding. Ordered collections require actual
lists/tuples; sets and arbitrary iterators cannot bypass capacity checks.

Record validation enforces stream order/unique epoch/clock scopes, clock/producer
agreement, complete ordered capabilities, source-local frame identity and sampling,
event references/order/unique endpoints, declared/total capacities, missing or
ambiguous correlation and exact conservation of ledger/event loss. Disabled
streams contain no evidence. Browser callbacks cannot claim host clocks/budgets.
Timestamp ties/interleaving and negative endpoint differences remain valid trace
input; reconstruction classifies negative pairs as exclusions rather than repairing them.

Summary validation independently reconstructs sample values and min/mean/max
from integer deltas, checks sample order and coverage/exclusions, requires all
four methods, applies producer/capability unavailability, and checks deadline
sample identity, slack, boundary-equality hits and hit fraction. Supported host
methods must agree on shared correlation exclusions. It normalizes floating
negative zero. A hash field alone does not authenticate a supplied summary;
[reconstruction](N4_TIMING_RECONSTRUCTION.md) recomputes it with its validated input record.

## Delivered commands and schemas

Existing `validate` recognizes the two new roots and prints canonical JSON:

```bash
.venv/bin/python -m latency_fingerprinting validate path/to/trace-record.json
.venv/bin/python -m latency_fingerprinting validate path/to/trace-summary.json
.venv/bin/python -m latency_fingerprinting export-schemas --check
```

The v1 schemas are [record](../../schemas/stage-trace-record-v1.schema.json) and
[summary](../../schemas/stage-trace-summary-v1.schema.json). JSON Schema describes
shape, closed enums, required fields and local bounds. Runtime validators enforce
cross-field identity, counts, alias suffix bounds and arithmetic that schemas
cannot fully express. Generic validate uses its existing file-reading boundary;
[trace-specific no-follow bundle ingestion](N4_TRACE_ADOPTION.md) and ingest-trace
are available. inspect-trace is delivered in [implementation guide](N4_TIMING_RECONSTRUCTION.md).

The [independent regression suite](../../tests/observability/test_contracts.py)
covers the [examples](N4_TRACE_EXAMPLES.md), false clocks/identities,
capabilities, versions, boolean/range errors, copied instances, partial correlation,
loss/sampling, resource caps, JSON ambiguity, unavailable results and deadline
arithmetic. These are software tests, not live measurement or overhead evidence.
N2 StageTiming and N3 matching retain their separate contracts.

## Browser execution v2

The additive [execution contract](N4_BROWSER_EXECUTION_CONTRACT.md) introduces
`StageTraceRecordV2` and `StageTraceSummaryV2` from the same public model modules.
These browser-only roots retain original API endpoints and add callback-entry
execution timing. V1 models still reject v2 payloads. Generic `validate`,
`ingest-trace` and `inspect-trace` explicitly dispatch on versioned roots; both
new generated schemas are checked alongside all original schemas. Shared
validation policies preserve the exact v1 schema and fixture bytes.
