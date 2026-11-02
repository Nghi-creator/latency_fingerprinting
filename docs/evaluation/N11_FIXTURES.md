# N11 offline evaluation fixtures

The [software corpus](../../fixtures/evaluation-v1/README.md) freezes four complete
manifest/report cases, every required source byte and compact independent outcome
expectations. Its exact inventory and release hash are checked before reconstruction.
The checker is read-only and has no regeneration or blessing mode.

```sh
python -m tests.evaluation.check_reproduction
python -m pytest tests/evaluation
python -m tests.packaging.check_wheel
```

The planned-ledger case retains failed, unstarted and unknown held-out groups. The
raw-passive case links original bytes through N2 slices, N6, N9 and the N11 report;
two windows from one run count as one held-out group. The diagnosis case proves
that an N6/N7/N8 chain without raw proof remains unavailable in the outer report.
Full-root snapshots pin result links, serialization and content identities; compact
expectations independently check the ledger, availability and denominators.

Mutations of private copies check omitted groups, conflicting roles, duplicate
exports, missing query/training proof and a structurally valid rehashed false
proposal. Additional tests check exact boundary arithmetic, counter resets,
protected outputs and unsupported live/final-study declarations. Existing N6–N9
corpora retain their independent context, circular-label, exclusion, mixed/unseen,
staleness and reset coverage; N11 reuses those methods.

The clean-wheel gate copies this corpus outside the checkout and reconstructs
all four retained reports through the installed CLI. Input order cannot alter the
reconstructed result. Frozen bytes and checked expectations must be reviewed
when behavior changes; do not regenerate snapshots solely to pass a regression.

## Producer packaging boundary

With a local Pixelated checkout and Node supporting TypeScript stripping:

```sh
node --experimental-strip-types tests/evaluation/export_producer_windows.mjs \
  ../Pixelated-Studio-Edition /tmp/n11-producer-window.tar
python -m tests.evaluation.producer_boundary /tmp/n11-producer-window.tar
```

The exporter requires a new output path and calls the producer's real v2 manifest
composer and TAR writer on artificial sanitized telemetry. The checker adopts
two exact-anchor windows and compares all measurements/support states with the
original content. Independent arithmetic is 52/56 median received fps, 300 decoded
frames in each five-second interval, and 60 decoded fps in each window. Both
windows retain one source and clock identity. The frozen producer archive is also
checked without a sibling checkout; its source revision/module hashes are recorded
in the corpus.

This checks the composer/archive interface. It does not run a live collector, test
native control lifecycle, qualify real labels/clocks or establish empirical study
acceptance. All reviews and telemetry in this release remain artificial.

For the wider sample-to-export boundary, use
`tests/evaluation/export_producer_samples.mjs` in the same way and pass
`--full-sample-export` to the checker. This exercises the producer's real browser,
engine and event CSV writers plus derived support declarations, manifest and TAR.
The [sampled fixture](../../tests/data/pixelated_bundle/README.md) pins its output.
Numeric summaries and source rows must remain equal; support provenance changes
from sparse source fallback to explicit declarations where the producer supplies
them. Packet-loss totals retain the current source-support fallback. These are
artificial samples, with no runtime/process/clock authenticity claim.
