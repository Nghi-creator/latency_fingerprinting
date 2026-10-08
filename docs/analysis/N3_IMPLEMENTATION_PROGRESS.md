# N3 implementation progress

**Slice:** V2 analytical features and offline fingerprint/matching
**Started locally:** 2026-10-07
**Starting commit:** `06e697105e918c0c2f3ae2d25bf75c833f7982ad`

**Completed locally:** Steps 0–7; see [software closeout](N3_SOFTWARE_CLOSEOUT.md)
and [final audit](N3_ARCHITECTURE_AUDIT.md). Hosted/minimum-version verification
remains pending. Select successor scope from the broader roadmap before replacing
the completed plan.

## Step 0 — Preserve the N2 baseline

The starting checkout was clean. Reproduced existing local gates on macOS/Python
3.13.13: **1,166 tests pass; 93.05% branch-inclusive coverage** at the unchanged
85% floor. Ruff lint/format, installed dependencies, all six schemas, canonical
registry, all three fixture families, five controlled P0 artifacts, run-001 seed
and exact run-002 match bytes pass without rewriting frozen artifacts.

Frozen SHA-256 pins reproduced:

| Artifact | SHA-256 |
| --- | --- |
| N1 registry | `50329d193303c271194b28e9164ae8627dd257d7620174c5ab136ba209864884` |
| N1 sanitized report | `295f57a6f0e0ab80f64c7323be3cd5fc4e278aac712825f0173955594513c423` |
| N2 browser adoption | `50fd2ff8cb013a1d52564b5a21bbe210a25e810e0e55e036da5ca25c15911b81` |
| N2 engine adoption | `f92e1fe241200609a8133be233053a79c7bbb3dca179ffd6ab3e1bbba09ab179` |
| N2 synthetic pair | `d6b96c18e0104fcd62ea2525b5637c6aadf7a033ac30d3b4e918be3ff8088954` |

Python 3.11 and the GitHub CLI are not installed here. Hosted results were not
retrieved; actual minimum-version/hosted execution remains pending. The local
baseline is verified separately from release/remote verification.

## Step 1 — Freeze the analytical and matching contract

**Specified locally:** 2026-10-07
**Design version:** 1.0.0

The [field contract](N3_ANALYTICAL_CONTRACT.md) fixes four additive roots:
feature-policy-v1, analytical-response-v2, fingerprint-v2 and match-result-v2.
It specifies embedded observation/policy evidence, immutable strict boundaries,
deterministic IDs, registry/feature binding, per-window exclusions, signed relative
responses, fingerprint reconstruction, structural context/probe compatibility,
weighted RMS comparison and ordered conservative unknown decisions.

The [normative policy specification](N3_FEATURE_POLICY_SPEC.json) selects exactly
22 registered primary analytical outputs, excluding eight audit totals and the
unsupported pipeline proxy. Its explicit floors, weights, full-coverage requirements
and decision thresholds are software-provisional, not experimental calibration.
The policy requires at least 17/22 shared eligible features for a candidate;
missing or partial evidence cannot become replacement zeros. Confounded pairs
produce invalid analytical responses with retained audit evidence.

Policy identity is `n3-offline-conservative / 1.0.0`; content hash:

`sha256:96457b318cc714f3d9d0d63a35b12548f6e030b10057b2c8e5a3a77e352fe1af`

The specification JSON is documentation, not an implemented production root or
schema. Read-only checks verify its canonical self-excluding hash, exact registry
bindings/inventory and independent numerical examples. Markdown links and diff
whitespace checks pass. Source, tests, schemas, existing fixtures, CI and controlled
artifacts remain unchanged against the starting commit.

No analytical runtime models, new schema exports, normalization function,
fingerprint/matcher implementation or commands are delivered by Step 1. The next
action is Step 2: strict policy and analytical response models/schemas. Pending
hosted verification and scientific/instrumentation boundaries remain explicit.


## Step 2 — Strict policy and analytical response models

**Implemented locally:** 2026-10-07
**Starting commit:** `bc0bc779364edca31e67fe85c0d0e229521286a2` (clean checkout)

[Immutable policy/response models](N3_ANALYTICAL_MODELS.md) now enforce approved
release content, canonical identity, registry bindings and evidence reconstruction.
They reject forged arithmetic, exclusions, validity, strict types and copied model
instances; detach caller containers; preserve numeric zero and null calculations.
Confounded pairs retain audit evidence while excluding every feature.

