#!/usr/bin/env python3
"""Build or verify a controlled run's sanitized checksum manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tarfile
from pathlib import Path
from typing import Any

from latency_fingerprinting.json_io import strict_json_loads

PHASES = ("healthy", "degraded", "relief")
EXPERIMENT_NAME = re.compile(r"controlled-run-[0-9]{3,}")
MAX_EMBEDDED_MANIFEST_BYTES = 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def embedded_manifest(bundle_path: Path) -> dict[str, Any]:
    try:
        with tarfile.open(bundle_path, mode="r:*") as archive:
            matching_members = [
                member for member in archive.getmembers() if member.name == "bundle-manifest.json"
            ]
            if len(matching_members) != 1:
                raise ValueError("archive must contain exactly one bundle-manifest.json")
            member = matching_members[0]
            if not member.isfile():
                raise ValueError("bundle-manifest.json is not a regular file")
            if member.size > MAX_EMBEDDED_MANIFEST_BYTES:
                raise ValueError("bundle-manifest.json exceeds the 1 MiB safety limit")
            source = archive.extractfile(member)
            if source is None:
                raise ValueError("bundle-manifest.json could not be read")
            value = strict_json_loads(source.read(MAX_EMBEDDED_MANIFEST_BYTES + 1).decode("utf-8"))
    except (KeyError, OSError, tarfile.TarError, UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"{bundle_path.name}: invalid embedded manifest: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{bundle_path.name}: embedded manifest must be an object")
    return value


def require_value(manifest: dict[str, Any], key: str, expected: object, bundle_path: Path) -> None:
    if manifest.get(key) != expected:
        raise ValueError(
            f"{bundle_path.name}: embedded {key} must be {expected!r}, got {manifest.get(key)!r}"
        )


def build_manifest(experiment_root: Path) -> dict[str, Any]:
    comparison_case_id = experiment_root.name
    if EXPERIMENT_NAME.fullmatch(comparison_case_id) is None:
        raise ValueError("experiment directory must be named controlled-run-NNN")

    raw_root = experiment_root / "raw" / "full_data"
    artifacts: list[dict[str, Any]] = []
    run_id: str | None = None
    for phase in PHASES:
        bundle_path = raw_root / f"{phase}.tar"
        if not bundle_path.is_file():
            raise ValueError(f"missing required capture: {bundle_path}")
        embedded = embedded_manifest(bundle_path)
        require_value(embedded, "schemaVersion", 2, bundle_path)
        require_value(embedded, "comparisonCaseId", comparison_case_id, bundle_path)
        require_value(embedded, "phase", phase, bundle_path)

        artifact_run_id = embedded.get("runId")
        if not isinstance(artifact_run_id, str) or not artifact_run_id.strip():
            raise ValueError(f"{bundle_path.name}: embedded runId must be non-empty")
        if run_id is None:
            run_id = artifact_run_id
        elif artifact_run_id != run_id:
            raise ValueError("accepted captures must share one runId")

        created_at = embedded.get("createdAt")
        if not isinstance(created_at, str) or not created_at.strip():
            raise ValueError(f"{bundle_path.name}: embedded createdAt must be non-empty")
        artifacts.append(
            {
                "bundleSchemaVersion": 2,
                "bytes": bundle_path.stat().st_size,
                "capturedAt": created_at,
                "fileName": bundle_path.name,
                "phase": phase,
                "sha256": sha256_file(bundle_path),
            }
        )

    return {
        "artifacts": artifacts,
        "comparisonCaseId": comparison_case_id,
        "hashAlgorithm": "sha256",
        "runId": run_id,
        "schemaVersion": 1,
    }


def render_manifest(manifest: dict[str, Any]) -> str:
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment", type=Path, help="controlled-run-NNN directory")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="verify manifest.json")
    mode.add_argument("--write", action="store_true", help="write manifest.json")
    args = parser.parse_args()

    experiment_root = args.experiment.resolve()
    manifest_path = experiment_root / "manifest.json"
    try:
        rendered = render_manifest(build_manifest(experiment_root))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.check:
        if not manifest_path.is_file():
            print(f"missing checksum manifest: {manifest_path}", file=sys.stderr)
            return 1
        if manifest_path.read_text(encoding="utf-8") != rendered:
            print("manifest.json is stale or the accepted TARs changed", file=sys.stderr)
            return 1
        print(f"{experiment_root.name} checksum manifest is current")
        return 0
    if args.write:
        manifest_path.write_text(rendered, encoding="utf-8")
        print(f"wrote {manifest_path}")
        return 0

    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
