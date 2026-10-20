# Linked calibration inspection

`inspect_calibration_dataset` verifies an N6 dataset directory, reconstructs its
lineage/split and produces a deterministic eligibility report. It reads local
files and does not execute experiments. The [evidence contract](N6_EVIDENCE_CONTRACT.md)
defines bounds, labels and exclusion reasons; [declaration validation](N6_MODELS.md)
and [lineage validation](N6_LINEAGE.md) remain available separately.

```python
from pathlib import Path
from latency_fingerprinting.calibration import inspect_calibration_dataset

result = inspect_calibration_dataset(Path("dataset"))
result.dataset  # immutable CalibrationDataset
result.report  # immutable CalibrationReport
result.artifacts  # tuple of artifact_id/validated record pairs
```

The directory must contain exactly `calibration-dataset.json` and the declared
flat JSON or gzip USTAR files. The reader pins the directory and its ancestors,
rejects symlinks/special files, bounds raw and decoded bytes, and hashes and
validates the same snapshots. Nested experiment bundles pass the existing N5
version-dispatched inspector, including effect recomputation. Inputs are read-only;
bounded experiment snapshots may be staged privately in a temporary directory.
Malformed inputs produce `ValueError("invalid_calibration_dataset")` with no
partial result or input content in the error.

Each entry's run, original source identity, window and phase must agree with its
actual validated response/window. N6's `healthy` binding maps explicitly to N2's
`baseline` phase; response bindings retain N2's `degraded`/`relief` phases.
Controlled labels require the fixed scenario mapping, compatible workload/revision
and settings, recomputed effect and a confirmed label-binding review. Known
contradictions reject the dataset. Valid failed or missing support stays visible
with ordered exclusion reasons. Synthetic evidence remains excluded from calibration.

Reports retain all entries, artifact receipts, source groups, role counts and
compatibility partitions. Exact response identities and canonical baseline-window
identities collapse repeated exports to the lexical first entry; extra exports
remain visible with `duplicate_evidence`. Conflicting nonnull duplicate labels
reject the dataset. Counts use unique source groups rather than frame/window counts.
A reviewed baseline qualifies for baseline use, never as a response vector.

## Compatibility projection

Each partition ID is `partition-` followed by the SHA-256 of the canonical JSON
projection below, using the model's snake_case fields and existing canonical
serialization (sorted keys, two-space indentation, trailing LF):

- `input_kind`, full `registry`, response `policy_hash` (null for baseline),
  `provenance`, and full `capture_method`.
- `clock`: `basis` and `provenance`, excluding local clock IDs and timestamps.
- `context`: the full context except `context_id`, `node_id`, `network_scenario`.
- `probe`: response intervention `probe_type`, `probe_version`,
  `application_method`, `intensity`, `requested_settings`, `observed_settings`;
  null for baseline.
- `effective_settings`: each actual N2 phase name mapped to its full settings.

Booleans remain distinct from numbers. Local acquisition aliases cannot manufacture
compatibility or independence; changed producer versions, observed settings or
measurement meaning produce separate partitions. Partition membership itself
does not establish a sufficient sample size or scientific trust.

## CLI and replay anchors

```sh
latency-fingerprint inspect-calibration \
  --directory dataset \
  --output reports/calibration-report.json
```

The output parent must exist outside the input directory. Success is silent exit
0 with canonical atomic mode-0600 output. On failure the old output is preserved,
stdout is empty, exit status is 1 and stderr is exactly
`error: inspect-calibration: invalid_input_or_output`. Argument errors retain
argparse exit status 2.

Both API and CLI accept optional `expected_split_id`/`--expected-split-id` and
`expected_dataset_content_hash`/`--expected-dataset-content-hash`. Supply these
from a separately trusted retained declaration to reject replay drift. Without
such an anchor, the inspector checks internal consistency of the supplied input.

Reviews remain unsigned external declarations. Inspection cannot authenticate
physical acquisitions, establish prospective timing or prove the truth of labels.
The report always retains `external_review_declarations_not_authenticated` assurance.
