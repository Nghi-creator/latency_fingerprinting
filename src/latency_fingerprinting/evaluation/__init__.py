"""Offline N11 evaluation, retaining missing slots and original evidence gates."""

from .contracts import EvaluationManifest, EvaluationReport, seal_manifest

__all__ = [
    "EvaluationManifest",
    "EvaluationReport",
    "EvaluationExecution",
    "seal_manifest",
    "run_evaluation",
    "verify_evaluation_report",
]


def __getattr__(name):
    if name in ("EvaluationExecution", "run_evaluation", "verify_evaluation_report"):
        from . import runner

        return getattr(runner, name)
    raise AttributeError(name)
