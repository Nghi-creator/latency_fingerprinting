"""Raw-linked comparison inputs cannot acquire labels, timing or extra features."""

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from latency_fingerprinting.calibration.contracts import Label
from latency_fingerprinting.evaluation.study.comparison_inputs import (
    inspect_comparison_pair as inspect_pair,
)
from latency_fingerprinting.passive_gating.evidence import bounds
from tests.evaluation.study.test_paired_phase_export import adopt

ROOT = Path("fixtures/paired-phase-v1")


def inspect_comparison_pair(observation, bundles):
    pinned = {
        role: "sha256:" + hashlib.sha256((ROOT / f"{role}.tar").read_bytes()).hexdigest()
        for role in ("degraded", "relief")
    }
    return inspect_pair(observation, bundles, expected_raw_sha256=pinned)


@pytest.fixture
def operands():
    degraded, relief = adopt("degraded"), adopt("relief")
    pair = dict(
        schema_version="observation-v2",
        contract_version="2.0.0",
        observation_id="comparison-input-fixture",
        comparison_case_id=degraded.comparison_case_id,
        degraded_window=degraded.model_dump(mode="json"),
        relief_window=relief.model_dump(mode="json"),
        intervention=dict(
            probe_id="invented-test-declaration",
            probe_type="stream_profile_relief",
            probe_version="1.0.0",
            requested_settings=dict(fps=24, targetFps=24),
            observed_settings=dict(fps=24, targetFps=24),
            intensity=0.2,
            application_method="paired_run",
            execution_status="executed",
            restoration_status="restored",
            degraded_window_id=degraded.window_id,
            relief_window_id=relief.window_id,
            paired_window_order=["degraded", "relief"],
            confounder_codes=[],
        ),
    )
    return json.dumps(pair).encode(), {
        p: (ROOT / f"{p}.tar").read_bytes() for p in ("degraded", "relief")
    }


def test_replay_derives_original_features_and_preserves_comparison_limits(operands):
    observation, bundles = operands
    result = inspect_comparison_pair(observation, bundles)
    expected = json.loads((ROOT / "expectations.json").read_bytes())
    assert result.response.features["encoder.frames_in_rate_fps"].normalized_value == pytest.approx(
        expected["relative_encoder_input_response"]
    )
    assert result.response.features["client.available_incoming_bitrate_kbps"].state == "excluded"
    summary = result.summary()
    assert summary["raw_windows_reproduced"] == 2
    assert summary["feature_count"] == 22
    assert summary["eligible_features"] + summary["excluded_features"] == 22
    assert summary["diagnostic_label"] is None
    assert summary["passive_timing"] == "unavailable_source_local_phase_windows"
    assert summary["comparison_accuracy"] is None


@pytest.mark.parametrize("change", ["missing", "extra", "swapped", "tampered", "not_bytes"])
def test_wrong_or_incomplete_raw_operands_fail(operands, change):
    observation, bundles = operands
    if change == "missing":
        bundles.pop("relief")
    elif change == "extra":
        bundles["healthy"] = bundles["degraded"]
    elif change == "swapped":
        bundles["degraded"], bundles["relief"] = bundles["relief"], bundles["degraded"]
    elif change == "tampered":
        bundles["degraded"] += b"changed"
    else:
        bundles["degraded"] = "not raw bytes"
    with pytest.raises(ValueError, match="invalid_comparison_pair"):
        inspect_comparison_pair(observation, bundles)


def test_structurally_valid_changed_window_must_reproduce_from_raw(operands):
    observation, bundles = operands
    pair = json.loads(observation)
    for role in ("degraded_window", "relief_window"):
        pair[role]["context"]["context_id"] = "edited-context"
    # Context is explicitly supplied to the adopter and is not authenticated by
    # raw replay. A changed measured value, however, must fail reconstruction.
    pair["degraded_window"]["measurements"]["client.received_fps"]["summary"]["value"] = 27
    with pytest.raises(ValueError, match="invalid_comparison_pair"):
        inspect_comparison_pair(json.dumps(pair).encode(), bundles)


def test_duplicate_json_keys_cannot_override_observation(operands):
    observation, bundles = operands
    observation = observation[:-1] + b',"observation_id":"override"}'
    with pytest.raises(ValueError, match="invalid_comparison_pair"):
        inspect_comparison_pair(observation, bundles)


def test_stable_zero_response_remains_eligible(operands):
    result = inspect_comparison_pair(*operands)
    feature = result.response.features["host.camera_cpu_percent"]
    assert feature.state == "eligible"
    assert feature.normalized_value == 0


def test_existing_profile_label_and_passive_clock_limits_are_real(operands):
    result = inspect_comparison_pair(*operands)
    for condition in ("no_injected_fault", "owned_identity_delay", "owned_cpu_pressure"):
        with pytest.raises(ValidationError):
            TypeAdapter(Label).validate_python(condition)
    with pytest.raises(ValueError, match="does not accept source-local"):
        bounds(result.response.observation.degraded_window)
