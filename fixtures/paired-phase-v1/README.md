# Invented paired-phase export fixtures

Three **artificial** sampled phases exercise the producer's actual CSV, summary,
manifest and TAR exporters, core source-local 1.2.0 adoption, N2 pair validation
and N3 response arithmetic. Nothing was collected from a native runtime. The
`passed` status and phase declarations in the invented acquisition JSON are test
inputs, not successful real executions, fault labels or restoration evidence.

Independent expectations specify a 30→24→30 cadence example, four browser rows
per phase on [0,3000] ms, three included engine rows on [500,2500] ms, camera CPU
median 21 and exact encoder-input rates of 30/24/30 FPS. N3's relative input-rate
response is −0.2. Missing bitrate evidence remains missing. A test supplies an
explicitly invented intervention declaration separately; recovery export alone
never creates a restoration outcome.

The format permits at most four seconds of retained phase span, with a separate
acquisition-protocol context partition from eight-row baselines. The short format fits within the existing five-second action limit in principle;
actual target readiness, collection and restoration feasibility remain unproven.
Normal read-only eight-row baseline exports retain their existing format/bytes.

Producer recipe: `engine/runtime/scripts/research/n10/pairedPhaseFixture.mjs`.
It requires an existing fresh output directory and refuses to overwrite files.
Generate to a separate directory for byte comparison; do not bless changed output
in place. `inventory.json` pins exact original bytes. Core consumer:
`tests/evaluation/test_paired_phase_export.py`; installed-wheel checks also adopt
all three phase archives through the protected CLI.
