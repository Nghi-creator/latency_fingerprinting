"""Adapters for external telemetry and experiment formats."""

from .pixelated_bundle_common import PixelatedBundleError
from .pixelated_measurement_samples import (
    MetricSampleSeries,
    PixelatedMeasurementSamples,
    load_pixelated_measurement_samples,
)
from .pixelated_observation_v2 import ingest_pixelated_v2
from .pixelated_source_local import ingest_pixelated_source_local
from .pixelated_windows import WindowBounds, ingest_pixelated_windows

__all__ = [
    "PixelatedBundleError",
    "ingest_pixelated_bundle",
    "MetricSampleSeries",
    "PixelatedMeasurementSamples",
    "load_pixelated_measurement_samples",
    "ingest_pixelated_v2",
    "ingest_pixelated_source_local",
    "WindowBounds",
    "ingest_pixelated_windows",
]


def __getattr__(name):
    # Keep the public P0 ingestion import without loading P0 from shared readers.
    if name == "ingest_pixelated_bundle":
        from ..p0.adapters.pixelated_bundle import ingest_pixelated_bundle

        return ingest_pixelated_bundle
    raise AttributeError(name)
