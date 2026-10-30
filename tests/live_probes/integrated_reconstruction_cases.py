"""Invented arithmetic examples, not native acquisitions or qualification evidence."""

from latency_fingerprinting.live_probes.integrated_game import MODES

CONTROL = "n10-contained-game-control-disturbance-v1"
FAILURE = "n10-contained-game-failure-v1"
PHASES = ("baseline", "during", "restored")


def event(kind, **body):
    return dict(kind=kind, **body)


def request(duration):
    return dict(
        request_id="request-1",
        generation=dict(owner="owner", pipeline="pipeline", peer="peer"),
        target_fps=24,
        duration_ns=duration,
    )


def finish():
    return [
        event("complete", live_authority=False, worker_cleanup=True, game_alive=True),
        *[
            event("host_shutdown", stage=stage)
            for stage in (
                "camera_loop_returned",
                "disconnect_thread_joined",
                "socket_closed",
                "scene_close_start",
                "scene_closed",
                "scope_closed",
            )
        ],
        event("camera_process_exit", code=0, signal=None),
        event("relay_shutdown", stage="close_start"),
        event("relay_shutdown", stage="closed"),
    ]


def base(index):
    mode = MODES[index]
    return dict(
        status="passed",
        mode=mode,
        live_authority=False,
        context=dict(
            image="sha256:" + "a" * 64,
            software_hash="b" * 64,
            host_platform="synthetic",
            host_arch="synthetic",
        ),
        browser="synthetic-1",
        events=[
            event(
                "camera_ready",
                mode=mode,
                source="isolated_game",
                profile=dict(id="balanced", fps=30, bitrate_kbps=1500),
            ),
            event(
                "control_capture_bound",
                method=CONTROL if index == 0 else FAILURE,
                scope="owned_x99_game_display",
                binding_hash="c" * 64,
                live_authority=False,
            ),
        ],
    )


def trace(peer):
    frames, groups, count = [], [], 100
    for index in range(3):
        fps = 24 if index == 1 and peer == 0 else 30
        group = []
        for i in range(fps * 4 + (1 if index == 2 else 0)):
            t = index * 4000 + i * 1000 / fps
            f = dict(at_ms=t, pts_ms=5000 + t, presented=count, width=640, height=480)
            frames.append(f)
            if i <= fps * 2:
                group.append({**f, "at_ms": i * 1000 / fps})
            count += 1
        groups.append(group)
    return dict(
        basis="browser_performance_relative_ms", duration_ms=12000, frames=frames, failure=None
    ), groups


def quality(frames, fps):
    start = frames[0]["presented"]
    return dict(
        basis="browser_performance_relative_ms",
        duration_ms=2000,
        frames=frames,
        stats=[
            dict(
                at_ms=t,
                decoded=start + int(fps * t / 1000),
                dropped=0,
                freezes=0,
                width=640,
                height=480,
            )
            for t in range(0, 2001, 200)
        ],
        visuals=[
            dict(at_ms=t, hash=10 + i, color_bins=10) for i, t in enumerate(range(0, 2001, 500))
        ],
        failure=None,
        connection_state="connected",
    )


def native(index):
    samples = []
    for i in range(11):
        start = 10**9 + index * 4 * 10**9 + i * 250000000
        workers = {}
        for peer in ("first", "second"):
            fps = 24 if index == 1 and peer == "first" else 30
            workers[peer] = dict(
                cpu_ticks=index * 100 + i * 2,
                rss_bytes=1024,
                capture_buffers=index * 500 + int(i * fps / 4),
                encoded_buffers=index * 500 + int(i * fps / 4),
                settings=dict(
                    configured_fps=fps,
                    negotiated_fps=fps,
                    width=640,
                    height=480,
                    target_bitrate=1500000,
                    cpu_used=6,
                    max_quantizer=48,
                ),
            )
        actor = dict(cpu_ticks=index * 100 + i * 2, rss_bytes=2048)
        samples.append(
            dict(
                read_start_ns=start,
                read_end_ns=start + 1000,
                workers=workers,
                parent=actor.copy(),
                relay=actor.copy(),
                game=actor.copy(),
                game_phase=dict(
                    game_age_ns=start, script_age_ns=start, script_actions=index * 100 + i
                ),
            )
        )
    return event(
        "control_native",
        phase=PHASES[index],
        method=CONTROL,
        worker_identities=dict(first="d" * 64, second="e" * 64),
        basis="linux_monotonic_brackets_exact_owned_process_ticks",
        ticks_per_second=100,
        samples=samples,
    )


