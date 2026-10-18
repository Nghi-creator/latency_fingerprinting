# N5 independent experiment fixtures and reproduction

See [inspection](N5_EXPERIMENT_INSPECTION.md) and the [contract](N5_EXPERIMENT_CONTRACT.md).

The `fixtures/scenarios/` corpus contains eight independently authored synthetic
cases, 80 JSON files and 280,156 bytes. Fixtures were constructed from the frozen
contract arithmetic and explicit N4 event/capability expectations, independently of
producer export and effect calculation. Every byte is pinned in
`tests/scenarios/check_reproduction.py`; there is no regeneration/update mode.
`expected.json` is a separate expectation, never a bundle member. Changing a
result does not change that expectation automatically.

| Case | Expected result/effect | Evidence distinction |
| --- | --- | --- |
| healthy | completed / verified | All evaluated phases 30 fps, no workers or pressure |
| host | completed / verified | Healthy/recovery 30 fps, degraded 24 fps, CPU 60% |
| boundary | completed / verified | Degraded/recovery 28.5 fps, CPU 50%; inclusive thresholds |
| failed-pressure | completed / failed pressure_not_observed | CPU 40%; action startup is insufficient |
| cancelled | aborted / unavailable incomplete_run | 25-second degraded prefix, observed stop/restoration |
| unsupported | unsupported / unavailable adapter_unavailable | No execution, artifacts or rates |
| missing-trace | aborted / unavailable incomplete_run | Raw phases retained; no substituted traces |
| unknown-cleanup | aborted / unavailable incomplete_run | Stop offsets null, restoration unverified |

All manifests declare synthetic provenance and engineering assignment. Repeated
export-local aliases do not imply independent acquisitions. No fixture is a real
reference or held-out query. Four fresh measured-phase collectors use sampling
1/1000 with bounds 2 frames/10 events, keeping the corpus compact. Their single
sample per phase does not satisfy real capture/coverage acceptance. Raw counters
retain all second intervals; event timing and interval timing remain separate clocks.
Fixed runtime/commit strings are synthetic declarations, not measured versions.

Read-only core check, including independent expectations and directory API/CLI:

```sh
.venv/bin/python -m tests.scenarios.check_reproduction
```

For the actual producer-to-core path, create an existing disposable directory and
run the producer's fixed synthetic driver from its trusted checkout:

```sh
mkdir -p /private/tmp/n5-reproduction
python3 scripts/n5/exportSyntheticExperiments.py /private/tmp/n5-reproduction
```

Then from the core checkout:

```sh
.venv/bin/python -m tests.scenarios.check_reproduction \
  --producer-bundles /private/tmp/n5-reproduction
```

The producer script uses explicit synthetic integer execution inputs and actual
fresh `HostTraceRecording` collectors and production exporter. It never invokes
ScenarioRunner, GI, a workload, native workers, pressure, networking or real capture.
It publishes eight deterministic private gzip USTARs and is silent on success.
The core checks every uncompressed member byte against the independent fixtures,
validates/adopts the models and independently recomputes effects, then compares
canonical API and CLI outputs. Producer unit tests separately pin a digest of each
bundle's sorted member-name/SHA-256 map. Compressed gzip hashes are intentionally
excluded because their header bytes differ across supported Python versions.

Core regressions verify read-only checks, changed/missing/extra file drift,
independent expectation failure, every archive, missing/corrupt/wrong-case producer
outputs and fixed command failures. Producer regressions exercise actual export,
release content pins, repeated-export determinism, silent CLI/private output and
sanitized failure. Both configured core CI jobs include this gate; the producer's
existing Node scenario wrapper discovers its new Python reproduction tests.
Configured CI is separate from observed hosted/minimum-version execution.
