# N3 pure response derivation

**Delivered:** Step 3, 2026-10-08
**Contract:** [Analytical field contract](N3_ANALYTICAL_CONTRACT.md)
**Models:** [Strict policy and response models](N3_ANALYTICAL_MODELS.md)

`derive_analytical_response(observation, policy)` takes an `ObservationRecordV2`
and an explicit `FeaturePolicyV1`. It revalidates both inputs, including copied
model instances, and returns a root-validated immutable `AnalyticalResponseV2`.

```python
from pathlib import Path

from latency_fingerprinting.analytical.responses import derive_analytical_response
from latency_fingerprinting.json_io import load_model_file
from latency_fingerprinting.models import FeaturePolicyV1, ObservationRecordV2

observation = load_model_file(Path("observation.json"), ObservationRecordV2)
policy = load_model_file(Path("policy.json"), FeaturePolicyV1)
response = derive_analytical_response(observation, policy)
```

The file reads above are the caller's choice; derivation itself reads or writes no
files. It uses no current time or random identifiers. The response ID hashes the
canonical embedded observation and policy, so repeat calls produce identical JSON.
Invalid models or altered policies fail before derivation; accepted incomplete or
confounded observations produce auditable exclusions rather than replacement zeros.

For each of the 22 policy features, the result retains primary degraded/relief
values, unit, aggregation, support/status, coverage, sample/interval counts and
duration. Eligible calculations are:

- `rawDelta = reliefPrimary - degradedPrimary`
- `referenceValue = degradedPrimary`
- `denominator = max(abs(referenceValue), epsilon)`
- `normalizedValue = rawDelta / denominator`

The approved epsilon is 1.0 in each feature's canonical unit. A primary zero is
numeric: zero to zero yields 0; zero to 2 yields 2. A 60 to 30 change yields -0.5;
0.25 to 0.5 yields 0.25 because the floor is 1. There is no clipping. Arithmetic
must remain finite; malformed non-finite input fails revalidation. With approved
nonnegative primaries and epsilon 1.0, normalization cannot amplify a finite delta
into overflow.

Counter features consume N1's interval-derived primary rates. Equivalent activity
at doubled sampling intervals retains the same rate response even when audit
totals double. Derivation neither recalculates rates from totals nor subtracts
cross-domain timestamps. Audit totals, the unsupported pipeline proxy and unavailable
stage timings are absent from the analytical inventory.

Per-window exclusions retain the contract's priority and degraded/relief order.
Any pair confounder overrides them with `confounded_pair` for every feature.
Excluded calculations are null. Entirely excluded evidence is invalid with
`no_eligible_features`; partially eligible responses remain valid without implying
sufficient evidence for a later match.

30 new tests compare full records against independently authored expectations and
check cadence, numerical boundaries, partial evidence, confounders, copied-model
revalidation and unchanged inputs. At Step 3, the full local suite passed 1,290 tests with
93.15% branch-inclusive coverage; existing schemas and reproduction pins are
unchanged. Actual Python 3.11/hosted verification remains pending.

[Step 4 fingerprints and bounded repository loading](N3_FINGERPRINTS.md) are now
implemented, along with [Step 5 v2 matching](N3_MATCHING.md). Next is Step 6
additive commands. The proposed
`build-response-v2` command belongs to Step 6; current CLI root validation can
validate a serialized derived response.
