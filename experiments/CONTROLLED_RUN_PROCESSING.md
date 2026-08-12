# Controlled-run processing guide

Use this checklist after exporting one complete Pixelated controlled run. Run
all commands from the repository root with the project virtual environment
installed.

This guide uses `controlled-run-NNN` as a placeholder. Replace `NNN` with the
new run number everywhere before running a command.

## 1. Preserve the private inputs

Place the three Pixelated exports here without extracting them:

```text
experiments/controlled-run-NNN/raw/full_data/
├── healthy.tar
├── degraded.tar
└── relief.tar
```

The repository ignores `raw/` and TAR files. Confirm that Git will not track
them:

```bash
git check-ignore \
  experiments/controlled-run-NNN/raw/full_data/healthy.tar \
  experiments/controlled-run-NNN/raw/full_data/degraded.tar \
  experiments/controlled-run-NNN/raw/full_data/relief.tar
```

Do not continue unless the embedded bundle manifests have:

- the expected `comparisonCaseId`;
- phases `healthy`, `degraded`, and `relief`;
- one shared, newly generated `runId`;
- valid browser, engine, and encoder sources;
- the intended Balanced, Balanced, Performance profile order.

## 2. Finalize `context.json`

Create `experiments/controlled-run-NNN/context.json`. A previous context may be
used as a starting template only when the environment is genuinely unchanged.
At minimum, review:

- anonymized node and node class;
- workload and repeatable input procedure;
- browser and Pixelated revision;
- runtime and operating system;
- route and network scenario;
- encoder family and nominal profile;
- capture and transport implementations;
- compatibility group.

Give the new record its own `contextId`, but retain the same
`compatibilityGroup` as a reference fingerprint only when the measurement
contract, metric meanings, probe type, and relevant environment class remain
compatible. Never change compatibility metadata merely to force a match.

Do not record a username, hostname, absolute path, token, share URL, ROM,
session credential, or device serial.

## 3. Record restoration evidence

Create `experiments/controlled-run-NNN/restoration-evidence.json` immediately
after the experiment. Record only what was actually observed:

- pressure process completion and worker count;
- whether the script reported `restored: true`;
- whether Balanced was restored;
- whether the stream was live and ICE connected afterward;
- limitations and the evidence type, such as an operator note or screenshot.

If this evidence was not saved, use `restorationStatus: "unknown"`. A valid
relief-phase bundle does not prove later cleanup. The same value must be used in
`probe.json`.

## 4. Generate sanitized bundle checksums

Each run currently carries a small run-specific checksum script. Copy the
latest `record_bundle_checksums.py` into the new run directory and change its
`COMPARISON_CASE_ID` to `controlled-run-NNN`. Review the diff before running it.

Generate and verify `manifest.json`:

```bash
.venv/bin/python \
  experiments/controlled-run-NNN/record_bundle_checksums.py --write

.venv/bin/python \
  experiments/controlled-run-NNN/record_bundle_checksums.py --check
```

This manifest contains sanitized TAR names, sizes, capture times, schema
versions, run identity, and SHA-256 hashes. It does not contain raw telemetry.

## 5. Ingest the three observation windows

Create the output directories:

```bash
mkdir -p \
  experiments/controlled-run-NNN/healthy \
  experiments/controlled-run-NNN/degraded \
  experiments/controlled-run-NNN/relief
```

Ingest each untouched TAR:

```bash
.venv/bin/python -m latency_fingerprinting ingest-pixelated \
  experiments/controlled-run-NNN/raw/full_data/healthy.tar \
  --phase baseline \
  --comparison-case-id controlled-run-NNN \
  --context experiments/controlled-run-NNN/context.json \
  > experiments/controlled-run-NNN/healthy/window.json

.venv/bin/python -m latency_fingerprinting ingest-pixelated \
  experiments/controlled-run-NNN/raw/full_data/degraded.tar \
  --phase degraded \
  --comparison-case-id controlled-run-NNN \
  --context experiments/controlled-run-NNN/context.json \
  > experiments/controlled-run-NNN/degraded/window.json

.venv/bin/python -m latency_fingerprinting ingest-pixelated \
  experiments/controlled-run-NNN/raw/full_data/relief.tar \
  --phase relief \
  --comparison-case-id controlled-run-NNN \
  --context experiments/controlled-run-NNN/context.json \
  > experiments/controlled-run-NNN/relief/window.json
```

The generic `validate` command accepts top-level observation, fingerprint, and
match-result records—not standalone windows. Validate the windows through the
model instead:

