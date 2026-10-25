# Offline live-probe evidence models

`live-probe-evidence-v1`, method `n10-live-evidence-v1`, is an immutable forensic
record for the initial `vp8_target_bitrate` candidate. It stores declarations and
observations without executing a request, qualifying a capability or accepting a
causal/diagnostic response. Its [JSON Schema](../../schemas/live-probe-evidence-v1.schema.json)
is additive; N1–N9 schemas, clocks, fixtures and response derivations retain their
meaning. The broader [live-evidence design](N10_LIVE_EVIDENCE_CONTRACT.md) includes
future production control requirements that this model does not implement.

The separate [capture-cadence evidence contract](N10_CADENCE_EVIDENCE.md) covers
the isolated Gst WebRTC cadence worker. It does not widen this bitrate root.

## Read, validate and inspect

```python
from pathlib import Path
from latency_fingerprinting.live_probes import (
    LiveProbeEvidence,
    inspect_live_probe_evidence,
)

evidence = LiveProbeEvidence.model_validate_json(Path("evidence.json").read_bytes())
inspection = inspect_live_probe_evidence(evidence)
print(inspection.model_dump(mode="json"))
```

The generic CLI validates the root and prints normalized JSON:

```sh
latency-fingerprint validate evidence.json
latency-fingerprint export-schemas --output schemas --check
```

`create_live_probe_evidence(**fields)` validates supplied fields, normalizes nested
typed objects, computes canonical SHA-256 content identity and returns the frozen
root. Supply the fields below except `schema_version`, `method_release`,
`assurance`, `evidence_id` and `content_hash`, which the factory owns. A successful
factory call is evidence validation, not approval or execution of a request.

## Retained fields

| Field | Meaning |
| --- | --- |
| `scope` | Acquisition and owner/pipeline/peer generations, process-relative monotonic clock domain/generation, declared provenance, producer revision and image SHA-256 |
| `intent` | Opaque request/capability identifiers, declared policy hash, exact control/units, prior/requested bitrate, intent time, application/restoration deadlines and settling exclusions |
| `receipts` | Up to three ordered application/restoration/cleanup attempts; requested value, call bracket and returned/raised/interrupted/unknown outcome |
| `windows` | Up to three ordered baseline/during/restoration observation windows, each with at most 64 bracketed counter/setting reads |
| `reason_codes` | Unique closed declarations of missing/failed evidence, always including `capability_unqualified` |
| Identity and assurance | Content-derived `live-evidence-<sha256>` ID and `sha256:<digest>`, method/version and `offline_declared_evidence_not_live_authority` |

All fields are closed, typed and required; nullable values mean missing evidence,
not zero. IDs are bounded aliases rather than arbitrary paths or native objects.
Hashes bind supplied content, not authenticity, acquisition independence or a
trusted policy. No policy is qualified by presenting its hash. `isolated_synthetic`
requires a null peer generation; `declared_producer_capture` requires a declared
peer generation. This binding does not authenticate a real producer or peer.

Only `vp8enc.target-bitrate`, in integer `bit_per_second`, is supported. Intent
declares a strict reduction from a positive prior setting, with ordered intent,
application deadline and restoration deadline. It is a record of the intended
operation, not an executable/live-authorized request. Late calls remain valid
evidence and appear in inspection; a deadline declaration is not a safety limit
enforced by this offline library.

Timestamps and counters are strict nonnegative integers no greater than 2^53−1.
Timestamps use nanoseconds relative to one declared process-monotonic origin.
Windows cannot mix domains or generations; a changed producer lifetime needs a
new record and an explicit missing/interrupted outcome. UTC, browser and old N2/N5
elapsed values cannot be silently rebased into this clock.

Windows are half-open, positive-duration and non-overlapping. Each sample's entire
read bracket lies inside its window; sample brackets strictly advance. Windows
exclude setter brackets. During/restoration windows require the corresponding
setter attempt and start after its declared settling exclusion. Baseline ends
before application; during ends before restoration. Settling times and the gaps
between windows are retained through the intent and timestamp bounds; they are
not usable response samples. No implicit window is created for a missing phase.

An incomplete setter bracket is retained for raised/interrupted/unknown calls.
Such a call may have acted. This record does not infer that it was harmless or
refund any execution budget. Actual ownership, durable intent/reservation,
idempotency, watchdog and journal recovery must be established by a future
producer adapter; this library neither implements nor verifies them.

## Counter reconstruction

Each read retains encoded bytes/frames, locally decoded frames/drops, the observed
bitrate, counter generation and a closed encoder/media settings snapshot. Missing
values remain null. An unknown counter generation stays null rather than receiving
a fabricated epoch. Settings include CPU/quantizer/rate-control, resolution/FPS,
threads/deadline/keyframe, buffer/lag/drop/resize controls. The first baseline
sample supplies the declared unrelated-settings reference; missing baseline
settings prevent an unrelated-controls comparison.

`inspect_live_probe_evidence` revalidates even typed instances and reconstructs
counter deltas across every sample, with these reasons in fixed order:

1. `insufficient_samples`
2. `missing_counter_generation`
3. `counter_generation_changed`
4. `missing_counter`
5. `counter_reset`
6. `missing_setting`
7. `setting_mismatch`
8. `missing_unrelated_settings`
9. `unrelated_settings_changed`
10. `no_encoded_progress`
11. `no_decoded_progress`

Fewer than two samples, a missing/changed counter generation, any missing counter
or any counter regression makes all counter deltas unavailable for that window. A
missing intermediate read cannot be hidden by valid endpoints. With usable
counters, deltas remain visible alongside setting/control diagnostics; they do
not establish a comparable response if those diagnostics are present. Zero
encoded or decoded progress is retained explicitly; queued decoder output cannot
stand in for encoder recovery. The measurement duration is last minus
first observation-start time, with raw read brackets retained as uncertainty.
For usable bytes, output bit/s can be computed as `8 * bytes_delta * 1e9 /
duration_ns`; this root stores exact integer operands rather than a rounded rate.
No response, similarity score, capability or safety threshold is derived here.

Inspection also reports missing phases, known late setter brackets,
`unknown_completion_phases` for attempts without an end timestamp, whether any
application was attempted and that an attempted action needs an independently
verified budget reservation. An unknown return time cannot establish deadline
compliance. Restoration is `not_needed` without an attempt, otherwise `unknown`,
or `setting_and_local_progress_only` when the restoration window has no listed
diagnostics. The last value still establishes neither independent output recovery
nor receiver continuity, verified rollback or permission to clear dirty state.

This release fixes `live_authority=false`, `capability=unavailable_unqualified`,
`receiver_continuity=unverified` and `quality=not_evaluated`. It cannot represent
qualified capability or verified live restoration. The producer inventory/trial
JSON is a separate operator format and is not automatically converted into this
root. A future exporter must preserve actual revision/image/clock identity and
missing outcomes; synthetic tests cannot manufacture those acquisition facts.
