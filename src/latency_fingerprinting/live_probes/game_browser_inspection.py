"""Independent engineering reconstruction; no live execution or qualification."""

from typing import Annotated, Literal

from pydantic import Field, StrictBool

from ..calibration.contracts import Hash
from .cadence import SECOND
from .game_browser import (
    BrowserCounters,
    GameBrowserChecks,
    GameBrowserModel,
    GameBrowserProbeEvidence,
)
from .models import Time

Percent = Annotated[float, Field(strict=True, allow_inf_nan=False, ge=0)]
COUNTERS = (
    "framesReceived",
    "framesDecoded",
    "framesDropped",
    "freezeCount",
    "totalFreezesDuration",
    "totalDecodeTime",
    "jitterBufferDelay",
    "jitterBufferEmittedCount",
    "keyFramesDecoded",
    "packetsLost",
    "bytesReceived",
)
REQUIRED_SOURCES = {
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
}


class GamePhaseInspection(GameBrowserModel):
    phase: Literal["baseline", "during", "restoration"]
    state: Literal["met", "not_met", "incomplete"]
    source_rate_met: StrictBool
    presentation_rate_met: StrictBool
    health_supported: StrictBool
    browser_progress_supported: StrictBool
    browser_counter_interval_start_ns: Time | None
    browser_counter_interval_end_ns: Time | None
    browser_counter_deltas: BrowserCounters | None
    worker_cpu_percent: Percent | None
    game_cpu_percent: Percent | None
    peak_game_rss_bytes: Time | None
    resource_state: Literal["observed", "missing", "counter_reset"]


class GameBrowserInspection(GameBrowserModel):
    evidence_hash: Hash
    phases: tuple[GamePhaseInspection, ...] = Field(max_length=3)
    checks: GameBrowserChecks
    presentation_counts_consistent: StrictBool
    unrelated_settings_stable: StrictBool
    workload_context_declared: StrictBool
    producer_assessment_matches: StrictBool
    controller_outcome_consistent: StrictBool
    browser_counters_consistent: StrictBool
    engineering_screen: Literal["met", "not_met", "incomplete"]
    declared_restoration_supported: StrictBool
    browser_cpu_percent: Percent | None
    browser_cpu_state: Literal["observed", "missing_or_changed_inventory", "counter_reset"]
    worker_during_to_baseline_cpu_ratio: Percent | None
    receiver_scope: Literal["dedicated_headless_chromium_video"]
    quality_scope: Literal["temporal_and_nonblank_samples_only"]
    resource_scope: Literal["worker_and_game_linux_cpu_separate_owned_browser_host_cpu"]
    clock_alignment: Literal["none"]
    perceptual_quality: Literal["not_evaluated"]
    diagnostic_value: Literal["unverified"]
    evidence_role: Literal["engineering"]
    capability: Literal["unavailable_unqualified"]
    live_authority: Literal[False]


def _monotonic(items, field):
    values = [getattr(item, field) for item in items]
    return all(
        a is not None and b is not None and a <= b for a, b in zip(values, values[1:], strict=False)
    )


def _deltas(stats):
    if len(stats) < 2:
        return None
    values = [s.values for s in stats]
    result = {}
    for field in BrowserCounters.model_fields:
        present = [getattr(v, field) for v in values]
        result[field] = (
            present[-1] - present[0]
            if all(v is not None for v in present) and _monotonic(values, field)
            else None
        )
    # Dimensions are settings, not accumulating counters.
    result["frameWidth"] = None
    result["frameHeight"] = None
    return BrowserCounters(**result)


