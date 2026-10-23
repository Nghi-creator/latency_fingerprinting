# Linked passive baseline and replay

N9 links its [immutable models and pure operations](N9_MODELS.md) to actual N6
source files. Each operation performs one fresh N6 inspection. It does not start
timers, contact the producer, execute probes or persist mutable detector state.

## Python API

```python
from latency_fingerprinting.passive_gating import (
    build_passive_baseline,
    replay_passive_gate,
)

baseline = build_passive_baseline(
    directory,
    policy,
    expected_split_id=split_id,
    expected_dataset_content_hash=dataset_content_hash,
)
result = replay_passive_gate(
    directory,
    baseline,
    replay,
    policy,
    expected_split_id=split_id,
    expected_dataset_content_hash=dataset_content_hash,
)
```

`directory` is a flat N6 calibration directory containing its manifest and exactly
the declared artifacts. `policy` is the approved PassiveGatePolicy model or its
JSON data. The optional split/dataset anchors default to None and are checked by
the N6 inspector. `baseline` and `replay` accept their immutable models or JSON
data; copied instances revalidate.

The builder extracts original N2 windows for exactly the metadata-eligible
healthy training entries. Other entries retain exclusions. A valid dataset with
insufficient or synthetic evidence can produce a rejected baseline; the builder
does not manufacture healthy groups or bypass N6 exclusions.

The replay operation rebuilds the entire baseline from its one inspected object
and compares it with the supplied baseline, including all retained windows,
exclusions, statistics, dataset/report declarations and identities. It extracts
every referenced passive query from that same object's verified records and
compares the complete N2 window with the retained replay operand. Query pools are
bounded before serialization. Only then does it evaluate a result using those
source-extracted windows. Missing and response entries supply no passive window;
response relief is never substituted for a passive observation.

All references validate before any transitions, including references after a
terminal reset. Missing, surplus, altered, rehashed or stale operands fail rather
than being silently replaced. Updating a source file and its manifest receipt
creates a new dataset snapshot: an old baseline/replay cannot be reused even if
the fitted FPS center happens to remain unchanged. Rebuild the baseline and
prepare a replay bound to that exact snapshot.

Successful results are identical to pure evaluation of the same verified
declarations. Acquisition reviews, generation identity and independence remain
external declarations. Fresh inspection verifies bytes and bindings, not the
truth of those declarations or monotonic clock behavior. Evidence is pinned for
one operation; this is not a continuous filesystem monitor or a live-control
lease. A `probe` recommendation remains an offline proposal.

API failures expose only ValueError with `invalid_passive_baseline` or
`invalid_passive_replay`.

## CLI

```sh
latency-fingerprint build-passive-baseline \
  --directory calibration-evidence \
  --policy docs/passive_gating/N9_PASSIVE_POLICY_SPEC.json \
  --output local/passive-baseline.json

latency-fingerprint replay-passive-gate \
  --directory calibration-evidence \
  --baseline local/passive-baseline.json \
  --replay local/passive-replay.json \
  --policy docs/passive_gating/N9_PASSIVE_POLICY_SPEC.json \
  --output local/passive-result.json
```

Prepare passive-replay.json using the fields and `create_passive_replay` operation
in the [model guide](N9_MODELS.md). Its validation/final_test mode, stream identity,
explicit ticks/resets and complete bounded event history are retained in the
replay file. No additional mode or evaluation-time CLI flag overrides them.

Both commands support `--expected-split-id` and
`--expected-dataset-content-hash`. The output parent must already exist. Successful
commands are silent and write canonical normalized JSON through an atomic private
0600 file. Existing ordinary output may be replaced. Input operands, the actual
inspected source directory and its members are protected, including hardlinks
outside the directory and paths renamed after inspection. Symlink operands or
parents and nonregular input/output files are rejected. New output inside the
source directory is also refused.

Operational failures preserve prior output, leave no partial file and print only:

```text
error: build-passive-baseline: invalid_input_or_output
error: replay-passive-gate: invalid_input_or_output
```

Missing required arguments remain argparse syntax errors. These commands do not
change any producer settings or earlier measurement/matching releases. A frozen
N9 runtime reproduction corpus remains separate from these source-binding and
installed-package checks.
