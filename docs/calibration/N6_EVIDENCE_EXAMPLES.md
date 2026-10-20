# Independent calibration evidence and split examples

These are hand-authored expectations for the
[calibration evidence contract](N6_EVIDENCE_CONTRACT.md), independent of
model, grouping and inspector code. The examples specify synthetic design inputs;
they neither assert real measurements nor create eligible scientific data.
The projection notation below is not an additional production schema or a
fixture-release regeneration command. Implementation tests must expand it into
strict existing records and new N6 models without deriving expected decisions
from production grouping/scoring functions.

## Notation and common premises

`a`, `b`, etc. below abbreviate safe source aliases. Distinct letters initially
mean different original runs, content, sessions and declared independence groups
within one pseudonymous acquisition namespace. `R(a,b)` is an existing validated
analytical response with degraded source a and relief source b. `H(a)` is a
healthy observation window. `M` is an entry with missing measurements.
`a -> b` means an explicit derivation edge; `a ~ b` means one shared session.

Group IDs hash the actual source aliases, not the letters in a drawing. All
examples with checked real eligibility use a **hypothetical** controlled-real
record, verified effect/binding and confirmed unsigned reviews unless changed
explicitly. No retained real file is asserted to meet those premises. Prospective
assignments/freeze review are confirmed unless the example changes them. Every
example's actual expansion must bind reviews to the computed exact group/split
and reproduce original window/source hashes.

For examples about a single exclusion, all other gates pass. Eligible feature
counts use the existing N3 policy: 22 features, positive weights, minimum coverage
0.75 and minimum shared count 4. Thus 16/22 = 0.727272… fails; 17/22 = 0.772727…
passes. Missing input has no group, role, partition or feature count. Independent
support is counted by components, not entries or frames.

## 1. Distinct paired acquisitions and healthy baseline

Inputs and assignments:

| Entry | Sources | Assigned group role | Label | Kind |
| --- | --- | --- | --- | --- |
| e1 | R(a,b) | training | host_contention | response |
| e2 | R(c,d) | validation | host_contention | response |
| e3 | R(e,f) | final_test | host_contention | response |
| e4 | H(g) | training | healthy | healthy_window |
| e5 | M | none | null | missing |

Expected groups: `{a,b}`, `{c,d}`, `{e,f}`, `{g}`. Each response's sources are
connected even though their runs were captured separately. No other joins exist.
Assume the three responses have the same compatibility payload P and the baseline
has its distinct baseline payload B.

| Counter | Global | training | validation | final_test | engineering |
| --- | --- | --- | --- | --- | --- |
| retained_entries | 5 | 2 | 1 | 1 | 0 |
| eligible_entries | 4 | 2 | 1 | 1 | 0 |
| excluded_entries | 1 | 0 | 0 | 0 | 0 |
| retained_groups | 4 | 2 | 1 | 1 | 0 |
| eligible_groups | 4 | 2 | 1 | 1 | 0 |

e5 has only `missing_measurements`. It contributes only to global entry counts;
there is no invented role or group. P has 3 retained/eligible entries and 3 eligible
groups; B has 1/1/1. A baseline never adds a response feature vector. These counts
establish inventory correctness only, not enough repetitions for N7 or a calibrated
accuracy estimate.

## 2. Renamed export cannot cross a split

R(a,b) and R(c,d) are named differently, but a and c have equal source-type/content
hash. The join a=c links both pairs, yielding `{a,b,c,d}`. A split assigning old
`{a,b}` to training and old `{c,d}` to final_test is invalid: neither old group ID
is a reconstructed component. Reject the dataset, not just its test entry.

If c is a second export of a with a different content hash, equal namespace/run
identity still gives the same join. Changing export filename, response ID,
namespace, timestamp or claimed operator group cannot undo an existing content
or derivation join. Distinct hashes with entirely undisclosed lineage cannot be
proven independent; missing independence review excludes them.

## 3. Pairing and transitive derivation propagate grouping

R(a,b), R(c,d), edge b -> c and H(e) with d ~ e give one component
`{a,b,c,d,e}`. A parent does not become independent because an intermediate derived
artifact was renamed. One training assignment for the whole component is valid;
training/final_test assignments to its constituent subsets are rejected.

For two responses in that valid component, both may be eligible but yield **one**
eligible group, not two repetitions. If their compatibility partitions differ,
retain both partitions with one group in each; the global group count remains one.

## 4. Duplicate analytical evidence and conflicting labels

Entries e1/e2 contain the exact same response ID/content and complete evidence.
Both are retained; e1 is the lexical representative. e2 has `duplicate_evidence`,
`representative_entry_id=e1`. Expected retained=2, eligible=1, excluded=1,
retained_groups=eligible_groups=1. Swapping directory enumeration changes nothing.

If e1/e2 assign different nonnull labels to that exact evidence, reject the dataset
rather than choosing the first label. If two well-formed different responses from
one source group have different controlled conditions/labels and valid bindings,
retain them in one unsplittable group; label diversity does not add independence.

## 5. Ordered exclusions and retained failures

