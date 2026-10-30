# Calibration evidence and independent splits, release 1.0.0

**Method release:** `n6-calibration-evidence-v1`.
**Specification:** 1.0.0. [Standalone models, schemas and generic validation](N6_MODELS.md)
and [pure source-component/split checks](N6_LINEAGE.md) are implemented.
Linked file inspection remains a specified interface, not an implemented capability.
**Independent examples:** [Evidence and split examples](N6_EVIDENCE_EXAMPLES.md).

## Purpose and limits

Calibration requires repeated responses with supported labels and independent
source groups. This contract binds existing analytical responses, acquisition
lineage, experiment evidence, review declarations and frozen split assignments.
It distinguishes valid retained evidence from evidence eligible for calibration.
It neither builds profiles nor declares a profile scientifically trusted.

Existing [analytical v2](../analysis/N3_ANALYTICAL_CONTRACT.md),
[observation v2](../measurement/OBSERVATION_V2_CONTRACT.md),
[experiment](../scenarios/N5_EXPERIMENT_CONTRACT.md) and
[capture-pacing](../scenarios/N5_CAMPAIGN_WORKFLOW.md) releases remain unchanged.
A verified fault effect is not a relief response. A hash establishes content
identity, not acquisition truth, causal isolation, independent repetition or
reviewer authority. Reviews below are explicit external declarations, not signed
attestations or automatic proof. Final scientific acceptance remains external.

## Roots, representation and identities

Two new roots use snake_case keys, strict types, forbidden extra fields, immutable
nested containers and revalidation of reused/copied model instances:

- `calibration-dataset-v1`: requested evidence inventory and split.
- `calibration-report-v1`: linked inspection and reconstructed eligibility.

Every root requires `method_release: "n6-calibration-evidence-v1"`. Existing
embedded records retain their own aliases, versions, hashes and semantics.
All listed keys are required, including nullable keys. JSON booleans are not
numbers; nonfinite values, duplicate keys and unordered/set inputs are invalid.
Array ordering is lexical by declared ID unless a different rule is stated.
Source edges are ordered lexically by `(parent_source_id, child_source_id)`.
Collections are unique by their declared IDs. Review subjects have 1–256 IDs;
entry source bindings have at most two members. New report counts are strict
integers in 0–256; response feature counts are integers in 0–22 or null.
Receipt byte lengths obey their artifact-kind limits. No new free-form note fields
are accepted.
Caller aliases are ASCII `[A-Za-z0-9][A-Za-z0-9_-]{0,127}`. Derived IDs
(`dataset-`, `split-`, `group-`, `partition-`, `calibration-report-`) have exactly
the indicated prefix and 64 lowercase hex digits; labels are the closed set
`healthy`, `host_contention`, `render_capture_slowdown`. Existing embedded N2/N3
IDs retain their original validation; they are not rewritten to fit this syntax.
Hashes are `sha256:` followed by 64 lowercase hexadecimal digits.

Canonical JSON is sorted by key, indented two spaces, UTF-8 without ASCII escaping,
with no NaN/Infinity and exactly one final LF. Hash canonical bytes unless a field
explicitly hashes original file bytes. No current time, random ID or filesystem
path enters content-derived identities.

For the dataset, remove only root `dataset_id` and `content_hash`, canonicalize
and hash. `content_hash` is that hash; `dataset_id` is `dataset-<digest hex>`.
Both must reconstruct. For a report, remove only `report_id`, canonicalize and
hash; the ID is `calibration-report-<digest hex>`. Report fields are all required. A report embeds the dataset hash
and exact raw artifact references; verification against the dataset is separate
from standalone report validation.

## Dataset fields

| Field | Meaning |
| --- | --- |
| schema_version, method_release | Exact root and release above |
| dataset_id, content_hash | Reconstructed self-excluding identity/hash |
| artifacts | 0–256 unique Artifact declarations |
| sources | 0–256 unique Source declarations |
| derivations | 0–512 directed SourceEdge declarations |
| reviews | 0–256 unique Review declarations |
| split | One SplitDeclaration |
| entries | 1–256 unique Entry declarations |

An empty artifact/source inventory is permitted only for entries with no supplied
response/window; it represents missing data, not a usable empty calibration set.
Every supplied artifact/source/review must be reachable from an entry or the split.
No speculative unreferenced files or remote references are allowed.

### Artifact

