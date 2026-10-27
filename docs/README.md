# Documentation

These guides describe the project's contracts, APIs, workflows and limitations.
The P0 and N1–N9 names identify the original analysis path and its additive
measurement, analytical, observability, experiment, profile, matching and passive
gate contracts. N9 provides immutable models, pure offline replay and linked
source inspection through protected commands. It does not execute live probes.

| Topic | Start here |
| --- | --- |
| Architecture | [System boundaries and data flow](ARCHITECTURE.md) |
| P0 analysis | [Research contract](p0/RESEARCH_CONTRACT.md), [model and matcher](p0/DATA_MODEL_AND_MATCHER.md), [Pixelated import](p0/PIXELATED_ADAPTER_AND_EXPERIMENT.md) |
| Metric semantics | [Inventory](measurement/METRIC_SEMANTICS_V2.md), [canonical registry](measurement/CANONICAL_REGISTRY.md), [registry models](measurement/REGISTRY_MODELS.md) |
| Raw measurement | [Sample extraction](measurement/SAMPLE_EXTRACTION.md), [gauges](measurement/GAUGE_AGGREGATION.md), [counters](measurement/COUNTER_AGGREGATION.md), [inspection](measurement/MEASUREMENT_INSPECTION.md) |
| Observation v2 | [Field contract](measurement/OBSERVATION_V2_CONTRACT.md), [models](measurement/OBSERVATION_V2_MODELS.md), [bundle adoption](measurement/OBSERVATION_V2_ADOPTION.md) |
| Analytical v2 | [Contract](analysis/N3_ANALYTICAL_CONTRACT.md), [approved policy](analysis/N3_FEATURE_POLICY_SPEC.json), [models](analysis/N3_ANALYTICAL_MODELS.md), [response derivation](analysis/N3_RESPONSE_DERIVATION.md) |
| Fingerprint matching | [References/repositories](analysis/N3_FINGERPRINTS.md), [matching](analysis/N3_MATCHING.md), [CLI commands](analysis/N3_COMMANDS.md) |
| Stage traces | [Contract](observability/N4_TRACE_CONTRACT.md), [models](observability/N4_TRACE_MODELS.md), [capabilities](observability/N4_PRODUCER_CAPABILITIES.md), [examples](observability/N4_TRACE_EXAMPLES.md) |
| Trace collection and analysis | [Host hooks](observability/N4_HOST_INSTRUMENTATION.md), [browser hooks](observability/N4_BROWSER_INSTRUMENTATION.md), [export/adoption](observability/N4_TRACE_ADOPTION.md), [reconstruction](observability/N4_TIMING_RECONSTRUCTION.md) |
| Browser execution timing | [Contract](observability/N4_BROWSER_EXECUTION_CONTRACT.md), [timestamp-method rationale](observability/N4_BROWSER_TIMING_REVIEW.md) |
| Scenario experiments | [Contract](scenarios/N5_EXPERIMENT_CONTRACT.md), [models](scenarios/N5_EXPERIMENT_MODELS.md), [examples](scenarios/N5_EXPERIMENT_EXAMPLES.md), [inspection](scenarios/N5_EXPERIMENT_INSPECTION.md) |
| Runtime adapters | [Capabilities](scenarios/N5_ADAPTER_CAPABILITIES.md), [lifecycle](scenarios/N5_RUN_LIFECYCLE.md), [supported adapters/effects](scenarios/N5_SUPPORTED_ADAPTERS.md), [campaign workflow](scenarios/N5_CAMPAIGN_WORKFLOW.md) |
| Calibration evidence | [Evidence, lineage and split contract](calibration/N6_EVIDENCE_CONTRACT.md), [independent examples](calibration/N6_EVIDENCE_EXAMPLES.md), [models and validation](calibration/N6_MODELS.md), [lineage and splits](calibration/N6_LINEAGE.md), [linked inspection and CLI](calibration/N6_INSPECTION.md) |
| Robust profiles and explicit lifecycle | [Profile contract](profiles/N7_PROFILE_CONTRACT.md), [provisional policy](profiles/N7_PROFILE_POLICY_SPEC.json), [independent examples](profiles/N7_PROFILE_EXAMPLES.md), [models and validation](profiles/N7_MODELS.md), [builder and commands](profiles/N7_COMMANDS.md) |
| Profile matching and evaluation | [Matching contract](profile_matching/N8_MATCH_CONTRACT.md), [provisional policy](profile_matching/N8_MATCH_POLICY_SPEC.json), [evaluation and refits](profile_matching/N8_EVALUATION_CONTRACT.md), [independent examples](profile_matching/N8_MATCH_EXAMPLES.md), [models and validation](profile_matching/N8_MODELS.md), [linked APIs and commands](profile_matching/N8_COMMANDS.md) |
| Passive gating | [Baseline, scope and policy contract](passive_gating/N9_PASSIVE_CONTRACT.md), [ordered replay and persistence](passive_gating/N9_REPLAY_CONTRACT.md), [provisional policy](passive_gating/N9_PASSIVE_POLICY_SPEC.json), [independent examples](passive_gating/N9_PASSIVE_EXAMPLES.md), [models and pure operations](passive_gating/N9_MODELS.md), [linked APIs and commands](passive_gating/N9_COMMANDS.md), [frozen runtime fixtures](passive_gating/N9_FIXTURES.md) |
| Live-probe evidence and preflight | [Capability inventory and live-control boundary](live_probes/N10_CAPABILITY_INVENTORY.md), [live-evidence design contract](live_probes/N10_LIVE_EVIDENCE_CONTRACT.md), [abstract lifecycle vectors](live_probes/N10_DESIGN_VECTORS.json), [offline evidence models and inspection](live_probes/N10_MODELS.md), [integrated game cohort import and reconstruction](live_probes/N10_INTEGRATED_GAME_RECORD.md) |
| Development and reproduction | [Testing/CI](measurement/QUALITY_GATES.md), [fixture inventory and maintenance](../fixtures/README.md), [arithmetic fixtures](measurement/ARITHMETIC_FIXTURES.md), [observation fixtures](measurement/OBSERVATION_V2_FIXTURES.md), [analytical fixtures](analysis/N3_ANALYTICAL_FIXTURES.md), [trace integration](observability/N4_INTEGRATION_VERIFICATION.md), [experiment fixtures](scenarios/N5_EXPERIMENT_FIXTURES.md), [calibration fixtures](calibration/N6_FIXTURES.md), [profile fixtures](profiles/N7_FIXTURES.md), [profile matching fixtures](profile_matching/N8_FIXTURES.md) |

Sanitized recorded experiments and their reusable processing procedure are in
[experiments](../experiments/CONTROLLED_RUN_PROCESSING.md). Synthetic fixtures and
software checks establish reproducibility and interoperability; they do not
establish diagnosis accuracy or real runtime performance.
