# Integrated contained-game cohort custody

`integrated-game-cohort-record-v1`, method `n10-integrated-game-custody-v1`,
preserves the integrated camera, browser and dedicated-peer engineering cohort.
This is a custody record: validation checks the envelope, raw JSON wrapper and
content hashes. It does not independently reconstruct the producer's engineering
screen or authenticate execution. The older
[direct game/browser evidence](N10_GAME_BROWSER_EVIDENCE.md) has different actors,
lifetimes and clocks and cannot represent this acquisition by relabelling it.

## Import and inspection

```sh
latency-fingerprint import-integrated-game-cohort \
  --report /absolute/path/cohort.json \
  --output /absolute/path/record.json \
  --acquisition-id game-cohort-1 \
  --producer-revision FULL_40_CHARACTER_COMMIT
latency-fingerprint validate /absolute/path/record.json
latency-fingerprint inspect-integrated-game-record /absolute/path/record.json
```

Python callers use `import_integrated_game_cohort(raw_bytes, acquisition_id=...,
producer_revision=...)` and `inspect_integrated_game_record(record)` from
`latency_fingerprinting.live_probes`. These are local offline operations; they
execute no producer code and start no native runtime or browser. The CLI uses the
existing protected file reader and atomic writer, rejecting input symlinks and
output overlap through names, hard links or symlinks.

The original UTF-8 report is retained verbatim as `raw_report`, including
whitespace and line endings. `raw_report_hash` hashes those exact original bytes;
`content_hash` and `record_id` bind the canonical envelope, revision declaration
and report. Recover the original bytes with `record.raw_report.encode("utf-8")`.
Neither revision declarations nor hashes authenticate the producer, image,
ownership or execution. UTF-8 BOMs, invalid UTF-8, duplicate JSON keys, nonfinite
numbers and nesting beyond 128 levels are rejected. Raw input is limited to
1 MiB; the canonical envelope also has the normal 10 MiB contract limit.

The raw array must contain a nonempty prefix of this fixed order:

1. `engineering-game-disturbance`
2. `engineering-game-cancel`
3. `engineering-game-receiver-loss`
4. `engineering-game-source-loss`
5. `engineering-game-reconnect`

Each wrapper declares `status=passed|failed` and strict `live_authority=false`.
Failed rows, partial acquisition objects and early cleanup-stop checkpoints are
retained. Unknown nested fields are retained as opaque producer declarations,
not accepted as independently validated observations. Empty, reordered,
duplicated, extra or unrelated-mode cohorts are rejected. All five rows being
present means only structural completeness; it does not imply passing execution.

## Declaration inspection and limits

Inspection lists each acquisition's declared status, typed controller outcome
when present, and declared ledger state. Missing, null, invalid and duplicate
result events have distinct unavailable states. A declared verified restoration
remains a declaration; `restoration_independently_verified` is always false.
Worker death, reaping, replacement, dirty state and source-path recovery cannot
be promoted to verified restoration. Missing cases remain listed explicitly.
Nested observations and partial failure payloads remain available in the raw
report even when the declaration projection cannot interpret them.

All native host/worker read brackets, actor and generation identities, browser
relative timestamps, and separate host browser-resource clocks remain in the
original raw domains. Import performs no epoch substitution or clock alignment.
The cohort's local-owner restart describes a logical issuer restart, not a
camera process reboot; recording that scope does not independently verify it.

`engineering_screen=unavailable_independent_reconstruction_required` is fixed.
Perceptual quality, audio quality and desktop acceptance stay `not_evaluated`;
diagnostic value stays `unverified`. The root fixes engineering role,
`capability=unavailable_unqualified` and `live_authority=false`. Producer success
flags cannot qualify a relief family, enable production dispatch, authorize
mutation, clear a dirty ledger, or enter calibration/profile/final-test data.
Independent reconstruction and supported-context qualification are separate work.

## Independent reconstruction of supplied observations

