"""Strict detached N5 records; no runtime access or import-time filesystem side effects."""

from .evidence import ExperimentPhaseEvidence
from .manifest import ExperimentManifest
from .result import ExperimentResult

__all__ = [
    "ExperimentManifest",
    "ExperimentPhaseEvidence",
    "ExperimentResult",
    "inspect_experiment_bundle",
]


def inspect_experiment_bundle(path):
    """Load inspection lazily so standalone model imports remain independent."""
    from .inspect import inspect_experiment_bundle as inspect

    return inspect(path)
