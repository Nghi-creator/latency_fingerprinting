# Testing and reproducibility

Run checks from an installed development environment:

```sh
python -m pytest --cov=latency_fingerprinting --cov-branch \
  --cov-report=term-missing --cov-fail-under=85
ruff check .
ruff format --check .
python -m pip check
python -m latency_fingerprinting export-schemas --output schemas --check
python -m latency_fingerprinting export-metric-registry \
  --output schemas/metric-registry-v1.json --check
```

CI checks pushes and pull requests targeting `main` or `phase_2`, using Python
3.13 and the minimum supported Python 3.11 for the core suite.
The branch-inclusive coverage floor is 85%. Tests cover P0 compatibility,
registered aggregation, v2 adoption/matching, trace reconstruction, bounded file
and archive inputs, finite arithmetic, provenance and scenario inspection.

Each Python job has a 30-minute budget for setup, coverage, independent
reproductions and the installed-wheel check. The test step is separately bounded
to 20 minutes and reports its 25 slowest tests. Coverage and case inventories are
unchanged by these time budgets. A rerun of an old commit still uses that commit's
workflow; changed budgets take effect on a run containing the workflow update.

## Frozen fixture reproduction

```sh
python -m tests.measurement.check_reproduction
python -m tests.observation_v2.check_reproduction
python -m tests.analytical.check_reproduction
python -m tests.observability.check_reproduction
python -m tests.observability.check_browser_execution
python -m tests.scenarios.check_reproduction
python -m tests.calibration.check_reproduction
python -m tests.profiles.check_reproduction
python -m tests.profile_matching.check_reproduction
python -m pytest tests/profile_matching
python -m pytest tests/passive_gating
python experiments/controlled-run-001/record_seed_fingerprint.py --check
```

These commands check release pins and independent expectations without blessing
drift or regenerating expected results. Synthetic arithmetic is software evidence,
not a replacement for live capture. Versioned browser methods retain separate pins.
N8 tests pin independent policy/vectors and check immutable standalone models,
exact pure scoring/refits, complete result reconstruction and validation dispatch.
Linked N8 checks cover one-inspection source binding, fresh training verification,
query extraction, group refits and private commands with protected output.
N9 pins its original design policy/vectors and tests exact pure arithmetic,
baseline fitting, typed replay histories, immutable full-root reconstruction,
rehashed tampering, source declarations, bounded inputs and generic validation.
Linked N9 checks verify one-inspection source binding, fresh complete fits,
source-extracted queries, aliases, byte budgets, private errors and protected
output. Installed-wheel checks exercise all four roots, pure/linked APIs and both
commands. A frozen N9 runtime corpus remains subsequent work.

## Installed package

```sh
python -m tests.packaging.check_wheel
```

This builds a wheel and installs it in a fresh temporary environment outside the
checkout. It verifies the import location, console entry point, all frozen N6
calibration cases and the [frozen N7 profile corpus](../profiles/N7_FIXTURES.md),
including standalone validation, linked builds, lifecycle operations, private
errors/preserved output, N8 standalone match/evaluation roots, linked N8 match
and all three evaluation modes, the complete
[frozen N8 corpus](../profile_matching/N8_FIXTURES.md), N9 standalone models,
pure baseline/replay, linked source verification, both protected N9 commands,
generic validation and schema exports.
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
