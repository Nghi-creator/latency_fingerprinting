"""Metric mappings and auditable aggregation for Pixelated bundle rows."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from ..models import MetricAggregate
from .pixelated_bundle_common import PixelatedBundleError, finite_number

BROWSER_METRIC_COLUMNS: Mapping[str, tuple[str, str]] = {
    "client.received_fps": ("fps", "fps"),
    "client.received_bitrate_kbps": ("bitrate_kbps", "kbps"),
    "transport.jitter_ms": ("jitter_ms", "ms"),
    "transport.packets_lost_delta": ("packets_lost_delta", "packets"),
    "transport.round_trip_time_ms": ("round_trip_time_ms", "ms"),
    "client.decode_time_mean_ms": ("decode_time_mean_ms", "ms"),
    "client.jitter_buffer_delay_mean_ms": ("jitter_buffer_delay_mean_ms", "ms"),
    "client.available_incoming_bitrate_kbps": (
        "available_incoming_bitrate_kbps",
        "kbps",
    ),
}
ENGINE_METRIC_COLUMNS: Mapping[str, tuple[str, str, str]] = {
    "host.node_cpu_percent": ("engine_runtime", "node_cpu_percent", "percent"),
    "host.node_rss_mb": ("engine_runtime", "node_rss_mb", "MiB"),
    "host.game_cpu_percent": ("engine_runtime", "emulator_cpu_percent", "percent"),
    "host.game_rss_mb": ("engine_runtime", "emulator_rss_mb", "MiB"),
    "host.camera_cpu_percent": ("engine_runtime", "camera_cpu_percent", "percent"),
    "host.camera_rss_mb": ("engine_runtime", "camera_rss_mb", "MiB"),
    "encoder.queue_level_buffers": (
        "encoder_pipeline",
        "queue_level_buffers",
        "buffers",
    ),
    "encoder.pipeline_delay_proxy_ms": (
        "encoder_pipeline",
        "pipeline_delay_proxy_ms",
        "ms",
    ),
}
STREAM_COUNTER_METRICS: Mapping[str, tuple[str, str]] = {
    "client.frames_decoded_delta": ("frames_decoded", "frames"),
    "client.frames_dropped_delta": ("frames_dropped", "frames"),
    "client.freeze_count_delta": ("freeze_count", "freezes"),
    "client.freeze_duration_ms_delta": ("freeze_duration_total_ms", "ms"),
}
ENCODER_COUNTER_METRICS: Mapping[str, tuple[str, str]] = {
    "encoder.frames_in_delta": ("frames_in_total", "frames"),
    "encoder.frames_out_delta": ("frames_out_total", "frames"),
    "encoder.frames_dropped_delta": ("frames_dropped_total", "frames"),
}


def _percentile_95(values: Sequence[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)]


def _aggregate(values: Sequence[float], unit: str) -> MetricAggregate:
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        median = ordered[midpoint]
    else:
        lower = ordered[midpoint - 1]
        upper = ordered[midpoint]
        median = lower + (upper - lower) / 2 if lower >= 0 or upper <= 0 else lower / 2 + upper / 2
    return MetricAggregate(
        unit=unit,
        aggregation="median",
        value=median,
        count=len(ordered),
        median=median,
        p95=_percentile_95(ordered),
        minimum=ordered[0],
        maximum=ordered[-1],
    )


def mapped_metrics(
    rows: Sequence[Mapping[str, str]],
    metric_columns: Mapping[str, tuple[str, str]] = BROWSER_METRIC_COLUMNS,
    *,
    source_name: str = "stream-telemetry.csv",
) -> tuple[dict[str, MetricAggregate], list[str], dict[str, str]]:
    metrics: dict[str, MetricAggregate] = {}
    missing: list[str] = []
    rejected: dict[str, str] = {}
    for metric, (column, unit) in metric_columns.items():
        values: list[float] = []
        invalid: list[str] = []
        for index, row in enumerate(rows, start=2):
            raw = (row.get(column) or "").strip()
            if not raw:
                continue
            try:
                value = finite_number(raw, source=f"{source_name} row {index} {column}")
            except PixelatedBundleError as error:
                invalid.append(str(error))
                continue
            if value < 0:
                invalid.append(f"{source_name} row {index} {column} cannot be negative")
            else:
                values.append(value)
        if invalid:
            rejected[metric] = "; ".join(invalid)
        elif values:
            metrics[metric] = _aggregate(values, unit)
        else:
            missing.append(metric)
    return metrics, sorted(missing), rejected


def counter_metrics(
    rows: Sequence[Mapping[str, str]],
    metric_columns: Mapping[str, tuple[str, str]],
    *,
    source_name: str,
    availability_column: str | None = None,
) -> tuple[dict[str, MetricAggregate], list[str], dict[str, str]]:
    metrics: dict[str, MetricAggregate] = {}
    missing: list[str] = []
    rejected: dict[str, str] = {}
    for metric, (column, unit) in metric_columns.items():
        deltas: list[float] = []
        invalid: list[str] = []
        previous: float | None = None
        for index, row in enumerate(rows, start=2):
            if availability_column is not None and (
                row.get(availability_column, "").strip().lower() != "true"
            ):
                previous = None
                continue
            raw = (row.get(column) or "").strip()
            if not raw:
                previous = None
                continue
            try:
                value = finite_number(raw, source=f"{source_name} row {index} {column}")
            except PixelatedBundleError as error:
                invalid.append(str(error))
                previous = None
                continue
            if value < 0:
                invalid.append(f"{source_name} row {index} {column} cannot be negative")
                previous = None
                continue
            if previous is not None:
                delta = value - previous
                if delta < 0:
                    invalid.append(f"{source_name} {column} counter reset during the window")
                else:
                    deltas.append(delta)
            previous = value
        if invalid:
            rejected[metric] = "; ".join(invalid)
        elif deltas:
            metrics[metric] = _aggregate(deltas, unit)
        else:
            missing.append(metric)
    return metrics, sorted(missing), rejected


def engine_metrics(
    rows: Sequence[Mapping[str, str]],
) -> tuple[dict[str, MetricAggregate], list[str], dict[str, str]]:
    metrics: dict[str, MetricAggregate] = {}
    missing: list[str] = []
    rejected: dict[str, str] = {}
    for metric, (source, column, unit) in ENGINE_METRIC_COLUMNS.items():
        source_rows = [
            row
            for row in rows
            if row.get("source") == source and row.get("available", "").strip().lower() == "true"
        ]
        measured, absent, invalid = mapped_metrics(
            source_rows,
            {metric: (column, unit)},
            source_name="engine-telemetry.csv",
        )
        metrics.update(measured)
        missing.extend(absent)
        rejected.update(invalid)
    encoder_rows = [row for row in rows if row.get("source") == "encoder_pipeline"]
    measured, absent, invalid = counter_metrics(
        encoder_rows,
        ENCODER_COUNTER_METRICS,
        source_name="engine-telemetry.csv",
        availability_column="available",
    )
    metrics.update(measured)
    missing.extend(absent)
    rejected.update(invalid)
    return metrics, sorted(missing), rejected


__all__ = [
    "BROWSER_METRIC_COLUMNS",
    "STREAM_COUNTER_METRICS",
    "counter_metrics",
    "engine_metrics",
    "mapped_metrics",
]
