# Passive degradation gate — N9 contract

Method release: `n9-passive-gating-v1`. This is the frozen design for an additive
offline gate. Immutable models, schema exports and pure baseline fitting/replay
are implemented. Linked source-inspection APIs and dedicated commands remain
unimplemented; see [models and pure operations](N9_MODELS.md).
The machine-readable [policy](N9_PASSIVE_POLICY_SPEC.json),
[replay rules](N9_REPLAY_CONTRACT.md) and [examples](N9_PASSIVE_EXAMPLES.md) form
one contract. Existing N1–N8 releases keep their identities and behavior.

## Meaning and scope

The gate compares `client.received_fps` with a compatible healthy training
baseline. It uses the N1 registered gauge's median, in `fps`, semantic version
`1.0.0`, source `browser_webrtc`, raw field `fps`, clock `source_elapsed_ms`.
The source reports the maximum video-inbound `framesPerSecond` across supported
streams. Its window median is a median of exported samples, not a per-frame or
time-weighted statistic. It can hide degradation in another stream. Gauge coverage
does not establish temporal coverage or a sampling cadence.

An accepted low observation supports only `received_fps_degradation`. It does not
identify a bottleneck, end-to-end latency, user-perceived quality or a causal
fault. N8 hypotheses require paired-response evidence; this release does not
manufacture that evidence from passive windows. `profile_hypotheses` is the
literal `unavailable`, `cause_label` is null, and the effect hypothesis is present
only while degradation is latched. No probability or lifecycle promotion occurs.

All roots carry assurance `software_provisional_declared_elapsed_not_live_authority`.
A `probe` recommendation is an offline proposal, never an executed probe or a
permission to change the producer. N10 must establish actual capabilities,
ownership, durable action budgets, application/readback, cancellation and
restoration. Restarting replay does not reset any real execution budget.

## Provisional policy rationale

The policy chooses an interpretable relative FPS gate: at most 80% of healthy FPS
enters the low class; at least 90% enters recovery. The ten percentage-point band
prevents one threshold from controlling both directions. Entry requires three
consecutive usable windows and six seconds of their duration. Recovery requires
two windows and four seconds. Neither count alone nor one unusually long window
qualifies. A five-second explicit freshness timeout prevents retaining old
degradation indefinitely; a thirty-second proposal cooldown and three-proposal
replay cap bound repeated recommendations.

Five independent healthy groups and 80% group availability establish a minimum
software support gate and prevent one long recording from dominating the center.
Two samples and a one-to-ten-second window reject single-point and unbounded
summaries. These choices exercise conservative, bounded software behavior. They
are **not empirically calibrated detection, freshness or safety thresholds**.
Before scientific or live acceptance, predeclare and evaluate them on independent
target-runtime runs. Changing them requires a new policy/method release; never
tune on final-test data. No live implementation should inherit these values as a
claim of safe actuation.

## Healthy baseline

Use one freshly inspected N6 dataset/report and its complete connected source
groups, duplicate representatives, reviews and frozen split. Preserve the complete
entry inventory, including excluded entries. Baseline metadata reasons, in order:

1. `missing_measurements`: N6 missing entry.
2. `not_baseline_window`: input kind is not `healthy_window`.
3. `not_training`: group role is not `training` (including absent role).
4. `not_confirmed_healthy`: label is not healthy, label basis is unknown or
   declared-only, or its label-binding review is not confirmed.
5. `n6_excluded`: any N6 exclusion other than `duplicate_evidence`.
6. `duplicate_evidence`: entry is not its N6 canonical representative.
7. `group_not_explicitly_healthy`: any measured entry in its connected group has
   a label other than healthy, including a missing label.

Collect all applicable reasons in this order. Only metadata-eligible entries have
their original typed N2 window retained in baseline inputs and assigned a stratum;
other entries retain identifiers/reasons with null window and stratum. A N6
`healthy_window` binds an N2 `baseline` phase. That phase alone is not a truth label.
Reviews and independent-acquisition declarations remain unauthenticated evidence.

For a metadata-eligible window, append these metric reasons in order:
`unsupported_metric` (support not supported or role not analytical_candidate),
`incomplete_metric` (summary not complete or primary median absent),
`rejected_samples` (nonempty `rejected_reasons`), `insufficient_samples` (fewer
than two usable samples), `unsupported_window_duration` (outside inclusive
1000–10000 ms). N1 complete summaries already forbid missing/rejected reasons;
the explicit checks preserve that boundary if input construction changes. Never
invent a rejected-sample count. Invalid N2 structure fails validation, rather than
becoming a metric exclusion. Fractional clock bounds are outside this interface.

Each stratum retains all metadata-eligible groups, even groups with no usable FPS.
For each group, take the median of usable window medians; then take the median of
these group values as center. One group has one vote. Retain the raw median
absolute deviation of group values as a diagnostic, with no scale floor. Zero MAD
is valid: this gate compares FPS levels, unlike N7's standardized scoring.

