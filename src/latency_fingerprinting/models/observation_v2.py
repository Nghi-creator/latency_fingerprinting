"""Registry-bound standalone N2 windows; no normalization or matcher adoption."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal

from pydantic import FieldSerializationInfo, field_serializer, field_validator, model_validator

from .common import NonEmptyStr, ProvenanceKind, WindowPhase
from .measurement import (
    AggregationKind,
    MetricKind,
    MetricSeriesStatus,
    MetricSeriesSummary,
    MetricSource,
)
from .v2_common import (
    CaptureMethodReference,
    ConfounderCode,
    ImmutableJSONMap,
    RegistryReference,
    SourceArtifactV2,
    V2ContextSnapshot,
    V2Model,
    trusted_registry,
)
from .v2_support import (
    MetricSupport,
    SourceSupport,
    StageTiming,
    WindowClock,
    WindowValidityV2,
    resolve_metric_support,
)

MISSING_DIAGNOSTIC = "Missing source evidence."
REJECTED_DIAGNOSTIC = "Rejected source evidence."
PROVENANCE_DIAGNOSTIC = "Measurement provenance requires review."


class MetricMeasurement(V2Model):
    role: Literal["analytical_candidate", "audit_only"]
    support: MetricSupport
    summary: MetricSeriesSummary

    @model_validator(mode="after")
    def validate_evidence(self):
        summary = self.summary
        for reasons, allowed in (
            (summary.missing_reasons, MISSING_DIAGNOSTIC),
            (summary.rejected_reasons, REJECTED_DIAGNOSTIC),
            (summary.warnings, PROVENANCE_DIAGNOSTIC),
        ):
            if any(reason != allowed for reason in reasons):
                raise ValueError("summary diagnostic is outside the safe vocabulary")
        if self.support.state != "supported" and (
            summary.status is not MetricSeriesStatus.MISSING
            or summary.usable_sample_count
            or summary.aggregates
            or summary.counter_intervals
            or summary.observed_duration_ms
            or summary.coverage
        ):
            raise ValueError("unsupported/unavailable metrics must have missing evidence")
        return self


def _validate_registered_summary(summary, definition, registry, clock):
    fields = (
        "semantic_version",
        "source",
        "raw_fields",
        "kind",
        "canonical_unit",
        "primary_aggregation",
        "available_aggregations",
        "clock_basis",
    )
    if summary.registry_version != registry.registry_version or any(
        getattr(summary, field) != getattr(definition, field) for field in fields
    ):
        raise ValueError("summary meaning must match its trusted registry definition")
    if (
        summary.window_start_ms != clock.elapsed_start_ms
        or summary.window_end_ms != clock.elapsed_end_ms
        or summary.window_duration_ms != clock.duration_ms
        or summary.clock_basis != clock.basis
    ):
        raise ValueError("summary bounds/clock must match its window")
    if definition.non_negative and any(value < 0 for value in summary.aggregates.values()):
        raise ValueError("registered output cannot contain negative aggregates")
    if definition.kind is MetricKind.GAUGE:
        ordered = [
            summary.aggregates[aggregation]
            for aggregation in (
                AggregationKind.MINIMUM,
                AggregationKind.MEDIAN,
                AggregationKind.NEAREST_RANK_P95,
                AggregationKind.MAXIMUM,
            )
            if aggregation in summary.aggregates
        ]
        if ordered != sorted(ordered):
            raise ValueError("gauge statistics must be ordered")
    else:
        reset_rows = set(summary.reset_source_rows)
        if any(
            interval.wrapped or interval.end_source_row in reset_rows
            for interval in summary.counter_intervals
        ):
            # The only trusted release declares reject_segment without wrap widths.
            raise ValueError("canonical reset transitions cannot be accepted or wrapped")


class ObservationWindowV2(V2Model):
    schema_version: Literal["observation-window-v2"]
    contract_version: Literal["2.0.0"]
    run_id: NonEmptyStr
    window_id: NonEmptyStr
    comparison_case_id: NonEmptyStr
    context: V2ContextSnapshot
    phase: WindowPhase
    provenance: ProvenanceKind
    registry: RegistryReference
    capture_method: CaptureMethodReference
    clock: WindowClock
    source_artifact: SourceArtifactV2
    sources: Mapping[MetricSource, SourceSupport]
    effective_settings: ImmutableJSONMap
    measurements: Mapping[NonEmptyStr, MetricMeasurement]
    validity: WindowValidityV2
    confounder_codes: tuple[ConfounderCode, ...] = ()
    stage_timings: tuple[StageTiming, ...] = ()

    @field_validator("sources", "measurements", mode="after")
    @classmethod
    def freeze_maps(cls, value):
        return MappingProxyType(dict(sorted(value.items())))

    @field_serializer("sources", "measurements")
    def serialize_maps(self, value, info: FieldSerializationInfo):
        return {
            str(key): item.model_dump(mode=info.mode, by_alias=info.by_alias)
            for key, item in value.items()
        }

    @model_validator(mode="after")
    def validate_window(self):
        if not self.effective_settings:
            raise ValueError("effective settings cannot be empty")
        synthetic = self.provenance is ProvenanceKind.SYNTHETIC
        method = "synthetic_series" if synthetic else "pixelated_bundle_offline"
        source_type = "synthetic_series" if synthetic else "pixelated_bundle"
        clock_provenance = "synthetic_elapsed" if synthetic else "wall_clock_derived_elapsed"
        if (
            self.capture_method.method_id != method
            or self.source_artifact.source_type != source_type
            or self.clock.provenance != clock_provenance
        ):
            raise ValueError("provenance, capture method, artifact and clock must agree")
        if not synthetic and self.context.versions.get("pixelatedBundleSchema") != (
            self.source_artifact.bundle_schema_version
        ):
            raise ValueError("context and artifact bundle versions must match")
        if set(self.sources) != set(MetricSource):
            raise ValueError("all three source support records are required")
        for source, support in self.sources.items():
            expected_file = (
                None
                if synthetic
                else (
                    "stream-telemetry.csv"
                    if source is MetricSource.BROWSER_WEBRTC
                    else "engine-telemetry.csv"
                )
            )
            if support.source_file != expected_file:
                raise ValueError("source file must match the source/provenance")
        definitions = {item.name: item for item in trusted_registry().definitions}
        if set(self.measurements) != set(definitions):
            raise ValueError("measurements must contain exactly the 31 registered outputs")
        counter_groups = {}
        for name, measurement in self.measurements.items():
            summary = measurement.summary
            definition = definitions[name]
            if summary.metric_name != name:
                raise ValueError("measurement map key must equal summary metric name")
            _validate_registered_summary(summary, definition, self.registry, self.clock)
            source = self.sources[definition.source]
            if summary.source_sample_count != source.row_count or summary.usable_sample_count > (
                source.available_row_count
            ):
                raise ValueError("summary sample counts must agree with source availability")
            state, basis = resolve_metric_support(source, measurement.support.declared_state)
            if measurement.support.state != state or measurement.support.basis != basis:
                raise ValueError("metric support must follow typed declaration precedence")
            expected_role = (
                "audit_only"
                if definition.primary_aggregation is (AggregationKind.WINDOW_TOTAL)
                else "analytical_candidate"
            )
            if measurement.role != expected_role:
                raise ValueError("measurement role must match the registered aggregation")
            if definition.kind is MetricKind.CUMULATIVE_COUNTER:
                evidence = (
                    measurement.support,
                    summary.source_sample_count,
                    summary.usable_sample_count,
                    summary.usable_source_rows,
                    summary.counter_intervals,
                    summary.reset_source_rows,
                    summary.gap_source_rows,
                    summary.observed_duration_ms,
                    summary.coverage,
                    summary.status,
                    summary.missing_reasons,
                    summary.rejected_reasons,
                )
                key = (definition.source, definition.raw_fields)
                if key in counter_groups and counter_groups[key] != evidence:
                    raise ValueError("counter rate/total outputs must retain identical evidence")
                counter_groups[key] = evidence
        if len(set(self.confounder_codes)) != len(self.confounder_codes):
            raise ValueError("confounder codes cannot contain duplicates")
        stages = [timing.stage for timing in self.stage_timings]
        if len(set(stages)) != len(stages):
            raise ValueError("stage timings cannot contain duplicate stages")
        for timing in self.stage_timings:
            source_state = self.sources[timing.source].state
            if timing.reason_code == "unsupported_source" and source_state != "unsupported":
                raise ValueError("timing reason must match source support")
            if timing.reason_code == "source_unavailable" and source_state != "unavailable":
                raise ValueError("timing reason must match source support")
        return self
