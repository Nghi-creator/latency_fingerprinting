# Source-lineage grouping and frozen split validation

`validate_calibration_lineage` reconstructs the declared source groups and checks
that a dataset's split covers those groups exactly once. It is a pure API: it
revalidates the [dataset model](N6_MODELS.md), does not read files or clocks, and
returns immutable `CalibrationLineage`/`EntryLineage` values.

```python
from latency_fingerprinting.calibration import validate_calibration_lineage

lineage = validate_calibration_lineage(dataset)
for group in lineage.groups:
    print(group.group_id, group.source_ids, group.role, group.independence_review_state)
```

The [evidence contract](N6_EVIDENCE_CONTRACT.md) defines the identities, source
rules and review meanings. [Independent examples](N6_EVIDENCE_EXAMPLES.md) explain
why frame-level splits, renamed exports and correlated sessions cannot be counted
as independent calibration runs.

## Source groups

The API joins sources transitively when any declared relation holds:

- Same acquisition namespace and original run ID, even with different hashes.
- Same source type and content hash, even with different namespaces/run aliases.
- Same namespace and acquisition session or operator independence-group alias.
- Explicit parent/child derivation, in either direction for grouping.
- Both source bindings of a response, even when captured in separate runs.

Directed cycles remain invalid derivations. Component reconstruction is iterative
and bounded by the dataset's 256 sources and 512 edges. Member aliases are sorted
before hashing the group ID; output groups and entries are ordered by their IDs.
The computation is independent of dictionary-key or edge visitation order.

One component receives one assignment: engineering, training, validation or
final_test. Missing, stale, duplicate and extra assignments fail validation.
In particular, a declaration that assigns a response's degraded source to training
and its relief source to final_test does not describe two valid groups.
Several legitimate windows in a component remain several entries but only one
potential independent group. Different local window IDs or unrelated clock-domain
names cannot create independence. Equal window IDs in different unlinked sources
also cannot prove that those sources are correlated.

## Review states

A group's state is confirmed only when every member references the same confirmed
independence review and its subject list equals the complete component. A partial
review, separate confirmed reviews for fragments, or a confirmed review spanning
unrelated components cannot upgrade a whole group.

Otherwise, explicitly referenced rejected reviews take precedence over uncertain
reviews; if neither applies, the state is missing. Unknown/rejected/uncertain
support stays visible in the result. A prospective split's freeze-review state is
retained separately. A retrospective split has no prospective freeze review.
These are external review declarations, not authenticated authority or physical
proof of independence. This API does not calculate final entry eligibility.

## Duplicate declarations

Entries naming input artifacts with identical declared SHA-256 bytes share the
lexically first entry as their representative. Their input kind, byte length and
embedded run/window/source binding claims must agree. Local dataset source aliases
and acquisition namespaces are not embedded window identity and may differ.
Nonnull labels across the duplicate class must agree, including when the first
alias has an unknown label. Contradictory claims fail rather than selecting a label.
Missing entries represent themselves and create no acquisition group.

The representative retains its own label and support; nothing promotes an unknown
representative from a later alias. Report validation permits nullable labels in a
duplicate class but rejects conflicting nonnull labels across that entire class.

At this boundary, duplicate detection uses declared raw input-artifact receipts.
Different serializations of the same analytical response can have different raw
SHA-256 values. Checking those files' canonical response identities/healthy-window
content, their actual hashes and their embedded bindings requires linked artifact
inspection. Several distinct windows from one source are not automatically exact
duplicates, although they remain one source group.

## Frozen replay anchors

When replaying a previously accepted declaration, supply its trusted IDs:

```python
lineage = validate_calibration_lineage(
    dataset,
    expected_split_id=frozen_split_id,
    expected_dataset_content_hash=frozen_dataset_hash,
)
```

Changing role assignments changes the split ID. Changing other source/artifact
claims can leave the group aliases/assignments unchanged while changing the dataset
hash. The split anchor therefore protects assignments only; the dataset anchor
protects the complete declared snapshot. Obtain anchors from an independently
retained trusted record, not from the untrusted input currently being checked.
Without an anchor this API checks the supplied declaration's internal consistency;
it cannot prove that a different historical declaration was never used.

Anchors and content hashes do not establish when a physical measurement happened,
authenticate reviews or turn a retrospective split into a prospective one.

## Result and failures

The result retains dataset ID/content hash, split ID/mode/review state, immutable
group inspections and ordered entry lineage (entry ID, nullable group/role and
representative entry ID). Assurance is always
`external_review_declarations_not_authenticated`. Missing or uncertain evidence
is retained; malformed declarations or invalid split integrity raise
`ValueError("invalid_calibration_lineage")` without echoing identifiers or content.

Generic `validate` still checks standalone models. Call this API explicitly for
declared source-component and split checks. Use [linked inspection](N6_INSPECTION.md) for `inspect-calibration` and actual
artifact/experiment-byte verification.
No profile building, source-file ingestion or live producer mutation occurs here.
