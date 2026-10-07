"""Deterministic offline migration diagnostics; never an observation or matcher input."""

from __future__ import annotations

import json
import math
from pathlib import Path
from types import MappingProxyType

from .adapters import load_pixelated_measurement_samples
from .adapters.pixelated_bundle import ingest_pixelated_bundle
from .measurement import P0_FEATURE_CONFIG
from .measurement.aggregation import aggregate_counter, aggregate_gauge
from .measurement.metric_registry import CANONICAL_METRIC_REGISTRY, get_metric_definition
from .models import (
    ContextKey,
    MetricAggregate,
    MetricKind,
    MetricSeriesStatus,
    MetricSeriesSummary,
    ObservationWindow,
    WindowPhase,
)

# Reviewed P0-to-N1 naming decisions; neither suffix heuristics nor a new matcher config.
P0_TO_N1 = MappingProxyType(
    {
        **{
            name: (name,)
            for name in (
                "client.received_fps",
                "client.received_bitrate_kbps",
                "transport.jitter_ms",
                "transport.round_trip_time_ms",
                "client.decode_time_mean_ms",
                "client.jitter_buffer_delay_mean_ms",
                "client.available_incoming_bitrate_kbps",
                "host.node_cpu_percent",
                "host.game_cpu_percent",
                "host.camera_cpu_percent",
                "encoder.queue_level_buffers",
                "encoder.pipeline_delay_proxy_ms",
            )
        },
        "host.node_rss_mb": ("host.node_rss_mib",),
        "host.game_rss_mb": ("host.game_rss_mib",),
        "host.camera_rss_mb": ("host.camera_rss_mib",),
        "client.frames_decoded_delta": (
            "client.frames_decoded_rate_fps",
            "client.frames_decoded_window_total",
        ),
        "client.frames_dropped_delta": (
            "client.frames_dropped_rate_fps",
            "client.frames_dropped_window_total",
        ),
        "client.freeze_count_delta": (
            "client.freeze_count_rate_per_min",
            "client.freeze_count_window_total",
        ),
        "client.freeze_duration_ms_delta": (
            "client.freeze_duration_rate_ms_per_s",
            "client.freeze_duration_window_total_ms",
        ),
        "encoder.frames_in_delta": ("encoder.frames_in_rate_fps", "encoder.frames_in_window_total"),
        "encoder.frames_out_delta": (
            "encoder.frames_out_rate_fps",
            "encoder.frames_out_window_total",
        ),
        "encoder.frames_dropped_delta": (
            "encoder.frames_dropped_rate_fps",
            "encoder.frames_dropped_window_total",
        ),
        "transport.packets_lost_delta": (
            "transport.packets_lost_rate_per_s",
            "transport.packets_lost_window_total",
        ),
    }
)


def _p0_evidence(window: ObservationWindow | None, name: str) -> dict:
    if window is None:
        return {
            "status": "unavailable",
            "aggregate": None,
            "notes": ["P0 ingestion rejected this bundle; no frozen P0 value is available."],
        }
    metric = window.metrics.get(name)
    if metric is not None:
        payload = metric.model_dump(mode="json", by_alias=True)
        # Frozen windows have free-form strings. Do not echo unexpected content.
        if metric.unit != P0_FEATURE_CONFIG[name].unit:
            payload["unit"] = None
        if metric.aggregation not in {"median", "p95", "minimum", "maximum"}:
            payload["aggregation"] = None
        return {"status": "available", "aggregate": payload, "notes": []}
    if name in window.rejected_metrics:
        return {
            "status": "rejected",
            "aggregate": None,
            "notes": ["P0 rejected this feature; raw rejection text is omitted."],
        }
    return {"status": "missing", "aggregate": None, "notes": ["P0 has no value for this feature."]}


def _frozen_classification(metric: MetricAggregate | None, name: str, output: str) -> str:
    definition = get_metric_definition(output)
    if (
        definition.kind is MetricKind.GAUGE
        and metric is not None
        and metric.unit == definition.canonical_unit == P0_FEATURE_CONFIG[name].unit
        and metric.aggregation == definition.primary_aggregation
        and (
            not definition.non_negative
            or (metric.value >= 0 and (metric.minimum is None or metric.minimum >= 0))
        )
    ):
        return "identity_safe"
    return "not_recoverable_from_aggregate"


def _raw_classification(
    summary: MetricSeriesSummary, metric: MetricAggregate | None, name: str
) -> str:
    if summary.status is MetricSeriesStatus.REJECTED:
        return "rejected"
    if summary.source_sample_count == 0 or (
        summary.usable_sample_count == 0
        and not summary.rejected_reasons
        and summary.status is MetricSeriesStatus.MISSING
        and any(
            "declared unsupported" in reason
            or "declared unavailable" in reason
            or "source row is unavailable" in reason
            or "browser source is inactive" in reason
            for reason in summary.missing_reasons
        )
    ):
        return "unsupported_source"
    if summary.value is None:
        return "not_recoverable_from_aggregate"
    if (
        _frozen_classification(metric, name, summary.metric_name) == "identity_safe"
        and not summary.rejected_reasons
        and metric.count == summary.usable_sample_count
        and math.isclose(metric.value, summary.value, rel_tol=1e-12, abs_tol=0)
    ):
        return "identity_safe"
    return "recomputable_from_raw"


