# Offline study reconstruction

`n11-offline-evaluation-v1` coordinates the existing N6 inspection, N7 fit
verification, N8 group evaluation, original N3 point matcher and N9 linked replay.
Optional N10 game/browser or integrated custody roots retain separate forensic
results. The runner does not acquire data, dispatch probes, approve a protocol or
qualify a runtime. A paired response is not converted into a live response.

The initial release accepts only `software_only` and `exploratory_historical`.
Every report fixes empirical acceptance to
`unavailable_not_a_frozen_real_study`. Using N8's `final_test` role does not change
that assurance. Scientific targets and prospective acquisition authorization are
outside this release.

## Public API and CLI

```python
from latency_fingerprinting.evaluation import (
    EvaluationManifest,
    run_evaluation,
    verify_evaluation_report,
)

manifest = EvaluationManifest.model_validate_json(manifest_bytes)
execution = run_evaluation(manifest, receipt_paths)
report = execution.report
artifacts = execution.artifacts
verify_evaluation_report(report, receipt_paths)
```

`receipt_paths` is an explicit dictionary mapping every receipt ID to one local
file path, with no missing or extra keys. Paths are operands, not part of content
identity. No current/latest directory or remote source is discovered. Returned
artifacts are original immutable computed models, or an immutable mapping for the
existing integrated-cohort reconstruction dictionary. Their identity/hash links
remain in the report; the CLI writes only the report. Callers may retain those
artifacts separately, or reconstruct them from the same explicit sources.

```sh
latency-fingerprint evaluate-study \
  --manifest study.json --operands operands.json --output report.json
latency-fingerprint evaluate-study \
  --manifest study.json --operands operands.json \
  --verify-report report.json --output reconstructed-report.json
latency-fingerprint validate report.json
```

The operand file has exactly `{"paths": {"receipt-id": "/explicit/local/file"}}`.
Output parents must exist. Success is silent exit 0 with atomic mode-0600 output.
Failure preserves an existing output, exits 1, emits no stdout and prints exactly
`error: evaluate-study: invalid_input_or_output`. Argument errors retain exit 2.
The SDK exposes `ValueError("invalid_evaluation")` or
`ValueError("invalid_evaluation_report")` without paths or source-content echoes.

## Manifest fields

The [manifest schema](../../schemas/evaluation/n11-evaluation-manifest-v1.schema.json)
is normative. All keys are required, including nullable fields; types are strict,
collections ordered/unique and nested models immutable. `seal_manifest(payload)`
computes its content identity; it is not a protocol approval operation.

| Field | Meaning |
| --- | --- |
| schema_version, method_release | `n11-evaluation-manifest-v1`, `n11-offline-evaluation-v1` |
| manifest_id, content_hash | Canonical hash excluding these two fields; ID `evaluation-manifest-<digest>` |
| study_mode, scope | Explicit software/historical mode and `offline_separate_tracks_no_live_response_bridge` |
| protocol_receipt | Exact retained protocol file receipt, hashed without executing or interpreting it as authority |
| receipts | Lexically ordered ID/kind/original SHA-256/byte length; no paths or embedded raw data |
| datasets | Key, manifest receipt, expected dataset content hash and split ID |
| groups | Exact `(dataset_key, local N6 group_id) → study_group` mapping |
| raw_derivations | `(dataset_key, entry_id, healthy/degraded/relief role) → original raw TAR receipt` |
| diagnoses | Job ID, dataset, N7 snapshot, explicit N3 response policy, N8 policy, validation/final_test mode |
| passive | Job ID, dataset, N9 baseline/replay/policy receipts |
| live | Job ID and accepted game/browser or integrated-cohort evidence receipt |
| slots | One predeclared slot per study group: role, nullable declared truth, retained/failed/not_started state, failure code, nullable diagnosis/passive/live job IDs |

Each receipt must be used. Jobs have globally unique IDs. A passive stream cannot
count as multiple independent slots. Group bindings cover every actual N6 group
exactly once and agree with planned roles. Failed prefixes can retain source
evidence; their slot still remains failed. Missing N6 entries do not acquire a
fabricated role/group; the outer planned slot supplies their denominator.

The source reader checks receipts and exact N6 directory inventories, stages
verified snapshots privately, and calls the actual linked inspectors/operators.
Staging avoids reading changed public paths as if they were the originally hashed
input. Symlink/special inputs, output inside an original dataset and hard-link
aliases of consumed operands are rejected, including renamed original identities.