| Field | Meaning |
| --- | --- |
| artifact_id | Unique safe ID |
| kind | `analytical_response`, `observation_window`, `experiment_bundle` |
| file_name | Exactly `<artifact_id>.json` for JSON, `<artifact_id>.tar.gz` for experiment bundles |
| sha256, bytes | Hash and positive length of exact supplied file bytes |

The response/window must validate as existing `AnalyticalResponseV2` or
`ObservationWindowV2`; the experiment is inspected with the existing linked
`inspect_experiment_bundle`, including v1/v2 dispatch and effect recomputation.
A result/report JSON alone is not an experiment bundle. Only these three kinds
are accepted; v1 P0 observations and N4 traces cannot masquerade as responses.
Nested experiment members retain their own existing bounds and versions.

### Source and source edges

| Field | Meaning |
| --- | --- |
| source_id | Unique dataset-local safe alias |
| acquisition_namespace | Safe pseudonymous namespace for the original acquisition system |
| run_id | Exact original N2 run ID, nonblank string at most 256 UTF-8 bytes |
| session_id | Safe pseudonymous acquisition-session grouping alias; required |
| independence_group | Safe operator-declared grouping for correlated acquisitions; required |
| source_type | `pixelated_bundle` or `synthetic_series` |
| source_content_hash | Exact existing N2 SourceArtifactV2 content hash |
| bundle_schema_version | `1`, `2`, or null, following existing source-type rules |
| review_id | Independence Review ID or null |

A supplied source review must have kind independence. A supplied split freeze
review must have kind split_freeze. Wrong review kinds or nonexistent subjects
are structural errors, not uncertain evidence.

A Source represents an acquisition/source artifact, not a window, frame or export.
All sources in a dataset share the namespace for the same acquisition system;
changing a namespace does not establish independence. Degraded and relief sources
must both be represented. Source identity binds `(acquisition_namespace, run_id,
source_type, source_content_hash, bundle_schema_version)`; repeated aliases for
one identity are allowed but join the same group and do not add repetitions.

`source_content_hash` uses the existing source algorithm, not the compressed TAR
file hash. For Pixelated, `bundle_checksum` hashes sorted member filename UTF-8,
NUL, raw member bytes, NUL for each member in the existing
reader’s recognized file map: `bundle-manifest.json`, `run-metadata.json`,
`stream-telemetry.csv`, `stream-events.csv`, `summary.json`, `engine-telemetry.csv`
when present. Ignored attachments such as PNGs are excluded; do not hash every
physical TAR member. It is invariant to archive compression
or header formatting. Source hashes declared by a supplied response remain
claims unless original sources are independently checked. N6 does not reread
unlisted original paths, import raw telemetry or approve a new capture method.

Sources with equal original identity must not contradict one another’s session or
operator independence-group declarations. Reused run identity with different
content is retained in one group, never treated as an independent run.

An edge has exactly `parent_source_id`, `child_source_id`. It means that the child
was derived/re-exported from the parent. Both ends must exist. Duplicate edges,
self-edges and directed cycles are errors. Edges connect groups for independence;
they never create independent repetitions or permit rewriting original evidence.

### Review

| Field | Meaning |
| --- | --- |
| review_id, reviewer_id | Safe IDs, no names, emails, paths or credentials |
| kind | `independence`, `label_binding`, `split_freeze` |
| subject_ids | Sorted unique nonempty array of source IDs, one entry ID, or the split ID, respectively |
| outcome | `confirmed`, `rejected`, `uncertain` |
| evidence_sha256 | Hash of the externally retained review/protocol receipt |

A review must bind its exact subjects: no unrelated review or hash can substitute.
Independence review subjects must cover **all** source aliases in the reconstructed
group; every source's `review_id` must name that same review. Confirmation means
the reviewer asserts that correlation groups/aliases have been fully disclosed,
not that sources within a group are independent of each other.

Label review confirms the precise Entry association: source runs and windows,
workload, capture/encoder/runtime versions and actual settings, probe declaration,
causal label, and experiment/phase association where supplied. A valid immutable
response alone does not establish any such physical association.

Split-freeze review confirms the identified protocol/assignments were fixed before
any outcome in that cohort was inspected and before acquisition for a prospective
split. A wall-clock string or local receipt hash cannot prove this ordering.
N6 does not authenticate reviewers; report assurance is always
`external_review_declarations_not_authenticated`.

### Entry

