"""Minimal typed N2 metadata from the same validated envelope as N1 samples."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from ..measurement.metric_registry import CANONICAL_METRIC_REGISTRY
from ..models import MetricSource, SourceSupport
from ..models.v2_support import ValidityReason
from .pixelated_bundle_common import PixelatedBundleError
from .pixelated_bundle_validation import validity_reasons as browser_validity_reasons


@dataclass(frozen=True, slots=True)
class PixelatedAdoptionMetadata:
    run_id: str
    bundle_schema_version: str
    producer_version: str | None
    effective_settings: Mapping[str, Any]
    sources: Mapping[MetricSource, SourceSupport]
    metric_declarations: Mapping[str, str | None]
    invalid_reason_codes: tuple[ValidityReason, ...]


def _available(row: Mapping[str, str], source: MetricSource) -> bool:
    if source is not MetricSource.BROWSER_WEBRTC:
        return row["available"].strip().lower() == "true"
    return (
        row["status"] == "playing"
        and row["connection_state"] == "connected"
        and row["ice_connection_state"] in {"connected", "completed"}
        and not row["last_engine_error"].strip()
    )


def adoption_metadata(
    *,
    run_id: str,
    version: str,
    metadata: Mapping[str, Any],
    summary: Mapping[str, Any],
    manifest: Mapping[str, Any] | None,
    settings: Mapping[str, Any],
    source_rows: Mapping[MetricSource, Sequence[Mapping[str, str]]],
    events: Sequence[Mapping[str, str]],
) -> PixelatedAdoptionMetadata:
    sources = {}
    declarations = manifest["telemetrySources"] if manifest is not None else {}
    for source, rows in source_rows.items():
        declared = declarations.get(source)
        count = sum(_available(row, source) for row in rows)
        if declared in {"unsupported", "unavailable"}:
            count = 0
        state = declared if declared is not None else ("supported" if count else "unavailable")
        sources[source] = SourceSupport(
            state=state,
            declared_state=declared,
            basis="source_declaration"
            if declared is not None
            else "source_rows"
            if rows
            else "source_absent",
            source_file="stream-telemetry.csv"
            if source is MetricSource.BROWSER_WEBRTC
            else "engine-telemetry.csv",
            row_count=len(rows),
            available_row_count=count,
        )
    raw_support = manifest["measurementSupport"] if manifest is not None else {}
    metrics = {}
    for definition in CANONICAL_METRIC_REGISTRY.definitions:
        head, *tail = definition.raw_fields[0].split("_")
        key = f"{definition.source}.{head}{''.join(word.capitalize() for word in tail)}"
        metrics[definition.name] = raw_support.get(key)
    producer = manifest.get("producerVersion") if manifest is not None else None
    if producer is not None and (not isinstance(producer, str) or not producer.strip()):
        raise PixelatedBundleError("declared producerVersion must be a non-empty string or null")
    reasons = []
    browser_rows = source_rows[MetricSource.BROWSER_WEBRTC]
    if browser_validity_reasons(browser_rows, events) or (
        manifest is not None and not summary["validity"]["isValid"]
    ):
        reasons.append("producer_invalid")
    required = {MetricSource.BROWSER_WEBRTC}
    if version == "2" and metadata.get("scenario") != "browser_only_baseline":
        required.update({MetricSource.ENGINE_RUNTIME, MetricSource.ENCODER_PIPELINE})
    if any(sources[source].available_row_count == 0 for source in required):
        reasons.append("required_source_unavailable")
    if any(
        0 < sources[source].available_row_count < sources[source].row_count for source in required
    ):
        reasons.append("source_samples_unavailable")
    return PixelatedAdoptionMetadata(
        run_id=run_id,
        bundle_schema_version=version,
        producer_version=producer.strip() if producer is not None else None,
        effective_settings=MappingProxyType(dict(sorted(settings.items()))),
        sources=MappingProxyType(sources),
        metric_declarations=MappingProxyType(metrics),
        invalid_reason_codes=tuple(reasons),
    )
