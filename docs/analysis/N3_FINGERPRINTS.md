# N3 v2 fingerprints and repository loading

**Delivered:** Step 4, 2026-10-08
**Contract:** [Analytical field contract](N3_ANALYTICAL_CONTRACT.md)
**Input:** [Pure response derivation](N3_RESPONSE_DERIVATION.md)

`FingerprintV2` is exported from `latency_fingerprinting.models`. It embeds a full
valid analytical response, its observation provenance, a required caller-declared
bottleneck label, validation status and the exact eligible normalized vector.
The strict, immutable model revalidates nested instances and reconstructs vector
values, inventory, provenance and identity. A supplied vector cannot override the
retained evidence. Its ID hashes canonical response, label and status.

Labels are identifiers matching `[A-Za-z0-9][A-Za-z0-9_-]*`, such as
`network_pressure`; paths, URLs, whitespace and private free-form notes are
rejected. Labels are declared references, never inferred by creation or authenticated
by content hashes. Synthetic evidence retains synthetic provenance. Real provenance
requires a consistent real N2 observation; software checks cannot verify capture truth.

## Pure creation

```python
from latency_fingerprinting.analytical.fingerprints import create_fingerprint_v2

fingerprint = create_fingerprint_v2(response, bottleneck_label="network_pressure")
```

Creation revalidates the explicit response, reads or writes no files and uses no
current time or random identifier. Its default `software_checked` status requires
at least four eligible features and coverage >=0.75 of the 22 policy features,
which means at least **17**. It errors when evidence is insufficient. Explicit
`validation_status="unreviewed"` or `"rejected"` can retain a lesser valid vector
for audit. Invalid/confounded responses cannot be stored under any status.
Only software-checked records are eligible for later candidate compatibility.
This status means contract consistency, not experimentally validated causality.

## Separate bounded repository

```python
from pathlib import Path
from latency_fingerprinting.analytical.repository import load_fingerprint_repository_v2

repository = load_fingerprint_repository_v2(Path("references-v2"))
fingerprints = repository.fingerprints
```

The directory loader visits sorted entries recursively and validates every `.json`
file as `FingerprintV2`, including files named differently from `fingerprint.json`.
Non-JSON files are ignored but count toward the entry limit. It retains all valid
audit statuses; candidate filtering belongs to Step 5. Results are immutable tuples
in fingerprint ID order. An empty valid directory returns an empty repository.

| Limit | Bound |
| --- | --- |
| Fingerprint JSON files | 128 |
| Total directory entries, including directories and non-JSON files | 4,096 |
| Directory depth below root | 16 |
| Bytes per JSON file | 10 MiB, checked before and after reading |
| JSON nesting depth | 128 |

Duplicate IDs, wrong roots, malformed JSON/models, duplicate JSON keys, non-finite
numbers, invalid UTF-8, unsafe links and resource violations fail the whole load.
No malformed candidate is silently skipped and no partial repository is returned.
Symlinks in roots/ancestors or discovered entries are rejected. Directory descriptor
traversal and no-follow file opens prevent a replaced discovered file link from
being followed; nonblocking opens plus regular-file checks prevent FIFO reads.
Errors raise `FingerprintRepositoryErrorV2` with a short reason code, excluding
paths and malformed contents. The P0 loader and its limits remain unchanged.

## Schema and validation

The additive [fingerprint-v2 schema](../../schemas/fingerprint-v2.schema.json)
brings schema exports to nine roots. Generic `validate` accepts this root; runtime
validation also enforces reconstruction and evidence thresholds beyond JSON Schema.
Existing v1 matching rejects v2 fingerprints. The proposed `build-fingerprint-v2`
and `match-v2` commands belong to Step 6 and remain unimplemented.

62 new tests cover independent full-record expectations, the 16/17 threshold,
audit statuses, false provenance, forged vectors/IDs, sanitized labels, immutable
inputs, resource boundaries, unsafe links, file replacement/growth and fail-closed
repository behavior. [Progress](N3_IMPLEMENTATION_PROGRESS.md) records current local
results and unchanged reproduction pins. Actual Python 3.11/hosted verification
remains pending. Next is Step 5: compatibility, scoring and conservative v2 matching.
