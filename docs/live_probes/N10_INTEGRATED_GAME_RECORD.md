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