| Change from an otherwise admissible entry | Expected reason_codes in order |
| --- | --- |
| No measurements (M) | missing_measurements |
| Role engineering | engineering_only |
| Retrospective assignment of previously observed reference/query runs | retrospective_split |
| Prospective declaration with no confirmed freeze review | split_unverified |
| Unique hashes but missing group independence review | independence_unverified |
| Synthetic response, declared-only label, no independence/freeze review | split_unverified, independence_unverified, synthetic_only, label_unverified |
| Real response with 16 eligible features | insufficient_response_features |
| Real response with 17 eligible features | empty (eligible) |
| Confounded response with zero eligible features | confounded_response, insufficient_response_features |
| Healthy window has invalid validity or confounders | baseline_invalid |
| Healthy window has no supported complete numeric primary measurement | baseline_invalid |
| Caller label with declared_only basis | label_unverified |
| Exact label review uncertain/rejected, external_confirmation basis | label_unverified |
| Controlled effect failed or insufficient | effect_unverified |
| Controlled cleanup unverified | effect_unverified |
| Controlled binding review uncertain/rejected | label_unverified, binding_unverified |
| Controlled revision required by the contract is absent | binding_unverified |

All rows with nonempty reasons retain the entry and its role/group denominator,
where present; none qualifies for profile training. A failed effect does not
become verified just because its supplied effect JSON says so: independently
recompute the existing experiment bundle. A contradictory supplied claim inside
that bundle fails the existing inspector rather than yielding this retained row.

A confirmed review for unrelated subjects does not qualify an entry/group/split.
A source review that covers only a but not b does not confirm `{a,b}`.
A label review string is not authenticated external authority, even when all
software checks pass.

## 6. Labels must bind the actual evidence

| Input | Expected outcome |
| --- | --- |
| Complete verified v1 host_contention bundle, same workload/revision, degraded-phase association and confirmed full-pair review | Controlled host_contention support admissible, subject to all other gates |
| Same bundle but requested label render_capture_slowdown | Reject known scenario/label mismatch |
| Matching scenario but different known workload or producer revision | Reject known ownership/context mismatch, even with confirmed review |
| Same filenames/run aliases but another acquisition with no confirmed binding review | Retain label_unverified and binding_unverified; aliases do not prove a physical association |
| Matching name plus a standalone campaign report only | Reject artifact kind/shape: a report is not a linked experiment bundle |
| Valid bundle whose effect failed | Retain effect_unverified |
| N5 recovery phase submitted as N2 relief | Reject unsupported phase mapping; no approved conversion |
| N5 FPS/worker CPU only, no analytical observation | Missing entry, not a fabricated analytical-response-v2 |
| Existing P0 observation submitted as analytical_response artifact | Reject wrong root; no automatic migration |
| Confirmed exact-entry external review without N5 bundle | External-confirmation support admissible with explicit unauthenticated-review assurance |
| healthy_window labelled host_contention | Reject input-kind/label mismatch |

The initial three-label mapping is closed. A new scenario, mixed diagnosis or
new capture/relief method requires a versioned contract change, not a caller label.

## 7. Compatibility is independent from label and split

Take two valid paired responses with full support. Changing only a local
context/node alias or `network_scenario` does not change their partition. Changing
workload, structural runtime, versions, capture method, registry/policy,
probe intensity/type/requested settings/**observed settings**, or either effective
settings map does. Equal strings in caller labels cannot merge those partitions.
Clock domain IDs differ across independent captures without implying clock
synchronization; clock basis/provenance remains part of the partition.

Healthy and response input kinds have different partitions even if context,
registry and raw feature values match. Missing entries have no partition. Neither
a different partition nor different clock ID proves source independence.

## 8. Structural and boundary failures

Reject unknown root/release/kind, extra or omitted required fields, duplicate keys,
boolean numeric coercion, nonfinite values, unsafe alias/filename, wrong hash/length,
invalid embedded models, dangling edges, self-edges, directed cycles, wrong source
bindings, conflicting alias declarations, extra/absent directory files, links,
nonregular files, subdirectories and all declared resource excesses.

Bounds are inclusive: 256 artifacts plus one manifest is permitted; a 258th
inventory entry fails before parsing it. Exactly 10 MiB JSON including LF is
permitted; one additional byte fails. The 256 MiB aggregate includes manifest and
all artifact snapshots. An individually valid 64 MiB nested experiment archive
still fails if it would exceed the remaining aggregate budget.

No inspection result is accepted for a malformed dataset. CLI stdout stays empty
and the old output remains intact; fixed failure text cannot echo a supplied path
or field. Intrinsically valid but excluded data returns a normal report with zero
eligible counts, not a malformed-input error.

## 9. Exact component identity oracle

For actual safe aliases `source-a`, `source-b`, canonical input is exactly:

```json
{
  "source_ids": [
    "source-a",
    "source-b"
  ]
}
```

Include the final LF. SHA-256 and group ID are pinned in the
[design-vector file](N6_DESIGN_VECTORS.json). A second vector pins the five-source
component from example 3. These hashes use only standard-library JSON/SHA-256,
not the N6 renderer or grouping implementation.
