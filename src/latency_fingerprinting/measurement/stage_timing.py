"""Explicit absence of direct stage durations in current Pixelated captures."""

from collections.abc import Mapping

from ..models import MetricSource, SourceSupport, StageTiming

# Associations describe where future stage-local evidence would originate.
# They do not promote any existing mean/proxy or assert a measured clock domain.
_STAGE_SOURCES = (
    ("capture", MetricSource.ENGINE_RUNTIME),
    ("encode", MetricSource.ENCODER_PIPELINE),
    ("decode", MetricSource.BROWSER_WEBRTC),
    ("render", MetricSource.BROWSER_WEBRTC),
)


def unavailable_stage_timings(
    sources: Mapping[MetricSource, SourceSupport],
) -> tuple[StageTiming, ...]:
    """Retain typed source support without manufacturing stage timing evidence."""
    if set(sources) != set(MetricSource):
        raise ValueError("stage timing requires all three validated source support records")
    reasons = {
        "supported": "not_instrumented",
        "unsupported": "unsupported_source",
        "unavailable": "source_unavailable",
    }
    return tuple(
        StageTiming(
            stage=stage,
            state="unavailable",
            source=source,
            method_id=None,
            method_version=None,
            clock_domain_id=None,
            unit="ms",
            statistic=None,
            value=None,
            sample_count=0,
            reason_code=reasons[sources[source].state],
        )
        for stage, source in _STAGE_SOURCES
    )


__all__ = ["unavailable_stage_timings"]
