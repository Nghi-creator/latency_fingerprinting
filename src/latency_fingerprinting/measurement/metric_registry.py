"""Canonical N1 definitions and deterministic offline registry export/check."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType

from ..models import (
    AggregationKind,
    ClockBasis,
    CounterResetPolicy,
    MetricDefinition,
    MetricKind,
    MetricRegistry,
    MetricSource,
    MetricUnit,
    MissingDataPolicy,
)
from ..schemas import DEFAULT_SCHEMA_DIRECTORY, _atomic_write_text

METRIC_REGISTRY_VERSION = "latency-metrics-v2.0.0"
METRIC_SEMANTIC_VERSION = "1.0.0"
METRIC_REGISTRY_CREATED_AT = datetime(2026, 10, 6, tzinfo=UTC)
DEFAULT_METRIC_REGISTRY_PATH = DEFAULT_SCHEMA_DIRECTORY / "metric-registry-v1.json"


def _gauge(
    name: str, source: MetricSource, raw_field: str, unit: MetricUnit, description: str
) -> MetricDefinition:
    return MetricDefinition(
        name=name,
        semantic_version=METRIC_SEMANTIC_VERSION,
        source=source,
        raw_fields=(raw_field,),
        kind=MetricKind.GAUGE,
        canonical_unit=unit,
        primary_aggregation=AggregationKind.MEDIAN,
        available_aggregations=(
            AggregationKind.MEDIAN,
            AggregationKind.NEAREST_RANK_P95,
            AggregationKind.MINIMUM,
            AggregationKind.MAXIMUM,
        ),
        clock_basis=ClockBasis.SOURCE_ELAPSED_MS,
        expected_cadence_ms=None,
        cadence_tolerance_ratio=None,
        missing_data_policy=MissingDataPolicy.OMIT_MISSING_SAMPLES,
        counter_reset_policy=None,
        non_negative=True,
        description=description,
    )


def _counter_pair(
    source: MetricSource,
    raw_field: str,
    rate_name: str,
    rate_unit: MetricUnit,
    total_name: str,
    total_unit: MetricUnit,
    quantity: str,
) -> tuple[MetricDefinition, MetricDefinition]:
    definitions = []
    for name, unit, aggregation, meaning in (
        (
            rate_name,
            rate_unit,
            AggregationKind.TIME_WEIGHTED_RATE,
            "time-weighted rate over accepted elapsed intervals; analytical shadow output",
        ),
        (
            total_name,
            total_unit,
            AggregationKind.WINDOW_TOTAL,
            "sum of accepted interval deltas; audit-only, with no extrapolation",
        ),
    ):
        definitions.append(
            MetricDefinition(
                name=name,
                semantic_version=METRIC_SEMANTIC_VERSION,
                source=source,
                raw_fields=(raw_field,),
                kind=MetricKind.CUMULATIVE_COUNTER,
                canonical_unit=unit,
                primary_aggregation=aggregation,
                available_aggregations=(aggregation,),
                clock_basis=ClockBasis.SOURCE_ELAPSED_MS,
                expected_cadence_ms=None,
                cadence_tolerance_ratio=None,
                missing_data_policy=MissingDataPolicy.BREAK_COUNTER_CONTINUITY,
                counter_reset_policy=CounterResetPolicy.REJECT_SEGMENT,
                non_negative=True,
                description=(
                    f"{quantity}: {meaning}. Exported elapsed clock provenance is required."
                ),
            )
        )
    return definitions[0], definitions[1]


# Source declarations are independent of P0 configuration and adapter mappings.
# Meaning changes require explicit semantic/registry version changes and review.
_GAUGES = (
    _gauge(
        "client.available_incoming_bitrate_kbps",
        MetricSource.BROWSER_WEBRTC,
        "available_incoming_bitrate_kbps",
        MetricUnit.KILOBITS_PER_SECOND,
        "Selected candidate-pair incoming bandwidth estimate in decimal kilobits/s.",
    ),
    _gauge(
        "client.decode_time_mean_ms",
        MetricSource.BROWSER_WEBRTC,
        "decode_time_mean_ms",
        MetricUnit.MILLISECONDS,
        "Producer interval decode-time delta divided by decoded-frame delta across supported "
        "video streams; gauge percentiles describe exported interval means, not individual frames.",
    ),
    _gauge(
        "client.jitter_buffer_delay_mean_ms",
        MetricSource.BROWSER_WEBRTC,
        "jitter_buffer_delay_mean_ms",
        MetricUnit.MILLISECONDS,
        "Producer interval buffer-delay delta divided by emitted-count delta across supported "
        "video streams; gauge percentiles describe exported interval means.",
    ),
    _gauge(
        "client.received_bitrate_kbps",
        MetricSource.BROWSER_WEBRTC,
        "bitrate_kbps",
        MetricUnit.KILOBITS_PER_SECOND,
        "Sum of supported inbound byte-counter rates already derived by the producer, "
        "in decimal kilobits/s; not recomputed from CSV capture cadence.",
    ),
    _gauge(
        "client.received_fps",
        MetricSource.BROWSER_WEBRTC,
        "fps",
        MetricUnit.FPS,
        "Maximum reported video-inbound framesPerSecond across supported streams.",
    ),
    _gauge(
        "encoder.pipeline_delay_proxy_ms",
        MetricSource.ENCODER_PIPELINE,
        "pipeline_delay_proxy_ms",
        MetricUnit.MILLISECONDS,
        "Exported pipeline delay proxy, not direct encoder processing duration. "
        "The current camera producer emits null; missing values remain missing.",
    ),
    _gauge(
        "encoder.queue_level_buffers",
        MetricSource.ENCODER_PIPELINE,
        "queue_level_buffers",
        MetricUnit.BUFFERS,
        "Maximum pre/post encoder queue occupancy across active peers. Producer zero "
        "fallbacks for absent queues or failed reads cannot be distinguished in legacy CSV.",
    ),
    _gauge(
        "host.camera_cpu_percent",
        MetricSource.ENGINE_RUNTIME,
        "camera_cpu_percent",
        MetricUnit.PERCENT,
        "Camera bridge process CPU time per elapsed interval; 100 percent is one core, "
        "without host-capacity normalization or a 100-percent cap.",
    ),
    _gauge(
        "host.camera_rss_mib",
        MetricSource.ENGINE_RUNTIME,
        "camera_rss_mb",
        MetricUnit.MEBIBYTES,
        "Camera bridge resident memory in binary mebibytes; legacy raw mb suffix is misleading.",
    ),
    _gauge(
        "host.game_cpu_percent",
        MetricSource.ENGINE_RUNTIME,
        "emulator_cpu_percent",
        MetricUnit.PERCENT,
        "Emulator process CPU time per elapsed interval; 100 percent is one core, "
        "without host-capacity normalization or a 100-percent cap.",
    ),
    _gauge(
        "host.game_rss_mib",
        MetricSource.ENGINE_RUNTIME,
        "emulator_rss_mb",
        MetricUnit.MEBIBYTES,
        "Emulator resident memory in binary mebibytes; legacy raw mb suffix is misleading.",
    ),
    _gauge(
        "host.node_cpu_percent",
        MetricSource.ENGINE_RUNTIME,
        "node_cpu_percent",
        MetricUnit.PERCENT,
        "Node runtime process CPU time per elapsed interval; 100 percent is one core, "
        "without host-capacity normalization or a 100-percent cap.",
    ),
    _gauge(
        "host.node_rss_mib",
        MetricSource.ENGINE_RUNTIME,
        "node_rss_mb",
        MetricUnit.MEBIBYTES,
        "Node runtime resident memory in binary mebibytes; legacy raw mb suffix is misleading.",
    ),
    _gauge(
        "transport.jitter_ms",
        MetricSource.BROWSER_WEBRTC,
        "jitter_ms",
        MetricUnit.MILLISECONDS,
        "Maximum supported inbound RTP jitter across audio and video streams, in milliseconds.",
    ),
    _gauge(
        "transport.round_trip_time_ms",
        MetricSource.BROWSER_WEBRTC,
        "round_trip_time_ms",
        MetricUnit.MILLISECONDS,
        "Selected candidate-pair current round-trip time in milliseconds.",
    ),
)
_COUNTER_PAIRS = (
    _counter_pair(
        MetricSource.BROWSER_WEBRTC,
        "frames_decoded",
        "client.frames_decoded_rate_fps",
        MetricUnit.FRAMES_PER_SECOND,
        "client.frames_decoded_window_total",
        MetricUnit.FRAMES,
        "Supported video-inbound decoded-frame count",
    ),
    _counter_pair(
        MetricSource.BROWSER_WEBRTC,
        "frames_dropped",
        "client.frames_dropped_rate_fps",
        MetricUnit.FRAMES_PER_SECOND,
        "client.frames_dropped_window_total",
        MetricUnit.FRAMES,
        "Supported video-inbound dropped-frame count",
    ),
    _counter_pair(
        MetricSource.BROWSER_WEBRTC,
        "freeze_count",
        "client.freeze_count_rate_per_min",
        MetricUnit.FREEZES_PER_MINUTE,
        "client.freeze_count_window_total",
        MetricUnit.FREEZES,
        "Supported video-inbound freeze event count; rate uses minutes",
    ),
    _counter_pair(
        MetricSource.BROWSER_WEBRTC,
        "freeze_duration_total_ms",
        "client.freeze_duration_rate_ms_per_s",
        MetricUnit.MILLISECONDS_PER_SECOND,
        "client.freeze_duration_window_total_ms",
        MetricUnit.MILLISECONDS,
        "Supported video-inbound accumulated freeze duration; rate is ms/s, not a percentage",
    ),
    _counter_pair(
        MetricSource.ENCODER_PIPELINE,
        "frames_in_total",
        "encoder.frames_in_rate_fps",
        MetricUnit.FRAMES_PER_SECOND,
        "encoder.frames_in_window_total",
        MetricUnit.FRAMES,
        "Encoder input count summed across active peers; membership declines are treated as resets",
    ),
    _counter_pair(
        MetricSource.ENCODER_PIPELINE,
        "frames_out_total",
        "encoder.frames_out_rate_fps",
        MetricUnit.FRAMES_PER_SECOND,
        "encoder.frames_out_window_total",
        MetricUnit.FRAMES,
        "Encoder output count summed across active peers; "
        "membership declines are treated as resets",
    ),
    _counter_pair(
        MetricSource.ENCODER_PIPELINE,
        "frames_dropped_total",
        "encoder.frames_dropped_rate_fps",
        MetricUnit.FRAMES_PER_SECOND,
        "encoder.frames_dropped_window_total",
        MetricUnit.FRAMES,
        "Encoder drop count summed across active peers; membership declines are treated as resets",
    ),
    _counter_pair(
        MetricSource.BROWSER_WEBRTC,
        "packets_lost_total",
        "transport.packets_lost_rate_per_s",
        MetricUnit.PACKETS_PER_SECOND,
        "transport.packets_lost_window_total",
        MetricUnit.PACKETS,
        "Producer rounded non-negative packet-loss count summed across inbound streams; "
        "missing per-report counters may contribute upstream zeros. "
        "Derive from cumulative totals, excluding the synthetic first-row interval delta",
    ),
)


def build_metric_registry() -> MetricRegistry:
    """Build from explicit release definitions without reading files or the clock."""

    return MetricRegistry(
        registry_version=METRIC_REGISTRY_VERSION,
        created_at=METRIC_REGISTRY_CREATED_AT,
        definitions=(*_GAUGES, *(definition for pair in _COUNTER_PAIRS for definition in pair)),
    )


CANONICAL_METRIC_REGISTRY = build_metric_registry()
_DEFINITIONS_BY_NAME = MappingProxyType(
    {definition.name: definition for definition in CANONICAL_METRIC_REGISTRY.definitions}
)


def get_metric_definition(name: str) -> MetricDefinition:
    """Resolve only registered names; a P0 delta name cannot silently become a rate."""

    if not isinstance(name, str):
        raise ValueError("registered metric name must be a string")
    try:
        return _DEFINITIONS_BY_NAME[name]
    except KeyError as error:
        raise ValueError(f"unknown registered metric: {name!r}") from error


def render_metric_registry() -> str:
    """Return stable, newline-terminated JSON with contract aliases."""

    payload = CANONICAL_METRIC_REGISTRY.model_dump(mode="json", by_alias=True)
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def export_metric_registry(path: Path = DEFAULT_METRIC_REGISTRY_PATH) -> Path:
    """Atomically replace one artifact using the existing schema writer."""

    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(path, render_metric_registry())
    return path


def metric_registry_drift(path: Path = DEFAULT_METRIC_REGISTRY_PATH) -> bool:
    """Check exact bytes with bounded reads; never write or create directories."""

    expected = render_metric_registry().encode("utf-8")
    if not path.is_file() or path.stat().st_size != len(expected):
        return True
    with path.open("rb") as source:
        return source.read(len(expected) + 1) != expected


__all__ = [
    "CANONICAL_METRIC_REGISTRY",
    "DEFAULT_METRIC_REGISTRY_PATH",
    "METRIC_REGISTRY_CREATED_AT",
    "METRIC_REGISTRY_VERSION",
    "METRIC_SEMANTIC_VERSION",
    "build_metric_registry",
    "export_metric_registry",
    "get_metric_definition",
    "metric_registry_drift",
    "render_metric_registry",
]
