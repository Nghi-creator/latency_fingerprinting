"""Deterministic bounded replay of declared elapsed evidence; no timers or effects."""

from ..analytical.policy_release import payload_hash
from .arithmetic import classify, ratio
from .baseline import stratum_id
from .contracts import METRIC, RELEASE
from .evidence import bounds, quality_reasons, scope


def initial_state(start):
    return dict(
        status="unknown",
        degraded_latched=False,
        watermark_ms=start,
        last_window_end_ms=None,
        last_valid_end_ms=None,
        barrier_ms=start,
        bad_windows=0,
        bad_duration_ms=0,
        good_windows=0,
        good_duration_ms=0,
        proposals=0,
        last_proposal_ms=None,
        stream_invalidated=False,
    )


def clear(state):
    state.update(
        status="unknown",
        degraded_latched=False,
        last_valid_end_ms=None,
        bad_windows=0,
        bad_duration_ms=0,
        good_windows=0,
        good_duration_ms=0,
    )


def novelty(window, namespace):
    start, end, _ = bounds(window)
    return (
        "passive-window-"
        + payload_hash(
            dict(
                method_release=RELEASE,
                acquisition_namespace=namespace,
                run_id=window.run_id,
                clock_domain_id=window.clock.domain_id,
                source_type=window.source_artifact.source_type,
                source_content_hash=window.source_artifact.content_hash,
                window_id=window.window_id,
                start_ms=start,
                end_ms=end,
            )
        )[7:]
    )


def query_inventory(baseline, replay):
    """Validate every event/source binding before taking even a terminal transition."""
    if (replay.baseline_id, replay.dataset_id, replay.policy_content_hash) != (
        baseline.baseline_id,
        baseline.evidence.dataset.dataset_id,
        baseline.policy.content_hash,
    ):
        raise ValueError("N9 replay/baseline binding mismatch")
    evidence = baseline.evidence
    pool = {row.artifact_id: row.window for row in replay.windows}
    sources = {s.source_id: s for s in evidence.dataset.sources}
    used, queries, semantics = set(), [], {}
    for event in replay.events:
        if event.kind != "window":
            queries.append(None)
            continue
        declaration, entry = evidence.entry(event.entry_id)
        if entry.input_kind != "healthy_window":
            queries.append((declaration, entry, None, None))
            continue
        window = pool.get(declaration.artifact_id)
        if window is None:
            raise ValueError("N9 original query window missing")
        evidence.bind_window(declaration, entry, window)
        if event.at_ms != bounds(window)[1]:
            raise ValueError("N9 event time differs from original window end")
        used.add(declaration.artifact_id)
        namespace = sources[declaration.source_bindings[0].source_id].acquisition_namespace
        semantic = payload_hash(window.model_dump(mode="json", by_alias=True))
        previous = semantics.setdefault(semantic, entry.representative_entry_id)
        if previous != entry.representative_entry_id:
            raise ValueError("N9 semantic query duplicate contradicts report")
        queries.append((declaration, entry, window, namespace))
    if used != set(pool):
        raise ValueError("N9 replay contains unreferenced windows")
    return queries


def usable_transition(state, category, duration, end):
    """Mutate only this replay's local working state, then return an outcome."""
    state["last_valid_end_ms"] = end
    if category == "low":
        state.update(good_windows=0, good_duration_ms=0)
        state["bad_windows"] += 1
        state["bad_duration_ms"] += duration
        if state["bad_windows"] < 3 or state["bad_duration_ms"] < 6000:
            state["status"] = "degraded" if state["degraded_latched"] else "pending_degradation"
            return "observe", "entry_pending"
        state.update(status="degraded", degraded_latched=True)
        if state["proposals"] >= 3:
            return "no_action", "proposal_budget_exhausted"
        if state["last_proposal_ms"] is not None and end - state["last_proposal_ms"] < 30000:
            return "cooldown", "cooldown_active"
        state["proposals"] += 1
        state["last_proposal_ms"] = end
        return "probe", "persistent_degradation"
    if category == "recovered":
        state.update(bad_windows=0, bad_duration_ms=0)
        state["good_windows"] += 1
        state["good_duration_ms"] += duration
        if state["good_windows"] >= 2 and state["good_duration_ms"] >= 4000:
            state.update(status="healthy", degraded_latched=False)
            return "no_action", "healthy"
        state["status"] = "recovering" if state["degraded_latched"] else "pending_recovery"
        return "observe", "recovery_pending"
    state.update(bad_windows=0, bad_duration_ms=0, good_windows=0, good_duration_ms=0)
    state["status"] = "degraded" if state["degraded_latched"] else "unknown"
    return "observe", "hysteresis_band"


