"""N6 declarations and pure lineage checks; linked file inspection is separate."""

from .dataset import CalibrationDataset
from .evidence import (
    CalibrationArtifact,
    CalibrationEntry,
    CalibrationSource,
    EvidenceReview,
    SourceBinding,
    SourceEdge,
    SplitAssignment,
    SplitDeclaration,
)
from .lineage import CalibrationLineage, EntryLineage, validate_calibration_lineage
from .report import CalibrationReport

__all__ = [
    "CalibrationDataset",
    "inspect_calibration_dataset",
    "CalibrationLineage",
    "EntryLineage",
    "validate_calibration_lineage",
    "CalibrationReport",
    "CalibrationArtifact",
    "CalibrationSource",
    "CalibrationEntry",
    "EvidenceReview",
    "SourceBinding",
    "SourceEdge",
    "SplitAssignment",
    "SplitDeclaration",
]


def inspect_calibration_dataset(
    directory, *, expected_split_id=None, expected_dataset_content_hash=None
):
    """Lazily inspect bounded local files, keeping model imports free of file I/O."""
    from .inspection import inspect_calibration_dataset as inspect

    return inspect(
        directory,
        expected_split_id=expected_split_id,
        expected_dataset_content_hash=expected_dataset_content_hash,
    )
