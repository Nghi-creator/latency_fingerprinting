#!/usr/bin/env python3
"""Build or verify the sanitized checksum manifest for controlled run 001."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tarfile
from pathlib import Path
from typing import Any

COMPARISON_CASE_ID = "controlled-run-001"
PHASES = ("healthy", "degraded", "relief")
EXPERIMENT_ROOT = Path(__file__).resolve().parent
RAW_ROOT = EXPERIMENT_ROOT / "raw" / "full_data"
MANIFEST_PATH = EXPERIMENT_ROOT / "manifest.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def embedded_manifest(bundle_path: Path) -> dict[str, Any]:
    try:
        with tarfile.open(bundle_path, mode="r:*") as archive:
            member = archive.getmember("bundle-manifest.json")
            if not member.isfile():
                raise ValueError("bundle-manifest.json is not a regular file")
            source = archive.extractfile(member)
            if source is None:
                raise ValueError("bundle-manifest.json could not be read")
            value = json.loads(source.read().decode("utf-8"))
    except (KeyError, OSError, tarfile.TarError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{bundle_path.name}: invalid embedded manifest: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{bundle_path.name}: embedded manifest must be an object")
    return value


def required_manifest_value(
    manifest: dict[str, Any], key: str, expected: object, bundle_path: Path
) -> None:
    if manifest.get(key) != expected:
        raise ValueError(
            f"{bundle_path.name}: embedded {key} must be {expected!r}, got {manifest.get(key)!r}"
        )


def build_manifest() -> dict[str, Any]:
    artifacts: list[dict[str, Any]] = []
    run_id: str | None = None
    for phase in PHASES:
        bundle_path = RAW_ROOT / f"{phase}.tar"
        if not bundle_path.is_file():
            raise ValueError(f"missing required capture: {bundle_path}")
        embedded = embedded_manifest(bundle_path)
        required_manifest_value(embedded, "schemaVersion", 2, bundle_path)
        required_manifest_value(embedded, "comparisonCaseId", COMPARISON_CASE_ID, bundle_path)
        required_manifest_value(embedded, "phase", phase, bundle_path)

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
        "comparisonCaseId": COMPARISON_CASE_ID,
        "hashAlgorithm": "sha256",
        "runId": run_id,
        "schemaVersion": 1,
    }


def render_manifest(manifest: dict[str, Any]) -> str:
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="verify manifest.json")
    mode.add_argument("--write", action="store_true", help="write manifest.json")
    args = parser.parse_args()

    try:
        rendered = render_manifest(build_manifest())
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.check:
        if not MANIFEST_PATH.is_file():
            print(f"missing checksum manifest: {MANIFEST_PATH}", file=sys.stderr)
            return 1
        if MANIFEST_PATH.read_text(encoding="utf-8") != rendered:
            print("manifest.json is stale or the accepted TARs changed", file=sys.stderr)
            return 1
        print("controlled-run-001 checksum manifest is current")
        return 0
    if args.write:
        MANIFEST_PATH.write_text(rendered, encoding="utf-8")
        print(f"wrote {MANIFEST_PATH}")
        return 0

    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