The availability denominator is the number of metadata-eligible groups in that
stratum, not all dataset entries and not only usable groups. A stratum is
`provisional` iff it has at least five total groups, five contributing groups,
availability at least 4/5 and a strictly positive center. Otherwise it is
`rejected`, retaining applicable reasons in order: `insufficient_training_groups`,
`insufficient_metric_groups`, `insufficient_availability`,
`baseline_center_not_positive` (also applies to absent center). An empty fit has
no strata and a rejected root. A root is provisional iff any stratum is
provisional. Rejected strata never authorize persistence or proposals.

## Comparability and identity

The passive stratum scope contains the complete N2 registry reference, provenance,
capture method (including producer version), clock basis and provenance, source
type and bundle schema version, effective settings, and full context except exactly
`context_id`, `node_id`, `network_scenario`. Source hashes, window/run IDs, clock
domain and timestamps are excluded from comparability. This permits comparable
independent runs to contribute levels without pooling their clocks. Do not use an
N6 baseline/response partition ID or an N7 feature scope as this key.
The scope object has exactly registry, provenance, capture_method, clock,
source_format, context and effective_settings. Clock contains exactly basis and
provenance; source_format contains exactly source_type and bundle_schema_version;
context is the N2 context projection above. Other members retain their original
typed N2 representations. No implicit defaults or omitted null source-format fields.

A stream pins acquisition namespace, run ID, clock domain ID, externally declared
generation ID and stratum ID. Replay also binds its exact baseline and dataset.
Generation is a declaration, not an authenticated live lease. One replay has one
stream, no restored mutable initial state, and no cross-run rebasing.

Canonical bytes are sorted-key UTF-8 JSON with two-space indentation, finite
numbers, no ASCII escaping and a final LF. Identity uses the validated model's
`model_dump(mode="json")` field names, normalizing accepted N2 aliases to snake
case. Generic validation may render N2 wire aliases; raw file receipts remain
separate from these normalized identities. SHA-256 root identity excludes only
its own ID and `content_hash`. Prefixes and root contracts:

| Model / schema version | Own ID field / prefix | Other exact root fields |
| --- | --- | --- |
| PassiveGatePolicy / passive-gate-policy-v1 | policy_id / passive-gate-policy- | fields in the published policy |
| PassiveBaseline / passive-baseline-v1 | baseline_id / passive-baseline- | policy, evidence, inputs, strata, state, counts, assurance |
| PassiveReplay / passive-replay-v1 | replay_id / passive-replay- | policy_content_hash, baseline_id, dataset_id, mode, stream, start_ms, windows, events, assurance |
| PassiveGateResult / passive-gate-result-v1 | result_id / passive-gate- | policy, baseline, replay, rows, final_state, counts, assurance |

Every root also has `schema_version`, `method_release` and `content_hash`; unknown
fields fail. A result embeds its exact baseline/replay/policy and reconstructs
every row and counter. Evidence contains the complete N6 dataset and report once,
inside baseline. Baseline inputs are sorted by entry ID; each has entry_id,
group_id, stratum_id, window, selected and reason_codes. Strata are sorted by ID;
each has stratum_id, scope, groups, center, raw_mad, state and reason_codes.
Each group has group_id, entry_ids (sorted metadata-eligible entries), selected_entry_ids
(sorted usable entries) and value (null iff none usable). Baseline counts are
retained_entries, metadata_eligible_entries, selected_entries, excluded_entries,
retained_strata and provisional_strata; selected plus excluded equals retained.
All nested models, copied instances and supplied derived values must revalidate.
Retained containers are immutable snapshots without caller-owned mutable aliases.
The policy accepts only its exact approved release content/hash; recomputing a
hash after editing thresholds does not approve another policy. Standalone
validation checks declarations and reconstruction; only linked operations inspect
source files or establish that this is the freshly rebuilt training snapshot.

Derived scope keys hash `{method_release, scope}`, prefix `passive-stratum-`.
Stream keys hash `{method_release, baseline_id, dataset_id, stream}`, prefix
`passive-stream-`; retain `stream_id` alongside the descriptor in replay's
`stream`, excluding stream_id from that hash. The
descriptor has exactly acquisition_namespace, run_id, clock_domain_id,
generation_id, stratum_id, stream_id. Event keys hash `{method_release, event}`
with the event's own event_id omitted, prefix `passive-event-`.

All new digest suffixes are exactly 64 lowercase hexadecimal characters and hashes
have the `sha256:` prefix. Acquisition namespace and generation use N6 Alias
(`A-Za-z0-9` first, then up to 127 ASCII letters, digits, underscore or hyphen).
Original run/domain/window IDs use N6 OriginalID (nonblank, at most 256 UTF-8
bytes); original N2 values outside that bound fail the N9 interface. Entry/artifact,
group and dataset IDs retain their N6 types. Booleans are strict; nullable fields
are required and explicitly null when absent. Computed counters are bounded by
256, streak durations by 2560000 ms. ID-sorted inventories are unique; repeated
references across events are permitted, but no unreferenced replay window is kept.
For stratum clocks and source format, copy `clock.basis`, `clock.provenance`,
`source_artifact.source_type` and `source_artifact.bundle_schema_version` exactly.
Acquisition namespace is declared once on the stream, not inferred from local
paths, artifact aliases, clock domains or machine identity.

