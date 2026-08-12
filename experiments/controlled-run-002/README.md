# Controlled run 002

**Status:** Complete independent repeatability query
**Evidence class:** Controlled-real preliminary repeatability evidence
**Comparison case:** `controlled-run-002`
**Reference:** Run 001 unvalidated controlled-real seed fingerprint

This independent repeat follows the run 001 workload, client, route, timing,
pressure and composite stream-profile procedure. Its observation is matched
only against run 001's compatible seed fingerprint. The result is preliminary
repeatability evidence, not diagnosis accuracy or generalization.

## Private inputs

```text
raw/full_data/
├── healthy.tar
├── degraded.tar
└── relief.tar
```

The TARs remain ignored and are never extracted for ingestion.

## Evidence limitation

No separate post-restoration evidence was supplied with these bundles.
`restoration-evidence.json` and the probe therefore preserve restoration as
`unknown`; the valid relief-phase stream is not treated as proof of later
cleanup or return to the nominal profile.

## Match outcome

Run 002 matched the independent run 001 seed fingerprint as
`host_encoder_pressure` with provisional match strength `0.9819067687174997`,
22 shared features and full feature coverage. There was no conflicting feature
evidence under the current residual rule.

This is preliminary within-context repeatability evidence only. Several highly
repeatable features—30 FPS output, frame counts and the bitrate reduction—are
direct consequences of applying the same composite Performance preset. They
can increase similarity without independently diagnosing the injected CPU
pressure. The repeat also used only one seed candidate, so there is no
top-two score margin or evidence of discrimination from other real causes.

The useful nontrivial repeated response includes camera CPU relief:
`47.09% → 26.03%` in run 002 versus `51.74% → 26.89%` in run 001. Even so, two
runs do not establish diagnosis accuracy, calibrated confidence or
generalization.

## Evidence checklist

- [x] Healthy, degraded and relief bundles are internally valid and share one run ID.
- [x] Sanitized checksums are recorded in `manifest.json`.
- [x] Fixed compatible context is recorded in `context.json`.
- [x] Observation windows are ingested and validated.
- [x] Executed composite probe and response observation validate.
- [x] Run 002 is matched against the independent run 001 seed fingerprint.
- [x] Result is reported only as preliminary repeatability evidence.
