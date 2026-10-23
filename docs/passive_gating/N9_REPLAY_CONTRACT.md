# N9 ordered replay and persistence

This document specifies the offline [passive gate](N9_PASSIVE_CONTRACT.md).
Each event has exactly event_id, kind (`window`, `tick`, `reset`), at_ms, entry_id
and reset_reason. Window events require entry_id and null reset_reason; ticks
require both null; resets require null entry_id and one of disconnect,
context_changed, clock_changed, generation_changed, operator_reset,
clock_unavailable. Identical repeated events may share an event ID; each row
retains its event_index, so identical ticks are not lost.

## Clock limitations

N2 exports capture-local `wall_clock_derived_elapsed`, or synthetic elapsed in
design fixtures. It has no monotonic guarantee. Retain this provenance and domain;
never rename it monotonic, subtract cross-domain timestamps, interpolate gaps or
infer ticks from wall time. Real linked synthetic evidence remains N6-excluded.
Ordered declared elapsed replay is provisional software evidence only. Silent
source clock discontinuities cannot be detected by the available contract.

Window at_ms must equal its original N2 elapsed end. Missing/nonpassive events
have only the supplied same-stream evaluation time. Ticks supply an explicit
evaluation time in that declared stream. Every original clock field remains
retained, with no correction or rebasing. A changed generation requires a new
replay; a terminal reset cannot be cleared by a later old window.

## Retained state and rows

State has exactly status (`unknown`, `pending_degradation`, `pending_recovery`,
`healthy`, `degraded`, `recovering`), degraded_latched, watermark_ms,
last_window_end_ms, last_valid_end_ms, barrier_ms, bad_windows, bad_duration_ms,
good_windows, good_duration_ms, proposals, last_proposal_ms, stream_invalidated.
Initial state is unknown, false latch, watermark/barrier equal replay start_ms,
null last timestamps, zero streaks/proposals, false invalidation.

Clearing the detector sets unknown, false latch, null last_valid_end_ms and zero
both streaks. Preserve last_window_end_ms, proposals and last_proposal_ms. A
barrier prevents a later arriving window from crediting time before a reset.
Terminal invalidation clears the detector and sets stream_invalidated; later
events cannot restore it. It never discards the proposal ledger.

Each row contains exactly event_index, event_id, entry_id, window_artifact_id,
novelty_key, classification (`low`, `recovered`, `band`, `unavailable`), observed_fps,
relative_fps, recommendation (`observe`, `probe`, `cooldown`, `no_action`),
reason_codes, effect_hypothesis, cause_label, profile_hypotheses and state (post-event).
Unavailable rows have null FPS/ratio; no excluded input is presented as used.
Window reference/key are null when no passive window exists, otherwise retained
even for exclusions. Hypothesis reflects the post-state latch, never a cause.

Result counts are total_events, window_events, tick_events, reset_events,
accepted_windows, ignored_duplicate_windows, ignored_out_of_order_windows,
unavailable_windows and proposals. Event-kind counts sum to total_events;
accepted/duplicate/out_of_order/unavailable counts partition window events.
Accepted means classified low/recovered/band. Terminal or post-terminal windows
are unavailable. Proposals equals the number of probe rows and final state ledger.
All integers, streaks, reasons and row states are fully reconstructed, not trusted
because a content hash matches. A separate derived seen-key set is reconstructed
from the entire event history, never supplied as mutable initial state.

## Ordered evaluation

Validate the complete request, references, original bounds and identities first,
including events after terminal invalidation. For each event use the first
applicable rule below. Reasons are one terminal/outcome reason unless expressly
specified otherwise. An unavailable outcome recommends no_action.

1. **Already invalidated:** unavailable `stream_invalidated`; state unchanged.
2. **Reset:** watermark becomes max(old watermark, at_ms), barrier becomes that
   watermark; terminal invalidation, reason `stream_reset`. Do not interpret a
   new clock origin from reset time. Its reset_reason remains in the input.
3. **Tick:** if at_ms < watermark, terminal `clock_reversed`, retaining the old
   watermark/barrier. Otherwise advance watermark to at_ms. If last_valid_end_ms
   exists and age >=5000, clear detector, set barrier to at_ms, reason `stale`;
   otherwise `tick_only`. A tick never grows a streak or proposes a probe, even
   when cooldown has expired. Repeating a stale tick becomes tick_only after clear.
