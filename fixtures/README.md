# Regression fixture inventory

These are software-test inputs and expected outcomes. Sanitized recorded
experiments belong in [`experiments/`](../experiments/CONTROLLED_RUN_PROCESSING.md),
and raw/private captures and session notes belong in ignored `local/`.
Artificial fixtures can exercise controlled-real model branches without being
measured acquisitions; consult each family's provenance and contract.

| Family | Purpose and maintenance reference |
| --- | --- |
| `reference_cases/`, `query_cases/` | Original P0 fingerprints, responses and positive/unknown match cases; [`synthetic/`](../src/latency_fingerprinting/p0/synthetic/rendering.py) checks deterministic rendering |
| `measurement/` | [N1 gauge/counter arithmetic](../docs/measurement/ARITHMETIC_FIXTURES.md), including gaps, resets, rejected samples and boundary conditions |
| `observation-v2/` | [N2 adoption and standalone observation records](../docs/measurement/OBSERVATION_V2_FIXTURES.md) |
| `analytical-v2/` | [N3 response, fingerprint and matching snapshots](../docs/analysis/N3_ANALYTICAL_FIXTURES.md) with independent numerical expectations |
| `observability/` | [Frozen N4 host/browser trace examples](observability/README.md) |
| `browser-execution-v1/` | [Additive browser execution-timing method](../docs/observability/N4_BROWSER_EXECUTION_CONTRACT.md); its directory release is distinct from trace schema versions |
| `scenarios/` | [N5 experiment, effect and cleanup cases](../docs/scenarios/N5_EXPERIMENT_FIXTURES.md) |
| `calibration-v1/` | [N6 source/label/split inspection cases](../docs/calibration/N6_FIXTURES.md), retaining excluded and invalid evidence |
| `profiles-v1/` | [N7 fitting and lifecycle outcomes](../docs/profiles/N7_FIXTURES.md) |
| `profile-matching-v1/` | [N8 matching, evaluation and group-refit outcomes](../docs/profile_matching/N8_FIXTURES.md) |
| `passive-gating-v1/` | [N9 baseline/replay/results and original source bytes](../docs/passive_gating/N9_FIXTURES.md) |

[`tests/data/`](../tests/data/pixelated_bundle/README.md) separately supplies small
upstream adapter inputs and test-support data. Those source examples serve a
different boundary from the expected output records here. Older versioned families
remain active compatibility checks; a newer method does not supersede their
contract or permit deleting their regression cases.

N10 evidence tests build small synthetic cases under
[`tests/live_probes/`](../tests/live_probes/) rather than adding native acquisition
dumps here. Those builders exercise custody, reconstruction and rejection
boundaries; they are invented test inputs, not qualified runtime evidence.

## Why complete records grow

A retained result can embed a policy, source dataset/report, fitted baseline,
original measurement windows, replay events and every derived row/state. Full
canonical snapshots check all those fields and their content IDs together;
small arithmetic projections alone cannot catch a dropped exclusion, forged
state field, source substitution or changed serialization. Longer cooldown and
whole-group-refit histories therefore have larger expected outcomes.

Some identical files are intentional. The same source can appear in multiple
experiment directories with different manifests or bindings; an identical false
baseline can test both standalone validation and linked source inspection.
N3 also deliberately reuses an N2 observation's exact bytes. These uses are not
additional independent acquisitions. Within N9, content-addressed flat source
members already share identical source bytes across histories.

## Adding, updating and retiring fixtures

- Add a fixture for a distinct contract, regression boundary or independently
  authored expected outcome, and give it an actual test/reproduction consumer.
- Reuse explicitly pinned upstream releases where possible instead of copying
  an earlier corpus wholesale. Keep separate raw-byte receipts and normalized
  semantic identities when wire aliases differ.
- Keep fixtures minimal within their contract: complete retained roots are useful;
  unrelated captures, generated dumps and audit receipts are not regression cases.
- Treat exact inventories, original bytes, content IDs and release pins as part of
  the check. Do not replace files with symlinks or rewrite expected results merely
  to make current production output pass.
- When a case is genuinely retired or a release format changes, review every
  consumer and dependent release, version the affected corpus as appropriate,
  then update its inventory, independent expectations and pins together.

Run the relevant read-only reproductions and installed-wheel checks from the
[testing guide](../docs/measurement/QUALITY_GATES.md). Fixture changes require
reviewed expectations, not an automatic bless/update mode.
