"""Bounded raw sample extraction for N1; no rate, total or gauge aggregation."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import MappingProxyType

from ..measurement.metric_registry import CANONICAL_METRIC_REGISTRY
from ..models import ContextKey, MeasurementSample, MetricDefinition, MetricSource, WindowPhase
from .pixelated_adoption_metadata import PixelatedAdoptionMetadata, adoption_metadata
from .pixelated_bundle import (
    EVENT_COLUMNS,
    READABLE_FILES,
    TELEMETRY_COLUMNS,
    V1_REQUIRED_FILES,
    _validate_metadata,
)
from .pixelated_bundle_common import PixelatedBundleError, finite_number, utc_datetime
from .pixelated_bundle_io import bundle_checksum, csv_rows, json_object, read_bundle
from .pixelated_bundle_v2 import (
    ENGINE_TELEMETRY_COLUMNS,
    engine_effective_settings,
    validate_engine_rows,
    validate_engine_window_alignment,
    validate_event_privacy,
    validate_manifest,
    validate_metadata_privacy,
    validate_summary,
    validity_reasons,
)
from .pixelated_bundle_validation import validate_cross_file_identity


@dataclass(frozen=True, slots=True)
class MetricSampleSeries:
    """Source identity and ordered raw evidence for one registered output."""

    metric_name: str
    source: MetricSource
    source_file: str
    samples: tuple[MeasurementSample, ...]
    missing_reason: str | None = None


@dataclass(frozen=True, slots=True)
class PixelatedMeasurementSamples:
    """One parsed bundle, with shared sample tuples for rate/total definitions."""

    registry_version: str
    checksum: str
    started_at: datetime
    ended_at: datetime
    elapsed_start_ms: float
    elapsed_end_ms: float
    series: Mapping[str, MetricSampleSeries]
    clock_provenance: str = "wall_clock_derived_elapsed"
    warnings: tuple[str, ...] = (
        "Exported elapsed timestamps are wall-clock-derived; monotonic capture is unverified.",
    )
    adoption: PixelatedAdoptionMetadata | None = None


def _source_file(source: MetricSource) -> str:
    return (
        "stream-telemetry.csv" if source is MetricSource.BROWSER_WEBRTC else "engine-telemetry.csv"
    )


def _timestamps(
    rows: Sequence[Mapping[str, str]], indices: Sequence[int], source_file: str
) -> tuple[tuple[float, datetime], ...]:
    times: list[tuple[float, datetime]] = []
    for row, index in zip(rows, indices, strict=True):
        label = f"{source_file} row {index}"
        elapsed = finite_number(row["elapsed_ms"], source=f"{label} elapsed_ms")
        timestamp = utc_datetime(row["captured_at"], source=f"{label} captured_at")
        if elapsed < 0:
            raise PixelatedBundleError(f"{label} elapsed_ms cannot be negative")
        if times:
            if elapsed <= times[-1][0]:
                raise PixelatedBundleError(f"{label} elapsed_ms must be strictly increasing")
            if timestamp <= times[-1][1]:
                raise PixelatedBundleError(f"{label} captured_at must be strictly increasing")
            elapsed_seconds = (elapsed - times[0][0]) / 1000
            wall_seconds = (timestamp - times[0][1]).total_seconds()
            if not math.isfinite(elapsed_seconds) or not math.isclose(
                elapsed_seconds, wall_seconds, rel_tol=1e-6, abs_tol=0.001
            ):
                raise PixelatedBundleError(f"{label} wall-clock and elapsed times disagree")
        times.append((elapsed, timestamp))
    return tuple(times)


def _samples(
    definition: MetricDefinition,
    rows: Sequence[Mapping[str, str]],
    indices: Sequence[int],
    times: Sequence[tuple[float, datetime]],
    measurement_support: Mapping[str, str],
) -> tuple[MeasurementSample, ...]:
    raw_field = definition.raw_fields[0]
    head, *tail = raw_field.split("_")
    support_key = f"{definition.source}.{head}{''.join(word.capitalize() for word in tail)}"
    support = measurement_support.get(support_key)
    source_file = _source_file(definition.source)
    samples = []
    for row, index, (elapsed, timestamp) in zip(rows, indices, times, strict=True):
        available = True
        missing = None
        rejected = None
        value = None
        label = f"{source_file} row {index} {raw_field}"
        if support in {"unsupported", "unavailable"}:
            available = False
            missing = f"{label}: metric is declared {support}"
        elif definition.source is MetricSource.BROWSER_WEBRTC:
            if (
                row["status"] != "playing"
                or row["connection_state"] != "connected"
                or row["ice_connection_state"] not in {"connected", "completed"}
                or row["last_engine_error"].strip()
            ):
                available = False
                missing = f"{label}: browser source is inactive, disconnected or has an error"
        elif row["available"].strip().lower() != "true":
            available = False
            missing = f"{label}: source row is unavailable"
        if available:
            raw = (row.get(raw_field) or "").strip()
            if not raw:
                if definition.source is MetricSource.BROWSER_WEBRTC:
                    missing = f"{label}: source field is missing"
                else:
                    rejected = f"{label}: available source row is missing a required numeric cell"
            else:
                try:
                    value = finite_number(raw, source=label)
                except PixelatedBundleError:
                    rejected = f"{label}: value must be finite and numeric"
                else:
                    if definition.non_negative and value < 0:
                        value = None
                        rejected = f"{label}: value cannot be negative"
        samples.append(
            MeasurementSample(
                elapsed_ms=elapsed,
                captured_at=timestamp,
                value=value,
                available=available,
                source_row=index,
                missing_reason=missing,
                rejection_reason=rejected,
            )
        )
    return tuple(samples)


def load_pixelated_measurement_samples(
    bundle_path: Path,
    *,
    phase: WindowPhase,
    comparison_case_id: str,
    context: ContextKey,
    include_adoption_metadata: bool = False,
) -> PixelatedMeasurementSamples:
    """Validate the existing bundle envelope and extract canonical raw evidence once.

    Invalid identity/clock/file contracts raise PixelatedBundleError. Numeric metric
    cells become missing/rejected sample evidence. No P0 aggregation is invoked.
    """

    if not comparison_case_id.strip():
        raise PixelatedBundleError("comparison_case_id cannot be empty")
    files = read_bundle(
        bundle_path, readable_files=READABLE_FILES, required_files=V1_REQUIRED_FILES
    )
    metadata = json_object(files, "run-metadata.json")
    summary = json_object(files, "summary.json")
    manifest = (
        json_object(files, "bundle-manifest.json") if "bundle-manifest.json" in files else None
    )
    version = "2" if manifest is not None else "1"
    declared_version = context.versions.get("pixelatedBundleSchema")
    if declared_version not in {"1", "2"}:
        raise PixelatedBundleError("context requires pixelatedBundleSchema version '1' or '2'")
    if version != declared_version:
        raise PixelatedBundleError(
            "context pixelatedBundleSchema disagrees with the ingested bundle"
        )
    browser_rows = csv_rows(files, "stream-telemetry.csv", TELEMETRY_COLUMNS)
    events = csv_rows(files, "stream-events.csv", EVENT_COLUMNS)
    if not browser_rows:
        raise PixelatedBundleError("stream-telemetry.csv requires at least one data row")
    run_id, session_id, workload_id, player_mode, settings = _validate_metadata(metadata)
    if workload_id != context.workload_id:
        raise PixelatedBundleError(
            "run-metadata.json workload identity disagrees with the explicit context"
        )
    validate_cross_file_identity(
        summary,
        browser_rows,
        events,
        run_id=run_id,
        session_id=session_id,
        workload_id=workload_id,
        player_mode=player_mode,
    )
    browser_indices = tuple(range(2, len(browser_rows) + 2))
    browser_times = _timestamps(browser_rows, browser_indices, "stream-telemetry.csv")
    elapsed_start, started_at = browser_times[0]
    elapsed_end, ended_at = browser_times[-1]
    duration_ms = (ended_at - started_at).total_seconds() * 1000
    if duration_ms <= 0:
        raise PixelatedBundleError("telemetry window duration must be greater than zero")
    source_rows: dict[MetricSource, list[dict[str, str]]] = {
        MetricSource.BROWSER_WEBRTC: browser_rows,
        MetricSource.ENGINE_RUNTIME: [],
        MetricSource.ENCODER_PIPELINE: [],
    }
    source_indices: dict[MetricSource, tuple[int, ...]] = {
        MetricSource.BROWSER_WEBRTC: browser_indices,
        MetricSource.ENGINE_RUNTIME: (),
        MetricSource.ENCODER_PIPELINE: (),
    }
    source_times = {MetricSource.BROWSER_WEBRTC: browser_times}
    if manifest is not None:
        validate_metadata_privacy(metadata)
        validate_manifest(
            manifest, files, comparison_case_id=comparison_case_id, phase=phase, run_id=run_id
        )
        validate_event_privacy(events)
        engine_rows = csv_rows(files, "engine-telemetry.csv", ENGINE_TELEMETRY_COLUMNS)
        for source in (MetricSource.ENGINE_RUNTIME, MetricSource.ENCODER_PIPELINE):
            selected = [
                (index, row)
                for index, row in enumerate(engine_rows, start=2)
                if row["source"] == source
            ]
            source_rows[source] = [row for _, row in selected]
            source_indices[source] = tuple(index for index, _ in selected)
            source_times[source] = _timestamps(
                source_rows[source], source_indices[source], "engine-telemetry.csv"
            )
        validate_engine_rows(
            engine_rows,
            run_id=run_id,
            session_id=session_id,
            workload_id=workload_id,
            allow_empty=metadata.get("scenario") == "browser_only_baseline",
        )
        settings.update(engine_effective_settings(engine_rows))
        validate_engine_window_alignment(
            engine_rows,
            started_at=started_at,
            ended_at=ended_at,
            elapsed_start_ms=elapsed_start,
            elapsed_end_ms=elapsed_end,
        )
        validate_summary(
            summary, engine_rows, telemetry_count=len(browser_rows), duration_ms=duration_ms
        )
        # Also cross-check declared source support against actual availability.
        validity_reasons(metadata, manifest, engine_rows)
    series: dict[str, MetricSampleSeries] = {}
    cache: dict[tuple[MetricSource, tuple[str, ...], bool], tuple[MeasurementSample, ...]] = {}
    for definition in CANONICAL_METRIC_REGISTRY.definitions:
        source = definition.source
        key = (source, definition.raw_fields, definition.non_negative)
        if key not in cache:
            cache[key] = _samples(
                definition,
                source_rows[source],
                source_indices[source],
                source_times.get(source, ()),
                manifest["measurementSupport"] if manifest is not None else {},
            )
        series[definition.name] = MetricSampleSeries(
            metric_name=definition.name,
            source=source,
            source_file=_source_file(source),
            samples=cache[key],
            missing_reason="source has no supplied rows" if not source_rows[source] else None,
        )
    return PixelatedMeasurementSamples(
        registry_version=CANONICAL_METRIC_REGISTRY.registry_version,
        checksum=bundle_checksum(files),
        started_at=started_at,
        ended_at=ended_at,
        elapsed_start_ms=elapsed_start,
        elapsed_end_ms=elapsed_end,
        series=MappingProxyType(series),
        adoption=adoption_metadata(
            run_id=run_id,
            version=version,
            metadata=metadata,
            summary=summary,
            manifest=manifest,
            settings=settings,
            source_rows=source_rows,
            events=events,
        )
        if include_adoption_metadata
        else None,
    )


__all__ = [
    "MetricSampleSeries",
    "PixelatedMeasurementSamples",
    "load_pixelated_measurement_samples",
]
