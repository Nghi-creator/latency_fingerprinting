# Controlled run 001

**Status:** Awaiting real Pixelated capture  
**Evidence class:** Controlled-real feasibility evidence  
**Comparison case:** `controlled-run-001`

This experiment exercises the complete Pixelated-to-matcher path. It does not
establish diagnosis accuracy, recovery benefit, or generalization. An
`unknown` match remains a valid result when the real evidence is weak or
ambiguous.

## Fixed factors to record before capture

Do not begin recording until every item below has one stable, anonymized value:

- legal test workload/game ID and repeatable input procedure;
- Pixelated Studio version and source revision;
- anonymized node ID and node class;
- engine operating system and runtime class;
- browser/client class;
- localhost or LAN route and network type;
- VP8 encoder implementation and nominal `balanced` profile;
- recording duration and warm-up duration;
- pressure worker count and duration;
- known background-load or network confounders.

Put these values into a contract-valid `context.json`. Do not include a user
name, hostname, absolute path, session credential, share URL, ROM, or device
serial. Both paired windows must use the same context file.

## Frozen P0 procedure

Use one workload, browser, client, route, input procedure, warm-up period and
recording duration for all three captures. Sixty seconds after a fixed warm-up
is the default when no better duration has been pre-registered.

1. Start Docker Desktop and Pixelated Studio, then start the engine and verify
   its health indicator.
2. Select the fixed legal test workload and the `balanced` stream profile:
   60 FPS, 1400 kbps, VP8 `cpu-used=6`, maximum quantizer 48.
3. With no experiment load running, perform the fixed warm-up, record telemetry
   for the fixed duration, and export the research bundle as the healthy run.
4. Start `bounded_cpu_pressure.py` in a separate terminal. Record its start
   output and do not change the worker count during the paired runs.
5. Keep the `balanced` profile, repeat the identical warm-up/input procedure,
   record for the same duration, and export the degraded bundle.
6. While the same pressure process remains active, select the `performance`
   profile and allow the stream restart to settle. Repeat the identical
   warm-up/input procedure and duration, then export the relief bundle.
7. Stop or allow the bounded pressure process to expire. Restore `balanced`,
   verify engine and stream health, and record the restoration evidence.
8. Move the private exports into the ignored paths below. Do not commit them.

The relief is a composite `stream_profile_relief` probe because it changes FPS,
bitrate and VP8 encoder settings together:

| Setting | Degraded | Relief |
| --- | ---: | ---: |
| `streamProfileId` | `balanced` | `performance` |
| `fps` | 60 | 30 |
| `bitrateKbps` | 1400 | 700 |
| VP8 `cpu-used` | 6 | 8 |
| VP8 maximum quantizer | 48 | 56 |

No response may be attributed to only one of those controls.

## Private input layout

```text
experiments/controlled-run-001/raw/full_data/
├── healthy.tar
├── degraded.tar
└── relief.tar
```

The repository ignore rules exclude `raw/` and TAR archives. Derived windows,
the observation, result, sanitized manifest and checksums may be committed only
after confirming that they contain no personal or secret data.

Record or verify the accepted TAR checksums without exposing their raw path:

```bash
python record_bundle_checksums.py --write
python record_bundle_checksums.py --check
```

## Processing commands

After capture, create `context.json` and ingest each bundle:

```bash
python -m latency_fingerprinting ingest-pixelated raw/full_data/healthy.tar \
  --phase baseline \
  --comparison-case-id controlled-run-001 \
  --context context.json > healthy/window.json

python -m latency_fingerprinting ingest-pixelated raw/full_data/degraded.tar \
  --phase degraded \
  --comparison-case-id controlled-run-001 \
  --context context.json > degraded/window.json

python -m latency_fingerprinting ingest-pixelated raw/full_data/relief.tar \
  --phase relief \
  --comparison-case-id controlled-run-001 \
  --context context.json > relief/window.json
```

Create `probe.json` from the observed effective-setting difference, using
`applicationMethod: paired_run`, `executionStatus: executed`, the actual run
order, and the verified restoration state. Then run:

```bash
python -m latency_fingerprinting build-response \
  --degraded degraded/window.json \
  --relief relief/window.json \
  --probe probe.json > observation.json

python -m latency_fingerprinting match observation.json \
  --fingerprints ../../fixtures/reference_cases > match-result.json

python -m latency_fingerprinting validate observation.json
python -m latency_fingerprinting validate match-result.json
```

## Evidence checklist

- [x] Fixed factors and procedure recorded in `context.json`.
- [x] Healthy bundle captured without experiment pressure.
- [x] Degraded bundle captured under bounded pressure with `balanced`.
- [x] Relief bundle captured under the same pressure with `performance`.
- [ ] Pressure stopped and stream profile restored to `balanced`.
- [ ] Runtime health verified after restoration.
- [x] Bundle checksums recorded in sanitized `manifest.json`.
- [ ] Real windows, observation and match result validate.
- [ ] Result described only as feasibility evidence.
