"""Deterministic synthetic corpus definitions, builders, and rendering."""

from .definitions import (
    FEATURE_BASELINES,
    QUERY_EXPECTATIONS,
    QUERY_VECTORS,
    REFERENCE_VECTORS,
    SYNTHETIC_COMPATIBILITY_GROUP,
)
from .rendering import (
    DEFAULT_FIXTURE_DIRECTORY,
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
