# Source-local stable-phase adoption, version 1.2.0

User-approved software temporal contract. This extends `pixelated_bundle_offline`
with a separate method version; old 1.0.0 and 1.1.0 common-window outputs and all
existing registry/policy semantics remain unchanged. It describes measurements
within a stable phase, with different observed source intervals. It provides no
clock alignment, simultaneous-channel, causal, authenticated-label or empirical
acceptance claim.

## Frozen interpretation

The complete raw bundle is the phase. Browser bounds remain its root bounds.
Every registered metric of each source uses that source's actual first/last raw
row times, including rows with unavailable/missing metric values. Bounds must be
contained in the phase; phase and positive source windows must be 1–10 seconds.
No slicing, metric-specific trimming, dropped prefixes, timestamp rebasing,
interpolation, extrapolation or zero filling is supported by this method.

Each metric summary already carries its explicit start/end/duration. All summaries
of one source must agree, even unsupported metrics. Browser bounds equal the root.
Absent/one-point sources retain root bounds and missing summaries with no usable
values; raw source availability/row counts remain truthful. Original raw validity,
confounders, settings, counters, reset/gap evidence and row lineage are preserved.

Context must explicitly declare
`versions.pixelatedTemporalContract = "source_local_stable_phase_v1"`.
Old methods refuse this marker; the new method requires it. This context, exact
method version and source hash separate source-local partitions from common-window
partitions. A version-string edit cannot turn an old output into linked proof.

The raw v2 manifest must contain a strict `sourceLocalPhase` declaration:

```json
{
  "schemaVersion": "source-local-stable-phase-v1",
  "basis": "operator_declared_not_authenticated",
  "phase": "healthy",
  "comparisonCaseId": "example-case",
  "elapsedStartMs": 0,
  "elapsedEndMs": 10000,
  "evidenceSha256": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
}
```

The declaration's phase/case/bounds must match the entire retained bundle. `healthy`
corresponds to a baseline observation. Its hash identifies separately retained
phase evidence; the declaration is not authentication or automatically accepted
cause truth. Do not add declarations to old real captures to manufacture an
accepted acquisition. Artificial fixtures explicitly declare their invented basis.
Fresh acquisitions must freeze this contract and retain actual phase evidence.
Known source invalidity/lifecycle failures cannot be hidden by a local crop.

For real pairs, existing probe/context/settings/restoration and root duration
checks remain. For each source with two or more rows in both windows, its actual
per-source durations must also differ by no more than the existing 10% relative
pair limit. Missing sources still exclude their features rather than fabricating
comparison support. N3 uses unchanged arithmetic and missingness gates on these
explicit source windows; N7 positive dispersion/group support is still required.

N11 linked proofs must rebuild 1.2.0 from the exact declared raw source. This
phase-local method is rejected by current N9 baseline/replay clock entry points;
it does not acquire passive onset/detection-time authority.

## Independent expectations

[Method vectors](../../fixtures/source-local-v1/expectations.json) were authored
before implementation. An artificial browser interval [0,10000] and engine interval
[500,5500] yield engine coverage 1, 32.5 median camera CPU, 60 input fps and 59.4
output fps. An internal missing metric remains incomplete on [500,5500]. Old methods
keep coverage 0.5 on the shared phase. These are distinct temporal denominators;
source-local success never rewrites the old result.
