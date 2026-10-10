# N5 strict experiment records

**Delivered:** Step 3 software, 2026-10-10.
**Contract:** [Frozen v1](N5_EXPERIMENT_CONTRACT.md).
**Independent cases:** [Step 2 examples](N5_EXPERIMENT_EXAMPLES.md).
**Next:** [Step 4 bounded producer lifecycle and recording control](../plans/NEXT_IMPLEMENTATION_PLAN.md).

The detached core exports `ExperimentManifest`, `ExperimentPhaseEvidence` and
`ExperimentResult` from `latency_fingerprinting.models` and
`latency_fingerprinting.scenarios`. They declare requested configuration, actual
raw counters and execution/effect/cleanup state respectively. They have no runtime
or filesystem side effects and introduce no matcher features or policy changes.

The three corresponding `experiment-*-v1.schema.json` files are additive.
`export-schemas --check` checks fifteen schemas; all twelve earlier schema bytes
remain unchanged. JSON Schema describes shape and primitive bounds. Cross-field
rules below require Python validation; schema validation alone cannot prove them.

```python
from latency_fingerprinting.models import ExperimentManifest

manifest = ExperimentManifest.model_validate_json(manifest_bytes)
```

```sh
latency-fingerprint validate experiment-manifest.json
latency-fingerprint validate artifact-1.json
latency-fingerprint validate experiment-result.json
latency-fingerprint export-schemas --check
```

Generic validation dispatches by the three snake_case `schema_version` values and
prints existing canonical JSON. It validates one supplied root and reads no
referenced artifacts. The existing camelCase roots and N4 commands retain their
formats and behavior. Public imports are covered in isolated CLI subprocesses.

## Enforced invariants

Every required field is explicit, including nullable values. Unknown fields,
versions, methods, actions and adapter names fail. Models are frozen, collections
become immutable tuples, mutable caller inputs are detached and copied nested
instances are revalidated. Integers reject coercion, configuration constants reject
floats, floating values reject strings/booleans/nonfinite inputs and normalize
negative zero. JSON input rejects duplicate keys, invalid UTF-8, more than 10 MiB
or nesting beyond 32. Container bounds apply before element validation.

Manifest validation enforces aliases/commits, runtime/provenance agreement, closed
scenario/adapter mapping, six fixed planned phases, watchdog/pressure allowance,
CPU allocation and exact integer ceiling arithmetic for per-phase trace capacity.
Unavailable host preflight retains its requested action; unsupported scenarios
cannot request actions. This does not certify declared tools or a live runtime.

Phase evidence enforces actual contiguous prefix coverage, full coverage for
complete records, empty unavailable records, interval duration bounds, frame
counter continuity and owned-worker CPU capacity. Missing evidence never becomes
fabricated zero samples. It does not pool independently scoped clocks.

Result validation enforces ordered phase prefixes and transition gaps, a single
final partial phase, action timestamp/state consistency, bounded cleanup, sorted
unique artifact IDs and role/phase ownership, safe filenames, bytes/hash syntax,
and required evidence/trace references for completed runs. Completed actions must
be stopped and restoration must precede recovery. Unsupported execution is empty
with no effect numbers; aborted results retain unavailable/incomplete_run
precedence. Completed execution can retain a failed effect. Unverified restoration
cannot supply an available effect or represent a successful trial.

## Checks requiring linked evidence

A valid standalone root does **not** verify its manifest hash, artifact hashes or
byte counts, correspondence to a requested action, planned-versus-actual timing,
expected worker counts, N4 trace producer/provenance or clock agreement. It also
does not prove sufficient effect samples, recompute the inclusive FPS/CPU
thresholds, or establish independent source runs/reference/query separation.

Step 6 bundle inspection will bind these roots and recompute effects from complete
hash-verified intervals using integer arithmetic. `inspect_experiment_bundle` and
`inspect-experiment` are still intended APIs. A supplied `verified` field passing
shape validation is not proof of a measured fault. Synthetic tests use explicit
placeholder artifact hashes/byte counts and cannot establish real capture.

## Verification

`tests/scenarios/` contains independent hand-authored Step 2 tables and 155
regressions for valid/failing plans, raw intervals, complete/aborted/unsupported
results, cleanup/action states, exact capacity ceilings, strict parsing, required
fields, immutable copies, JSON Schema shape and isolated generic CLI validation.
Expectations do not call a production exporter or effect derivation function.
No fixture release pins are created or refreshed; those remain Step 7 work.

The current full-suite and preservation results are recorded in
[N5 progress](N5_IMPLEMENTATION_PROGRESS.md). Producer runtime code is unchanged
in Step 3; its Step 1 full-suite counts remain historical. Actual Linux trials,
[N4 runtime/overhead acceptance](../observability/N4_RUNTIME_ACCEPTANCE.md), minimum
versions, hosted execution and two real fault classes remain pending.
