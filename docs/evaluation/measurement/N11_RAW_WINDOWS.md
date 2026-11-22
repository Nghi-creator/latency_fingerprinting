# Same-source raw windows

`pixelated_bundle_offline / 1.1.0` adds bounded subwindow extraction without
changing version 1.0.0's complete-bundle output or existing schema bytes. The
method ID remains in N2's closed vocabulary; the version distinguishes measurement
meaning in N6 partitions, N3 compatibility and N9 strata. Synthetic methods remain
version 1.0.0. A version 1.1.0 record cannot match a 1.0.0 reference implicitly.

```python
from latency_fingerprinting.adapters import WindowBounds, ingest_pixelated_windows

windows = ingest_pixelated_windows(
    bundle_path,
    context=context,
    phase="baseline",
    comparison_case_id="recording-001",
    windows=[
        WindowBounds(start_ms=0, end_ms=2000),
        WindowBounds(start_ms=2000, end_ms=4000),
    ],
)
```

Bounds above are examples: each endpoint must actually occur in the original
browser timestamp sequence. Unsupported bounds fail; they are never rounded or
interpolated. One call reads and validates the original raw bundle once and
returns an immutable tuple of 1–256 ordered, nonoverlapping windows, each 1–10 s
long with strict integer-ms bounds. The SDK accepts the original bounded directory
or TAR formats. The protected CLI accepts an explicit archive file:

```sh
latency-fingerprint ingest-pixelated-window \
  --bundle recording.tar --context context.json --phase baseline \
  --comparison-case-id recording-001 --start-ms 0 --end-ms 2000 \
  --output window.json
```

Optional `--provenance` accepts controlled_real/organic_real; repeated
`--confounder-code` retains the existing closed confounder vocabulary. Synthetic
raw adoption is rejected. The raw manifest must agree with the original phase and
comparison case; the command cannot rename a degraded/relief export as baseline.
Output is a normal observation-window-v2 with capture method version 1.1.0.

## Exact boundary semantics

Retain every original sample with `start_ms ≤ elapsed_ms ≤ end_ms`, including
missing/unavailable/rejected rows. Preserve original row numbers, values, clocks
and UTC browser anchor timestamps. N1 aggregation is reused without extrapolation.
Counters use only adjacent usable pairs whose two endpoints lie within the
slice. Missing/reset/gap transitions retain existing N1 rules. Source/metric
declarations continue to mask stale numeric evidence.

Adjacent slices may share one boundary sample as an endpoint; their supported
counter intervals and interval durations do not overlap. Gauge medians describe
the retained boundary-inclusive samples, not a duration-weighted signal. Those
medians or sample counts must not be summed as independent acquisitions. No row
outside a slice is used to invent a boundary value or bridge a gap. An engine
series without boundary support can remain incomplete even with browser anchors.

Source availability counts are recomputed from actual selected source activity,
separately from numeric metric support. Original producer invalidity is retained
conservatively, including events outside the slice; windowing cannot repair a
producer-invalid bundle by hiding a bad prefix. New missing/partial source
availability is also explicit. Unsupported stage timings remain unavailable.

Each window keeps the original source checksum, run ID, clock-domain ID and
elapsed axis. UTC boundaries come from actual retained browser samples; no new
clock origin, synchronization or monotonic-capture guarantee is inferred.
Window IDs hash source, method version, exact bounds, phase, context, case,
provenance and confounders. Re-exporting or slicing one source creates correlated
observations in the same N6 source group, never independent repetitions.

## Safety and errors

The existing raw loaders validate the full envelope, source chronology, privacy,
settings and bounds before extraction. Invalid requests raise
`PixelatedBundleError("invalid_pixelated_windows")`. No partial tuple is returned.
The CLI uses no-follow bounded reads, private staging and atomic mode-0600 output.
Input/context hard-link aliases and unsafe output paths are protected even if
an original operand was renamed. Success is silent exit 0; failure preserves the
old output and prints exactly
`error: ingest-pixelated-window: invalid_input_or_output` with exit 1.

This is an offline measurement method. Real producer availability, supported
labels, capture quality, independence and an accepted study remain separate
requirements. N10 live observations cannot be imported through this method.
