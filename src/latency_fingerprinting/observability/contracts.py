"""Closed vocabulary and strict primitives for N4, independent of N2/N3."""

from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

SAFE_MAX = 2**53 - 1
ALIAS_MAX = 2**31 - 1
MAX_FRAMES = 2000
MAX_EVENTS = 10000
BOUNDARIES = (
    "render_ready",
    "capture_begin",
    "capture_output",
    "pre_encode_queue_enter",
    "pre_encode_queue_exit",
    "encode_input",
    "encode_output",
    "wire_send",
    "receive",
    "decode_ready",
    "presentation_proxy",
)
ENGINE_EVENTS = BOUNDARIES[2:7]
BROWSER_EVENTS = ("presentation_proxy", "presentation_callback")
METHODS = (
    "pre-encode-queue-sojourn",
    "encode-boundary-elapsed",
    "capture-output-age-at-encode-output",
    "presentation-callback-lag",
)
PAIRS = (
    (BOUNDARIES[3], BOUNDARIES[4]),
    (BOUNDARIES[5], BOUNDARIES[6]),
    (BOUNDARIES[2], BOUNDARIES[6]),
    BROWSER_EVENTS,
)
Producer = Literal["pixelated_engine", "pixelated_browser"]
Provenance = Literal["producer_capture", "synthetic"]
Release = Literal["n4-stage-local-v1"]
Boundary = Literal[*BOUNDARIES]
EventBoundary = Literal[*ENGINE_EVENTS, *BROWSER_EVENTS]
Method = Literal[*METHODS]
Count = Annotated[int, Field(strict=True, ge=0, le=SAFE_MAX)]
Positive = Annotated[int, Field(strict=True, ge=1, le=SAFE_MAX)]
Float = Annotated[float, Field(strict=True, allow_inf_nan=False)]
NonnegativeFloat = Annotated[Float, Field(ge=0)]
Commit = Annotated[str, Field(strict=True, pattern=r"^[0-9a-f]{40}$")]
Hash = Annotated[str, Field(strict=True, pattern=r"^[0-9a-f]{64}$")]


def strict_version(value):
    if type(value) is not int:
        raise ValueError("method version must be a strict integer")
    return value


Version = Annotated[Literal[1], BeforeValidator(strict_version)]


def alias_number(value):
    return int(value.rsplit("-", 1)[1])


def bounded_alias(value):
    if alias_number(value) > ALIAS_MAX:
        raise ValueError("alias suffix exceeds its bound")
    return value


def alias(prefix):
    return Annotated[
        str,
        Field(strict=True, pattern=rf"^{prefix}-[1-9][0-9]{{0,9}}$"),
        AfterValidator(bounded_alias),
    ]


TraceID, SessionID, RunID = alias("trace"), alias("session"), alias("run")
StreamID, EpochID, ClockID, FrameID = (
    alias("stream"),
    alias("epoch"),
    alias("clock"),
    alias("frame"),
)


class TraceModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always", validate_default=True
    )

    @classmethod
    def model_validate_json(cls, json_data, **kwargs):
        from .json import decode_trace_json

        return cls.model_validate(decode_trace_json(json_data), **kwargs)

    @field_validator("*", mode="after")
    @classmethod
    def normalize_zero(cls, value):
        return 0.0 if isinstance(value, float) and value == 0 else value

    @field_validator("*", mode="before")
    @classmethod
    def bound_containers(cls, value, info):
        caps = {
            "streams": 16,
            "frames": MAX_FRAMES,
            "events": MAX_EVENTS,
            "samples": MAX_FRAMES,
            "results": 4,
            "capabilities": 11,
        }
        if info.field_name in caps and not isinstance(value, (list, tuple)):
            raise ValueError("contract collections must be lists or tuples")
        if (
            info.field_name in caps
            and isinstance(value, (list, tuple))
            and len(value) > caps[info.field_name]
        ):
            raise ValueError("container exceeds trace limit")
        return value


def ordered(items, key):
    values = [key(item) for item in items]
    if any(a >= b for a, b in zip(values, values[1:], strict=False)):
        raise ValueError("identities/sequences must be strictly increasing")


def check_scopes(streams):
    ordered(streams, lambda s: alias_number(s.stream_id))
    for field in ("epoch_id", "clock_id"):
        values = [getattr(s, field) for s in streams]
        if len(set(values)) != len(values):
            raise ValueError("lifetimes cannot share epoch or clock aliases")


def allowed(producer):
    return ENGINE_EVENTS if producer == "pixelated_engine" else BROWSER_EVENTS


def capability_boundary(boundary):
    return "presentation_proxy" if boundary == "presentation_callback" else boundary


def check_support(stream, producer):
    expected = "python_monotonic_ns" if producer == "pixelated_engine" else "browser_performance"
    if stream.clock.source != expected:
        raise ValueError("clock source does not match producer")
    for cap in stream.capabilities:
        if cap.boundary not in allowed(producer) and (
            cap.state != "unavailable" or cap.reason not in ("unsupported_source", "disabled")
        ):
            raise ValueError("unsupported producer boundary")
    if producer == "pixelated_engine" and stream.loss.browser_missed_presentations:
        raise ValueError("engine cannot report missed browser presentations")


class Clock(TraceModel):
    source: Literal["python_monotonic_ns", "browser_performance"]
    unit: Literal["ns"]
    origin: Literal["stream_start"]
    resolution_ns: Positive | None
    synchronization: Literal["none"]


class Sampling(TraceModel):
    every_nth_frame: Annotated[int, Field(strict=True, ge=1, le=1000)]


class Capability(TraceModel):
    boundary: Boundary
    state: Literal["supported", "unavailable"]
    reason: (
        Literal[
            "not_instrumented",
            "unsupported_source",
            "api_unavailable",
            "disabled",
            "source_unavailable",
        ]
        | None
    )

    @model_validator(mode="after")
    def consistency(self):
        if (self.state == "supported") != (self.reason is None):
            raise ValueError("capability state/reason disagree")
        return self


Capabilities = Annotated[tuple[Capability, ...], Field(min_length=11, max_length=11)]


class Loss(TraceModel):
    offered_frames: Count
    sampled_frames: Count
    unsampled_frames: Count
    frame_capacity_dropped: Count
    attempted_events: Count
    retained_events: Count
    event_capacity_dropped: Count
    event_invalid_timestamp_dropped: Count
    event_contention_dropped: Count
    event_shutdown_dropped: Count
    event_correlation_dropped: Count
    browser_missed_presentations: Count

    @model_validator(mode="after")
    def accounting(self):
        if (
            self.offered_frames
            != self.sampled_frames + self.unsampled_frames + self.frame_capacity_dropped
        ):
            raise ValueError("frame loss does not conserve counts")
        drops = sum(getattr(self, f) for f in type(self).model_fields if f.startswith("event_"))
        if self.attempted_events != self.retained_events + drops:
            raise ValueError("event loss does not conserve counts")
        return self


class StreamScope(TraceModel):
    stream_id: StreamID
    epoch_id: EpochID
    clock_id: ClockID
    clock: Clock
    capabilities: Capabilities
    sampling: Sampling
    loss: Loss

    @model_validator(mode="after")
    def declarations(self):
        if tuple(c.boundary for c in self.capabilities) != BOUNDARIES:
            raise ValueError("capabilities must follow complete boundary order")
        n = self.sampling.every_nth_frame
        eligible = (self.loss.offered_frames + n - 1) // n
        if self.loss.sampled_frames + self.loss.frame_capacity_dropped != eligible:
            raise ValueError("sampling accounting is inconsistent")
        return self