def browser_resources(index):
    return dict(
        basis="host_hrtime_browser_owned_process_cpu_separate_clock",
        before=dict(
            host_at_ns=index * 4 * 10**9,
            cpu_seconds=index,
            process_count=2,
            inventory_hash="f" * 64,
        ),
        after=dict(
            host_at_ns=index * 4 * 10**9 + 2 * 10**9,
            cpu_seconds=index + 0.5,
            process_count=2,
            inventory_hash="f" * 64,
        ),
    )


def control():
    run = base(0)
    run.update(method=CONTROL, role="contained_game_control_disturbance_not_qualification")
    traces = [trace(peer) for peer in (0, 1)]
    run["continuity"] = [t[0] for t in traces]
    run["control_windows"] = []
    for index, phase in enumerate(PHASES):
        if index == 1:
            run["events"].append(
                event(
                    "control_dispatched",
                    method=CONTROL,
                    request=request(5000000000),
                    live_authority=False,
                )
            )
        if index == 2:
            run["events"].append(
                event(
                    "control_result",
                    method=CONTROL,
                    ledger_state="clean",
                    actions=1,
                    reserved_ns=7000000000,
                    result=dict(
                        request_id="request-1",
                        outcome="completed",
                        reason="duration_elapsed",
                        restoration="verified_by_port",
                        live_authority=False,
                    ),
                )
            )
        run["events"].extend(
            [event("control_window_started", phase=phase, method=CONTROL), native(index)]
        )
        run["control_windows"].append(
            dict(
                phase=phase,
                quality=[
                    quality(t[1][index], 24 if index == 1 and peer == 0 else 30)
                    for peer, t in enumerate(traces)
                ],
                browser_resources=browser_resources(index),
            )
        )
    run["events"].extend(finish())
    run["viewers"] = [
        dict(failures=0, epochs=[peer], unbound=1, bindings=1) for peer in ("first", "second")
    ]
    return run


def failure(index):
    run = base(index)
    case = MODES[index].removeprefix("engineering-game-")
    run.update(method=FAILURE, role="contained_game_failure_not_qualification", case=case)
    scoped = dict(method=FAILURE, case=case)
    clean = case == "cancel"
    run["events"].append(
        event(
            "game_failure_dispatched", **scoped, request=request(2000000000), live_authority=False
        )
    )
    if case == "reconnect":
        run["events"].append(event("game_failure_reconnect", **scoped))
    run["events"].append(event("game_failure_fault", **scoped, target_observed=True))
    if case == "source-loss":
        run["events"].append(event("game_failure_source_restored", **scoped))
    ledger = dict(ledger_state="clean" if clean else "dirty", actions=1, reserved_ns=4000000000)
    run["events"].append(
        event(
            "game_failure_result",
            **scoped,
            **ledger,
            result=dict(
                request_id="request-1",
                outcome="aborted",
                reason="cancelled" if clean or case == "reconnect" else "health_abort",
                restoration="verified_by_port" if clean else "unknown",
                live_authority=False,
            ),
        )
    )
    if clean:
        run["events"].append(event("game_failure_reconnect", **scoped))
    run["events"].append(
        event(
            "game_failure_verified",
            **scoped,
            **ledger,
            old_exit=0 if clean else -9,
            old_reaped=True,
            stale_handles_rejected=True,
            owner_restarted=True,
            old_owner_rejected=True,
            dirty_blocked=not clean,
            clean_draft_allowed=clean,
            source_restored=case == "source-loss",
            game_progress=True,
            sibling_progress=True,
            sibling_identity_retained=True,
            live_authority=False,
        )
    )
    run["events"].extend(finish())
    run["viewers"] = [
        dict(
            failures=1 if case in ("receiver-loss", "source-loss") else 0,
            epochs=["first", "replacement"],
            unbound=1,
            bindings=3,
        ),
        dict(failures=0, epochs=["second"], unbound=1, bindings=2),
    ]
    run["sibling_quality"] = quality(trace(1)[1][0], 30)
    return run


def cohort():
    return [control(), *[failure(index) for index in range(1, 5)]]
