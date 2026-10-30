# Passive gating fixture release

[`fixtures/passive-gating-v1`](../../fixtures/passive-gating-v1) freezes
`n9-passive-gating-v1` software behavior under fixture release `1.0.0`.
Its [release inventory](../../fixtures/passive-gating-v1/release.json) pins complete
baseline/replay/result operands, original N2/N6 source bytes, the provisional
policy, preimplementation design vectors and N6/N7/N8 fixture releases. The checker
separately pins the release itself.

```sh
python -m tests.passive_gating.check_reproduction
python -m pytest tests/passive_gating
python -m tests.packaging.check_wheel
```

The corpus has 42 cases and 116 pinned files. Every successful case compares the
complete canonical API result with a frozen expected root, including identities,
embedded evidence, exclusions, every row/state field and all accounting. Linked
commands must produce those same bytes with empty stdout/stderr. Invalid linked
operations must retain fixed private errors and preserve existing output. Generic
`validate` checks all four roots, wire rendering and rejected retained-root lies;
its validation diagnostics follow the generic CLI rather than the linked commands'
private error contract.

| Histories and boundaries | Frozen expectations |
| --- | --- |
| Persistence and recovery | Three contiguous two-second low windows propose at 6000 ms; the band retains the latch; two recovered windows clear it |
| Novelty and ordering | Repeated evidence is ignored; overlap clears persistence; a gap credits only the new window; older evidence is ignored |
| Freshness and lifecycle | A tick at 10999 ms retains the latch; 11000 ms expires it; generation reset and backward clocks invalidate the stream |
| Scope and baseline support | Changed settings invalidate the stream; four healthy training groups retain a rejected baseline and unavailable query |
| Exact binary64 arithmetic | At center 1, binary64 0.8 is in the band and 0.9 is recovered; raw negative-zero FPS survives while computed zero is positive |
| Cooldown and proposal budget | Continued lows propose at 6000, 36000 and 66000 ms; the next low is blocked by the three-proposal limit |
| Retained-root and linked failures | Rehashed false statistics, state, row fields and excessive histories fail; wrong split/dataset anchors and forged linked operands fail |

Expected results were authored from literal state snapshots and closed-form
all-low timeline milestones, with independent Decimal ratios and existing
independent group-median/MAD calculations. N9 production fitting/replay code was
used to verify expectations, never to generate them. Upstream N2 serializers
provide wire aliases; they do not decide N9 outcomes. The original 83
[design cases](N9_PASSIVE_EXAMPLES.md) additionally cover arithmetic, quality and
abstract predicates that cannot all be represented as valid N2/N6 acquisitions.

The reader permits at most 192 flat members, 10 MiB per operand and 64 MiB total,
including a separately capped 1 MiB release file. Every read uses bounded,
no-follow file descriptors; unexpected/missing members or mismatched bytes fail.
Source members are content-addressed flat operands. The checker stages their exact
bytes under original basenames in temporary directories so actual linked APIs and
commands inspect the pinned N6 manifest and N2 files. It never reserializes source
bytes to repair a receipt. The staged inventories/bytes are checked after each
case, and all four fixture releases are verified again after execution. All writes
are temporary. There is no update/bless mode.

Both CI Python jobs run reproduction. The installed-wheel check copies all four
corpora, exercises every N9 case through the installed console entry point outside
the checkout, and separately checks installed pure/linked SDK behavior, output
protection and all schema exports.

**Provenance is `synthetic_and_model_only`.** These artificial sources exercise
eligible metadata and the controlled-real model branch without claiming physical
acquisition, authenticated reviews, real independence or calibrated thresholds.
A probe recommendation is an offline proposal with no execution authority.
Producer integration, hosted/platform checks, manual desktop acceptance and
scientific/live probe acceptance are separate checks; this checker runs none of
them.

To revise the release, review operand changes and independent expected outcomes,
version the fixture release as appropriate, and explicitly update operand/release
pins. Never regenerate expectations from current N9 results to bless a failure.