def _resources(report, window):
    samples = [
        s for s in report.resource_samples if window.start.at_ns <= s.at_ns <= window.end.at_ns
    ]
    empty = dict(
        worker_cpu_percent=None,
        game_cpu_percent=None,
        peak_game_rss_bytes=None,
        resource_state="missing",
    )
    if (
        len(samples) < 2
        or samples[0].at_ns != window.start.at_ns
        or samples[-1].at_ns != window.end.at_ns
    ):
        return empty
    a, b = samples[0], samples[-1]
    wall = b.read_start_ns - a.read_start_ns
    if wall <= 0:
        return empty
    worker_ok = _monotonic(report.resource_samples, "worker_cpu_ns")
    game_ok = _monotonic([s.game for s in report.resource_samples], "cpu_ticks")
    hz = report.resource_clock_ticks_per_second
    return dict(
        worker_cpu_percent=100 * (b.worker_cpu_ns - a.worker_cpu_ns) / wall if worker_ok else None,
        game_cpu_percent=(
            100 * (b.game.cpu_ticks - a.game.cpu_ticks) * SECOND / (hz * wall)
            if game_ok and hz is not None
            else None
        ),
        peak_game_rss_bytes=max(s.game.rss_bytes for s in samples),
        resource_state="counter_reset"
        if not worker_ok or not game_ok
        else "observed"
        if hz is not None
        else "missing",
    )


def _healthy_stats(sample):
    return (
        sample.values.framesDropped == 0
        and sample.values.freezeCount == 0
        and sample.values.frameWidth == 640
        and sample.values.frameHeight == 480
    )


def _phase(report, name):
    target = 24 if name == "during" and report.mode != "sham" else 30
    window = getattr(report.windows, name)
    empty = dict(
        phase=name,
        state="incomplete",
        source_rate_met=False,
        presentation_rate_met=False,
        health_supported=False,
        browser_progress_supported=False,
        browser_counter_interval_start_ns=None,
        browser_counter_interval_end_ns=None,
        browser_counter_deltas=None,
        worker_cpu_percent=None,
        game_cpu_percent=None,
        peak_game_rss_bytes=None,
        resource_state="missing",
    )
    if window is None:
        return GamePhaseInspection(**empty)
    a, b = window.start, window.end
    wall = b.at_ns - a.at_ns
    observations = [o for o in report.observations if a.at_ns <= o.at_ns <= b.at_ns]
    for field, key in (
        ("capture_buffers", "source_rate_met"),
        ("receiver_frames", "presentation_rate_met"),
    ):
        delta = getattr(b, field) - getattr(a, field)
        empty[key] = _monotonic(observations, field) and (
            9 * target * wall <= 10 * delta * SECOND <= 11 * target * wall
        )
    stats_ordered = _monotonic(report.browser_stats, "worker_at_ns") and _monotonic(
        report.browser_stats, "browser_at_ns"
    )
    health = all(o.healthy and o.configured_fps == o.negotiated_fps == target for o in observations)
    for observation in observations:
        prior = [s for s in report.browser_stats if s.worker_at_ns <= observation.at_ns]
        health = (
            health
            and bool(prior)
            and (
                observation.at_ns - prior[-1].worker_at_ns <= 500000000
                and _healthy_stats(prior[-1])
            )
        )
    empty["health_supported"] = health and stats_ordered
    stats = [s for s in report.browser_stats if a.at_ns <= s.worker_at_ns <= b.at_ns]
    deltas = _deltas(stats)
    if deltas is not None:
        empty.update(
            browser_counter_deltas=deltas,
            browser_counter_interval_start_ns=stats[0].worker_at_ns,
            browser_counter_interval_end_ns=stats[-1].worker_at_ns,
        )
        empty["browser_progress_supported"] = (
            stats_ordered
            and all(_healthy_stats(s) for s in stats)
            and deltas.framesReceived is not None
            and deltas.framesReceived > 0
            and deltas.framesDecoded is not None
            and deltas.framesDecoded > 0
            and deltas.framesDropped == deltas.freezeCount == 0
            and all(
                getattr(deltas, field) is not None for field in ("framesReceived", "framesDecoded")
            )
        )
    empty.update(_resources(report, window))
    minimum = {
        "baseline": report.protocol.baseline_measure_ns,
        "restoration": report.protocol.restoration_measure_ns,
        "during": 2 * SECOND if report.mode in ("changed", "sham") else 1,
    }[name]
    empty["state"] = (
        "incomplete"
        if wall < minimum
        else "met"
        if all(
            empty[k]
            for k in (
                "source_rate_met",
                "presentation_rate_met",
                "health_supported",
                "browser_progress_supported",
            )
        )
        else "not_met"
    )
    return GamePhaseInspection(**empty)