## Source, grouping and scoring gates

N6 source content hashes, acquisition namespaces/runs/sessions and operator groups
are reconciled across datasets. An alias cannot split one source into additional
study groups or roles. Contradictory declarations for one original identity fail.
Several sources may conservatively share one study group; that produces one slot,
not additional independent observations. External independence/label/freeze
reviews remain unauthenticated declarations.

Each supplied raw derivation is rebuilt with the real adopter, original context,
phase, comparison case, provenance and confounders. Version 1.0.0 reproduces the
whole bundle; [version 1.1.0](N11_RAW_WINDOWS.md) reproduces exact subwindow bounds.
The entire resulting N2 window must agree. Wrong supplied raw bytes fail; absent
raw links retain `raw_sources_unverified` and cannot produce a source-verified
diagnostic or passive outcome. A response's declared checksum is not a substitute
for original raw bytes. Source truth and execution authenticity remain unproven.

N8 freshly verifies the supplied N7 snapshot and evaluates every measured entry
in the explicit role. Original N8 group votes, truth exclusions, unknowns, confusion
and metric rules are reused. The N3 point baseline uses all the same selected
training responses and the exact explicit policy. It preserves same-label
competition, top-two margin, conflict and compatibility gates. It does not choose
the most successful reference after viewing queries. Only self-representative,
eligible responses supply point queries. N8's group summarizer also combines point
query votes; duplicates do not create votes or repetitions.

The runner refuses a diagnostic group omitted from its planned ledger. A slot's
nonnull truth must agree with supported N8 group truth. Both query and selected
training raw sources must reconstruct before predictions enter the outer outcome.
N9 freshly verifies its full baseline and source-extracts every replay query,
including after terminal resets. A stream's queried groups must belong to its
declared study slot. N9 produces proposals only, with no cause prediction.

## Reports and interpretation

The [report schema](../../schemas/evaluation/n11-evaluation-report-v1.schema.json)
embeds the manifest once, ordered result links and one outcome per planned slot.
Every linked job has a result reference. Failed/unstarted slots cannot claim
computed diagnosis or passive observations. Source-unavailable rows keep null
predictions/counts, distinct from a computed zero proposals or conservative
unknown. N10 linked observations remain `engineering_only`.

Counts use all planned validation/final_test slots, including failures and unknowns.
Correct/wrong predictions require a nonnull supported declared truth; unknown
counts include every null prediction. Zero denominators yield null ratios.
Training and engineering slots remain visible but cannot inflate held-out counts.
Per-role N8 confusion/metrics are in retained evaluation artifacts; all point
per-query comparisons and final per-slot labels are retained for reconstruction.
The initial outer summary combines both explicit held-out roles and does not
claim a final-only scientific accuracy estimate or an accepted numerical target.

`first_proposal_ms` is an event timestamp on the original replay clock, not
detection latency. Fault onset alignment, live diagnosis time, probe usefulness,
causal relief/cost benefit, audio/perceptual quality and production acceptance
are unavailable unless separately measured under an appropriate future protocol.
No cross-clock subtraction is performed.

Standalone root validation checks intrinsic structure, identities and denominators.
Use `verify_evaluation_report` or `--verify-report` to recompute all supplied
source/result links. A self-consistent rehashed output alone is not linked proof.

## Limits and compatibility

Limits are 256 slots, 160 datasets, 4096 group bindings/raw derivations/receipts,
128 passive jobs, 4096 aggregate point/profile comparisons, 4096 result links,
1 GiB aggregate input/decoded/result bytes and 10 MiB/depth 32 per outer root.
Embedded operations keep their existing stricter limits and fail rather than
truncate a cohort. N8's feature-row budget can require multiple bounded datasets
with the same study group/role map; do not silently drop queries to fit a call.

All 40 preceding schema files and all existing policy/fixture bytes remain pinned.
The two additive schemas describe software/historical evaluation, not a new live
response contract or a prospective empirical acceptance format.

The [frozen software corpus and producer packaging checks](N11_FIXTURES.md) verify
complete report reconstruction and independent ledger/window expectations.

[Source-local stable-phase adoption](N11_SOURCE_LOCAL_USAGE.md) adds explicit method
1.2.0 raw reconstruction for phase-level diagnosis. Its source spans are declared
individually, and current N9 passive timing rejects that method.
