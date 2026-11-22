# Evaluation package

The public entry points remain `latency_fingerprinting.evaluation` and the
`latency-fingerprint evaluate-study` command. Implementation modules are grouped by
responsibility:

| Package | Responsibility |
| --- | --- |
| `study/` | Manifest/report contracts, input loading, lineage, execution and CLI commands |
| `protocols/` | Prospective fixture and repeated-block declarations; capacity selection |
| `responses/` | Fixture, median, temporal and CPU response construction and readiness |
| `projections/` | Combined/counter-specific/shared-window source projections and encoded source inspection |
| `candidates/` | Experimental classifiers, calibration and within/cross-session scoring |
| `bounds/` | Contrast, rate, rank and shared-window interval arithmetic |

Tests follow the same groups under `tests/evaluation/`, with shared producer
boundary and fixture helpers in `tests/evaluation/support/`. Operator programs
remain in `experiments/`; research evidence and personal plans stay in ignored
`local/`. Relocation does not change method release names, arithmetic or
acceptance gates. Frozen source hashes still refer to their original checkouts.
