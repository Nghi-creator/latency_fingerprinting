#!/usr/bin/env python3
"""Create and verify an exclusive local evidence archive with per-file SHA-256."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import tarfile
from pathlib import Path, PurePosixPath

from latency_fingerprinting.json_io import strict_json_loads


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def archive_name(name: str) -> str:
    parts = PurePosixPath(name)
    if not name or parts.is_absolute() or ".." in parts.parts or "\\" in name:
        raise ValueError("archive names must be relative POSIX paths without traversal")
    if str(parts) != name or name == "MANIFEST.json":
        raise ValueError("noncanonical or reserved archive name")
    return name


def verify_archive(path: Path) -> dict:
    """Verify every member without extracting paths to disk."""
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        names = [m.name for m in members]
        if len(set(names)) != len(names) or names.count("MANIFEST.json") != 1:
            raise ValueError("duplicate members or missing manifest")
        member = archive.getmember("MANIFEST.json")
        if not member.isfile() or member.size > 64 * 1024 * 1024:
            raise ValueError("invalid archive manifest")
        with archive.extractfile(member) as stream:
            manifest = strict_json_loads(stream.read().decode("utf-8"))
        if not isinstance(manifest, dict) or set(names) != set(manifest) | {"MANIFEST.json"}:
            raise ValueError("archive member set differs from manifest")
        for name, expected in manifest.items():
            archive_name(name)
            member = archive.getmember(name)
            if not member.isfile() or member.size != expected["size"]:
                raise ValueError("archive member type or size mismatch")
            with archive.extractfile(member) as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != expected["sha256"]:
                raise ValueError("archive member digest mismatch")
    return dict(
        archive=str(path.resolve()),
        sha256=digest(path),
        bytes=path.stat().st_size,
        verified_files=len(manifest),
        assurance="verified_local_copy_not_remote_backup",
    )


def create_archive(target: Path, includes: dict[str, Path], *, prior=None) -> dict:
    """Include explicitly selected files/directories; optional prior=(path, expected_sha256).

    Symlinks are rejected. Existing archives are never overwritten. A failed archive
    is retained for inspection, and no successful verification receipt is returned.
    """
    files = {}
    if not includes:
        raise ValueError("at least one explicit include required")
    if prior is not None:
        path, expected = prior
        if path.is_symlink() or digest(path) != expected:
            raise ValueError("prior custody digest mismatch")
        name = "prior-custody/" + path.name
        if name in includes:
            raise ValueError("duplicate prior-custody include")
        includes = {**includes, name: path}
    for prefix, source in includes.items():
        archive_name(prefix)
        if source.is_symlink():
            raise ValueError("symlink evidence is not supported")
        if source.is_dir() and target.resolve().is_relative_to(source.resolve()):
            raise ValueError("archive destination must be outside included directories")
        candidates = sorted(source.rglob("*")) if source.is_dir() else [source]
        for candidate in candidates:
            if candidate.is_symlink():
                raise ValueError("symlink evidence is not supported")
            if candidate.is_dir():
                continue
            if not candidate.is_file():
                raise ValueError("regular evidence files required")
            name = prefix
            if source.is_dir():
                name += "/" + candidate.relative_to(source).as_posix()
            archive_name(name)
            if name in files:
                raise ValueError("duplicate archive path")
            files[name] = candidate
    if not files:
        raise ValueError("no evidence files selected")
    manifest = {name: dict(size=p.stat().st_size, sha256=digest(p)) for name, p in files.items()}
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with (
        os.fdopen(descriptor, "wb") as stream,
        tarfile.open(fileobj=stream, mode="w:gz") as archive,
    ):
        payload = (json.dumps(manifest, indent=2) + "\n").encode()
        member = tarfile.TarInfo("MANIFEST.json")
        member.mode, member.size = 0o600, len(payload)
        archive.addfile(member, io.BytesIO(payload))
        for name, source in files.items():
            archive.add(source, arcname=name, recursive=False)
    return verify_archive(target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--include", action="append", default=[], metavar="NAME=PATH")
    parser.add_argument("--prior", type=Path)
    parser.add_argument("--prior-sha256")
    args = parser.parse_args()
    try:
        if args.verify:
            if args.include or args.prior or args.prior_sha256:
                raise ValueError("verification does not accept creation options")
            result = verify_archive(args.archive)
        else:
            includes = {}
            for item in args.include:
                name, separator, path = item.partition("=")
                if not separator or not path or name in includes:
                    raise ValueError("unique NAME=PATH includes required")
                includes[name] = Path(path)
            if bool(args.prior) != bool(args.prior_sha256):
                raise ValueError("prior path and expected SHA-256 must be supplied together")
            prior = (args.prior, args.prior_sha256) if args.prior else None
            result = create_archive(args.archive, includes, prior=prior)
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, KeyError, TypeError, tarfile.TarError) as exc:
        print(f"archive verification failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
