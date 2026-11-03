"""Explicit whole-phase source-local adoption, pixelated_bundle_offline / 1.2.0."""

from typing import Literal

from ..analytical.policy_release import payload_hash
from ..models import ContextKey, ProvenanceKind, V2ContextSnapshot, WindowPhase
from ..models.common import NonEmptyStr, NonNegativeFiniteFloat
from ..models.v2_common import ContentHash, V2Model
from .pixelated_bundle_common import PixelatedBundleError
from .pixelated_measurement_samples import load_pixelated_measurement_samples
from .pixelated_observation_v2 import _adopt_samples

METHOD_VERSION = "1.2.0"
TEMPORAL_CONTRACT = "source_local_stable_phase_v1"


class SourceLocalPhaseDeclaration(V2Model):
    schema_version: Literal["source-local-stable-phase-v1"]
    basis: Literal["operator_declared_not_authenticated"]
    phase: Literal["healthy", "degraded", "relief", "recovery"]
    comparison_case_id: NonEmptyStr
    elapsed_start_ms: NonNegativeFiniteFloat
    elapsed_end_ms: NonNegativeFiniteFloat
    evidence_sha256: ContentHash


def ingest_pixelated_source_local(
    bundle_path,
    *,
    context,
    phase,
    comparison_case_id,
    provenance=ProvenanceKind.CONTROLLED_REAL,
    confounder_codes=(),
):
    """Rebuild every source on its full observed span; never crop per metric.

    The phase declaration is explicit external evidence, not authenticated truth.
    This API does not emit a paired response or qualify a passive timing stream.
    """
    try:
        if provenance not in (ProvenanceKind.CONTROLLED_REAL, ProvenanceKind.ORGANIC_REAL):
            raise ValueError("source-local adoption requires real-shaped raw evidence")
        if not isinstance(confounder_codes, (list, tuple)):
            raise ValueError("ordered confounder codes required")
        context = ContextKey.model_validate(context)
        if context.versions.get("pixelatedTemporalContract") != TEMPORAL_CONTRACT:
            raise ValueError("explicit source-local context required")
        snapshot = V2ContextSnapshot.model_validate(context.model_dump(mode="json", by_alias=True))
        phase = WindowPhase(phase)
        raw = load_pixelated_measurement_samples(
            bundle_path,
            context=context,
            phase=phase,
            comparison_case_id=comparison_case_id,
            include_adoption_metadata=True,
        )
        if raw.source_local_phase_json is None or raw.adoption.bundle_schema_version != "2":
            raise ValueError("explicit v2 stable-phase declaration required")
        declaration = SourceLocalPhaseDeclaration.model_validate_json(raw.source_local_phase_json)
        if (
            declaration.phase != ("healthy" if phase is WindowPhase.BASELINE else phase.value)
            or declaration.comparison_case_id != comparison_case_id
            or declaration.elapsed_start_ms != raw.elapsed_start_ms
            or declaration.elapsed_end_ms != raw.elapsed_end_ms
        ):
            raise ValueError("stable declaration must bind the complete phase")
        if not 1000 <= raw.elapsed_end_ms - raw.elapsed_start_ms <= 10000:
            raise ValueError("source-local phase duration outside bounds")
        for series in raw.series.values():
            if len(series.samples) >= 2 and not (
                raw.elapsed_start_ms <= series.samples[0].elapsed_ms
                and series.samples[-1].elapsed_ms <= raw.elapsed_end_ms
                and 1000 <= series.samples[-1].elapsed_ms - series.samples[0].elapsed_ms <= 10000
            ):
                raise ValueError("source-native span outside supported phase/duration")
        digest = payload_hash(
            dict(
                source_hash="sha256:" + raw.checksum,
                method_version=METHOD_VERSION,
                context=snapshot.model_dump(mode="json"),
                phase=phase.value,
                comparison_case_id=comparison_case_id,
                provenance=str(provenance),
                confounder_codes=list(confounder_codes),
            )
        )
        return _adopt_samples(
            raw,
            snapshot,
            phase,
            comparison_case_id,
            provenance,
            tuple(confounder_codes),
            window_id="pixelated-source-local-" + digest[7:],
            method_version=METHOD_VERSION,
            source_local=True,
        )
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise PixelatedBundleError("invalid_pixelated_source_local") from None


__all__ = ["SourceLocalPhaseDeclaration", "ingest_pixelated_source_local"]
