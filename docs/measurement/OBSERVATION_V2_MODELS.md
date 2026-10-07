# N2 strict observation models

Step 2 implements the [v2 field contract](OBSERVATION_V2_CONTRACT.md) through four
focused modules, exported additively from the public `models` package:

| Module | Responsibility |
| --- | --- |
| [v2_common.py](../../src/latency_fingerprinting/models/v2_common.py) | Deeply immutable JSON/context, known capture methods and trusted registry identity |
| [v2_support.py](../../src/latency_fingerprinting/models/v2_support.py) | Elapsed/UTC clock bounds, typed source/metric support, validity and unavailable stage timing |
| [observation_v2.py](../../src/latency_fingerprinting/models/observation_v2.py) | Exact 31-output inventory, definition/window binding, safe diagnostics and equal counter rate/total evidence |
| [observation_pair_v2.py](../../src/latency_fingerprinting/models/observation_pair_v2.py) | Recorded interventions and degraded/relief comparability |

`ObservationWindowV2` uses `observation-window-v2`; `ObservationRecordV2` uses
`observation-v2`. Both require explicit `contractVersion: "2.0.0"`. P0 version
constants and roots are unchanged. No response delta, normalization or matcher
adoption is added to these models. The separate [v2 importer/command](OBSERVATION_V2_ADOPTION.md)
is implemented in Step 3.

## Validated construction and file boundaries

Use `ObservationWindowV2.model_validate(payload)` or
`ObservationRecordV2.model_validate(payload)` for in-memory inputs. For untrusted
files, use the existing duplicate-safe bounded reader:

```python
from pathlib import Path
from latency_fingerprinting.json_io import load_model_file
from latency_fingerprinting.models import ObservationWindowV2

window = load_model_file(Path("window-v2.json"), ObservationWindowV2)
```

Nested context/settings maps and arrays are detached and frozen; source/measurement
maps are read-only and nested models are frozen. JSON serialization restores normal
objects/arrays and respects `by_alias`. Use the existing `canonical_json` renderer
for deterministic sorted camelCase JSON with a trailing newline. Pydantic JSON
round trips are tested but do not replace duplicate-safe untrusted file loading.
Unvalidated `model_construct`, `model_copy(update=...)` and low-level mutation
remain trusted escape hatches, not ingestion boundaries.

## Meaning and evidence validation

The registry reference accepts only the frozen canonical version/hash pair and
verifies that the in-package registry renderer still produces the pinned bytes.
Resolution is lazy to avoid the existing models/schema/registry import cycle;
no file path, URL or supplied definition is resolved from a record. Each summary
must agree with its resolved definition and the window's clock/bounds. Counter
reset transitions rejected by the canonical policy cannot become accepted or
wrapped intervals. Gauge statistics must be ordered and non-negative where required.

Typed source and metric support declarations follow explicit precedence, including
unsupported declarations overriding stale values. Missing/rejected/partial/zero
states retain N1 semantics. Audit totals cannot claim the analytical-candidate role;
counter rate/total outputs must have identical support and accepted evidence.
Diagnostic text is limited to the field contract's fixed vocabulary. Nested known
private metadata keys are rejected; caller-provided identity labels still require
sanitized research aliases.

Pair construction requires compatible context, registry, capture method and clock
meaning, correct window/probe identities, valid windows, comparable durations and
an applied recorded intervention. Independent run clock-domain identifiers can
differ. Partial metric support is retained rather than filled or discarded.
Simulated pairs cannot claim runtime execution; real pairs require executed metadata
and observed settings. Undeclared setting changes require explicit confounder codes.

Stage timing admits empty or explicitly unavailable evidence only. No measured or
estimated method is approved. Timing reasons declaring an unsupported/unavailable
source must agree with the source support record. Existing interval means/proxies
are not reclassified as direct stage latency.

## Schemas and CLI

Two new files are generated additively:
[window schema](../../schemas/observation-window-v2.schema.json) and
[observation schema](../../schemas/observation-v2.schema.json).
`export-schemas --check` now checks all six schema files without writing.
Cross-field rules require Python model validation; JSON Schema alone cannot
authenticate registry contents or prove numerical/source compatibility.

```bash
latency-fingerprint validate path/to/window-v2.json
latency-fingerprint validate path/to/observation-v2.json
latency-fingerprint export-schemas --output schemas --check
```

Existing `match` and `build-response` commands reject v2 records through their
unchanged v1 loaders. No v1 record or production match result is generated from v2.

The [window tests](../../tests/models/test_observation_v2.py) and
[pair tests](../../tests/models/test_observation_pair_v2.py) add 168 cases covering
meaning, support, arithmetic evidence, privacy, strict values, immutability,
round trips, schema conformance, root validation, duplicate keys and P0 isolation.
Their [synthetic input builder](../../tests/models/v2_cases.py) is test support,
not a production importer or a scientific measurement. Deterministic adopted-record
fixtures and raw-bundle reproduction are later N2 gates.