```bash
.venv/bin/python -c "from pathlib import Path; from latency_fingerprinting.models import ObservationWindow; root = Path('experiments/controlled-run-NNN'); [ObservationWindow.model_validate_json((root / phase / 'window.json').read_text()) for phase in ('healthy', 'degraded', 'relief')]; print('windows valid')"
```

Also inspect the windows for the same run ID, comparison case, context, expected
profiles, durations, sample counts, validity, missing metrics, and confounders.

## 6. Finalize `probe.json`

Create `experiments/controlled-run-NNN/probe.json` from the actual degraded and
relief windows. Do not reuse old window IDs. Record:

- the exact degraded and relief `windowId` values;
- `probeType: "stream_profile_relief"`;
- `applicationMethod: "paired_run"`;
- `executionStatus: "executed"`;
- order `["degraded", "relief"]`;
- every requested and observed effective-setting change;
- measured quality cost;
- known confounders and safety notes;
- the truthful restoration status from Step 3.

For the current composite profile, all of these changes must be declared:

```text
bitrateKbps
encoderCpuUsed
encoderMaxQuantizer
fps
streamProfileId
targetBitrateKbps
targetFps
```

Do not attribute the response to only one of those settings.

## 7. Build and validate `observation.json`

```bash
.venv/bin/python -m latency_fingerprinting build-response \
  --degraded experiments/controlled-run-NNN/degraded/window.json \
  --relief experiments/controlled-run-NNN/relief/window.json \
  --probe experiments/controlled-run-NNN/probe.json \
  > experiments/controlled-run-NNN/observation.json

.venv/bin/python -m latency_fingerprinting validate \
  experiments/controlled-run-NNN/observation.json \
  > /dev/null
```

Inspect the raw and normalized response, warnings, missing features, rejected
features, and clipping before matching. Missing evidence must remain missing;
never replace it with zero.

## 8. Match against an independent fingerprint repository

For a repeat of controlled run 001, use its seed fingerprint repository:

```bash
.venv/bin/python -m latency_fingerprinting match \
  experiments/controlled-run-NNN/observation.json \
  --fingerprints experiments/controlled-run-001 \
  > experiments/controlled-run-NNN/match-result.json

.venv/bin/python -m latency_fingerprinting validate \
  experiments/controlled-run-NNN/match-result.json \
  > /dev/null
```

Preserve `matched` or `unknown` exactly as returned. Do not modify context,
thresholds, labels, or inputs after seeing the result merely to obtain a match.

Re-run the command into a temporary file and compare it to prove deterministic
output:

```bash
.venv/bin/python -m latency_fingerprinting match \
  experiments/controlled-run-NNN/observation.json \
  --fingerprints experiments/controlled-run-001 \
  > /tmp/controlled-run-NNN-match-result.json

cmp \
  experiments/controlled-run-NNN/match-result.json \
  /tmp/controlled-run-NNN-match-result.json
```

## 9. Optional: designate a run as a seed fingerprint

Only create a fingerprint when the run is intentionally designated as a
reference. Never evaluate a run against a fingerprint derived from itself.

The existing `controlled-run-001/record_seed_fingerprint.py` is deliberately
specific to run 001. Do not run it for another directory unchanged. A new seed
generator must update the source observation, fingerprint ID, known injected
condition, creation time, and notes, while retaining:

- `provenance: "controlled_real"`;
- `validationStatus: "unvalidated"` until independent evidence justifies a
  different status;
- complete source case, run, and window lineage;
- explicit provisional-weight and composite-probe limitations.

## 10. Final verification and privacy review

```bash
.venv/bin/python -m pytest
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m latency_fingerprinting export-schemas \
  --output schemas --check
git diff --check
git status --short --untracked-files=all
```

Before committing, inspect every trackable JSON and Markdown artifact. Confirm
that no raw bundle, ROM, personal path, identity, credential, or secret is
included. The final run directory should contain:

```text
experiments/controlled-run-NNN/
├── README.md
├── context.json
├── manifest.json
├── restoration-evidence.json
├── probe.json
├── observation.json
├── match-result.json
├── record_bundle_checksums.py
├── healthy/window.json
├── degraded/window.json
├── relief/window.json
└── raw/full_data/               # ignored and private
    ├── healthy.tar
    ├── degraded.tar
    └── relief.tar
```

Report a successful repeat match only as preliminary within-context
repeatability evidence. One or two controlled runs do not establish diagnosis
accuracy, calibrated confidence, cause discrimination, recovery benefit, or
generalization.