| Field | Meaning |
| --- | --- |
| entry_id | Unique safe ID |
| input_kind | `response`, `healthy_window`, `missing` |
| artifact_id | Response/window Artifact ID or null for missing |
| source_bindings | Exactly the bindings below, or empty for missing |
| label | Closed label above or null |
| label_basis | `controlled_effect`, `external_confirmation`, `declared_only`, `unknown` |
| label_review_id | Label-binding Review ID or null |
| experiment_artifact_id | Experiment Artifact ID or null |
| experiment_phase | `healthy`, `degraded`, or null |

Each SourceBinding has exactly `window_role` (`degraded`, `relief`, `healthy`),
`source_id` and `window_id` (exact original ID, nonblank, at most 256 UTF-8 bytes).
A response requires degraded and relief bindings in that order, each equal to its
embedded window's source identity/run/window. A healthy window requires one
healthy binding and actual N2 `phase=baseline` (the N6-to-N2 role mapping). A missing entry has null artifact,
empty bindings, unknown label basis, null label/review/experiment/phase, and cannot
claim checked evidence. A healthy-window entry must have label `healthy` or null;
its nonnull experiment phase must be `healthy`. Wrong references, roles,
versions or mismatched embedded source claims are errors, not missing data.

A response's query/profile feature support is reconstructed using its embedded
approved policy, including coverage, exclusions and confounders. N6 does not
replace normalization or alter the 22-feature inventory. `healthy_window` retains
baseline evidence separately; it never becomes a zero response/profile vector.

### Label support

The initial controlled mapping is fixed, not supplied as a caller policy:

| Experiment release/scenario | Permitted label and phase |
| --- | --- |
| `n5-single-cause-v1` / `healthy` | `healthy`, `healthy` phase |
| `n5-single-cause-v1` / `host_contention` | `host_contention`, `degraded` phase |
| `n5-capture-pacing-v1` / `render_capture_slowdown` | `render_capture_slowdown`, `degraded` phase |

Controlled support requires a supplied fully inspected bundle, available adapter,
completed result, recomputed `effect.state=verified`, verified cleanup and a
confirmed label-binding review. The selected phase must exist and be complete.
The binding review must assert correspondence between that phase's acquisition
and the entry's healthy/degraded source; N2 and N5 local aliases/clocks do not
supply this correspondence themselves. Check all mechanically comparable fields:
label/scenario/release/phase, workload ID and encoder family `vp8`. When the selected
window declares `effective_settings.targetFps`, it must agree exactly with manifest
`runtime.fps` (booleans do not equal numbers). This applies to the degraded or
baseline acquisition, not to the deliberately changed relief setting. Required
producer revision is `capture_method.producer_version`; it must be nonnull and
equal the experiment manifest producer revision. Context `versions` are retained
in the partition and checked if they declare a `pixelatedSourceRevision` revision. A known mismatch is rejected even if a review
claims confirmation. Missing required workload/producer agreement gives
`binding_unverified`; do not guess or compare unrelated clocks.

An existing N5 recovery phase is not an N2 relief window. A confirmed association
must cover the actual requested relief intervention and both source runs, not
merely fault removal, the experiment's `probe` phase name or matching FPS.

`external_confirmation` requires a confirmed exact-entry label review. It can
support any of the three labels without an N5 bundle; it remains an unauthenticated
external declaration. `declared_only` and `unknown` never qualify labels. Null
label is allowed only with unknown basis. Controlled basis requires nonnull
experiment and phase. A label_review_id, if supplied, must reference a label_binding review whose sole
subject is this entry. Other bases require null experiment and phase; no unused
experiment can lend authority to an unrelated entry.

## Split and lineage semantics

A SplitDeclaration has exactly `split_id`, `mode`, `protocol_sha256`,
`assignments`, `freeze_review_id`. Mode is `prospective` or `retrospective`.
Each assignment contains `group_id`, `role`. Roles are `engineering`, `training`,
`validation`, `final_test`. Assignments are sorted/unique by group ID and cover
all reconstructed groups exactly once, including groups with excluded entries.

Hash canonical `{mode, protocol_sha256, assignments}` for `split-<digest hex>`.
For a prospective split, `freeze_review_id` may name an exact split-freeze review;
without confirmation evidence is retained with `split_unverified`. For a
retrospective split, it must be null and entries retain `retrospective_split`.
Changing an assignment yields a different split/dataset identity, invalidating
old reviews. No model can establish real chronological precedence from hashes.

Reconstruct undirected independence components by joining sources with any of:

1. Equal `(acquisition_namespace, run_id)` (even if exported content differs).
2. Equal `(source_type, source_content_hash)` (even if namespaces/IDs differ).
3. Equal `(acquisition_namespace, session_id)`.
4. Equal `(acquisition_namespace, independence_group)`.
5. An explicit derivation edge in either direction.
6. Both sources of one paired response.

