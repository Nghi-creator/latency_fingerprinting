# Offline evaluation and N11 research

Start with the [interim fixture results](../../experiments/n11/receiver-ack-baseline-v1/README.md)
for the completed 36-acquisition study: 15 correct, 3 abstentions and 0 incorrect
held-out predictions. It is one correlated host session; broader N11 acceptance
is still open. Its public bundle checks its own ledger and checksums, while full
raw replay requires the preserved private inputs.

| Area | Guides |
| --- | --- |
| Study design and execution | [Offline ledger](study/N11_OFFLINE_EVALUATION.md), [fixtures](study/N11_FIXTURES.md), [fixture protocol](study/N11_FIXTURE_PROTOCOL.md), [combined study protocol](study/N11_COMBINED_STUDY_PROTOCOL.md), [within-session design](study/N11_WITHIN_SESSION.md) |
| Measurements and projections | [Raw windows](measurement/N11_RAW_WINDOWS.md), [source-local method](measurement/N11_SOURCE_LOCAL_METHOD.md), [usage](measurement/N11_SOURCE_LOCAL_USAGE.md), [CPU response](measurement/N11_CPU_RESOURCE_RESPONSE.md), [encoded events](measurement/N11_ENCODED_EVENT_RATE.md), [counter-specific projection](measurement/N11_COUNTER_SPECIFIC_PROJECTION.md) |
| Candidate methods | [Median response](methods/N11_MEDIAN_RESPONSE_EXPERIMENT.md), [readiness](methods/N11_REVIEWED_MEDIAN_READINESS.md), [fixture conditions](methods/N11_FIXTURE_CONDITION_EXPERIMENT.md), [combined intervals](methods/N11_COMBINED_INTERVAL_CANDIDATE.md), [temporal intervals](methods/N11_TEMPORAL_INTERVAL_CANDIDATE.md), [rank candidate](methods/N11_RANK_CONDITION_CANDIDATE.md), [shared-window separation](methods/N11_SHARED_WINDOW_SEPARATION.md) |
| Bounds and selection | [Contrast bounds](bounds/N11_COUNTER_CONTRAST_BOUNDS.md), [rank geometry](bounds/N11_RANK_GEOMETRY.md), [capacity calibration](bounds/N11_CAPACITY_CALIBRATION.md), [temporal rates](bounds/N11_TEMPORAL_RATE_RESPONSE.md) |
| Operator procedures | [Verification, custody and orchestration](operations/N11_OPERATOR_TOOLS.md), [pipeline qualification](operations/N11_PIPELINE_QUALIFICATION.md) |

Method guides specify behavior and evidence gates. Recorded results belong in
`experiments/`; plans, run logs and raw/private captures stay in ignored `local/`.
Earlier methods and failed outcomes remain relevant comparisons, rather than
being removed because a newer method exists.

[Source-local comparison inputs](study/N11_COMPARISON_INPUTS.md) documents raw-linked
N3 response inspection, fixture-label point comparisons, and the remaining N7/N8
label/group and N9 clock prerequisites.
