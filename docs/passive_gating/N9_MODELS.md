# N9 models and pure operations

N9 provides `PassiveGatePolicy`, `PassiveBaseline`, `PassiveReplay` and
`PassiveGateResult`, available from both `latency_fingerprinting.passive_gating`
and `latency_fingerprinting.models`. The [contract](N9_PASSIVE_CONTRACT.md) and
[replay rules](N9_REPLAY_CONTRACT.md) define their exact meanings and limits.

All four models are immutable. Nested N2 windows, N6 dataset/report declarations
and copied instances revalidate; caller-owned lists and maps are snapshotted.
The policy accepts only the approved content, even if changed parameters are
rehashed. Baseline statistics, input selection, group voting, support, every
result row/state, final state and counts reconstruct from retained operands.
Rehashing a changed derived field does not make it valid.

## Pure baseline and replay

These operations perform no file reads, source inspection, timers or producer
calls. Their evidence is supplied explicitly:

```python
from latency_fingerprinting.passive_gating import (
    PassiveGatePolicy,
    create_passive_replay,
    evaluate_passive_replay,
    fit_passive_baseline,
)
from latency_fingerprinting.passive_gating.policy_release import approved_policy_payload

policy = PassiveGatePolicy.model_validate(approved_policy_payload())
baseline = fit_passive_baseline(evidence, training_windows, policy)
replay = create_passive_replay(
    baseline,
    mode="validation",
    stream=stream_descriptor,
    start_ms=0,
    windows=original_query_windows,
    events=events,
)
result = evaluate_passive_replay(baseline, replay, policy)
```

`evidence` has exactly `dataset` and `report`, containing consistent N6 models or
their JSON data. `training_windows` maps entry IDs to original N2 windows for
**exactly** the metadata-eligible healthy training entries. Include windows whose
selected FPS metric is unusable, so their groups remain in the availability
denominator. Omit metadata-excluded entries. Missing or surplus keys fail.

The stream descriptor contains acquisition_namespace, run_id, clock_domain_id,
generation_id and stratum_id. The factory supplies stream_id; if supplied by the
caller, it must match. `original_query_windows` is an artifact-ID-sorted list of
`{artifact_id, window}` records. `events` is an ordered list of objects with kind,
at_ms, entry_id and reset_reason, including explicit nulls. The factory supplies
event_id; any supplied event_id must match. The replay retains the exact baseline,
dataset and policy identities. It has no mutable continuation state.

`evaluate_passive_replay` validates the baseline/replay/policy, checks all event
references against that baseline's dataset before processing events, and returns
a fully reconstructable result. Unknown entries, missing or surplus windows,
contradictory source bindings and mismatched original end times fail even after
a terminal reset. No later event can restore an invalidated generation.

Pure factory failures expose `invalid_passive_baseline` or
`invalid_passive_replay`. Invalid arithmetic fails the whole operation. Low FPS,
unsupported evidence, rejected baselines, stale input, cooldown and exhausted
proposal budgets remain explicit outcomes where the contract permits them.

## Validation and schemas

```sh
latency-fingerprint validate passive-result.json
latency-fingerprint export-schemas --output schemas --check
python -m pytest tests/passive_gating
```

Generic validation supports the four new schema versions. JSON readers reject
duplicate keys, nonfinite values, excess depth and oversized input. Python model
validation also bounds trees, total groups and entry references before constructing
nested models. Ordered collections reject iterators and sets. Canonical root
bytes are limited to 10 MiB; histories are bounded at 256 events with no eviction
or truncation. Earlier schema and registry bytes remain unchanged.

Identities use normalized `model_dump(mode="json")` content. N2 wire aliases are
also accepted during parsing and may appear in generic CLI output/schema exports.
Typed canonical N2 bytes are not an original artifact's raw file SHA. A valid
standalone declaration does not authenticate reviews, independence, source files,
the generation, or a real monotonic clock. [Linked build/replay APIs and
commands](N9_COMMANDS.md) inspect actual source bytes and verify the complete fresh
fit/query snapshot before evaluation. Frozen runtime reproduction remains later
work. No `probe` row is an execution receipt.
