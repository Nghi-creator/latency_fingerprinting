"""Internally reconstructable summaries; a summary alone does not prove its trace."""

from typing import Annotated, Literal

from pydantic import Field, StrictBool, model_validator

from .contracts import (
    MAX_EVENTS,
    MAX_FRAMES,
    METHODS,
    PAIRS,
    Commit,
    Count,
    Float,
    FrameID,
    Hash,
    Method,
    NonnegativeFloat,
    Positive,
    Producer,
    Provenance,
    Release,
    StreamScope,
    TraceModel,
    Version,
    alias_number,
    capability_boundary,
    check_scopes,
    check_support,
    ordered,
)


class Exclusions(TraceModel):
    unsupported: Count
    correlation_missing: Count
    correlation_ambiguous: Count
    missing_endpoint: Count
    negative_duration: Count


class DurationSample(TraceModel):
    frame_id: FrameID
    delta_ns: Count
    value_ms: NonnegativeFloat

    @model_validator(mode="after")
    def arithmetic(self):
        if self.value_ms != self.delta_ns / 1000000:
            raise ValueError("sample value differs from integer delta")
        return self


class TimingResult(TraceModel):
    method_id: Method
    method_version: Version
    state: Literal["measured", "unavailable"]
    reason: (
        Literal["unsupported_source", "capability_unavailable", "no_frames", "no_usable_pairs"]
        | None
    )
    eligible_frames: Annotated[int, Field(strict=True, ge=0, le=MAX_FRAMES)]
    usable_frames: Count
    excluded_frames: Count
    exclusions: Exclusions
    samples: Annotated[tuple[DurationSample, ...], Field(max_length=MAX_FRAMES)]
    min_ms: NonnegativeFloat | None
    mean_ms: NonnegativeFloat | None
    max_ms: NonnegativeFloat | None

    @model_validator(mode="after")
    def arithmetic(self):
        ordered(self.samples, lambda s: alias_number(s.frame_id))
        if (
            self.usable_frames != len(self.samples)
            or self.eligible_frames != self.usable_frames + self.excluded_frames
        ):
            raise ValueError("result coverage/counts disagree")
        if sum(self.exclusions.model_dump().values()) != self.excluded_frames:
            raise ValueError("exclusions do not conserve counts")
        if self.samples:
            values = [s.value_ms for s in self.samples]
            expected = (
                min(values),
                sum(s.delta_ns for s in self.samples) / (len(values) * 1000000),
                max(values),
            )
            if self.state != "measured" or self.reason is not None:
                raise ValueError("usable samples require measured state")
        else:
            expected = (None, None, None)
            if self.state != "unavailable" or self.reason is None:
                raise ValueError("empty result must be unavailable")
        if (self.min_ms, self.mean_ms, self.max_ms) != expected:
            raise ValueError("statistics differ from samples")
        return self


class DeadlineSample(TraceModel):
    frame_id: FrameID
    slack_ms: Float
    hit: StrictBool


class DeadlineResult(TraceModel):
    state: Literal["measured", "unavailable"]
    reason: Literal["budget_not_declared", "no_usable_pairs"] | None
    method_id: Literal["capture-output-budget"]
    method_version: Version
    budget_ns: Positive | None
    samples: Annotated[tuple[DeadlineSample, ...], Field(max_length=MAX_FRAMES)]
    usable_frames: Count
    hit_frames: Count
    hit_fraction: Annotated[Float, Field(ge=0, le=1)] | None

    @model_validator(mode="after")
    def accounting(self):
        ordered(self.samples, lambda s: alias_number(s.frame_id))
        if self.usable_frames != len(self.samples) or self.hit_frames != sum(
            s.hit for s in self.samples
        ):
            raise ValueError("deadline counts differ from samples")
        expected_fraction = self.hit_frames / self.usable_frames if self.usable_frames else None
        if self.hit_fraction != expected_fraction:
            raise ValueError("deadline hit fraction disagrees")
        reason = "budget_not_declared" if self.budget_ns is None else "no_usable_pairs"
        if self.samples:
            if self.budget_ns is None or self.state != "measured" or self.reason is not None:
                raise ValueError("deadline samples require declared budget")
        elif self.state != "unavailable" or self.reason != reason:
            raise ValueError("deadline unavailable reason disagrees")
        return self


