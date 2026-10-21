# Building and revising profile snapshots

The N7 builder calls the actual [N6 inspector](../calibration/N6_INSPECTION.md)
before selecting training responses. Supply the explicit approved
[profile policy](N7_PROFILE_POLICY_SPEC.json). Standalone reports and declared
feature maps are not substitutes for the linked dataset directory.

```python
from pathlib import Path
from latency_fingerprinting.profiles import (
    create_profile_snapshot,
    build_profile_snapshot,
    transition_profile_snapshot,
)

draft = create_profile_snapshot(policy)
built = build_profile_snapshot(
    Path("calibration-dataset"),
    policy,
    parent=draft,
    expected_split_id=trusted_split_id,
    expected_dataset_content_hash=trusted_dataset_hash,
)
stale = transition_profile_snapshot(
    built,
    operation="mark_stale",
    reason_code="external_review",
    review=review,
)
```

`policy`, `parent`, `review` and `replacement` accept validated models or structured
payloads; copied/nested models are revalidated. Replay anchors and `parent` are
optional. Each call returns a new immutable `ProfileSnapshot`. Create and
transition failures raise `ValueError("invalid_profile_snapshot")`; build failures
raise `ValueError("invalid_profile_build")`.

Build reconstructs selection from N6 metadata before accessing feature values.
Only selected training responses contribute; validation/final-test entries,
baselines, missing records, duplicates, mixed-label groups and N6 exclusions
retain their reasons with null feature maps. Selected N3 records must match the
approved response policy and metric registry. Missing/excluded features remain
null. The [contract](N7_PROFILE_CONTRACT.md) defines group medians, centers, raw
MAD, exact arithmetic and support gates. Rebuild always inspects fresh inputs;
it does not inherit a parent's statistics. A build with no supported candidate
returns a valid rejected snapshot, not a CLI error. Existing synthetic N6 fixtures
are excluded evidence and produce rejected snapshots.

## Local commands

```sh
latency-fingerprint create-profile-snapshot \
  --policy docs/profiles/N7_PROFILE_POLICY_SPEC.json --output draft.json
latency-fingerprint build-profiles \
  --directory calibration-dataset \
  --policy docs/profiles/N7_PROFILE_POLICY_SPEC.json \
  --parent draft.json --output built.json
latency-fingerprint transition-profile-snapshot \
  --snapshot built.json --operation mark_stale \
  --reason external_review --review review.json --output stale.json
```

Build also accepts `--expected-split-id` and `--expected-dataset-content-hash`.
Supersession requires `--replacement SNAPSHOT.json`; other operations forbid it.
Review JSON has exactly these fields:

```json
{
  "actor_id": "operator",
  "subject_snapshot_id": "profile-snapshot-<parent digest>",
  "replacement_snapshot_id": null,
  "reason_code": "external_review",
  "evidence_sha256": "sha256:<external review digest>"
}
```

Replace digest placeholders with actual lowercase 64-character SHA-256 digests.
The subject must identify the supplied parent, reason must match the operation,
and supersession must name the supplied replacement. `actor_id` is a safe alias;
`evidence_sha256` is a declared receipt. Neither authenticates an external reviewer.

| Operation | Allowed parent | Result | Reasons |
| --- | --- | --- | --- |
| Create | None | created | draft |
| Build | None, created, provisional, rejected, stale | provisional or rejected | supported_profiles, no_supported_profiles |
| Mark stale | Built provisional or rejected | stale | method_changed, context_changed, policy_changed, external_review |
| Reject | created, provisional, stale | rejected | operator_rejected, evidence_rejected |
| Supersede | Built provisional, rejected or stale | superseded | replacement_selected |

Superseded revisions are terminal. A rejected unbuilt draft may only rebuild.
A created parent must use the same policy when built. Replacement must be a
complete valid, distinct provisional snapshot. Withdrawal/supersession preserves
the parent's policy, source report, inputs, profiles, counts and assurance exactly;
only lifecycle and root identity change. The API validates the supplied revisions,
not an unseen history. There is no trust promotion or profile matching command.

Successful commands write canonical JSON silently and return 0. Invalid inputs or
output targets return 1, empty stdout and exactly
`error: <command>: invalid_input_or_output` on stderr. Argument errors return 2.
Readers enforce bounded regular files, reject symlinks including ancestors, and
reuse N6's linked evidence and inventory checks. Output parents must exist.
Atomic output uses private mode 0600 and pinned no-follow directory descriptors.
It cannot replace an input operand (including hard-link aliases) or write any
member of the inspected N6 directory. An explicitly selected unrelated existing
regular output may be replaced; failures before replacement preserve it and clean
temporary files. Commands run locally without contacting or executing a producer.

Snapshots remain software-provisional summaries. Source inspection and arithmetic
validation do not prove real sample adequacy, independence or reviewer authority.