`reconstruct-integrated-game-record /absolute/path/record.json` and the Python
API `reconstruct_integrated_game_record(record)` provide a separate derived view,
method `n10-integrated-game-reconstruction-v1`. The original custody root and
declaration-only inspection retain their meanings and content hashes. The
derived JSON is an inspection result, not an additional accepted root. It binds
both the record hash and original report hash and never executes producer code.

The core implementation independently checks these supplied observations:

| Case | Recomputed measurements and consistency checks |
| --- | --- |
| Complete action | Three ordered native windows; advancing capture/encode and game/script counters; stable distinct worker identity hashes; fixed encoder settings; source rates; browser decode/presentation rates; drops/freezes; picture variation; continuous callback/media gaps across the action; request/result and retained budget consistency |
| Cancellation and failures | One scoped request/fault/result sequence; expected clean or dirty reservation; replacement/restart assertions consistent with that outcome; exit and cleanup assertions; viewer epoch/binding counts; independently recomputed sibling browser window |

Native windows contain 10–14 samples spanning 2.5–3 seconds. Read timestamps must
be integral, nonoverlapping, advance by at most 500 ms and have brackets at most
50 ms wide. Phases must not overlap. Both workers retain their distinct declared
identity hashes across the complete-action windows. Every settings sample must
show the balanced 640×480, 1.5 Mbps, CPU 6, quantizer 48 profile, at 30 FPS except
the first worker's 24 FPS during window. Source and encoded rates use counter
deltas over the native read-start interval, with a 10% engineering tolerance.
Counter resets within or between windows invalidate reconstruction; endpoint
agreement cannot hide them.

Browser measurement windows span 2–2.5 seconds. Rates use their own callback and
stats intervals, at 30 FPS or 24 FPS with the same 10% tolerance. Callback/media
gaps are limited to 250 ms, stats coverage to 500 ms, with no new drops/freezes,
640×480 dimensions and at least three varying, nonblank picture hashes. Visual
samples must be ordered, within the window and cover it within 750 ms. Continuous
traces span 10–26 seconds and must cover each phase frame's exact presentation
count and media timestamp. Phase presentation counts cannot overlap or reverse.
No browser-relative timestamp is converted to a native clock.

Native CPU percentages are descriptive tick deltas over native read-start
intervals using the supplied tick frequency. Read brackets remain in the retained
report; the point estimate does not eliminate bracket or tick quantization
uncertainty. RSS maxima describe retained samples, not continuous high-water
marks. Parent, relay, game and each worker stay separate. Browser CPU uses the
separate host interval and an unchanged declared process inventory. Missing
resources, changed inventories, resets or invalid intervals yield unavailable
CPU with `null`, never zero. Missing browser resource data does not turn an
otherwise measured temporal window into a failure; no resource budget, CPU
benefit, causal relief or native/browser combined cost is inferred.

When native OS counter metadata is supplied, core also recomputes each process's
tick conversion, inventory hash and aggregate total. Per-process lifetimes and
timebases must persist, and no process counter may reset behind a rising total.
Native and host read brackets must be bounded and consistent. Partial or
contradictory metadata makes CPU unavailable. Historical aggregate-only snapshots
retain their original, narrower interpretation; neither format authenticates
process ownership or execution.

The fixed cancellation reservation is one action and four seconds, with a clean
ledger and declared verified cancellation. Uncertain failure results must retain
unknown restoration and a dirty ledger with that same reservation; a supported
uncertain reason stays unchanged. Receiver loss/reconnect may retain an explicit
null result as `unavailable_no_result`; source loss requires an explicit unknown
result. The complete five-second action reserves seven seconds including grace.
No new reservation is inferred from a replacement or logical owner restart.

`supplied_observation_screen` is `met`, `not_met` or `unavailable`. It describes
only the supplied measurements and declaration consistency in the table. Missing,
malformed or contradictory observations make a case unavailable; measured
temporal/rate/visual limit violations are not met. All five cases remain visible,
including missing cases, and later cases are evaluated after an unavailable row.
Any unavailable case keeps the aggregate unavailable. Producer pass/screen flags
do not substitute for samples or independently determine this result.

