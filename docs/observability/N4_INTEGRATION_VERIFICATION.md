# N4 integration verification

**Release:** synthetic fixtures 1.0.0, methods `n4-stage-local-v1`.
**Scope:** software integration. [Real acceptance and overhead criteria](N4_PRODUCER_CAPABILITIES.md)
remain mandatory for full N4 acceptance.

## Independent pinned evidence

[Three fixture cases](../../fixtures/observability/README.md) pin nine canonical
JSON files separately from N1–N3. The host case covers zero duration, partial pairs,
mean arithmetic, a deadline hit at equality and a deadline miss. Browser cases
cover supported local callback lag and unsupported API evidence. Existing focused
model/collector/adoption/reconstruction tests cover resets, negative durations,
correlation ambiguity, sampling and capacity/drop accounting.

The read-only checker compares all JSON pins, validates records, reconstructs
against independent expected summaries and adopts exactly the two approved bundle
members. It writes only disposable temporary files. It cannot bless drift or
update fixtures. Both configured Python CI jobs now run it; default CI needs no
sibling checkout, Node, GI or real runtime.

```sh
python -m tests.observability.check_reproduction
```

## Actual collector/exporter to core reproduction

Use trusted checkouts of both repositories and an existing disposable directory.
The producer scripts feed fixed timestamps/opaque PTS to the actual bounded
collectors, then invoke production host/browser exporters. They do not import the
core, read golden fixtures, capture a screen or run a live video callback. All
records use synthetic provenance and a placeholder commit. Archive compression
bytes are not pinned across Python/Node versions; canonical record/manifest and
summary bytes are pinned.

From the Pixelated checkout:

```sh
mkdir -p /private/tmp/n4-step7-bundles
python3 scripts/n4/exportSyntheticTraces.py /private/tmp/n4-step7-bundles
node --experimental-strip-types scripts/n4/exportSyntheticTraces.mts /private/tmp/n4-step7-bundles
```

From the core checkout, using its installed environment:

```sh
.venv/bin/python -m tests.observability.check_reproduction \
  --producer-bundles /private/tmp/n4-step7-bundles
```

The last command validates the producer's three gzip-TAR archives and compares
adopted records and reconstructed summaries to pinned expectations. It also runs
`ingest-trace` → `inspect-trace` and compares both output files byte for byte.
Success reports `producerIntegration: passed` and `provenance: synthetic`.
The default command reports `producerIntegration: not_run`; standalone fixture
reproduction cannot silently stand in for cross-repository execution.

## Remaining real gate

Provision the frozen Linux/Xvfb/PulseAudio X11→queue→VP8 path and a draining local
WebRTC receiver, using an animated nonprivate scene, one peer, 1280×720 at 30 fps.
Save exact producer/core commits, runtime versions, configuration, commands and
CPU allocation. Use sampling 1, caps 2000/10000 and illustrative 50,000,000 ns
capture-output budget. Start a fresh recording after 10 s warm-up and collect 30 s.

Follow every case in the capability document: at least 500 usable queue and encode
pairs, ≥95% joint coverage with demonstrated unique PTS association, zero nominal
collector drops, tiny-capacity/interrupted/disable-re-enable/two-peer cases, and
supported/unsupported browser cases. Adopt/export/inspect the sanitized real trace
and independently recompute from integer timestamps; retain failed correlation
as a failed gate.

Run all five paired disabled/enabled trials in the predeclared alternating order.
Each baseline must sustain ≥27 fps. Acceptance requires median CPU increase ≤5
percentage points and median FPS change ≥−5%, with no failures or nominal drops.
Save every pair; also report ≥1000-probe diagnostic callback count/min/mean/max,
diagnostic overhead and export/write time. The capability document governs exact
formulas and limits. No measured values are currently available.

Full N4 acceptance remains pending until this evidence is recorded. Actual Python
3.11 and hosted CI execution are also pending; configured jobs are not run results.
