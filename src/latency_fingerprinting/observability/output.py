"""Atomic local output through pinned no-follow directory descriptors."""

import os
import stat
import uuid
from pathlib import Path

from ..adapters.pixelated_bundle_io import _open_bundle
from ..json_io import MAX_CONTRACT_JSON_BYTES


def write_trace_output(path: Path, payload: bytes):
    if len(payload) > MAX_CONTRACT_JSON_BYTES:
        raise ValueError("trace output exceeds byte limit")
    path = Path(path).absolute()
    parent = _open_bundle(path.parent)
    temporary = f".n4-{uuid.uuid4().hex}.tmp"
    created = False
    try:
        if not stat.S_ISDIR(os.fstat(parent).st_mode):
            raise ValueError("output parent must be a directory")
        try:
            metadata = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            metadata = None
        if metadata is not None and not stat.S_ISREG(metadata.st_mode):
            raise ValueError("output must be a regular file")
        fd = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent,
        )
        created = True
        try:
            with os.fdopen(fd, "wb", closefd=False) as target:
                target.write(payload)
                target.flush()
                os.fsync(target.fileno())
        finally:
            os.close(fd)
        os.replace(temporary, path.name, src_dir_fd=parent, dst_dir_fd=parent)
        created = False
    finally:
        try:
            if created:
                os.unlink(temporary, dir_fd=parent)
        finally:
            os.close(parent)
