# JSON Schema inventory

Schemas are grouped by the project area that owns each contract. Versions of the
same contract stay together; a `v1` suffix does not imply legacy P0 code.

| Directory | Contracts |
| --- | --- |
| [`p0/`](p0/) | Frozen original observation, fingerprint and match result |
| [`measurement/`](measurement/) | Metric registry and v2 observation/window records |
| [`analytical/`](analytical/) | Feature policy, analytical response, v2 fingerprint and match result |
| [`observability/`](observability/) | Stage trace records and summaries, v1 and v2 |
| [`scenarios/`](scenarios/) | Experiment manifests, phase evidence and results; campaign and overhead records |
| [`calibration/`](calibration/) | Calibration dataset and inspection report |
| [`profiles/`](profiles/) | Profile policy and fitted snapshot |
| [`profile_matching/`](profile_matching/) | Match policy, result and evaluation |
| [`passive_gating/`](passive_gating/) | Gate policy, baseline, replay and result |
| [`evaluation/`](evaluation/) | Offline N11 manifest and failure-retaining report |
| [`live_probes/`](live_probes/) | Bitrate/cadence/game-browser probe evidence and integrated cohort record |

Run `latency-fingerprint export-schemas --output schemas --check` to check all
42 generated schemas. Exporting without `--check` writes this directory layout
beneath the requested output directory. Schema keys in the exporter and CLI
reports are paths relative to that directory.

[`measurement/metric-registry-v1.json`](measurement/metric-registry-v1.json) is
registry data rather than a JSON Schema; check it separately with
`latency-fingerprint export-metric-registry --output schemas/measurement/metric-registry-v1.json --check`.
