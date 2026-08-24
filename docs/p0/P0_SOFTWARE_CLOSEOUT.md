# P0 Software Closeout

**Verified:** 2026-08-24
**Software status:** P0 vertical slice verified  
**Overall P0 status:** Complete as controlled-real integration-feasibility evidence

## Verified vertical slice

The checked-in synthetic path executes end to end:

```text
paired windows
-> comparability validation
-> raw response delta
-> normalized response
-> compatible fingerprint loading
-> weighted ranking and feature evidence
-> matched or unknown result
```

The Pixelated adapter also ingests controlled-real Pixelated bundles through
the same core window contract. Run 001 produces a valid normalized response and
a conservative `unknown` against incompatible synthetic references. A
separately captured run 002 then matches the unvalidated run 001 seed. This
proves software integration and preliminary within-context repeatability, not
diagnosis accuracy or real-world latency reduction.

## Clean-environment verification

A new temporary Python 3.13 virtual environment was created and the following
commands completed successfully:

```bash
python -m pip install -e '.[dev]'
pytest
ruff check .
ruff format --check .
latency-fingerprint export-schemas --check
latency-fingerprint match \
  fixtures/query_cases/similar_network/observation.json \
  --fingerprints fixtures/reference_cases
```

Verification result:

- 283 tests passed with branch-aware coverage above the enforced 85% floor;
- all three generated schemas matched their checked-in files;
- the console entry point executed successfully;
- the clear-network result was byte-identical to the checked-in example;
- the generated result validated as `match-result-v1`;
- Ruff lint and format checks passed.

The post-P0 hardening pass additionally verified duplicate-safe and bounded JSON
loading, numeric-overflow and nesting rejection, archive/file/row limits,
symlink rejection, explicit Pixelated bundle versions, exact required-manifest
declarations, telemetry workload and clock alignment, summary validity/duration
retention, cross-record arithmetic and provenance invariants, positive probe
intensity, and positive-weight matcher coverage. CI now runs on every pushed
branch, enforces an 85% coverage floor, checks dependencies, and includes Ruff
security rules.

The final review also bounds compressed archive inputs before TAR decoding,
enforces total readable bytes for directory bundles, preserves exact rejected-
feature reasons across derived records, validates matcher configuration on all
early-return paths, and prevents rejected repository records from colliding
with valid fingerprint identifiers.

## Inspectable examples

- Clear query input: [`../../fixtures/query_cases/similar_network/observation.json`](../../fixtures/query_cases/similar_network/observation.json)
- Network reference fingerprint: [`../../fixtures/reference_cases/network_pressure/fingerprint.json`](../../fixtures/reference_cases/network_pressure/fingerprint.json)
- Ranked matched output: [`../../tests/data/clear-network-match-result.json`](../../tests/data/clear-network-match-result.json)
- Ambiguous `unknown` output: [`../../fixtures/query_cases/ambiguous/expected-match-result.json`](../../fixtures/query_cases/ambiguous/expected-match-result.json)
- Sanitized Pixelated adapter input: [`../../tests/data/pixelated_bundle/README.md`](../../tests/data/pixelated_bundle/README.md)
- Controlled-real procedure and evidence index: [`../../experiments/controlled-run-001/README.md`](../../experiments/controlled-run-001/README.md)
- Controlled-real response: [`../../experiments/controlled-run-001/observation.json`](../../experiments/controlled-run-001/observation.json)
- Controlled-real matcher output: [`../../experiments/controlled-run-001/match-result.json`](../../experiments/controlled-run-001/match-result.json)
- Sanitized bundle checksums: [`../../experiments/controlled-run-001/manifest.json`](../../experiments/controlled-run-001/manifest.json)
- Independent repeat observation: [`../../experiments/controlled-run-002/observation.json`](../../experiments/controlled-run-002/observation.json)
- Independent repeat match: [`../../experiments/controlled-run-002/match-result.json`](../../experiments/controlled-run-002/match-result.json)

The fixture examples use `synthetic` provenance. The controlled-run observation
uses `controlled_real` provenance and remains clearly separated from those
software-test references.

## Fixture reproduction

Regenerate and check the deterministic fixture corpus with:

```bash
python -c "from latency_fingerprinting.synthetic_fixtures import export_fixture_files; export_fixture_files()"
python -c "from latency_fingerprinting.synthetic_fixtures import fixture_drift; assert fixture_drift() == {}"
```

Controlled-real reproduction is documented in
[`../../experiments/controlled-run-001/README.md`](../../experiments/controlled-run-001/README.md).
Private raw bundles remain excluded from Git.

## Controlled-real outcome

Controlled run 001 now includes the three private captures, finalized anonymized
context, sanitized checksums, operator-observed restoration evidence, derived
windows, executed probe, response observation and matcher output. The private
TAR bundles remain excluded from Git.

The matcher returned `unknown` with `incompatible_context` because none of the
three synthetic reference fingerprints shares the real Pixelated compatibility
group. That refusal is preserved as the correct P0 result; it was not relabeled
to force a diagnosis.

An independent controlled run 002 was subsequently processed as a held-out
query against the unvalidated run 001 seed. It matched
`host_encoder_pressure` with provisional strength `0.9819067687174997`, 22
shared features and full coverage. This is preliminary within-context
repeatability evidence, not diagnosis accuracy: there was only one compatible
candidate, and several strongly matching dimensions directly encode the shared
composite Performance preset.

## Known limitations and threats to validity

- The reference fingerprints are constructed synthetic vectors, not learned or
  validated distributions.
- Provisional match thresholds are engineering defaults, not calibrated
  probabilities or confidence values.
- The controlled response contains 22 cross-layer metrics, but
  `encoder.pipeline_delay_proxy_ms` is unavailable and tail behavior is not a
  separate matcher feature when the declared aggregate is the median.
- P0 cumulative frame counters are represented as median interval deltas. A v2
  contract must migrate these to explicitly versioned rates and/or total-window
  deltas before comparing captures with different sampling cadence.
- Sender queues, GPU behavior and exact display timing remain incompletely or
  indirectly observed.
- The stream-profile relief is composite: FPS, bitrate and VP8 encoder settings
  change together, so its response cannot be attributed to one control.
- Matching repeated runs with the same composite preset includes deterministic
  intervention effects (such as target FPS and bitrate), which may inflate
  similarity relative to cause-specific diagnostic features.
- Run 002 had one compatible real seed candidate, so no top-two discrimination
  margin could be measured.
- P0 uses paired runs rather than a tested live mutation and rollback path.
- Controlled pressure may differ from organic bottlenecks and may introduce
  hidden confounders.
- Two controlled runs provide one preliminary repeat match, but do not support
  variance estimates, cause discrimination, cross-workload, cross-client or
  cross-node claims.
- Match strength is a similarity measure, not probability or calibrated
  confidence.
- Recovery benefit, diagnosis accuracy and comparative superiority remain
  untested hypotheses.

## Repository safety review

The closeout scan found no committed ROM files, TAR experiment bundles,
personal absolute paths, bearer credentials, private keys or obvious assigned
secret values. The controlled derived JSON artifacts passed the same scan, and
the raw experiment inputs remain ignored.
