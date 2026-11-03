# Source-local method API and commands

The [1.2.0 temporal contract](N11_SOURCE_LOCAL_METHOD.md) adopts a complete declared
stable phase. Its raw v2 manifest must contain `sourceLocalPhase`, and its context
must declare `versions.pixelatedTemporalContract = "source_local_stable_phase_v1"`.
The source hash binds the declaration. Evidence hashes identify separately retained
phase evidence, without authenticating truth or accepting a diagnosis label.

```python
from latency_fingerprinting.adapters import ingest_pixelated_source_local

window = ingest_pixelated_source_local(
    "bundle.tar", context=context, phase="baseline", comparison_case_id="case-1"
)
for name, measurement in window.measurements.items():
    summary = measurement.summary
    print(name, summary.window_start_ms, summary.window_end_ms, summary.coverage)
```

The SDK accepts the existing bounded directory/archive formats. The protected CLI
accepts an archive and writes one atomic private result:

```sh
latency-fingerprint ingest-pixelated-source-local \
  --bundle bundle.tar --context context.json --phase baseline \
  --comparison-case-id case-1 --output window.json
latency-fingerprint validate window.json
```

Both preserve declared provenance/confounders. The phase and all positive source
spans must be 1–10 seconds; each source uses its full retained span. Absent/one-point
sources produce missing summaries and retain original source availability/row counts.
Every metric from a source uses the same bounds, including missing/unsupported
metrics. No arbitrary interval or per-metric cropping is accepted.

A source-local pair must meet all existing N2 settings/probe/context/restoration
checks and the 10% duration comparison separately for each measurable source.
N3 arithmetic and N6/N7/N8 support/partition rules are reused. Different method /
temporal-context partitions remain separate. Existing N9 baseline and replay
entry points reject this phase-local method; passive timing requires its own review.

`evaluate-study` reconstructs supplied source-local raw derivations with the new
adopter. Missing raw proof remains unavailable. All original source invalidity and
counter reset/gap evidence survive, and no acceptance mode or numeric target changes.

For fresh contained observations, the producer exposes the explicit
`prepare-source-local` command documented in its
[collector guide](../../../Pixelated-Studio-Edition/docs/research/n11/n11-raw-observation.md).
Retain the original acquisition bytes matching `evidenceSha256`, source snapshots,
plan, raw bundle and any failed prefix. Do not retrofit declarations into earlier
real acquisitions to change their reported outcome.

The producer's additive `exportObservedPhase` preparation API supports explicitly
recorded degraded/relief/recovery phases for a fixed 30→24→30 FPS example. Its short
four-row format uses a separate acquisition-protocol context partition. The
[artificial interoperability fixture](../../fixtures/paired-phase-v1/README.md)
checks original timestamps, source spans, effective settings and N2/N3 arithmetic.
It does not implement native dispatch, a persistent fault or restoration proof.
A recovery-phase export alone cannot supply a paired intervention outcome or label.