The trusted in-package policy exactly reproduces the unchanged specification and
its existing hash. Generic root validation and schema export accept the two new
roots. No response builder, fingerprint, matcher or build command is delivered yet.

Local Python 3.13.13 results: **94 new analytical tests; 1,260 total tests pass;
93.15% branch-inclusive coverage**, above the unchanged 85% floor. Ruff lint/format,
dependency consistency, all eight schemas, canonical registry, three fixture
families, five controlled P0 artifacts, run-001 seed and exact run-002 match bytes
pass. All six existing schema bytes, numerical source, fixtures and P0/N1/N2 pins
remain unchanged. Python 3.11/hosted execution remains pending.


## Step 3 — Pure auditable response derivation

**Implemented locally:** 2026-10-08
**Starting commit:** `bca40248edaed0f984124ff8722ca95f1dd0bb46` (clean checkout)

[Pure derivation](N3_RESPONSE_DERIVATION.md) revalidates the explicit observation
and approved policy, derives signed responses from primary summaries and returns
an immutable, root-validated record. It retains null exclusions and confounder
invalidity; uses no ambient identifiers, cross-domain timestamp subtraction or
file writes. Fingerprints, repositories, matching and build commands remain pending.

Local Python 3.13.13 results: **30 new derivation tests; 1,290 total tests pass;
93.15% branch-inclusive coverage** at the unchanged 85% floor. Independent cases
cover positive/negative/zero/floor arithmetic, equivalent counter rates at different
cadences, mixed/missing/rejected/incomplete/unsupported evidence, confounders,
large finite values, copied model tampering and deterministic immutable inputs.
Ruff lint/format, dependency consistency, eight schemas, canonical registry,
three fixture families, controlled artifacts, run-001 seed and exact run-002 match
bytes pass. All existing schemas, policy specification, numerical source and
P0/N1/N2 pins remain unchanged. Actual Python 3.11/hosted execution remains pending.


## Step 4 — V2 fingerprints and bounded repositories

**Implemented locally:** 2026-10-08
**Starting commit:** `a73ba71e1940e84f976a636a20c6d6a3a7ef29b9` (clean checkout)

[Fingerprint creation/models and the separate repository loader](N3_FINGERPRINTS.md)
retain valid response evidence, exact eligible vectors, caller-declared sanitized
labels, consistent provenance and deterministic identities. Default software checking
requires 17/22 features; explicit unreviewed/rejected status permits lesser valid
audit evidence. No status authenticates experimental truth or promotes synthetic
provenance. Invalid/confounded responses fail creation.

Repository traversal validates every JSON file, sorts by ID and fails wholly on
duplicate IDs, malformed/mixed roots, unsafe links or resource violations. Bounds
are 128 files, 4,096 entries, depth 16, 10 MiB/file and JSON depth 128. Descriptor
traversal/no-follow opens and regular-file checks guard link replacement and FIFO
reads; pre/post-read bounds reject file growth. Empty repositories and retained
audit statuses are valid. Compatibility/candidate decisions belong to Step 5.

Local Python 3.13.13 results: **62 new fingerprint/repository tests; 1,352 total tests
pass; 93.35% branch-inclusive coverage** at the unchanged 85% floor. Ruff lint/format,
installed dependencies, nine schemas, canonical registry, three fixture families,
five controlled P0 artifacts, run-001 seed and exact run-002 match bytes pass.
All eight existing schema bytes, the normative policy, P0/N1/N2 source/fixtures and
pins remain unchanged. Generic root validation accepts fingerprint-v2. V2 matching
and build commands remain pending, as does actual Python 3.11/hosted execution.


## Step 5 — V2 compatibility, scoring and conservative matching

**Implemented locally:** 2026-10-08
**Starting commit:** `c5855adf3618ca0057f01ad50d5aab31639b4084` (clean checkout)

[The separate v2 matcher and result model](N3_MATCHING.md) revalidate all inputs,
retain ordered structural compatibility/shared-feature rejections and derive finite
weighted RMS residual evidence using the approved policy. All scored comparisons
remain auditable; top-five ranking uses distance then ID, with margin from all
scored candidates. Exact ordered unknown decisions preserve invalid, empty,
incompatible, insufficient, weak, ambiguous and conflicting outcomes. No additional
boundary epsilon or P0 defaults enter decisions.