def reconstruct_replay(baseline, replay):
    queries = query_inventory(baseline, replay)
    strata = {s.stratum_id: s for s in baseline.strata}
    stratum = strata.get(replay.stream.stratum_id)
    training_groups = {
        g.group_id for s in baseline.strata for g in s.groups if g.selected_entry_ids
    }
    training_sources, training_receipts = baseline.evidence.footprint(training_groups)
    state, seen, rows = initial_state(replay.start_ms), set(), []
    for index, (event, query) in enumerate(zip(replay.events, queries, strict=True)):
        at = event.at_ms
        declaration, entry, window, namespace = query if query is not None else (None,) * 4
        key = novelty(window, namespace) if window is not None else None
        row = dict(
            event_index=index,
            event_id=event.event_id,
            entry_id=event.entry_id,
            window_artifact_id=declaration.artifact_id if window is not None else None,
            novelty_key=key,
            classification="unavailable",
            observed_fps=None,
            relative_fps=None,
            recommendation="no_action",
            reason_codes=[],
            effect_hypothesis=None,
            cause_label=None,
            profile_hypotheses="unavailable",
        )
        reasons = row["reason_codes"]
        if state["stream_invalidated"]:
            reasons.append("stream_invalidated")
        elif event.kind == "reset":
            state["watermark_ms"] = state["barrier_ms"] = max(state["watermark_ms"], at)
            clear(state)
            state["stream_invalidated"] = True
            reasons.append("stream_reset")
        elif event.kind == "tick":
            if at < state["watermark_ms"]:
                clear(state)
                state["stream_invalidated"] = True
                reasons.append("clock_reversed")
            else:
                state["watermark_ms"] = at
                if (
                    state["last_valid_end_ms"] is not None
                    and at - state["last_valid_end_ms"] >= 5000
                ):
                    clear(state)
                    state["barrier_ms"] = at
                    reasons.append("stale")
                else:
                    reasons.append("tick_only")
        elif window is None:
            clear(state)
            state["watermark_ms"] = state["barrier_ms"] = max(state["watermark_ms"], at)
            reasons.append(
                "missing_measurements" if entry.input_kind == "missing" else "not_passive_window"
            )
        elif (namespace, window.run_id, window.clock.domain_id) != (
            replay.stream.acquisition_namespace,
            replay.stream.run_id,
            replay.stream.clock_domain_id,
        ):
            clear(state)
            state["stream_invalidated"] = True
            reasons.append("clock_scope_changed")
        elif entry.representative_entry_id != entry.entry_id or key in seen:
            reasons.append("duplicate_window")
        else:
            seen.add(key)
            start, end, duration = bounds(window)
            previous = state["last_window_end_ms"]
            if end < state["watermark_ms"] or (previous is not None and end <= previous):
                reasons.append("out_of_order")
            elif stratum_id(scope(window)) != replay.stream.stratum_id:
                clear(state)
                state.update(watermark_ms=end, barrier_ms=end, stream_invalidated=True)
                reasons.append("scope_changed")
            elif (previous is not None and start < previous) or start < state["barrier_ms"]:
                reasons.append(
                    "overlapping_window"
                    if previous is not None and start < previous
                    else "pre_barrier_window"
                )
                clear(state)
                state.update(watermark_ms=end, last_window_end_ms=end, barrier_ms=end)
            else:
                if previous is not None and start > previous:
                    clear(state)
                    state["barrier_ms"] = start
                    reasons.append("gap_reset")
                state.update(watermark_ms=end, last_window_end_ms=end)
                blocking = []
                if entry.role != replay.mode:
                    blocking.append("not_requested_role")
                if set(entry.reason_codes) - {"label_unverified", "duplicate_evidence"}:
                    blocking.append("n6_excluded")
                if stratum is None or stratum.state != "provisional":
                    blocking.append("baseline_unavailable")
                sources, receipts = baseline.evidence.footprint({entry.group_id})
                if sources & training_sources or receipts & training_receipts:
                    blocking.append("source_overlap")
                blocking.extend(quality_reasons(window))
                if blocking:
                    clear(state)
                    state["barrier_ms"] = end
                    reasons.extend(blocking)
                else:
                    value = window.measurements[METRIC].summary.value
                    category = classify(value, stratum.center)
                    row.update(
                        classification=category,
                        observed_fps=value,
                        relative_fps=ratio(value, stratum.center),
                    )
                    action, reason = usable_transition(state, category, duration, end)
                    row["recommendation"] = action
                    reasons.append(reason)
        row["effect_hypothesis"] = "received_fps_degradation" if state["degraded_latched"] else None
        row["state"] = dict(state)
        rows.append(row)
    windows = [r for r, e in zip(rows, replay.events, strict=True) if e.kind == "window"]
    accepted = sum(r["classification"] != "unavailable" for r in windows)
    duplicates = sum(r["reason_codes"] == ["duplicate_window"] for r in windows)
    late = sum(r["reason_codes"] == ["out_of_order"] for r in windows)
    counts = dict(
        total_events=len(rows),
        window_events=len(windows),
        tick_events=sum(e.kind == "tick" for e in replay.events),
        reset_events=sum(e.kind == "reset" for e in replay.events),
        accepted_windows=accepted,
        ignored_duplicate_windows=duplicates,
        ignored_out_of_order_windows=late,
        unavailable_windows=len(windows) - accepted - duplicates - late,
        proposals=state["proposals"],
    )
    return rows, state, counts