Window novelty keys hash `{method_release, acquisition_namespace, run_id,
clock_domain_id, source_type, source_content_hash, window_id, start_ms, end_ms}`,
prefix `passive-window-`. N6 duplicates are ignored independently of this key.
Renaming a window cannot evade overlap/order checks. Novelty excludes entry and
artifact aliases. Source content hashes and primary N2 JSON file receipts occupy
different roles; typed canonical N2 bytes need not equal an original file's raw
SHA (whitespace is legal). Only linked inspection binds original bytes.

## Query evidence, arithmetic and budgets

Replay mode is exactly validation or final_test; incoming measured entries must
belong to that role. No training query, leave-one-out refit, query fitting or
automatic tuning is provided. For passive queries ignore only N6
`label_unverified`; query labels never influence FPS or state. Handle N6 duplicates
as ignored events. Every other N6 reason remains blocking. Responses are
`not_passive_window`; missing entries are `missing_measurements`. Never extract a
response's relief window. The query's complete connected source footprint must
be disjoint from **all contributing baseline groups**, across all strata.

Replay windows contain exactly the unique primary N2 artifacts referenced by
healthy_window events, sorted by artifact_id, each `{artifact_id, window}`. Even
unusable measured queries retain their full N2 input; missing and response entries
add no window. All references and typed inputs validate before evaluation. A
standalone root reconstructs declarations, not filesystem authenticity.
A standalone replay checks its own shape, bounds and identities. It has no
embedded dataset; exact entry/artifact membership and original-window end times
are checked when it is evaluated with its baseline or retained in a full result.

FPS operands are finite, nonnegative binary64 numbers; zero FPS is a usable low
observation. A baseline center must be positive. Compute medians with exact
arithmetic, rounding an even midpoint once to nearest binary64, ties to even.
Compute each absolute deviation from the rounded center exactly, round once,
then median those values for raw MAD. Relative FPS is exact FPS/center rounded
once. Nonfinite results and nonzero exact results rounding to zero fail the entire
operation. Canonicalize computed zero to +0.0; preserve source signed zero.
Classification uses exact cross-products on binary64 operands: `5*fps <= 4*center`
is low; otherwise `10*fps >= 9*center` is recovered; otherwise band. Never classify
using rounded relative FPS. Availability uses integer cross-products.

All counts and elapsed times are strict integers (booleans rejected). N2 elapsed
start/end/duration must be exactly integral, with no quantization; timestamps and
event at_ms/start_ms lie in 0..2^53-1. At most 256 dataset entries, baseline retained
windows, groups, strata, replay windows and replay events respectively; at most
256 group-entry references across a baseline. Each root is at most 10 MiB of
canonical JSON and nesting depth 32, with existing N6/N2 limits still applying.
Group and group-entry-reference budgets count retained occurrences across strata,
not just distinct IDs. Every stratum/group row has at least one metadata-eligible
input; the zero-stratum empty fit is represented at the baseline root.
Every limit is checked before unbounded materialization. A legal count does not
waive byte limits. No truncation, partial successful result or rolling eviction.

## Future linked operations

The planned linked operations in `latency_fingerprinting.passive_gating` are:

```python
build_passive_baseline(directory, policy, *, expected_split_id=None,
                       expected_dataset_content_hash=None)
replay_passive_gate(directory, baseline, replay, policy, *, expected_split_id=None,
                    expected_dataset_content_hash=None)
```

Replay performs one N6 inspection, rebuilds the complete training baseline from
that inspected snapshot and compares it with the supplied baseline, then extracts
query windows from the same snapshot. Any source or snapshot discrepancy fails
the operation. Full replay history is evaluated afresh; no hidden cache, mutable
continuation or replay ID acting as a durable runtime budget.

Future CLI names are `build-passive-baseline` and `replay-passive-gate`, with required
`--directory`, `--policy`, `--output`; replay also requires `--baseline`, `--replay`.
Optional anchors are `--expected-split-id`, `--expected-dataset-content-hash`.
Use bounded no-follow inputs, fresh source checks and protected atomic private
0600 output; refuse output aliases/hardlinks to any input or inspected member.
Failures preserve existing output and expose only `invalid_passive_baseline` or
`invalid_passive_replay`. Arithmetic failures are private operation failures,
never clipped, imputed or successful unknown outcomes. These linked APIs/commands
belong to the next slice. The four standalone schemas are exported now, bringing
the total to 36; all 32 earlier schema bytes are preserved.
