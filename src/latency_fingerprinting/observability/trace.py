"""Strict additive stage trace record; no runtime instrumentation."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .contracts import (
    ALIAS_MAX,
    MAX_EVENTS,
    MAX_FRAMES,
    Commit,
    Count,
    EventBoundary,
    FrameID,
    Positive,
    Producer,
    Provenance,
    Release,
    RunID,
    SessionID,
    StreamScope,
    TraceID,
    TraceModel,
    Version,
    allowed,
    capability_boundary,
    check_scopes,
    check_support,
    ordered,
)


class Limits(TraceModel):
    max_frames: Annotated[int, Field(strict=True, ge=1, le=MAX_FRAMES)]
    max_events: Annotated[int, Field(strict=True, ge=1, le=MAX_EVENTS)]


class Deadline(TraceModel):
    method_id: Literal["capture-output-budget"]
    method_version: Version
    budget_ns: Positive


class Frame(TraceModel):
    frame_id: FrameID
    source_sequence: Annotated[int, Field(strict=True, ge=1, le=ALIAS_MAX)]
    correlation: Literal["exact", "missing", "ambiguous"]

    @model_validator(mode="after")
    def identity(self):
        if self.frame_id != f"frame-{self.source_sequence}":
            raise ValueError("frame alias does not match source sequence")
        return self


class Event(TraceModel):
    sequence: Positive
    frame_id: FrameID
    boundary: EventBoundary
    timestamp_ns: Count


class TraceStream(StreamScope):
    limits: Limits
    deadline: Deadline | None
    frames: Annotated[tuple[Frame, ...], Field(max_length=MAX_FRAMES)]
    events: Annotated[tuple[Event, ...], Field(max_length=MAX_EVENTS)]
    stop_reason: Literal["completed", "disabled", "capacity", "shutdown", "source_error"]

    @model_validator(mode="after")
    def consistency(self):
        if len(self.frames) > self.limits.max_frames or len(self.events) > self.limits.max_events:
            raise ValueError("collection exceeds declared capacity")
        if self.loss.sampled_frames != len(self.frames) or self.loss.retained_events != len(
            self.events
        ):
            raise ValueError("ledger/event counts disagree")
        ordered(self.frames, lambda f: f.source_sequence)
        ordered(self.events, lambda e: e.sequence)
        n = self.sampling.every_nth_frame
        # Earliest eligible frames are retained; capacity never creates a rolling ledger.
        for index, frame in enumerate(self.frames):
            if (
                frame.source_sequence != 1 + index * n
                or frame.source_sequence > self.loss.offered_frames
            ):
                raise ValueError("frame ledger violates prefix sampling")
        frames = {f.frame_id: f for f in self.frames}
        supported = {c.boundary for c in self.capabilities if c.state == "supported"}
        seen = set()
        for event in self.events:
            if event.sequence > self.loss.attempted_events or event.frame_id not in frames:
                raise ValueError("event sequence/reference is outside ledger")
            key = (event.frame_id, event.boundary)
            if key in seen:
                raise ValueError("duplicate frame endpoint")
            seen.add(key)
            if capability_boundary(event.boundary) not in supported:
                raise ValueError("event has no supported capability")
            if frames[event.frame_id].correlation != "exact" and event.boundary != "capture_output":
                raise ValueError("uncorrelated frame has downstream events")
        if self.stop_reason == "disabled" and (
            any(self.loss.model_dump().values())
            or any(c.reason != "disabled" for c in self.capabilities)
        ):
            raise ValueError("disabled streams cannot contain evidence")
        return self


class StageTraceRecord(TraceModel):
    schema_version: Literal["stage-trace-record-v1"]
    method_release: Release
    trace_id: TraceID
    session_id: SessionID
    run_id: RunID
    provenance: Provenance
    producer: Producer
    producer_version: Commit
    streams: Annotated[tuple[TraceStream, ...], Field(min_length=1, max_length=16)]

    @model_validator(mode="before")
    @classmethod
    def total_containers(cls, value):
        if isinstance(value, dict):
            streams = value.get("streams")
            if isinstance(streams, (list, tuple)):
                if len(streams) > 16:
                    raise ValueError("trace exceeds lifetime limit")
                for key, maximum in (("frames", MAX_FRAMES), ("events", MAX_EVENTS)):
                    total = 0
                    for stream in streams:
                        items = (
                            stream.get(key, ())
                            if isinstance(stream, dict)
                            else getattr(stream, key, ())
                        )
                        if isinstance(items, (list, tuple)):
                            total += len(items)
                    if total > maximum:
                        raise ValueError("trace exceeds total frame/event limit")
        return value

    @model_validator(mode="after")
    def scopes(self):
        check_scopes(self.streams)
        if (
            sum(len(s.frames) for s in self.streams) > MAX_FRAMES
            or sum(len(s.events) for s in self.streams) > MAX_EVENTS
        ):
            raise ValueError("trace exceeds total frame/event limit")
        for stream in self.streams:
            check_support(stream, self.producer)
            origin = (
                "capture_output" if self.producer == "pixelated_engine" else "presentation_proxy"
            )
            if stream.frames and not any(
                c.boundary == origin and c.state == "supported" for c in stream.capabilities
            ):
                raise ValueError("frames require a supported source boundary")
            if any(e.boundary not in allowed(self.producer) for e in stream.events):
                raise ValueError("producer cannot supply event boundary")
            if self.producer == "pixelated_browser" and (
                stream.deadline is not None or any(f.correlation != "exact" for f in stream.frames)
            ):
                raise ValueError("browser cannot declare host budget/correlation")
        return self
