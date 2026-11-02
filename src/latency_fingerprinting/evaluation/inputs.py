"""Pinned receipts and immutable private staging before linked reconstruction."""

import hashlib
import os
from pathlib import Path

from ..adapters.pixelated_archive import bounded_tar_bytes
from ..calibration.bundle_io import MANIFEST, DatasetSnapshot, read_at
from ..profiles.commands import _Operands
from .contracts import MAX_INPUT_BYTES


class _Bytes:
    @staticmethod
    def model_validate_json(raw):
        return raw


class FileOperands(_Operands):
    def _archive(self, path, maximum):
        from ..adapters.pixelated_bundle_io import _open_bundle
        from ..observability.bundle import _read_file

        path = path.absolute()
        parent = _open_bundle(path.parent)
        try:
            descriptor = os.open(
                path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
            )
            try:
                self.names.add(((os.fstat(parent).st_dev, os.fstat(parent).st_ino), path.name))
                self.files.add((os.fstat(descriptor).st_dev, os.fstat(descriptor).st_ino))
                with os.fdopen(descriptor, "rb", closefd=False) as source:
                    return _read_file(source, maximum)
            finally:
                os.close(descriptor)
        finally:
            os.close(parent)


class Inputs(FileOperands):
    def __init__(self, manifest, paths):
        super().__init__()
        self.manifest = manifest
        self.paths = dict(paths) if isinstance(paths, dict) else {}
        self.raw = {}
        self.receipts = {r.receipt_id: r for r in manifest.receipts}
        self.input_bytes = self.decoded_bytes = 0
        if not isinstance(paths, dict) or set(paths) != self.receipts.keys():
            raise ValueError("explicit receipt path map must be exact")
        if sum(r.bytes for r in manifest.receipts) > MAX_INPUT_BYTES:
            raise ValueError("declared evaluation input budget exceeded")
        for receipt in manifest.receipts:
            if receipt.kind == "raw_bundle":
                # The generic JSON operand reader is intentionally capped at 10 MiB.
                # Raw archives use a separate bounded descriptor reader below.
                raw = self._archive(Path(self.paths[receipt.receipt_id]), receipt.bytes)
            else:
                raw = self.read(self.paths[receipt.receipt_id], _Bytes)
            self._charge(raw, archive=receipt.kind == "raw_bundle")
            self._verify(raw, receipt)
            self.raw[receipt.receipt_id] = raw

    @staticmethod
    def _verify(raw, receipt):
        if (
            len(raw) != receipt.bytes
            or "sha256:" + hashlib.sha256(raw).hexdigest() != receipt.sha256
        ):
            raise ValueError("receipt bytes changed")

    def _charge(self, raw, *, archive=False):
        self.input_bytes += len(raw)
        if self.input_bytes > MAX_INPUT_BYTES:
            raise ValueError("evaluation aggregate input bound exceeded")
        decoded = len(raw)
        if archive:
            expanded = bounded_tar_bytes(
                raw,
                declared_limit=min(64 * 1024 * 1024, MAX_INPUT_BYTES - self.decoded_bytes),
                member_limit=256,
            )
            decoded = len(expanded)
        self.decoded_bytes += decoded
        if self.decoded_bytes > MAX_INPUT_BYTES:
            raise ValueError("evaluation decoded aggregate bound exceeded")

    def model(self, identifier, cls):
        return cls.model_validate_json(self.raw[identifier])

    def stage_dataset(self, binding, temporary):
        original = Path(self.paths[binding.manifest_receipt]).absolute()
        if original.name != MANIFEST:
            raise ValueError("dataset operand must name its manifest")
        snapshot = DatasetSnapshot(original.parent)
        try:
            metadata = os.fstat(snapshot.descriptor)
            self.directories.add((metadata.st_dev, metadata.st_ino))
            raw = read_at(snapshot.descriptor, MANIFEST, 10 * 1024 * 1024)
            if raw != self.raw[binding.manifest_receipt]:
                raise ValueError("manifest changed before pinned inspection")
            dataset = snapshot.dataset
            if (dataset.content_hash, dataset.split.split_id) != (
                binding.content_hash,
                binding.split_id,
            ):
                raise ValueError("dataset anchors disagree")
            destination = temporary / binding.dataset_key
            destination.mkdir(mode=0o700)
            (destination / MANIFEST).write_bytes(raw)
            for receipt in dataset.artifacts:
                if self.input_bytes + receipt.bytes > MAX_INPUT_BYTES:
                    raise ValueError("dataset exceeds remaining evaluation input budget")
                raw = snapshot.read(receipt)
                self._verify(raw, receipt)
                self._charge(raw, archive=receipt.kind == "experiment_bundle")
                (destination / receipt.file_name).write_bytes(raw)
            self.files.update(snapshot.file_identities)
            return destination
        finally:
            snapshot.close()
