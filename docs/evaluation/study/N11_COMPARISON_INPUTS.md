# Source-local comparison inputs

`n11-source-local-comparison-inputs-v1` connects original N2 source-local pairs
to the unchanged approved N3 analytical response. It is an input inspection API,
not a new diagnosis policy, profile fit, passive replay or acquisition tool.

```python
from latency_fingerprinting.evaluation.study.comparison_inputs import inspect_comparison_pair

inspection = inspect_comparison_pair(
    original_observation_json_bytes,
    {"degraded": original_degraded_tar_bytes, "relief": original_relief_tar_bytes},
    expected_raw_sha256={"degraded": frozen_degraded_tar_hash, "relief": frozen_relief_tar_hash},
)
response = inspection.response
summary = inspection.summary()
```

Supply exact original JSON bytes and exactly two TAR byte strings. JSON is bounded
to 10 MiB and each TAR to 64 MiB; existing adopter member/decoded limits still
apply. The caller must pin the original observation and expected TAR receipts in
its protocol before execution. TAR hashes and N2 bundle-content hashes have
different meanings: repacking a bundle can preserve the latter while changing the
former. The inspector verifies the supplied TAR hashes, stages private copies,
re-adopts both complete windows with capture method `1.2.0`, and requires equality
with their recorded N2 windows before deriving any analytical response.

The original 22-feature policy, normalization, exclusions and missingness rules
are reused. Stable zero responses remain eligible when their original evidence
passes N3 quality gates; this bridge adds no MAD divisor or dispersion threshold.
It neither accepts the candidate's nine coordinates as N3 features nor fills
missing metrics. Errors raise `ValueError("invalid_comparison_pair")` without
echoing private source content. The returned response is the existing immutable
`AnalyticalResponseV2`; the summary is an ordinary inspection dictionary, not a
new generic-validation/schema root. No CLI or existing schema changes.

Raw reconstruction does not authenticate operator context, declared condition,
intervention execution, restoration or independent session boundaries. Those
require their separate evidence. A valid analytical response only establishes
input availability, not that a matcher will predict a label.

## Comparison tracks

| Track | Supported use | Boundary |
| --- | --- | --- |
| N3 point matcher | Existing `create_fingerprint_v2` and `match_response_v2` accept declared identifier labels, including explicitly prefixed fixture names | Fixture names are not verified causal labels; keep the original reference selection and all margin/conflict/compatibility gates |
| N7/N8 profiles | Existing linked N6/N7/N8 evaluation when its actual prerequisites are present | N6 labels are exactly `healthy`, `host_contention`, `render_capture_slowdown`; owned fixture conditions cannot be silently translated into them. Independent source groups must be established; repeated same-session blocks cannot manufacture them |
| N9 passive gate | Existing supported-clock healthy baselines and ordered replay | N9 rejects capture method `1.2.0`. Do not rename source-local spans or concatenate separate captures into a passive stream |

The inspector reports profile prerequisites as unestablished and passive timing
as unavailable; it does not execute N7/N8/N9 and present their absence as a zero
performance score. See [profile support gates](../../profiles/N7_PROFILE_CONTRACT.md),
[passive clock rules](../../passive_gating/N9_REPLAY_CONTRACT.md) and
[the original study runner](N11_OFFLINE_EVALUATION.md).

## Freezing a historical comparison

Pin original role/condition declarations and every observation/response/raw
receipt. Preserve all planned queries, including unavailable and abstaining cases.
Declare that outcomes were already seen; freezing an analysis now cannot turn it
into an untouched prospective test. Keep source versions and sessions separate.

For a point comparison, declare reference selection before scoring, use training
responses only, retain every comparison and preserve same-label competition.
`software_checked` references are software-validated, not empirically validated.
Report input availability, correct fixture predictions, abstentions, incorrect
predictions and operation failures separately. Null prediction means abstention;
an operation that did not run is unavailable. Neither case disappears from the
planned denominator. Do not tune thresholds, select a favorable reference or
refit on query outcomes. A prospective comparison needs fresh independent review
and data appropriate to its claim.
