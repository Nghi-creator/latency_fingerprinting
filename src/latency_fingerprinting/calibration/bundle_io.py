"""Pinned flat-directory snapshots for N6; reuse existing no-follow file readers."""

import os
import re
import stat

from ..adapters.pixelated_bundle_io import _open_bundle
from ..observability.bundle import _read_file
from .contracts import AGGREGATE_BYTES, JSON_BYTES
from .dataset import CalibrationDataset

MANIFEST = "calibration-dataset.json"


def inventory(descriptor):
    names = set()
    with os.scandir(descriptor) as entries:
        for entry in entries:
            if (
                len(names) >= 257
                or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\.(json|tar\.gz)", entry.name)
                is None
            ):
                raise ValueError("invalid calibration directory inventory")
            names.add(entry.name)
    return names


def read_at(descriptor, name, maximum, *, identities=None):
    child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
    try:
        if identities is not None:
            metadata = os.fstat(child)
            identities.add((metadata.st_dev, metadata.st_ino))
        with os.fdopen(child, "rb", closefd=False) as source:
            return _read_file(source, maximum)
    finally:
        os.close(child)


class DatasetSnapshot:
    """Own the pinned root for the lifetime of all inventory/relative member reads."""

    def __init__(self, directory):
        self.descriptor = _open_bundle(directory)
        try:
            if not stat.S_ISDIR(os.fstat(self.descriptor).st_mode):
                raise ValueError("calibration input must be a directory")
            self.names = inventory(self.descriptor)
            if MANIFEST not in self.names:
                raise ValueError("calibration manifest missing")
            self.file_identities = set()
            raw = read_at(self.descriptor, MANIFEST, JSON_BYTES, identities=self.file_identities)
            self.dataset = CalibrationDataset.model_validate_json(raw)
            expected = {MANIFEST} | {artifact.file_name for artifact in self.dataset.artifacts}
            if len(expected) != len(self.dataset.artifacts) + 1 or self.names != expected:
                raise ValueError("calibration artifact inventory mismatch")
            self.input_bytes = len(raw)
            self.decoded_bytes = len(raw)
        except BaseException:
            os.close(self.descriptor)
            raise

    def read(self, artifact):
        remaining = AGGREGATE_BYTES - self.input_bytes
        raw = read_at(
            self.descriptor,
            artifact.file_name,
            min(artifact.bytes, remaining),
            identities=self.file_identities,
        )
        self.input_bytes += len(raw)
        return raw

    def close(self):
        try:
            if inventory(self.descriptor) != self.names:
                raise ValueError("calibration inventory changed while reading")
        finally:
            os.close(self.descriptor)
