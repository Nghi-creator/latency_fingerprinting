# N3 implementation progress

**Slice:** V2 analytical features and offline fingerprint/matching
**Started locally:** 2026-10-07
**Starting commit:** `06e697105e918c0c2f3ae2d25bf75c833f7982ad`

**Current next action:** Step 4 — strict v2 fingerprints and bounded repository loading. Steps 0–3
are complete locally; hosted/minimum-version verification remains pending.

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
