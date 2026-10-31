"""The frozen implementation has one home; shared facilities stay reusable."""

import subprocess
import sys
from pathlib import Path

from latency_fingerprinting import models
from latency_fingerprinting.p0 import models as p0_models
from latency_fingerprinting.p0.synthetic import DEFAULT_FIXTURE_DIRECTORY


def test_public_model_facade_keeps_the_same_p0_classes():
    for name in (
        "ObservationWindow",
        "ObservationRecord",
        "Probe",
        "ResponseDelta",
        "Fingerprint",
        "MatchResult",
        "MatchThresholds",
        "ValidatedOutcome",
    ):
        model = getattr(models, name)
        assert model is getattr(p0_models, name)
        assert model.__module__.startswith("latency_fingerprinting.p0.models.")
    assert models.ContextKey is p0_models.ContextKey
    assert models.ContextKey.__module__ == "latency_fingerprinting.models.context"
    assert models.ObservationWindowV2.__module__ == "latency_fingerprinting.models.observation_v2"


def test_shared_imports_do_not_load_the_p0_pipeline_or_matcher():
    code = """
import sys
import latency_fingerprinting.json_io
import latency_fingerprinting.measurement
import latency_fingerprinting.adapters.pixelated_observation_v2
assert 'latency_fingerprinting.p0.pipeline' not in sys.modules
assert 'latency_fingerprinting.p0.matcher' not in sys.modules
from latency_fingerprinting.adapters import ingest_pixelated_bundle
from latency_fingerprinting.p0.adapters.pixelated_bundle import ingest_pixelated_bundle as p0
assert ingest_pixelated_bundle is p0
"""
    result = subprocess.run(  # noqa: S603 -- fixed script in the current test interpreter
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_synthetic_source_default_still_points_to_the_repository_fixtures():
    assert Path(__file__).resolve().parents[2] / "fixtures" == DEFAULT_FIXTURE_DIRECTORY
