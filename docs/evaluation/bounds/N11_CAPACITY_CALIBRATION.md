# Fixed-grid capacity calibration

`evaluation.capacity_calibration` is a separate, opt-in engineering method
`n11-capacity-calibration-v1`. It does not change N7, N8 or N11 defaults, admit N6
training groups, classify causes or authorize acquisition.

`select_capacity_calibration(cases)` requires exactly eight cases in fixed order,
with delays `[0, 30000, 32000, 34000, 36000, 37500, 40000, 50000]` microseconds.
Each case contains `plan`, `acquisition` and `control` mappings from the separately
versioned producer capacity mode. Source manifest, image and both revisions must
match across cases; acquisition and generation identities must be distinct.
Missing or failed slots invalidate selection. Retain failed prefixes and unstarted
suffixes; never silently omit or replace them.

Worker counter reads must cover healthy reference, initial, relief, recovery and
post reference, in one generation-bound clock with increasing sequences and no
counter reset. The guarded windows use the actual worker read brackets and the
explicit one-buffer sensitivity described in [counter bounds](N11_COUNTER_CONTRAST_BOUNDS.md).
They are finite-window descriptions, not confidence intervals, counter-freshness
proof, processing-latency measurements or transferable future-rate guarantees.

Only healthy, initial and post windows enter selection. A grid point qualifies if
healthy lower ≥27 FPS, initial lower >24 FPS, initial upper ≤95% of healthy lower,
and post lower ≥95% of healthy upper. Comparisons use exact rational arithmetic.
Select the lower median qualifying grid index; do not interpolate or optimize
relief separation. No qualifying point produces `no_candidate`.

`inspect_capacity_confirmation(cases, selection, confirmation)` recomputes the
complete selection, requires the selected dose and same source context, and rejects
calibration identity reuse. It reports guarded initial/relief separation separately.
The caller must bind original selection-file bytes to the confirmation plan and
independently check N3. Combined contrast remains unavailable in this API.

All inputs and controller receipts are declarations. Content hashes check internal
consistency, not authenticity. Before using a selection, independently verify raw
source custody and rerun the source-bound producer inspector for controller,
property persistence, rollback, worker cleanup and reference timing. No outcome
creates a diagnostic label or establishes generalization. Keep calibration and its
single fresh confirmation separate from untouched evaluation.
