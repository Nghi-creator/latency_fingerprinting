"""Opt-in browser callback execution method; frozen v1 endpoints remain distinct."""

from typing import Annotated, Literal

from pydantic import Field

from .contracts import BOUNDARIES, BROWSER_EVENTS, METHODS, PAIRS, Capability
from .summary import StageTraceSummary, SummaryStream, TimingResult
from .trace import Event, StageTraceRecord, TraceStream

EXECUTION = "presentation_callback_execution"
BROWSER_BOUNDARIES = (*BOUNDARIES, EXECUTION)
BROWSER_EVENTS_V2 = (*BROWSER_EVENTS, EXECUTION)
BROWSER_METHODS = (*METHODS, "presentation-execution-lag")
BROWSER_PAIRS = (*PAIRS, ("presentation_proxy", EXECUTION))


class BrowserCapabilityV2(Capability):
    boundary: Literal[*BROWSER_BOUNDARIES]


class BrowserEventV2(Event):
    boundary: Literal[*BROWSER_EVENTS_V2]


class BrowserTraceStreamV2(TraceStream):
    boundaries = BROWSER_BOUNDARIES
    collection_limits = {"results": 5, "capabilities": 12}
    capabilities: Annotated[tuple[BrowserCapabilityV2, ...], Field(min_length=12, max_length=12)]
    events: Annotated[tuple[BrowserEventV2, ...], Field(max_length=10000)]


class StageTraceRecordV2(StageTraceRecord):
    browser_events = BROWSER_EVENTS_V2
    schema_version: Literal["stage-trace-record-v2"]
    method_release: Literal["n4-browser-execution-v1"]
    producer: Literal["pixelated_browser"]
    streams: Annotated[tuple[BrowserTraceStreamV2, ...], Field(min_length=1, max_length=16)]


class BrowserTimingResultV2(TimingResult):
    method_id: Literal[*BROWSER_METHODS]


class BrowserSummaryStreamV2(SummaryStream):
    boundaries = BROWSER_BOUNDARIES
    methods = BROWSER_METHODS
    collection_limits = {"results": 5, "capabilities": 12}
    capabilities: Annotated[tuple[BrowserCapabilityV2, ...], Field(min_length=12, max_length=12)]
    results: Annotated[tuple[BrowserTimingResultV2, ...], Field(min_length=5, max_length=5)]


class StageTraceSummaryV2(StageTraceSummary):
    pairs = BROWSER_PAIRS
    browser_events = BROWSER_EVENTS_V2
    schema_version: Literal["stage-trace-summary-v2"]
    method_release: Literal["n4-browser-execution-v1"]
    producer: Literal["pixelated_browser"]
    streams: Annotated[tuple[BrowserSummaryStreamV2, ...], Field(min_length=1, max_length=16)]


def parse_trace_record(payload):
    """Dispatch only explicit roots; never reinterpret v1 as the execution method."""
    if not isinstance(payload, dict):
        raise ValueError("trace must be an object")
    version = payload.get("schema_version")
    if version == "stage-trace-record-v1":
        return StageTraceRecord.model_validate(payload)
    if version == "stage-trace-record-v2":
        return StageTraceRecordV2.model_validate(payload)
    raise ValueError("unsupported trace root")
