# Profile policy and standalone snapshot validation

`ProfilePolicy` and `ProfileSnapshot` are available from both
`latency_fingerprinting.profiles` and `latency_fingerprinting.models`. Their
[contract](N7_PROFILE_CONTRACT.md) fixes field meanings, numerical conventions,
selection and lifecycle shape. The [policy](N7_PROFILE_POLICY_SPEC.json) is the
repository-approved software-provisional release; changing and rehashing its
parameters does not create an approved policy.

```python
from latency_fingerprinting.profiles import ProfilePolicy, ProfileSnapshot

policy = ProfilePolicy.model_validate_json(policy_json)
snapshot = ProfileSnapshot.model_validate_json(snapshot_json)

# Structured inputs must already have passed an appropriate bounded reader.
snapshot = ProfileSnapshot.model_validate(snapshot_payload)
```

JSON entry points enforce the existing 10 MiB/depth-32 boundary, duplicate-key
and finite-number checks. Models require closed fields, strict booleans/counts,
finite binary64 numbers, safe IDs and the exact 22-feature inventory. Containers
are detached into immutable tuples/maps. Nested instances, including unchecked
`model_copy` edits, are revalidated. Ordered collections and total feature/group
references are bounded before nested validation, including structured inputs.

## What is reconstructed

- Exact approved policy content, canonical identity and existing registry/N3 release.
- Selection from N6 entry metadata: training responses only, retained N6 exclusions,
  duplicate representatives and conflicting labels within a source group/partition.
- Exactly one input row per N6 entry. Unselected entries cannot export feature
  values; selected maps must match their N6 eligible-feature count.
- One median vote per contributing source group/feature; centers and raw MAD;
  exact rational availability/coverage gates; explicit missing and zero-dispersion
  exclusions and supported/excluded weights.
- Candidate inventory, all 22 features, contributing group/entry IDs, source-group
  counts, selection denominators, candidate support states and nested/root IDs.
- Current lifecycle shape and exact review subject/replacement/reason references.
  Created/rejected unbuilt drafts cannot invent source evidence. `trusted` fails.

Statistics use bounded exact rational binary64 midpoint/deviation arithmetic,
rounded once. Overflow and nonzero-to-zero underflow fail. Computed zeros are
positive; raw selected signed zero may remain in the input map. Unsupported
nonempty features retain diagnostic statistics. No data is imputed, clamped or
silently dropped. The [independent examples](N7_PROFILE_EXAMPLES.md) and Decimal
oracles predate this implementation and cover rounding, group multiplicity,
missing support, threshold boundaries and failed arithmetic.

## CLI and schemas

```sh
latency-fingerprint validate docs/profiles/N7_PROFILE_POLICY_SPEC.json
latency-fingerprint validate SNAPSHOT.json
latency-fingerprint export-schemas --output schemas --check
```

Generic validation prints the canonical validated root. The additive schemas are
[policy](../../schemas/profile-policy-v1.schema.json) and
[snapshot](../../schemas/profile-snapshot-v1.schema.json); the earlier 27 schemas
retain their bytes and meaning. JSON Schema checks shape and local bounds;
runtime validation additionally reconstructs arithmetic, references, approval and
content identities. A shape-only schema check is not release approval.

## Evidence and lifecycle limits

Standalone validation reconstructs statistics from **declared retained values**.
It does not open source artifacts, verify original measurements, authenticate
external reviews or prove physical independence. It accepts a self-consistent
N6 report as a declaration, not as proof of fresh linked inspection. Model-only
unit examples with eligible report metadata are artificial arithmetic tests and
are not real calibration evidence.

The [linked builder and lifecycle API/CLI](N7_COMMANDS.md) inspect actual N6
files and preserve supplied parent evidence during withdrawal. Lifecycle models
check the current record's shape; they do not authenticate unseen parent history. Candidates remain
provisional or rejected support summaries, not trusted or match-eligible profiles.
