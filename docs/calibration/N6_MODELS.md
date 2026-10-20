# Calibration declaration models and standalone validation

`CalibrationDataset` and `CalibrationReport` are available from
`latency_fingerprinting.calibration` and `latency_fingerprinting.models`.
The [contract](N6_EVIDENCE_CONTRACT.md) defines the versioned field meanings;
[independent examples](N6_EVIDENCE_EXAMPLES.md) define acceptance expectations.

```python
from latency_fingerprinting.calibration import CalibrationDataset, CalibrationReport

# Structured data must already have been decoded with an appropriate bounded reader.
dataset = CalibrationDataset.model_validate(dataset_payload)
report = CalibrationReport.model_validate(report_payload)

# Text boundaries enforce duplicate-key, finite-number, byte and depth limits.
dataset = CalibrationDataset.model_validate_json(dataset_json)
report = CalibrationReport.model_validate_json(report_json)
```

Both new roots use snake_case fields, required nullable keys, closed enums,
strict integers/booleans and immutable nested declarations. Lists are detached
into tuples. Sets, iterators and oversized collections fail before nested model
validation. Model instances passed through validation are revalidated, including
nested instances altered through `model_copy`. Assignment to a validated field
is forbidden; `model_copy` itself remains a Pydantic unchecked-copy operation,
so consumers must revalidate at their boundary.

Original run/window identifiers retain their strings and have a 256 UTF-8 byte
bound. New aliases/hashes are closed ASCII tokens; whitespace, newline suffixes,
paths and coercion are rejected. Canonical output is bounded to 10 MiB.
The JSON entry point reuses the duplicate-safe 10 MiB/depth-32 decoder. In-memory
model validation operates on structured fields, not raw file bytes.

## What dataset validation checks

- Exact root/method release, fields, identity/hash reconstruction and ordering.
- Artifact kind, safe derived filename, positive byte length and kind-specific
  limits; canonical manifest plus declared lengths must fit the aggregate bound.
- Source-type/schema agreement, source aliases and original-identity consistency.
- Entry input kind, degraded/relief/healthy binding order, artifact/source
  references, label basis and controlled-experiment phase requirements.
- Review kind, subject references and reachability; rejected/uncertain/missing
  review support remains representable.
- Directed derivation references, self-edges, duplicates and cycles. Referenced
  ancestors remain retained; no undeclared or unreachable inventory is accepted.
- Split content identity, ordered unique assignments and prohibition of a claimed
  freeze review for a retrospective split.

There is no file read, producer import, policy URL lookup or live action during
construction. Artifact lengths/hashes are declarations at this boundary.

## What report validation checks

The report reconstructs its content identity and the declared dataset ID/hash
relationship. Each supplied group ID reconstructs from its ordered source aliases;
source groups cannot overlap. Entries must use a declared group/role and partition.
Eligibility must equal the absence of ordered exclusions. Missing measurements
cannot invent labels, features, groups or roles. Healthy baselines cannot claim
response feature vectors. Confounded responses have zero eligible features, and
response counts below 17 require the current policy's insufficient-evidence reason.

Global, all-four-role and partition entry/group counts reconstruct from the
report's actual entries. Multiple windows do not add independent groups. Duplicate
entries require an earlier direct representative with matching kind, group,
partition, label and feature count. Retrospective/engineering and group-review
exclusions must agree with their declarations. A split-freeze state applies
consistently to the whole report. Assurance is always the literal
`external_review_declarations_not_authenticated`.

## What requires linked inspection

Standalone validation does **not** reconstruct source components from a dataset's
sessions, original/content identities, paired sources and derivations, or prove
that the declared split excludes shared source lineage. It does not open artifact
files, verify their actual bytes, reconstruct analytical responses/compatibility
partitions from those files, recompute experiment effects, or verify that a report
matches a particular dataset. These checks belong to source/split validation and
linked inspection; the `inspect-calibration` API/command is not yet available.

A valid declaration or self-consistent report is not a verified calibration set.
External review declarations are neither authenticated authority nor physical
proof of acquisition independence. Synthetic, retrospective, unsupported and
incomplete evidence must retain its applicable exclusions in an inspected report.

## CLI and schemas

Generic validation recognizes both roots:

```sh
latency-fingerprint validate calibration-dataset.json
latency-fingerprint validate calibration-report.json
latency-fingerprint export-schemas --output schemas --check
```

Generic validation prints the validated canonical root; it does not run linked
inspection. Its existing bounded root-dispatch reader precedes the N6 JSON entry
point. The new generated schemas are
[dataset](../../schemas/calibration-dataset-v1.schema.json) and
[report](../../schemas/calibration-report-v1.schema.json). JSON Schema validates
shape, closed fields and local type/range bounds. Runtime models also check
cross-field references, content hashes and reconstructed counts.

Existing schemas, registry/policy releases, matching APIs and fixture bytes retain
their meanings. [Model tests](../../tests/calibration/test_models.py),
[report tests](../../tests/calibration/test_report.py) and
[boundary tests](../../tests/calibration/test_boundaries.py) use independently
written expectations and the standard library for identity oracles.
