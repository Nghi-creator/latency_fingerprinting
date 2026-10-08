# N3 strict policy and analytical response models

**Delivered:** Step 2, 2026-10-07
**Contract:** [Analytical field contract](N3_ANALYTICAL_CONTRACT.md)
**Successor:** [Step 3 pure response derivation](N3_RESPONSE_DERIVATION.md), implemented 2026-10-08

`FeaturePolicyV1` and `AnalyticalResponseV2` are exported from
`latency_fingerprinting.models`. They use required camelCase JSON fields, strict
finite numbers, closed identities, forbidden extra fields and immutable detached
containers. Nested model instances are revalidated, including instances altered
through `model_copy`. Existing P0/N1/N2 roots and numerical behavior are preserved.

## Approved policy boundary

`latency_fingerprinting.analytical.policy_release.approved_policy_payload()` renders
the trusted in-package release. It reproduces the canonical
[policy specification](N3_FEATURE_POLICY_SPEC.json) without reading documentation
or resolving a supplied path/URL. Its self-excluding SHA-256 pin is:

`sha256:96457b318cc714f3d9d0d63a35b12548f6e030b10057b2c8e5a3a77e352fe1af`

Validation requires both hash agreement and exact approved content. Recomputing a
hash after changing a threshold, binding, inventory or method does not approve it.
The 22 features use registered primary outputs; audit totals and the unsupported
pipeline proxy are excluded. Parameters remain software-provisional.

```python
from latency_fingerprinting.analytical.policy_release import approved_policy_payload
from latency_fingerprinting.models import FeaturePolicyV1

policy = FeaturePolicyV1.model_validate(approved_policy_payload())
```

## Response reconstruction

An analytical response embeds its full `ObservationRecordV2` and approved policy.
Its deterministic ID hashes their canonical JSON. Every policy feature retains
both windows' primary values, support/status, sample and interval counts, duration
and coverage. Validation reconstructs those fields from the embedded summaries,
then checks eligibility, ordered exclusions, signed delta, reference, denominator,
normalized value and root validity.

Eligible calculations are `relief - degraded`, divided by
`max(abs(degraded), epsilon)`. Zero remains numeric; excluded calculations must be
explicit nulls. The initial policy permits no clipping. Calculations use the
contract's 1e-12 relative/absolute comparison tolerance. Any window/intervention
confounder excludes all features and makes the response invalid. Without a
confounder, an entirely excluded inventory has `no_eligible_features`; a valid
response alone does not establish enough evidence for future matching.

Step 2 validates supplied response records. [Step 3](N3_RESPONSE_DERIVATION.md)
now provides a public pure derivation function, and [Step 4](N3_FINGERPRINTS.md)
delivers fingerprints/repositories. [Step 5](N3_MATCHING.md) implements the separate
v2 matcher; proposed build/match commands remain pending. Existing v1
commands reject these new roots.

## Validation and schema export

The existing bounded, duplicate-safe JSON reader and generic root validator now
recognize `feature-policy-v1` and `analytical-response-v2`. Failures emit no partial
canonical record. For example, the normative policy can be checked read-only:

```bash
.venv/bin/python -m latency_fingerprinting validate docs/analysis/N3_FEATURE_POLICY_SPEC.json
.venv/bin/python -m latency_fingerprinting export-schemas --check
```

The additive schemas are
[feature-policy-v1](../../schemas/feature-policy-v1.schema.json) and
[analytical-response-v2](../../schemas/analytical-response-v2.schema.json), bringing
exports to eight roots. JSON Schema describes field structure; runtime validation
also enforces trusted release content and cross-record reconstruction.

## Local verification

94 analytical tests cover policy tampering with recomputed hashes, reconstructed
responses, unsupported/unavailable/missing/rejected/incomplete evidence, signed and
zero-floor arithmetic, confounders, immutable inputs, reused model instances and
public JSON reader failures. At Step 2, the full suite passed 1,260 tests with 93.15%
branch-inclusive coverage on Python 3.13.13. Existing schema bytes and P0/N1/N2
pins reproduce unchanged. Actual Python 3.11/hosted execution remains pending;
[progress](N3_IMPLEMENTATION_PROGRESS.md) records the separate verification status.