def _report(
    window: ObservationWindow | None,
    summaries: dict[str, MetricSeriesSummary] | None,
    *,
    phase: WindowPhase,
    checksum: str | None,
    warnings: tuple[str, ...],
) -> dict:
    features = []
    for name, outputs in sorted(P0_TO_N1.items()):
        metric = window.metrics.get(name) if window is not None else None
        proposed = []
        for output in outputs:
            definition = get_metric_definition(output)
            frozen = _frozen_classification(metric, name, output)
            summary = summaries[output] if summaries is not None else None
            classification = (
                _raw_classification(summary, metric, name) if summary is not None else frozen
            )
            if (
                summary is not None
                and definition.kind is MetricKind.GAUGE
                and classification != "identity_safe"
            ):
                frozen = "not_recoverable_from_aggregate"
            notes = []
            if definition.kind is MetricKind.CUMULATIVE_COUNTER:
                notes.append(
                    "P0 median interval deltas lack cumulative samples, "
                    "interval durations and continuity."
                )
            else:
                notes.append(
                    "Gauge meaning and aggregation require compatible units and usable evidence. "
                    "Frozen scalars cannot recover source coverage or support."
                )
            if classification == "not_recoverable_from_aggregate":
                notes.append(
                    "Required usable raw evidence is unavailable; no new value is inferred."
                )
            proposed.append(
                {
                    "definition": definition.model_dump(mode="json", by_alias=True),
                    "classification": classification,
                    "frozenAggregateClassification": frozen,
                    "value": summary.value
                    if summary is not None
                    else (metric.value if frozen == "identity_safe" else None),
                    "summary": summary.model_dump(mode="json", by_alias=True)
                    if summary is not None
                    else None,
                    "notes": notes,
                }
            )
        priority = (
            "rejected",
            "unsupported_source",
            "not_recoverable_from_aggregate",
            "recomputable_from_raw",
            "identity_safe",
        )
        classification = next(
            item
            for item in priority
            if any(output["classification"] == item for output in proposed)
        )
        features.append(
            {
                "p0Feature": name,
                "p0": _p0_evidence(window, name),
                "classification": classification,
                "outputs": proposed,
            }
        )
    return {
        "schemaVersion": "measurement-inspection-v1",
        "reportKind": "shadow_measurement_inspection",
        "matcherInput": False,
        "notice": (
            "Offline diagnostic report; not observation-v2 and not matcher input. "
            "No normalization or matcher adoption."
        ),
        "registryVersion": CANONICAL_METRIC_REGISTRY.registry_version,
        "inputMode": "raw_bundle" if summaries is not None else "frozen_window",
        "phase": phase.value,
        "bundleChecksum": f"sha256:{checksum}" if checksum is not None else None,
        "p0Ingestion": "accepted" if window is not None else "rejected",
        "p0WindowValid": window.validity.is_valid if window is not None else None,
        "warnings": list(warnings),
        "features": features,
    }


def inspect_measurements(
    bundle_path: Path, *, context: ContextKey, phase: WindowPhase, comparison_case_id: str
) -> dict:
    """Inspect an existing bounded bundle through the unchanged P0 and N1 paths.

    Each path reads the bundle independently; checksum agreement is required for
    comparison. Source-contract errors in N1 fail closed. P0-only rejection is
    reported without echoing private producer values or raw exception text.
    """
    raw = load_pixelated_measurement_samples(
        bundle_path, context=context, phase=phase, comparison_case_id=comparison_case_id
    )
    try:
        window = ingest_pixelated_bundle(
            bundle_path, context=context, phase=phase, comparison_case_id=comparison_case_id
        )
    except ValueError:
        window = None
    if window is not None and window.source_artifact.checksum != f"sha256:{raw.checksum}":
        raise ValueError("bundle changed between N1 extraction and P0 ingestion")
    summaries = {}
    for definition in CANONICAL_METRIC_REGISTRY.definitions:
        series = raw.series[definition.name]
        aggregate = aggregate_gauge if definition.kind is MetricKind.GAUGE else aggregate_counter
        summaries[definition.name] = aggregate(
            definition,
            series.samples,
            window_start_ms=raw.elapsed_start_ms,
            window_end_ms=raw.elapsed_end_ms,
            registry_version=raw.registry_version,
            warnings=raw.warnings,
            source_missing_reason=series.missing_reason,
        )
    return _report(window, summaries, phase=phase, checksum=raw.checksum, warnings=raw.warnings)


def inspect_frozen_window(window: ObservationWindow) -> dict:
    """Assess a validated P0 window without pretending its aggregates are raw samples."""
    return _report(
        window,
        None,
        phase=window.phase,
        checksum=None,
        warnings=(
            "Frozen P0 aggregates cannot reconstruct counter rates, totals, gaps or resets.",
        ),
    )


def render_measurement_inspection(report: dict) -> str:
    return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"


__all__ = [
    "P0_TO_N1",
    "inspect_measurements",
    "inspect_frozen_window",
    "render_measurement_inspection",
]
