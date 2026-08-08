"""Deterministic rendering, export, and drift checks for synthetic fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from .builders import build_fingerprint, build_observation
from .definitions import (
    QUERY_EXPECTATIONS,
    QUERY_VECTORS,
    REFERENCE_VECTORS,
    SYNTHETIC_COMPATIBILITY_GROUP,
    ExpectedDecision,
)
from .expectations import expected_match_result

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FIXTURE_DIRECTORY = PROJECT_ROOT / "fixtures"


def _json(model: BaseModel) -> str:
    payload = model.model_dump(mode="json", by_alias=True)
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _readme(case_name: str, *, reference: bool, expectation: ExpectedDecision | None) -> str:
    role = "reference fingerprint" if reference else "query case"
    expected = (
        f"Expected label: `{expectation.label}`."
        if expectation is not None and expectation.label is not None
        else f"Expected decision: `unknown` ({expectation.unknown_reason.value})."
        if expectation is not None and expectation.unknown_reason is not None
        else "Expected artifact: a synthetic reference fingerprint."
    )
    return f"""# {case_name.replace("_", " ").title()}

This directory is a deterministic synthetic {role} for P0 software testing.
Its values are constructed regression evidence, not engine measurements,
experimental findings or a scientifically validated latency profile.

{expected}

The simulated pair records a declared `stream_profile_relief` change. No live
runtime action or restoration occurred.
"""


def rendered_fixture_files() -> dict[Path, str]:
    """Return all expected fixture files keyed by paths relative to ``fixtures``."""

    files: dict[Path, str] = {}
    for label, vector in REFERENCE_VECTORS.items():
        case_id = f"reference-{label}"
        observation = build_observation(case_id, vector)
        directory = Path("reference_cases") / label
        files[directory / "degraded.json"] = _json(observation.degraded_window)
        files[directory / "relief.json"] = _json(observation.relief_window)
        files[directory / "probe.json"] = _json(observation.probe)
        files[directory / "observation.json"] = _json(observation)
        files[directory / "fingerprint.json"] = _json(build_fingerprint(label, observation))
        files[directory / "README.md"] = _readme(label, reference=True, expectation=None)

    for case_name, vector in QUERY_VECTORS.items():
        compatibility_group = (
            "p0-incompatible-synthetic-v1"
            if case_name == "incompatible_context"
            else SYNTHETIC_COMPATIBILITY_GROUP
        )
        observation = build_observation(
            f"query-{case_name}", vector, compatibility_group=compatibility_group
        )
        directory = Path("query_cases") / case_name
        files[directory / "degraded.json"] = _json(observation.degraded_window)
        files[directory / "relief.json"] = _json(observation.relief_window)
        files[directory / "probe.json"] = _json(observation.probe)
        files[directory / "observation.json"] = _json(observation)
        files[directory / "expected-match-result.json"] = _json(
            expected_match_result(case_name, observation)
        )
        files[directory / "README.md"] = _readme(
            case_name,
            reference=False,
            expectation=QUERY_EXPECTATIONS[case_name],
        )
    return files


def export_fixture_files(
    output_directory: Path = DEFAULT_FIXTURE_DIRECTORY,
) -> tuple[Path, ...]:
    """Write the deterministic fixture corpus and return paths in stable order."""

    rendered = rendered_fixture_files()
    paths = tuple(output_directory / relative_path for relative_path in sorted(rendered))
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered[path.relative_to(output_directory)], encoding="utf-8")
    return paths


def fixture_drift(
    output_directory: Path = DEFAULT_FIXTURE_DIRECTORY,
) -> dict[Path, str]:
    """Return generated fixture files that are missing or out of date."""

    drift: dict[Path, str] = {}
    for relative_path, expected in rendered_fixture_files().items():
        path = output_directory / relative_path
        if not path.is_file() or path.read_text(encoding="utf-8") != expected:
            drift[path] = expected
    return drift


__all__ = [
    "DEFAULT_FIXTURE_DIRECTORY",
    "export_fixture_files",
    "fixture_drift",
    "rendered_fixture_files",
]
