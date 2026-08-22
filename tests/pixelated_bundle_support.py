"""Shared fixtures and file helpers for Pixelated bundle tests."""

from __future__ import annotations

import shutil
import tarfile
from pathlib import Path

import pytest

from latency_fingerprinting.adapters.pixelated_bundle import ingest_pixelated_bundle
from latency_fingerprinting.models import ContextKey, WindowPhase

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = PROJECT_ROOT / "tests" / "data" / "pixelated_bundle"
VALID_BUNDLE = FIXTURE_ROOT / "valid"
VALID_V2_BUNDLE = FIXTURE_ROOT / "valid-v2"


@pytest.fixture
def context() -> ContextKey:
    return ContextKey.model_validate_json(
        (FIXTURE_ROOT / "context.json").read_text(encoding="utf-8")
    )


@pytest.fixture
def context_v2() -> ContextKey:
    return ContextKey.model_validate_json(
        (FIXTURE_ROOT / "context-v2.json").read_text(encoding="utf-8")
    )


def ingest(path: Path, context: ContextKey):
    return ingest_pixelated_bundle(
        path,
        phase=WindowPhase.DEGRADED,
        comparison_case_id="controlled-case-001",
        context=context,
    )


def copy_bundle(
    tmp_path: Path,
    *,
    source: Path = VALID_BUNDLE,
    name: str = "bundle",
) -> Path:
    destination = tmp_path / name
    shutil.copytree(source, destination)
    return destination


def copy_v2_bundle(tmp_path: Path, *, name: str = "bundle-v2") -> Path:
    return copy_bundle(tmp_path, source=VALID_V2_BUNDLE, name=name)


def write_tar(source: Path, destination: Path) -> None:
    with tarfile.open(destination, "w") as archive:
        for path in sorted(source.iterdir()):
            archive.add(path, arcname=path.name)


__all__ = [
    "FIXTURE_ROOT",
    "VALID_BUNDLE",
    "VALID_V2_BUNDLE",
    "context",
    "context_v2",
    "copy_bundle",
    "copy_v2_bundle",
    "ingest",
    "write_tar",
]
