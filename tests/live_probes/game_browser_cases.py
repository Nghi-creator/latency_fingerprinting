"""Independent synthetic declarations; no native acquisition is inferred from these."""

import copy

from latency_fingerprinting.live_probes import import_game_browser_acquisition

S = 1000000000
META = dict(acquisition_id="synthetic-game-browser", producer_revision="a" * 40)
SOURCES = (
    "private_journal.py",
    "live_probe_control/controller.py",
    "live_probe_control/watchdog.py",
    "live_probe_control/game_scene.py",
    "live_probe_control/browser_game_worker.py",
    "live_probe_control/webrtc_worker.py",
    "live_probe_control/contracts.py",
    "live_probe_control/journal.py",
    "scripts/n10/gameBrowserTrial.mjs",
    "scripts/n10/gameBrowserReceiver.mjs",
)


def acquisition():
    times = []
    t = 0
    while t <= 8100000000:
        times.append(t)
        t += S // (24 if 4020000000 <= t < 7020000000 else 30)

    def count(t):
        return sum(v <= t for v in times)

    observations, windows, resources = [], {}, []
    for name, start, end, fps in (
        ("baseline", 3 * S, 4 * S, 30),
        ("during", 4600000000, 6900000000, 24),
        ("restoration", 7300000000, 8100000000, 30),
    ):
        endpoints = []
        for t in (start, (start + end) // 2, end):
            o = dict(
                at_ns=t,
                configured_fps=fps,
                negotiated_fps=fps,
                capture_buffers=count(t),
                receiver_frames=count(t),
                healthy=True,
                settings_hash="d" * 64,
            )
            observations.append(o)
            cpu = (
                0.3 * min(t, 4020000000)
                + 0.24 * min(max(t - 4020000000, 0), 3 * S)
                + 0.3 * max(t - 7020000000, 0)
            )
            resources.append(
                dict(
                    at_ns=t,
                    read_start_ns=t + 1,
                    read_end_ns=t + 10,
                    worker_cpu_ns=int(cpu),
                    game=dict(cpu_ticks=t // 25000000, rss_bytes=2000000),
                )
            )
            endpoints.append(o)
        windows[name] = dict(start=copy.deepcopy(endpoints[0]), end=copy.deepcopy(endpoints[-1]))
    stats = []
    for t in range(300000000, 8100000001, 200000000):
        n = count(t)
        stats.append(
            dict(
                type="stats",
                worker_at_ns=t,
                browser_at_ns=t + 2 * 10**12,
                values=dict(
                    framesReceived=n,
                    framesDecoded=n,
                    framesDropped=0,
                    freezeCount=0,
                    totalFreezesDuration=0,
                    totalDecodeTime=n * 0.001,
                    jitterBufferDelay=n * 0.005,
                    jitterBufferEmittedCount=n,
                    frameWidth=640,
                    frameHeight=480,
                    keyFramesDecoded=n // 30,
                    packetsLost=0,
                    bytesReceived=n * 1000,
                ),
            )
        )
    return dict(
        version="n10-game-browser-acquisition-v1",
        mode="changed",
        image_hash="sha256:" + "b" * 64,
        live_authority=False,
        browser_clock_basis="browser_performance_relative_ns",
        worker_clock_basis="worker_monotonic_relative_ns",
        host_clock_basis="harness_monotonic_relative_ns",
        clock_alignment="none",
        browser_version="151.0.0.1",
        browser_resources=[
            dict(
                host_at_ns=i * 4 * S,
                cpu_seconds=0.2 + i * 0.8,
                process_count=4,
                inventory_hash="f" * 64,
            )
            for i in range(3)
        ],
        source_hashes={name: "e" * 64 for name in SOURCES},
        receiver_screenshot_hash=None,
        container_cleanup="removed_or_already_removed",
        worker_exit_code=0,
        failure=None,
        stderr_bytes=0,
        bounded_stderr_hash="sha256:" + "c" * 64,
        report=dict(
            trial_version="n10-isolated-game-browser-v1",
            mode="changed",
            live_authority=False,
            workload="frozen_bubble_level_1_scripted_arrows",
            dimensions=[640, 480],
            receiver_scope="dedicated_headless_chromium_video",
            perceptual_quality="not_evaluated",
            diagnostic_value="unverified",
            status="observed",
            teardown="null_observed",
            scene_cleanup="reaped",
            protocol=dict(
                prior_fps=30,
                target_fps=24,
                duration_ns=3 * S,
                settling_ns=500000000,
                maximum_pts_gap_ns=250000000,
                maximum_worker_pull_gap_ns=500000000,
                rate_tolerance_percent=10,
                maximum_game_inputs=64,
                maximum_browser_frames_dropped=0,
                maximum_browser_freeze_count=0,
                minimum_visual_color_bins=4,
                warmup_ns=3 * S,
                baseline_measure_ns=S,
                restoration_measure_ns=750000000,
                restoration_settling_ns=200000000,
                visual_sample_period_ns=500000000,
                browser_stats_period_ns=200000000,
            ),
            generation=dict(owner="owner-1", pipeline="pipeline-1", peer="peer-1"),
            result=dict(
                request_id="game-browser",
                outcome="completed",
                reason="duration_elapsed",
                restoration="verified_by_port",
                live_authority=False,
            ),
            journal_state="clean",
            receipts=[
                dict(requested_fps=24, before_ns=4010000000, after_ns=4011000000),
                dict(requested_fps=30, before_ns=7010000000, after_ns=7011000000),
            ],
            observations=observations,
            windows=windows,
            resource_samples=resources,
            resource_clock_ticks_per_second=100,
            game_inputs=10,
            browser_stats=stats,
            receiver_timeline=[
                dict(
                    type="frame",
                    pts_ns=t + 20000000,
                    worker_at_ns=t,
                    browser_at_ns=t + 2 * 10**12,
                    presented_frames=i + 2,
                    width=640,
                    height=480,
                )
                for i, t in enumerate(times)
            ],
            visual_samples=[
                dict(
                    type="visual",
                    worker_at_ns=t,
                    browser_at_ns=t + 2 * 10**12,
                    hash=i,
                    color_bins=1 if t < 3 * S else 32,
                )
                for i, t in enumerate(range(500000000, 8100000001, 500000000))
            ],
            assessment=dict(
                status="met",
                checks={
                    name: True
                    for name in (
                        "baseline_capture_buffers",
                        "baseline_receiver_frames",
                        "during_capture_buffers",
                        "during_receiver_frames",
                        "restoration_capture_buffers",
                        "restoration_receiver_frames",
                        "presentation_continuity",
                        "nonblank_moving_scene",
                    )
                },
            ),
        ),
    )


def evidence():
    return import_game_browser_acquisition(acquisition(), **META)
