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

CI runs pull requests targeting `main` or `phase_2`, and pushes to those two
branches, on Python 3.13 and the minimum supported Python 3.11. Feature branches
run through their pull request to avoid duplicate push/PR suites. Before opening
a pull request, use the local commands above or manually dispatch the CI workflow.

Each Python version runs the complete collected suite across four independent
runners. The opt-in `tests.ci.sharding` plugin assigns each test function to
exactly one shard using SHA-256 of its stable file/class/function name. Parameter
cases stay together, so generated parameter IDs cannot change ownership between
processes. Newly added tests are included automatically.
Normal local pytest runs still execute the whole suite. To reproduce one shard:

```sh
python -m pytest -p tests.ci.sharding --shard-index=0 --shard-count=4 \
  --cov --cov-branch --cov-report= --cov-fail-under=0 --durations=25
```

The zero floor applies only to partial coverage files. Final `quality` and
`python-311-compatibility` gates require every shard and release check to pass,
require all four coverage artifacts for their Python version, combine them, then
enforce the unchanged **85% branch-inclusive full-suite coverage floor**.
Coverage uses relative source paths so separate runners can combine their data.
Missing, empty or invalid coverage artifacts, failed tests or failed release
checks fail the final gates.

Each test shard has a 25-minute job budget and a separate 20-minute test-step
limit, reporting its 25 slowest tests. Frozen release reproduction, installed-wheel
verification, lint, schemas/registry and controlled-real P0 artifact checks run
in separate 20-minute release jobs for both Python versions. The final coverage
gates have a 10-minute budget. This separates independent workloads without
removing cases or reducing validation. Rerunning an older commit uses its old
workflow; the new execution layout takes effect on a commit containing it.

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
python -m tests.passive_gating.check_reproduction
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
commands. The [frozen N9 corpus](../passive_gating/N9_FIXTURES.md) adds full
independent results, exact source bytes and before/after dependency pin checks.

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
the complete [frozen N9 corpus](../passive_gating/N9_FIXTURES.md), pure
baseline/replay, linked source verification, both protected N9 commands,
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