4. **Missing / response entry:** clear detector, advance watermark to max(old,
   at_ms), set barrier to watermark; respectively `missing_measurements` or
   `not_passive_window`. Never access a response's FPS.
5. **Foreign clock/run:** passive source acquisition namespace, run or domain differs from stream;
   terminal `clock_scope_changed`, preserving watermark/barrier. No subtraction
   or advance in the foreign domain. Namespace/generation are fixed declarations.
6. **Duplicate:** N6 non-representative or previously seen novelty key;
   `duplicate_window`, no_action, unchanged state, no metric extraction. An N6
   alias never marks its canonical representative seen. Otherwise mark this first
   self-representative novelty key seen before any subsequent order/quality rule.
7. **Late:** end < watermark or end <= last_window_end_ms when present;
   `out_of_order`, no_action, unchanged state. No timing credit or extraction.
8. **Changed stratum:** source's reconstructed scope differs from stream stratum;
   advance same-clock watermark to end, barrier to end, terminal `scope_changed`.
9. **Overlapping:** start < last_window_end_ms, or (if not overlapping) start <
   barrier; respectively `overlapping_window` or `pre_barrier_window`. Advance
   watermark/last_window_end_ms to end, clear detector, barrier=end. No FPS used.
10. **Gap:** start > last_window_end_ms when present; clear detector, barrier=start.
    Continue with this window as the first of a fresh streak, prefixing its
    outcome reasons with `gap_reset`. The gap contributes no duration.
11. **Evidence:** advance watermark/last_window_end_ms to end. Collect blocking
    reasons in order: `not_requested_role`, `n6_excluded` (all N6 reasons except
    label_unverified/duplicate_evidence), `baseline_unavailable`, `source_overlap`,
    followed by the five metric-quality reasons in the main contract. Any reason
    clears detector and sets barrier=end. Preserve every applicable reason.
12. **Usable:** set last_valid_end_ms=end; classify with exact cross-products.
    Apply the transitions below. A freshness age is not accumulated from a window's
    start; its summary is available at its end. Only a tick can expire silence.

Windows may start before an intervening fresh tick's watermark if their end is
not late and start is not before the barrier. A stale tick sets a new barrier,
so an in-flight window crossing that timeout cannot restore persistence.

## Usable-window transitions

Only the accepted window's own positive duration is credited. Contiguity is exact
start == previous end, with the gap/overlap rules above. Neither ticks nor ignored
duplicates change the previous accepted streak. Unavailable evidence breaks it.

| Class | Streak / latch behavior | Status, recommendation, final reason |
| --- | --- | --- |
| low, entry gates not met | clear good streak; add one bad window and its duration; retain latch | pending_degradation if unlatched, otherwise degraded; observe; entry_pending |
| low, >=3 bad windows AND >=6000 bad ms | latch degradation; retain growing bad streak | degraded; choose proposal rule below |
| recovered, recovery gates not met | clear bad streak; add one good window and its duration; retain latch | recovering if latched, otherwise pending_recovery; observe; recovery_pending |
| recovered, >=2 good windows AND >=4000 good ms | clear latch; retain growing good streak | healthy; no_action; healthy |
| band | clear both streaks; retain latch | degraded if latched, otherwise unknown; observe; hysteresis_band |

For qualifying low input, use this exact priority: if proposals >=3, no_action
`proposal_budget_exhausted`; otherwise, if last_proposal_ms is present and
end-last_proposal_ms <30000, cooldown `cooldown_active`; otherwise probe
`persistent_degradation`, increment proposals and set last_proposal_ms=end.
Equality at 30000 permits a proposal, but only on a new qualifying low window.
Healthy recovery, gaps, missing/invalid input, stale ticks and explicit resets
preserve this replay's proposal ledger. Subsequent low windows after a break
must satisfy both entry gates again, even when the previous latch had been set.

No operation starts timers, invokes N8, controls Pixelated or creates execution
receipts. Frozen design vectors are synthetic operands; typed baseline and result
models now reconstruct statistics and transitions against their retained N6/N2
declarations. Linked verification of source bytes remains a subsequent slice.
