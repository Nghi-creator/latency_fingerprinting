"""Actual contiguous frame/owned-worker counters in the runner clock."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from ..observability.contracts import ClockID, Count, Hash, RunID
from .contracts import SECOND, ExperimentModel, Phase, Release, Workers, ordered_times


class Interval(ExperimentModel):
    start_ns: Count
    end_ns: Count
    frames_start: Count
    frames_end: Count
    active_workers: Workers
    worker_cpu_ns: Count

    @model_validator(mode="after")
    def consistency(self):
        duration = self.end_ns - self.start_ns
        if not SECOND // 2 <= duration <= 5 * SECOND:
            raise ValueError("interval duration must be 0.5–5 seconds")
        if self.frames_end < self.frames_start:
            raise ValueError("frame counter regressed")
        if self.worker_cpu_ns > duration * self.active_workers:
            raise ValueError("worker CPU exceeds owned-worker capacity")
        return self


class ExperimentPhaseEvidence(ExperimentModel):
    schema_version: Literal["experiment-phase-evidence-v1"]
    method_release: Release
    manifest_sha256: Hash
    run_id: RunID
    phase: Phase
    clock_id: ClockID
    start_ns: Count
    end_ns: Count
    state: Literal["complete", "partial", "unavailable"]
    reason: (
        Literal[
            "source_unavailable",
            "counter_reset",
            "clock_error",
            "collection_gap",
            "cancelled",
            "timeout",
        ]
        | None
    )
    intervals: Annotated[tuple[Interval, ...], Field(max_length=1200)]

    @model_validator(mode="after")
    def consistency(self):
        ordered_times(self.start_ns, self.end_ns)
        if (self.state == "complete") != (self.reason is None):
            raise ValueError("evidence state/reason disagree")
        if self.state == "unavailable" and self.intervals:
            raise ValueError("unavailable evidence cannot contain intervals")
        if self.state == "complete" and (not self.intervals or self.end_ns == self.start_ns):
            raise ValueError("complete evidence requires positive full coverage")
        cursor = self.start_ns
        previous_frames = None
        for interval in self.intervals:
            if interval.start_ns != cursor or interval.end_ns > self.end_ns:
                raise ValueError("intervals must cover a contiguous bounded prefix")
            if previous_frames is not None and interval.frames_start != previous_frames:
                raise ValueError("adjacent frame counters disagree")
            cursor, previous_frames = interval.end_ns, interval.frames_end
        if self.state == "complete" and cursor != self.end_ns:
            raise ValueError("complete evidence must cover the entire phase")
        return self