def _browser_cpu(acquisition):
    samples = acquisition.browser_resources
    if (
        len(samples) < 2
        or acquisition.browser_resource_error is not None
        or (len({(s.inventory_hash, s.process_count) for s in samples}) != 1)
    ):
        return None, "missing_or_changed_inventory"
    wall = samples[-1].host_at_ns - samples[0].host_at_ns
    if (
        wall <= 0
        or not all(a.host_at_ns < b.host_at_ns for a, b in zip(samples, samples[1:], strict=False))
        or not _monotonic(samples, "cpu_seconds")
    ):
        return None, "counter_reset"
    return 100 * (samples[-1].cpu_seconds - samples[0].cpu_seconds) * SECOND / wall, "observed"


def inspect_game_browser_evidence(evidence):
    evidence = GameBrowserProbeEvidence.model_validate(evidence)
    acquisition = evidence.acquisition
    report = acquisition.report
    phases = (
        tuple(_phase(report, p) for p in ("baseline", "during", "restoration")) if report else ()
    )
    checks = {}
    for phase in ("baseline", "during", "restoration"):
        item = next((p for p in phases if p.phase == phase), None)
        for key, field in (
            ("capture_buffers", "source_rate_met"),
            ("receiver_frames", "presentation_rate_met"),
        ):
            checks[phase + "_" + key] = item is not None and getattr(item, field)
    frames = report.receiver_timeline if report else ()
    observations = report.observations if report else ()
    continuity = (
        len(frames) >= 2
        and bool(observations)
        and all(
            0 < b.pts_ns - a.pts_ns <= 250000000
            and 0 <= b.browser_at_ns - a.browser_at_ns <= 500000000
            and 0 <= b.worker_at_ns - a.worker_at_ns <= 500000000
            and b.presented_frames > a.presented_frames
            for a, b in zip(frames, frames[1:], strict=False)
        )
        and all(o.healthy for o in observations)
        and (0 <= observations[-1].at_ns - frames[-1].worker_at_ns <= 500000000)
    )
    checks["presentation_continuity"] = continuity
    windows = (
        [getattr(report.windows, p) for p in ("baseline", "during", "restoration")]
        if report
        else []
    )
    measured = (
        [
            s
            for s in report.visual_samples
            if any(
                w is not None and w.start.at_ns <= s.worker_at_ns <= w.end.at_ns for w in windows
            )
        ]
        if report
        else []
    )
    visuals_ordered = (
        report is not None
        and _monotonic(report.visual_samples, "worker_at_ns")
        and _monotonic(report.visual_samples, "browser_at_ns")
    )
    checks["nonblank_moving_scene"] = (
        visuals_ordered
        and len({s.hash for s in measured}) >= 3
        and all(s.color_bins >= 4 for s in measured)
        and all(
            any(w.start.at_ns <= s.worker_at_ns <= w.end.at_ns for s in measured)
            for w in windows
            if w is not None
        )
    )
    counts = (
        bool(observations)
        and _monotonic(observations, "capture_buffers")
        and _monotonic(observations, "receiver_frames")
        and all(
            o.receiver_frames == sum(f.worker_at_ns <= o.at_ns for f in frames)
            for o in observations
        )
    )
    stable = bool(observations) and len({o.settings_hash for o in observations}) == 1
    context = (
        report is not None
        and report.generation is not None
        and report.game_inputs is not None
        and report.game_inputs > 0
        and acquisition.browser_version is not None
        and REQUIRED_SOURCES.issubset({s.name for s in acquisition.source_hashes})
    )
    cleanup = (
        report is not None
        and report.status == "observed"
        and report.teardown == "null_observed"
        and report.scene_cleanup == "reaped"
        and acquisition.container_cleanup == "removed_or_already_removed"
        and acquisition.worker_exit_code == 0
        and acquisition.failure is None
    )
    outcome_consistent = False
    browser_counters_consistent = False
    if report is not None:
        browser_counters_consistent = (
            _monotonic(report.browser_stats, "worker_at_ns")
            and _monotonic(report.browser_stats, "browser_at_ns")
            and all(
                all(a <= b for a, b in zip(values, values[1:], strict=False))
                for values in (
                    [
                        getattr(s.values, field)
                        for s in report.browser_stats
                        if getattr(s.values, field) is not None
                    ]
                    for field in COUNTERS
                )
            )
        )
        outcome = report.result
        if report.mode == "sham":
            outcome_consistent = outcome is None and report.journal_state is None
        elif outcome is not None and report.mode in ("changed", "cancel"):
            expected = (
                ("completed", "duration_elapsed")
                if report.mode == "changed"
                else ("aborted", "cancelled")
            )
            outcome_consistent = (outcome.outcome, outcome.reason) == expected and (
                outcome.restoration == "verified_by_port" and report.journal_state == "clean"
            )
        elif outcome is not None:
            outcome_consistent = (
                outcome.outcome,
                outcome.reason,
                outcome.restoration,
                report.journal_state,
                acquisition.worker_exit_code,
            ) == ("aborted", "health_abort", "unknown", "dirty", 137)
    complete = len(phases) == 3 and all(p.state != "incomplete" for p in phases)
    met = (
        complete
        and all(p.state == "met" for p in phases)
        and all(checks.values())
        and counts
        and stable
        and context
        and cleanup
        and outcome_consistent
        and browser_counters_consistent
    )
    declared = report.assessment if report else None
    matches = (
        declared is not None
        and declared.checks.model_dump() == checks
        and declared.status == ("met" if all(checks.values()) else "not_met")
    )
    restored = (
        report is not None
        and report.mode != "sham"
        and report.result is not None
        and report.result.restoration == "verified_by_port"
        and report.journal_state == "clean"
        and len(phases) == 3
        and phases[2].state == "met"
        and continuity
        and counts
        and stable
        and context
        and browser_counters_consistent
        and any(
            report.windows.restoration.start.at_ns
            <= s.worker_at_ns
            <= report.windows.restoration.end.at_ns
            and s.color_bins >= 4
            for s in measured
        )
    )
    browser_cpu, browser_state = _browser_cpu(acquisition)
    baseline = phases[0].worker_cpu_percent if phases else None
    during = phases[1].worker_cpu_percent if phases else None
    return GameBrowserInspection(
        evidence_hash=evidence.content_hash,
        phases=phases,
        checks=GameBrowserChecks(**checks),
        presentation_counts_consistent=counts,
        unrelated_settings_stable=stable,
        workload_context_declared=context,
        producer_assessment_matches=matches,
        controller_outcome_consistent=outcome_consistent,
        browser_counters_consistent=browser_counters_consistent,
        engineering_screen="incomplete" if not complete else "met" if met else "not_met",
        declared_restoration_supported=restored,
        browser_cpu_percent=browser_cpu,
        browser_cpu_state=browser_state,
        worker_during_to_baseline_cpu_ratio=during / baseline
        if baseline is not None and baseline > 0 and during is not None
        else None,
        receiver_scope="dedicated_headless_chromium_video",
        quality_scope="temporal_and_nonblank_samples_only",
        resource_scope="worker_and_game_linux_cpu_separate_owned_browser_host_cpu",
        clock_alignment="none",
        perceptual_quality="not_evaluated",
        diagnostic_value="unverified",
        evidence_role="engineering",
        capability="unavailable_unqualified",
        live_authority=False,
    )
