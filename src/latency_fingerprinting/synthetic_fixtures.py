"""Compatibility façade for the split synthetic fixture generator."""

from .synthetic import (
    DEFAULT_FIXTURE_DIRECTORY,
    FEATURE_BASELINES,
    QUERY_EXPECTATIONS,
    QUERY_VECTORS,
    REFERENCE_VECTORS,
    SYNTHETIC_COMPATIBILITY_GROUP,
    export_fixture_files,
    fixture_drift,
    rendered_fixture_files,
)

__all__ = [
    "DEFAULT_FIXTURE_DIRECTORY",
    "FEATURE_BASELINES",
    "QUERY_EXPECTATIONS",
    "QUERY_VECTORS",
    "REFERENCE_VECTORS",
    "SYNTHETIC_COMPATIBILITY_GROUP",
    "export_fixture_files",
    "fixture_drift",
    "rendered_fixture_files",
]