Reports without separately versioned lifetime observations do **not** contain
process lifetime observations for the replacement and issuer restart. In this v1
view, capture bindings, opaque
worker hashes, cleanup, stale-handle rejection and dirty-ledger assertions remain
producer declarations. Consequently `process_lifetime_verification` remains
`unavailable_retained_declarations_only` and independent execution verification
remains unavailable, even when supplied observations are consistent. Neither a
`met` screen nor a declared clean result verifies durable ownership, restoration,
authorization, watchdog targeting or journal persistence. Perceptual/audio/desktop
acceptance, diagnostic value and live capability retain their unavailable or
unevaluated states. Additional lifetime evidence and supported-context
qualification remain necessary.

## Lifetime and journal comparison

With `--lifetimes`, the reconstruction command produces the additive derived view
`n10-integrated-game-reconstruction-v2`. Python callers use
`reconstruct_integrated_game_lifetimes(record)`. The original root, raw bytes,
schema inventory and default v1 view stay unchanged.

Each failure case needs three `failure_lifetime` events, method
`n10-contained-game-lifetime-observations-v1`: `active_target` before the fault,
`replacement_ready` before issuer replacement, and `issuer_restarted` after the
new issuer's fixed readiness interval. Core checks their placement among the
scoped action/result events, nonoverlapping read brackets at most 50 ms wide,
native receipt freshness at most 1.5 seconds, and at least 2.5 seconds between
replacement-ready and post-restart reads.

The contained producer samples only its current camera, owned game/display and
supervisor-owned live children. The peer sampler checks the actual owned pidfd
and Popen handle. PID/boot/start-time preimages stay private; exported hashes
identify these observed lifetimes for comparisons. Camera/game/display hashes
must remain stable, game CPU must advance, and the sibling must retain its
process, generation, token and offer hashes with advancing native counters,
sequences and child timestamps. The replacement must have a different process,
generation and token from the old worker, then retain that lifetime across the
logical issuer restart. The retained old Popen return code must agree with the
supervisor's exit code: zero for cancellation, minus nine for uncertain faults.
Worker death is still not restoration.

Camera read/receipt timestamps are relative to the fixture's camera clock.
Child snapshot clocks keep their separate origins and are compared only within
the same worker lifetime. The private journal's cooldown timestamp is exported
as exact bounded decimal text, avoiding JavaScript integer precision loss; it is
never aligned with camera or browser clocks.

Journal observations are bounded, sanitized projections of complete atomically
published files. The observer validates owner, mode, directory binding, no-follow
file rules and the existing journal format/hash without acquiring the writer's
lease or gaining write capability. Its projection replaces private boot/process
identities with hashes. `projection_hash` is independently recomputed by core;
`private_content_hash` references the producer-validated private content whose
hidden preimage core cannot recompute. Neither hash authenticates execution.

Core binds the single retained request and its preimage/generation to the old
process hash, reconstructs the one-action/four-second reservation, and checks
active versus clean/dirty state and retained results. The directory, policy and
boot bindings must persist. Both the entire projection and private-content hash
must remain identical across issuer restart. Typed admission outcomes must
record rejection of the retired draft/receiver and old issuer, plus either a
read-only draft after clean cancellation or a dirty-ledger rejection. These
records do not serialize capabilities or independently prove authorization.

`lifetime_cases` contains all four failure cases and
`supplied_lifetime_screen=met|unavailable` describes only these supplied
comparisons. Missing historical events stay unavailable; they are never filled
from flags. Later cases remain visible after an unavailable case. A passing
result reports `failure_case_hashed_lifetime_comparisons_only`, while independent
execution verification remains unavailable. This adds engineering evidence; live
qualification, diagnostic value and perceptual/audio/desktop acceptance remain
unchanged.
