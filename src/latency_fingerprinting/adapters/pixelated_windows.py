"""Version 1.1.0: exact-anchor windows on one validated raw Pixelated source."""

from collections.abc import Sequence
from dataclasses import replace
from types import MappingProxyType
from typing import Annotated

from pydantic import Field, model_validator

from ..analytical.policy_release import payload_hash
from ..models import ContextKey, MetricSource, ProvenanceKind, SourceSupport, V2ContextSnapshot
from ..models.common import WindowPhase
from ..models.v2_common import V2Model
from .pixelated_bundle_common import PixelatedBundleError
from .pixelated_measurement_samples import load_pixelated_measurement_samples
from .pixelated_observation_v2 import _adopt_samples

METHOD_VERSION = "1.1.0"
MAX_WINDOWS = 256
Time = Annotated[int, Field(strict=True, ge=0, le=2**53 - 1)]


class WindowBounds(V2Model):
    start_ms: Time
    end_ms: Time

    @model_validator(mode="after")
    def duration(self):
        if not 1000 <= self.end_ms - self.start_ms <= 10000:
            raise ValueError("window duration must be between 1 and 10 seconds")
        return self


def _slice(raw, bounds):
    series = {
        name: replace(
            item,
            samples=tuple(
                s for s in item.samples if bounds.start_ms <= s.elapsed_ms <= bounds.end_ms
            ),
        )
        for name, item in raw.series.items()
    }
    browser = next(s for s in series.values() if s.source == MetricSource.BROWSER_WEBRTC)
    anchors = {s.elapsed_ms: s.captured_at for s in browser.samples}
    if bounds.start_ms not in anchors or bounds.end_ms not in anchors:
        raise ValueError("exact browser boundary anchors are required")
    supports = {}
    for source, original in raw.adoption.sources.items():
        selected = next(s.samples for s in series.values() if s.source == source)
        available = set(raw.available_source_rows[source])
        count = sum(s.source_row in available for s in selected)
        declared = original.declared_state
        if declared in ("unsupported", "unavailable"):
            count = 0
        supports[source] = SourceSupport(
            state=declared or ("supported" if count else "unavailable"),
            declared_state=declared,
            basis="source_declaration"
            if declared
            else "source_rows"
            if selected
            else "source_absent",
            source_file=original.source_file,
            row_count=len(selected),
            available_row_count=count,
        )
    # Retain original invalidity conservatively, including events outside a slice.
    reasons = list(raw.adoption.invalid_reason_codes)
    required = {MetricSource.BROWSER_WEBRTC} | {
        source for source, support in raw.adoption.sources.items() if support.available_row_count
    }
    for code, condition in (
        ("required_source_unavailable", any(not supports[s].available_row_count for s in required)),
        (
            "source_samples_unavailable",
            any(0 < supports[s].available_row_count < supports[s].row_count for s in required),
        ),
    ):
        if condition and code not in reasons:
            reasons.append(code)
    return replace(
        raw,
        started_at=anchors[bounds.start_ms],
        ended_at=anchors[bounds.end_ms],
        elapsed_start_ms=float(bounds.start_ms),
        elapsed_end_ms=float(bounds.end_ms),
        series=MappingProxyType(series),
        adoption=replace(
            raw.adoption, sources=MappingProxyType(supports), invalid_reason_codes=tuple(reasons)
        ),
    )


def ingest_pixelated_windows(
    bundle_path,
    *,
    context,
    phase,
    comparison_case_id,
    windows: Sequence[WindowBounds],
    provenance=ProvenanceKind.CONTROLLED_REAL,
    confounder_codes=(),
):
    """Read once; use closed anchors, counting only intervals inside each slice.

    Adjacent slices can share their boundary *sample*, but never an interval.
    They are correlated observations from one source, not independent trials.
    """
    try:
        if not isinstance(windows, (tuple, list)) or not 1 <= len(windows) <= MAX_WINDOWS:
            raise ValueError("bounded ordered windows required")
        bounds = tuple(WindowBounds.model_validate(w) for w in windows)
        if any(a.end_ms > b.start_ms for a, b in zip(bounds, bounds[1:], strict=False)):
            raise ValueError("windows must be ordered and nonoverlapping")
        if provenance not in (ProvenanceKind.CONTROLLED_REAL, ProvenanceKind.ORGANIC_REAL):
            raise ValueError("raw Pixelated windows require real provenance")
        if not isinstance(confounder_codes, (list, tuple)):
            raise ValueError("ordered confounder codes required")
        confounder_codes = tuple(confounder_codes)
        context = ContextKey.model_validate(context)
        snapshot = V2ContextSnapshot.model_validate(context.model_dump(mode="json", by_alias=True))
        phase = WindowPhase(phase)
        raw = load_pixelated_measurement_samples(
            bundle_path,
            context=ContextKey.model_validate(snapshot.model_dump(mode="json")),
            phase=phase,
            comparison_case_id=comparison_case_id,
            include_adoption_metadata=True,
        )
        result = []
        for window in bounds:
            if window.start_ms < raw.elapsed_start_ms or window.end_ms > raw.elapsed_end_ms:
                raise ValueError("slice outside original source bounds")
            identity = payload_hash(
                dict(
                    source_hash="sha256:" + raw.checksum,
                    method_version=METHOD_VERSION,
                    bounds=window.model_dump(),
                    phase=phase.value,
                    comparison_case_id=comparison_case_id,
                    context=snapshot.model_dump(mode="json"),
                    provenance=str(provenance),
                    confounder_codes=list(confounder_codes),
                )
            )
            result.append(
                _adopt_samples(
                    _slice(raw, window),
                    snapshot,
                    phase,
                    comparison_case_id,
                    provenance,
                    confounder_codes,
                    window_id="pixelated-window-" + identity[7:],
                    method_version=METHOD_VERSION,
                )
            )
        return tuple(result)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise PixelatedBundleError("invalid_pixelated_windows") from None


__all__ = ["WindowBounds", "ingest_pixelated_windows"]
