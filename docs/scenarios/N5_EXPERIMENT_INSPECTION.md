# N5 experiment export and detached inspection

**Delivered:** Step 6 software, 2026-10-11. [Contract](N5_EXPERIMENT_CONTRACT.md),
[active plan](../plans/NEXT_IMPLEMENTATION_PLAN.md). [Independent release fixtures
and reproduction pins](N5_EXPERIMENT_FIXTURES.md) are delivered in Step 7; real campaigns remain Step 8.

Pixelated's `scenario_harness` exports `experiment_bundle_bytes(manifest, plan,
execution, recordings=(), observation_windows=())`, `unsupported_bundle_bytes(manifest)`
and `write_experiment_bundle(path, payload)`. The producer guide is
`Pixelated-Studio-Edition/docs/n5-experiment-export.md`. Export runs after collection
freezes and cleanup completes, outside frame callbacks. Caller-declared sanitized
runtime/workload/seed metadata must agree with the validated plan. No core dependency
enters the producer runtime.

The deterministic gzip USTAR contains two roots and hash-bound canonical artifact
JSON. Actual six-phase raw integer evidence, four fresh measured-phase N4 collector
snapshots and optional existing observation windows retain their meanings. Unknown
private fields, foreign collectors and plan drift reject. Missing frozen traces or
raw phase evidence retain an aborted result with unavailable effects. Unsupported
adapters export no execution or rates. Unknown action cleanup timing remains
unverified: private watchdog timestamps cannot substitute for runner-relative times.

```python
from pathlib import Path
from latency_fingerprinting.scenarios import inspect_experiment_bundle

inspected = inspect_experiment_bundle(Path("experiment.tar.gz"))
assert inspected.effect == inspected.result.effect
```

```sh
latency-fingerprint inspect-experiment --bundle experiment.tar.gz --output result.json
```

The API returns immutable validated manifest/result/effect models and an ordered
artifact tuple. It reads an exact directory or gzip USTAR without extraction,
producer execution or remote access. Bounds are 20 regular members, 10 MiB per
JSON and 64 MiB compressed/expanded or aggregate directory bytes. Paths are pinned
with no-follow opens. Duplicate keys/files, extra or absent members, special files,
symlinks, TAR extensions and hidden nonzero trailers reject.

Inspection verifies raw manifest/artifact hashes and lengths, run/clock/phase
ownership, requested actions, completed phase duration tolerance, worker counts,
frame-counter continuity, trace producer/provenance/version and sampling policy.
Completed action durations must remain within the declared bound; aborted overruns
remain truthful failure evidence. Partial evidence never fills missing intervals.
Existing N4 source aliases and observation phase/clock fields are preserved; their
hash-bound N5 phase mapping does not establish source-run disjointness.

The core independently recomputes the fixed effect from raw integer intervals.
A complete run with verified cleanup still needs complete evidence for all six
phases and at least 30 intervals/30 seconds in healthy/degraded/recovery. Baseline
must reach 27 fps. Host contention needs at least 50% of one CPU, degraded rate at
most 95% of healthy and recovery at least 95% of healthy. Healthy needs degraded
and recovery at least 27 fps. Cross-multiplication determines threshold boundaries;
floating rates are presentation only. Supplied claims that disagree reject.

CLI success is silent and writes canonical `ExperimentResult` atomically with mode
0600. Failure emits exactly `error: inspect-experiment: invalid_input_or_output`
and preserves an existing output. API failures are `ValueError("invalid_experiment_bundle")`
with no supplied data/path echo. Generic `validate` checks standalone shapes;
use inspection for linked verification.

Independent regressions cover hashes/ownership/policy drift, threshold equality,
partial evidence, old observation meanings, unsafe containers and preserved output.
Actual synthetic producer collectors/exporters passed core API and CLI for healthy,
host contention, failed pressure, unsupported runtime, missing traces and unknown cleanup timing. This is
software integration evidence, not live capture, measured overhead, scientific
causality, calibrated confidence or source independence. Earlier schemas, fixture
pins, metric registry and feature policies remain unchanged.
