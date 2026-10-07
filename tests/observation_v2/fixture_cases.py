"""Deterministic software records; adoption provenance is not experiment evidence."""

from pathlib import Path

from latency_fingerprinting.adapters import ingest_pixelated_v2
from latency_fingerprinting.json_io import load_model_file
from latency_fingerprinting.models import ContextKey, ObservationRecordV2, WindowPhase
from latency_fingerprinting.pipeline import canonical_json
from tests.models.v2_cases import pair_payload

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE_DIRECTORY = PROJECT_ROOT / "fixtures/observation-v2"
RAW_FIXTURES = PROJECT_ROOT / "tests/data/pixelated_bundle"


def rendered_fixture_files() -> dict[Path, bytes]:
    """Reconstruct expected records in memory using fixed, sanitized test inputs."""
    records = {}
    for name, bundle, context in (
        ("adopted-browser-v1", "valid", "context.json"),
        ("adopted-engine-v2", "valid-v2", "context-v2.json"),
    ):
        window = ingest_pixelated_v2(
            RAW_FIXTURES / bundle,
            context=load_model_file(RAW_FIXTURES / context, ContextKey),
            phase=WindowPhase.DEGRADED,
            comparison_case_id="controlled-case-001",
        )
        records[Path(f"{name}.json")] = canonical_json(window).encode("utf-8")
    # This records schema/pair compatibility only. No intervention was executed,
    # and the artificial numeric series does not claim a measured relief effect.
    records[Path("synthetic-pair.json")] = canonical_json(
        ObservationRecordV2.model_validate(pair_payload())
    ).encode("utf-8")
    return records


def fixture_drift(directory: Path = DEFAULT_FIXTURE_DIRECTORY) -> dict[Path, str]:
    """Check exact bytes without creating directories or rewriting fixtures."""
    expected = rendered_fixture_files()
    result = {}
    for relative, content in expected.items():
        path = directory / relative
        if not path.is_file():
            result[path] = "missing"
        elif path.read_bytes() != content:
            result[path] = "changed"
    if directory.is_dir():
        for path in directory.glob("*.json"):
            if path.relative_to(directory) not in expected:
                result[path] = "unexpected"
    return result