The last rule is essential: even separately captured degraded/relief runs produce
one inseparable response. Group ID is `group-<digest hex>` of canonical JSON
`{"source_ids": [sorted source aliases]}`. Aliases affect IDs but cannot evade
component reconstruction. Unknown source independence is retained and excluded,
not inferred from distinct files, hashes or clock-domain IDs.

Every entry with bindings must resolve to exactly one component. The split cannot
assign one component to multiple roles. Duplicate/shared component assignments,
missing group assignments and a stale pre-merge group ID are structural errors.
Multiple windows from the same source within one component/role are valid but add
no independent-run support. An exact response identity, or SHA-256 of the full canonical healthy-window model
(with original camelCase aliases), reused under multiple entry aliases is a duplicate: retain all aliases, report the
lexically first as representative, and exclude other aliases from eligible counts.
No duplicated content may acquire conflicting nonnull labels; that is an error.
A nullable representative label is retained without transferring label support
from another alias. Known identical raw artifact receipts can establish aliases
before file inspection; semantic response/window identity checks require the
actual validated records.

N5 `reference` and `held_out_query` are historical declarations, not automatically
training/validation/final-test assignments. A new mapping of already observed
outcomes must use retrospective mode. No random frame/interval split is permitted.
Do not subtract or order times across independently declared clock domains.

## Compatibility partitions

For a response, canonicalize the following payload and hash it as
`partition-<digest hex>`:

- Embedded registry reference, full approved policy content hash and provenance.
- Full capture method reference; clock `basis` and `provenance`, never domain ID.
- Degraded structural context excluding `context_id`, `node_id`, `network_scenario`.
- Intervention `probe_type`, `probe_version`, `application_method`, `intensity`,
  `requested_settings` **and** `observed_settings`.
- Both degraded and relief effective-settings maps.

Use snake_case nested model dumps for this new payload; JSON bool/number equality
is strict. Include an `input_kind` discriminator. Healthy windows use their registry,
provenance, capture method, clock meaning, structural context and effective settings,
with `policy_hash=null` and `probe=null`. Their partitions cannot merge with response
partitions. Missing entries have null partition. No normalization or feature
conversion is performed. Different valid partitions coexist, with counts kept
separate. A caller cannot override partition content with a supplied label/key.
This strengthens only the new partition contract; old v2 comparison behavior stays
unchanged. Different partitions do not by themselves make an entry invalid.

## Eligibility and report

Malformed roots, wrong hash/bytes, mismatched links, impossible ownership,
contradictory checked labels, cycles, inventory violations or invalid splits fail
the dataset inspection. Produce no partial accepted report. Well-formed failures,
unknown support and missing data remain entries with exclusions.

Group review state is confirmed only for a single confirmed exact-group review
referenced by every member. Otherwise use rejected if any applicable review is
rejected, uncertain if any is uncertain, missing in all other cases. An irrelevant
review never upgrades that state.

A report has exactly:

| Field | Meaning |
| --- | --- |
| schema_version, method_release, report_id | Exact release and reconstructed report ID |
| dataset_id, dataset_content_hash | Exact validated input identity/hash |
| split_id, split_mode | Reconstructed input split identity/mode |
| artifact_receipts | Exact sorted Artifact declarations verified against supplied bytes |
| groups | Sorted `{group_id, source_ids, role, independence_review_state}`; review state confirmed/rejected/uncertain/missing |
| entries | Sorted EntryInspection records below |
| partitions | Sorted `{partition_id, input_kind, retained_entries, eligible_entries, eligible_groups}` |
| counts | `{retained_entries, eligible_entries, excluded_entries, retained_groups, eligible_groups, by_role}` |
| assurance | Literal `external_review_declarations_not_authenticated` |

Each role count has the same five numeric counters; counts are entry/group counts,
never frame/interval counts. All four roles appear, including zeros. Missing entries
have `role=null` and count only in global retained/excluded entries. They create
no acquisition group. Group totals are distinct components, so several eligible
entries in one group contribute one eligible group globally and per partition.
Cross-partition counts are not summed as independent repetitions. Empty/no-eligible
datasets are valid reports, not successful calibration claims.

