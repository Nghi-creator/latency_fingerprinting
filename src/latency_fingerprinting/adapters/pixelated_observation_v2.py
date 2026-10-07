"""Deterministic additive observation-v2 adoption from bounded raw Pixelated evidence."""

from collections.abc import Sequence
from pathlib import Path

from ..measurement.aggregation import aggregate_counter, aggregate_gauge
from ..measurement.metric_registry import CANONICAL_METRIC_REGISTRY
from ..measurement.stage_timing import unavailable_stage_timings
from ..models import (
    CaptureMethodReference,
    ContextKey,
    MeasurementSample,
    MetricKind,
    MetricMeasurement,
    MetricSupport,
    ObservationWindowV2,
    ProvenanceKind,
    RegistryReference,
    SourceArtifactV2,
    V2ContextSnapshot,
    WindowClock,
    WindowPhase,
    WindowValidityV2,
)
from ..models.observation_v2 import MISSING_DIAGNOSTIC, PROVENANCE_DIAGNOSTIC, REJECTED_DIAGNOSTIC
from ..models.v2_common import REGISTRY_CONTENT_HASH, ConfounderCode
from ..models.v2_support import resolve_metric_support
from .pixelated_bundle_common import PixelatedBundleError
from .pixelated_measurement_samples import load_pixelated_measurement_samples


def ingest_pixelated_v2(
    bundle_path: Path,
    *,
    context: ContextKey,
    phase: WindowPhase,
    comparison_case_id: str,
    provenance: ProvenanceKind = ProvenanceKind.CONTROLLED_REAL,
    confounder_codes: Sequence[ConfounderCode] = (),
) -> ObservationWindowV2:
    """Read once and publish registered evidence; no P0 aggregate conversion or matching."""
    if provenance not in {ProvenanceKind.CONTROLLED_REAL, ProvenanceKind.ORGANIC_REAL}:
        raise PixelatedBundleError("Pixelated v2 adoption requires real provenance")
    phase = WindowPhase(phase)
    if not isinstance(confounder_codes, (list, tuple)):
        raise PixelatedBundleError("confounder codes must be an ordered list or tuple")
    # Snapshot explicit caller context before file I/O; no mutable caller data survives.
    snapshot = V2ContextSnapshot.model_validate(context.model_dump(mode="json", by_alias=True))
    extraction_context = ContextKey.model_validate(snapshot.model_dump(mode="json", by_alias=True))
    raw = load_pixelated_measurement_samples(
        bundle_path,
        context=extraction_context,
        phase=phase,
        comparison_case_id=comparison_case_id,
        include_adoption_metadata=True,
    )
    metadata = raw.adoption
    if metadata is None:
        raise PixelatedBundleError("adoption metadata is required from the validated raw envelope")
    measurements = {}
    masked = {}
    for definition in CANONICAL_METRIC_REGISTRY.definitions:
        series = raw.series[definition.name]
        declaration = metadata.metric_declarations[definition.name]
        state, basis = resolve_metric_support(metadata.sources[definition.source], declaration)
        samples = series.samples
        if state != "supported":
            key = (definition.source, definition.raw_fields)
            if key not in masked:
                masked[key] = tuple(
                    MeasurementSample(
                        elapsed_ms=row.elapsed_ms,
                        captured_at=row.captured_at,
                        value=None,
                        available=False,
                        source_row=row.source_row,
                        missing_reason=MISSING_DIAGNOSTIC,
                    )
                    for row in samples
                )
            samples = masked[key]
        aggregate = aggregate_gauge if definition.kind is MetricKind.GAUGE else aggregate_counter
        summary = aggregate(
            definition,
            samples,
            window_start_ms=raw.elapsed_start_ms,
            window_end_ms=raw.elapsed_end_ms,
            registry_version=raw.registry_version,
            warnings=raw.warnings,
            source_missing_reason=series.missing_reason,
        )
        safe = summary.model_dump()
        for field, message in (
            ("missing_reasons", MISSING_DIAGNOSTIC),
            ("rejected_reasons", REJECTED_DIAGNOSTIC),
            ("warnings", PROVENANCE_DIAGNOSTIC),
        ):
            safe[field] = (message,) if safe[field] else ()
        measurements[definition.name] = MetricMeasurement(
            role="audit_only"
            if definition.primary_aggregation == "window_total"
            else "analytical_candidate",
            support=MetricSupport(state=state, declared_state=declaration, basis=basis),
            summary=safe,
        )
    return ObservationWindowV2(
        schema_version="observation-window-v2",
        contract_version="2.0.0",
        run_id=metadata.run_id,
        window_id=f"pixelated-v2-{raw.checksum}-{phase.value}",
        comparison_case_id=comparison_case_id,
        context=snapshot,
        phase=phase,
        provenance=provenance,
        registry=RegistryReference(
            registry_version=raw.registry_version, content_hash=REGISTRY_CONTENT_HASH
        ),
        capture_method=CaptureMethodReference(
            method_id="pixelated_bundle_offline",
            method_version="1.0.0",
            producer_version=metadata.producer_version,
        ),
        clock=WindowClock(
            basis="source_elapsed_ms",
            provenance=raw.clock_provenance,
            domain_id=f"pixelated-{raw.checksum}",
            elapsed_start_ms=raw.elapsed_start_ms,
            elapsed_end_ms=raw.elapsed_end_ms,
            duration_ms=raw.elapsed_end_ms - raw.elapsed_start_ms,
            started_at=raw.started_at,
            ended_at=raw.ended_at,
        ),
        source_artifact=SourceArtifactV2(
            source_type="pixelated_bundle",
            content_hash=f"sha256:{raw.checksum}",
            bundle_schema_version=metadata.bundle_schema_version,
        ),
        sources=metadata.sources,
        effective_settings=metadata.effective_settings,
        measurements=measurements,
        validity=WindowValidityV2(
            is_valid=not metadata.invalid_reason_codes, reason_codes=metadata.invalid_reason_codes
        ),
        confounder_codes=tuple(confounder_codes),
        stage_timings=unavailable_stage_timings(metadata.sources),
    )


__all__ = ["ingest_pixelated_v2"]
