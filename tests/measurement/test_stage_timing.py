"""Source capability never substitutes for missing direct stage-duration evidence."""

import pytest
from pydantic import ValidationError

from latency_fingerprinting.measurement.stage_timing import unavailable_stage_timings
from latency_fingerprinting.models import MetricSource, SourceSupport


def sources(**states):
    return {
        source: SourceSupport(
            state=states.get(source, "supported"),
            declared_state=states.get(source, "supported"),
            basis="source_declaration",
            source_file="stream-telemetry.csv"
            if source is MetricSource.BROWSER_WEBRTC
            else "engine-telemetry.csv",
            row_count=3,
            available_row_count=3 if states.get(source, "supported") == "supported" else 0,
        )
        for source in MetricSource
    }


@pytest.mark.parametrize(
    ("source", "stages"),
    [
        (MetricSource.ENGINE_RUNTIME, ("capture",)),
        (MetricSource.ENCODER_PIPELINE, ("encode",)),
        (MetricSource.BROWSER_WEBRTC, ("decode", "render")),
    ],
)
@pytest.mark.parametrize(
    ("state", "reason"),
    [
        ("supported", "not_instrumented"),
        ("unsupported", "unsupported_source"),
        ("unavailable", "source_unavailable"),
    ],
)
def test_absence_reason_follows_source_not_a_numeric_proxy(source, stages, state, reason):
    result = unavailable_stage_timings(sources(**{source: state}))
    assert tuple(item.stage for item in result) == ("capture", "encode", "decode", "render")
    for timing in result:
        assert timing.state == "unavailable" and timing.value is None and timing.sample_count == 0
        assert timing.method_id is None and timing.method_version is None
        assert timing.clock_domain_id is None and timing.statistic is None and timing.unit == "ms"
        assert timing.reason_code == (reason if timing.stage in stages else "not_instrumented")
        if timing.stage in stages:
            assert timing.source is source


def test_timing_records_are_frozen_and_source_inputs_unchanged():
    original = sources()
    before = {key: value.model_dump() for key, value in original.items()}
    timing = unavailable_stage_timings(original)[0]
    with pytest.raises(ValidationError, match="frozen"):
        timing.value = 1
    assert {key: value.model_dump() for key, value in original.items()} == before


@pytest.mark.parametrize("missing", list(MetricSource))
def test_absent_support_record_does_not_invent_an_unavailable_source(missing):
    incomplete = sources()
    del incomplete[missing]
    with pytest.raises(ValueError, match="all three"):
        unavailable_stage_timings(incomplete)