class SummaryStream(StreamScope):
    results: Annotated[tuple[TimingResult, ...], Field(min_length=4, max_length=4)]
    deadline_result: DeadlineResult

    @model_validator(mode="after")
    def consistency(self):
        if tuple(r.method_id for r in self.results) != METHODS:
            raise ValueError("summary must contain ordered method results")
        n = self.sampling.every_nth_frame
        for result in self.results:
            if result.eligible_frames != self.loss.sampled_frames:
                raise ValueError("result eligible count differs from ledger count")
            for sample in result.samples:
                number = alias_number(sample.frame_id)
                if (number - 1) % n or (number - 1) // n >= self.loss.sampled_frames:
                    raise ValueError("summary sample is outside sampled frame prefix")
        age = self.results[2]
        deadline = self.deadline_result
        if deadline.budget_ns is not None:
            if tuple(s.frame_id for s in deadline.samples) != tuple(
                s.frame_id for s in age.samples
            ):
                raise ValueError("deadline samples differ from usable age pairs")
            for sample, duration in zip(deadline.samples, age.samples, strict=True):
                if sample.slack_ms != (
                    deadline.budget_ns - duration.delta_ns
                ) / 1000000 or sample.hit != (duration.delta_ns <= deadline.budget_ns):
                    raise ValueError("deadline arithmetic differs from budget/age")
        return self


class StageTraceSummary(TraceModel):
    schema_version: Literal["stage-trace-summary-v1"]
    method_release: Release
    trace_sha256: Hash
    provenance: Provenance
    producer: Producer
    producer_version: Commit
    streams: Annotated[tuple[SummaryStream, ...], Field(min_length=1, max_length=16)]

    @model_validator(mode="after")
    def consistency(self):
        check_scopes(self.streams)
        if sum(s.loss.sampled_frames for s in self.streams) > MAX_FRAMES:
            raise ValueError("summary exceeds total frames")
        if sum(s.loss.retained_events for s in self.streams) > MAX_EVENTS:
            raise ValueError("summary exceeds total events")
        for stream in self.streams:
            check_support(stream, self.producer)
            if (
                self.producer == "pixelated_browser"
                and stream.deadline_result.budget_ns is not None
            ):
                raise ValueError("browser cannot declare host deadline")
            supported = {c.boundary for c in stream.capabilities if c.state == "supported"}
            correlation_counts = set()
            for index, result in enumerate(stream.results):
                own_method = (index < 3) == (self.producer == "pixelated_engine")
                accessible = all(capability_boundary(b) in supported for b in PAIRS[index])
                if not own_method or not accessible:
                    reason = "unsupported_source" if not own_method else "capability_unavailable"
                    if (
                        result.reason != reason
                        or result.usable_frames
                        or result.exclusions.unsupported != result.eligible_frames
                    ):
                        raise ValueError("unsupported result must exclude every frame")
                else:
                    if self.producer == "pixelated_engine":
                        correlation_counts.add(
                            (
                                result.exclusions.correlation_missing,
                                result.exclusions.correlation_ambiguous,
                            )
                        )
                    reason = (
                        None
                        if result.usable_frames
                        else ("no_frames" if not result.eligible_frames else "no_usable_pairs")
                    )
                    if result.reason != reason or result.exclusions.unsupported:
                        raise ValueError("supported method reason/exclusions disagree")
                    if self.producer == "pixelated_browser" and (
                        result.exclusions.correlation_missing
                        or result.exclusions.correlation_ambiguous
                    ):
                        raise ValueError("browser callback correlation is exact")
            if len(correlation_counts) > 1:
                raise ValueError("supported host methods disagree on frame correlation")
        return self
