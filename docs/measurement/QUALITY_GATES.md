# Testing and reproducibility

Run checks from an installed development environment:

```sh
python -m pytest --cov=latency_fingerprinting --cov-branch \
  --cov-report=term-missing --cov-fail-under=85
ruff check.
ruff format --check.
python -m pip check
python -m latency_fingerprinting export-schemas --output schemas --check
python -m latency_fingerprinting export-metric-registry \
  --output schemas/metric-registry-v1.json --check
```

CI runs the core suite on Python 3.13 and the minimum supported Python 3.11.
The branch-inclusive coverage floor is 85%. Tests cover P0 compatibility,
registered aggregation, v2 adoption/matching, trace reconstruction, bounded file
and archive inputs, finite arithmetic, provenance and scenario inspection.

## Frozen fixture reproduction

```sh
python -m tests.measurement.check_reproduction
python -m tests.observation_v2.check_reproduction
python -m tests.analytical.check_reproduction
python -m tests.observability.check_reproduction
python -m tests.observability.check_browser_execution
python -m tests.scenarios.check_reproduction
python experiments/controlled-run-001/record_seed_fingerprint.py --check
```

These commands check release pins and independent expectations without blessing
drift or regenerating expected results. Synthetic arithmetic is software evidence,
not a replacement for live capture. Versioned browser methods retain separate pins.

## Installed package

```sh
python -m tests.packaging.check_wheel
```

This builds a wheel and installs it in a fresh temporary environment outside the
checkout. It verifies the import location, console entry point and schema exports.
Normal package-index access is needed for build/runtime dependencies.

## Cross-repository checks

The [trace integration guide](../observability/N4_INTEGRATION_VERIFICATION.md) and
[scenario fixture guide](../scenarios/N5_EXPERIMENT_FIXTURES.md) show how to export
synthetic producer bundles and inspect them independently in the core.

In the Pixelated checkout, `npm run lint`, `npm test` and `npm run build` cover all
workspaces. `npm run verify:api` checks API contracts; `npm run verify:hosted-contract`
also exercises browser interactions and TLS isolation. Hosted workflows provide
Linux, image-security and desktop-platform checks.

For real instrumentation/campaign measurements, use the producer's
[live test procedure](../../../Pixelated-Studio-Edition/docs/n5-live-test-procedure.md).
Record exact source versions, workload, environment, all trial outcomes and cleanup.
Passing software checks does not establish real timing accuracy, acquisition
independence, diagnosis accuracy or platform behavior.