EntryInspection fields are `entry_id`, `input_kind`, `group_id` (nullable), `role`
(nullable), `partition_id` (nullable), `label` (nullable), `eligible` (bool),
`reason_codes`, `representative_entry_id`, `eligible_feature_count` (nullable).
Representative is self except for duplicate response/window entries; missing
entries represent themselves. Feature count is reconstructed for responses only.
For missing input, the only reason is `missing_measurements`. For all other
entries, all applicable exclusions below appear once in this fixed order; split
freeze status applies consistently to every nonmissing entry.

1. `missing_measurements`: input kind missing.
2. `engineering_only`: assigned engineering role.
3. `retrospective_split`: retrospective mode.
4. `split_unverified`: prospective split lacks confirmed exact freeze review.
5. `independence_unverified`: any source lacks a confirmed complete-group review.
6. `synthetic_only`: supplied window/response provenance is synthetic.
7. `confounded_response`: response has confounded-pair invalidity.
8. `insufficient_response_features`: response is invalid or fails its existing
   positive-weight count/coverage gate; a confounded response can have both codes.
9. `baseline_invalid`: healthy window validity is false, confounder codes are
   nonempty, or no supported complete primary measurement with numeric value exists; missing metrics remain missing, never zero-filled.
10. `label_unverified`: null/unknown/declared-only label, or missing/rejected/uncertain
    exact label review for a checked basis.
11. `effect_unverified`: controlled support has failed/unavailable effect or cleanup.
12. `binding_unverified`: controlled support lacks a confirmed exact-entry binding
    review or the required source/phase/workload/producer association.
13. `duplicate_evidence`: same response/window identity already represented.

An entry is eligible iff it has no exclusions. Healthy entries are eligible only
for baseline use, not response profiles. No N6 count is a sample-size/trust gate;
N7 defines adequate profile/calibration support. No outcome implies causality,
calibrated confidence, acquisition authenticity or Phase 2 completion.

## I/O, bounds and interface

The Python API is `inspect_calibration_dataset(directory: Path)` in
`latency_fingerprinting.calibration`, returning immutable dataset/report/validated
artifact records. CLI:

```sh
latency-fingerprint inspect-calibration --directory DATASET_DIR --output REPORT.json
```

Directory input only for this release; no new outer archive reader. Require exactly
`calibration-dataset.json` plus listed flat artifact files, no subdirectories,
extra entries, symlinks or special files. Pin directory/ancestor descriptors with
existing no-follow readers; inventory and read all bytes from the same pinned
root. Hash, parse and inspect the same bounded snapshots; never reopen an unpinned
path after validation. Do not execute code, import a producer, dereference a URL,
follow review receipts or read original files named outside this inventory.

Bounds: 257 directory entries; manifest/report each at most 10 MiB UTF-8 including
LF; depth 32 for new JSON and JSON artifacts (or stricter embedded parser bounds);
response/window each at most 10 MiB; experiment archive each at most 64 MiB with
existing 64 MiB expanded/member constraints; aggregate input at most 256 MiB,
including manifest and all listed files. A separate 256 MiB decoded budget counts
the manifest, response/window JSON and uncompressed experiment member payloads.
Each archive expansion, including TAR headers/padding, must also fit the remaining
decoded budget before decoding; retained members consume that budget for later
artifacts. This prevents many small compressed bundles bypassing the aggregate
limit. JSON map/string/number constraints from
embedded records still apply. No truncation or silent omission to meet bounds.

Check all bounds before corresponding allocation/parse; bounded snapshots may be
staged in private temporary files for the existing experiment inspector. Unknown
versions and supplied hash changes fail closed. CLI success is silent exit 0 and
writes canonical private mode-0600 output atomically. Existing output survives
failure; parent directory must exist and must be outside the input directory
(the exact input inventory cannot also contain an output report). CLI failure is exit 1 with exactly
`error: inspect-calibration: invalid_input_or_output`, empty stdout and no supplied
path/payload echo. API boundary is `ValueError("invalid_calibration_dataset")`.
Argument errors retain argparse exit 2. Generic `validate`/schema export recognize
both roots without changing existing dispatch. Standalone validation checks only
the root and intrinsic relations; supplied-artifact verification requires inspection.

## Implementation acceptance

Use the independent examples before models. Test renamed duplicate exports,
transitive paired-source leakage, correlated sessions, wrong-run labels, mismatch
even with confirmed reviews, split changes, zero-feature/confounded responses,
missing measurements, baseline separation, mixed partitions, finite arithmetic,
resource limits, deterministic API/CLI and preserved-output failures.

Existing contracts, policies, schema bytes, fixtures and match decisions must
reproduce unchanged. Authentic external review and scientific adequacy remain
explicit limits even when all structural/software checks pass.
