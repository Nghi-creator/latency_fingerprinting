"""Small synthetic cadence declaration with independently countable observations."""

import copy

from latency_fingerprinting.live_probes import import_cadence_worker_report

META = dict(
    acquisition_id="synthetic-cadence",
    producer_revision="a" * 40,
    image_hash="sha256:" + "b" * 64,
    source_manifest_hash="sha256:" + "c" * 64,
)


def report():
    def observation(t, fps, count):
        return dict(
            at_ns=t,
            configured_fps=fps,
            negotiated_fps=fps,
            capture_buffers=count,
            receiver_frames=count,
            healthy=True,
            settings_hash="d" * 64,
        )

    # Enumerate each synthetic received frame at independent exact cadence steps.
    times = list(range(0, 1000000001, 33333333))
    times += list(range(1300000000, 3300000001, 41666666))
    times += list(range(3600000000, 4600000001, 33333333))
    # Include transition frames to keep the predeclared <=250ms PTS gap bound.
    times += [1100000000, 1200000000, 3400000000, 3500000000]
    times = sorted(t for t in times if t <= 4500000000)
    timeline = [dict(pts_ns=t, observed_at_ns=t) for t in times]
    obs = []
    for start, end, fps in (
        (100000000, 900000000, 30),
        (1800000000, 3100000000, 24),
        (3800000000, 4500000000, 30),
    ):
        for t in (start, end):
            obs.append(observation(t, fps, sum(f["observed_at_ns"] <= t for f in timeline)))
    return dict(
        trial_version="n10-isolated-webrtc-controller-v1",
        live_authority=False,
        scope="disposable_synthetic_gst_webrtc_pair",
        quality="not_evaluated",
        resource_cost="not_evaluated",
        diagnostic_value="unverified",
        receiver_scope="gst_loopback_not_browser",
        clock_basis="process_monotonic_relative_ns",
        pts_basis="receiver_pipeline_pts_not_source_or_browser_aligned",
        status="observed",
        teardown="null_observed",
        generation=dict(owner="owner-1", pipeline="pipeline-1", peer="peer-1"),
        receipts=[
            dict(requested_fps=24, before_ns=1050000000, after_ns=1060000000),
            dict(requested_fps=30, before_ns=3350000000, after_ns=3360000000),
        ],
        observations=obs,
        receiver_timeline=timeline,
        windows={
            p: dict(start=copy.deepcopy(obs[2 * i]), end=copy.deepcopy(obs[2 * i + 1]))
            for i, p in enumerate(("baseline", "during", "restoration"))
        },
        result=dict(
            request_id="isolated",
            outcome="completed",
            restoration="verified_by_port",
            reason="duration_elapsed",
            live_authority=False,
        ),
        journal_state="clean",
        protocol=dict(
            baseline_fps=30,
            target_fps=24,
            requested_duration_ns=3000000000,
            settling_ns=500000000,
            maximum_pts_gap_ns=250000000,
            maximum_pull_gap_ns=500000000,
            rate_tolerance_percent=10,
        ),
        assessment=dict(
            status="met",
            checks={
                key: True
                for key in (
                    "baseline_capture_buffers",
                    "baseline_receiver_frames",
                    "during_capture_buffers",
                    "during_receiver_frames",
                    "restoration_capture_buffers",
                    "restoration_receiver_frames",
                    "receiver_continuity",
                )
            },
        ),
    )


def evidence():
    return import_cadence_worker_report(report(), **META)