MatchResultV2 reconstructs retained calculations/ranking/decisions, enforces strict
immutable maps and bounded inventory/output, and is accepted by generic validation.
Repository-backed verification additionally checks full fingerprint hashes, vectors,
labels and compatibility rejections. Retained hashes alone do not authenticate
external evidence. Fresh interpreter tests guard the corrected import-order cycle.

Local Python 3.13.13 results: **76 new matching/model tests; 1,428 total tests pass;
93.51% branch-inclusive coverage**, above the unchanged 85% floor. Independent
numerics, unknown priorities, threshold equality, strict JSON compatibility,
17/22 coverage, ties/truncation, overflow, tampering, immutable inputs, repository
verification, resource limits and fresh imports pass. Ruff lint/format, dependencies,
ten schemas, canonical registry, three fixture families, five controlled P0 artifacts,
run-001 seed and exact run-002 match bytes pass. All nine existing schema bytes,
frozen policy and P0/N1/N2 source/fixtures/pins remain unchanged. Additive v2 commands
are next; separate analytical snapshot pins and software closeout remain Step 7.
Actual Python 3.11/hosted execution remains pending.


## Step 6 — Additive bounded public commands

**Implemented locally:** 2026-10-08
**Starting commit:** `df5762d49f25c3d86afdc74ff3603a941f16064e` (clean checkout)

[The v2 commands](N3_COMMANDS.md) deliver build-response-v2, build-fingerprint-v2
and match-v2 with explicit local policies and exact canonical pure-API output.
Command implementation remains in a separate cli_v2 module; existing handlers and
numerical paths are preserved. Direct inputs use bounded no-follow descriptor
traversal, regular-file checks and duplicate-safe JSON validation. Fingerprint
creation/matching require policy equality with the embedded response. Default
software checking, explicit audit status and conservative unknowns retain API rules.

Commands render and bound the entire UTF-8 output to 10 MiB before stdout receives
any bytes. Failures return 1 with deterministic privacy-limited errors and empty
stdout; argparse usage failures retain exit 2. There is no v1 conversion, remote
policy resolution, rejected-file skip option or input/directory mutation.

Local Python 3.13.13 results: **52 new public command tests; 1,480 total tests pass;
93.56% branch-inclusive coverage**, above the unchanged 85% floor. Tests cover
CLI/API byte parity, end-to-end module execution, statuses/unknowns, malformed and
altered policies, mixed roots, safe errors, repository failures, unsafe links/FIFOs,
input growth, exact output limits, readonly inputs and v1 rejection. Ruff lint/format,
dependencies, ten schemas, canonical registry, three fixture families, five controlled
P0 artifacts, run-001 seed and exact run-002 match bytes pass. Existing schemas,
policy specification, P0/N1/N2 and analytical APIs/fixtures/pins remain unchanged.
Step 7 analytical snapshots/pins and software closeout remain; actual Python
3.11/hosted execution remains pending.


## Step 7 — Synthetic fixtures, final gates and software closeout

**Implemented locally:** 2026-10-08
**Starting commit:** `b5224cb17409ff28640960b060134471a6fd3cfe` (clean checkout)

[19 synthetic snapshots](N3_ANALYTICAL_FIXTURES.md) retain approved policy, an
observation, three responses, six declared references and all eight match outcomes.
Independent primary/rate, response, residual, distance, strength, margin and conflict
expectations complement exact-byte/SHA-256 pins. Read-only reproduction is wired
into both configured Python jobs. Public commands and full repository verification
reproduce every match case without refreshing artifacts.

The [final audit](N3_ARCHITECTURE_AUDIT.md) closes a repository root ancestor race:
no-follow descriptor traversal replaces the raceable full-path open, and a
replacement regression fails closed. No further package restructuring is justified.
README, architecture, contracts/guides, plan navigation, quality gates, fixture
README and [software closeout](N3_SOFTWARE_CLOSEOUT.md) reflect delivered behavior.

Local Python 3.13.13 results: **40 new closeout cases; 1,520 total tests pass;
93.58% branch-inclusive coverage** at the unchanged 85% floor. Ruff lint/format,
dependencies, ten schemas, canonical registry, four fixture families, three
reproduction modules, five controlled P0 artifacts, run-001 seed and exact run-002
match bytes pass. Whole-tree Markdown/diff checks include the final fixture docs.
Existing schemas, policy and P0/N1/N2 source/fixtures/pins remain unchanged. N3 is
closed locally; actual Python 3.11/hosted execution remains pending. Stage
instrumentation, experiment foundation and scientific validation remain separate
roadmap work. Review successor scope against those remaining boundaries.
