"""Invented producer phase exports, with independent N1/N2/N3 expectations."""

import hashlib
import json
import tarfile
from pathlib import Path

import pytest

from latency_fingerprinting.adapters import ingest_pixelated_source_local
from latency_fingerprinting.analytical.responses import derive_analytical_response
from latency_fingerprinting.models import ContextKey, FeaturePolicyV1, ObservationRecordV2

ROOT = Path("fixtures/paired-phase-v1")
EXPECTED = json.loads((ROOT / "expectations.json").read_bytes())


def adopt(phase):
    return ingest_pixelated_source_local(
        ROOT / f"{phase}.tar",
        context=ContextKey.model_validate_json((ROOT / f"{phase}-context.json").read_bytes()),
        phase=phase,
        comparison_case_id=EXPECTED["comparison_case_id"],
    )


@pytest.mark.parametrize("phase", ["degraded", "relief", "recovery"])
def test_actual_export_retains_declared_phase_settings_and_raw_hash(phase):
    window = adopt(phase)
    assert window.validity.is_valid
    assert window.phase == phase
    assert window.run_id == EXPECTED["comparison_case_id"] + "-" + phase
    assert window.effective_settings["fps"] == EXPECTED["phase_fps"][phase]
    assert window.effective_settings["targetFps"] == EXPECTED["phase_fps"][phase]
    assert [window.clock.elapsed_start_ms, window.clock.elapsed_end_ms] == EXPECTED[
        "phase_bounds_ms"
    ]
    cpu = window.measurements["host.camera_cpu_percent"].summary
    assert [cpu.window_start_ms, cpu.window_end_ms] == EXPECTED["engine_bounds_ms"]
    assert cpu.value == EXPECTED["camera_cpu_median"]
    assert cpu.coverage == EXPECTED["engine_coverage"]
    assert cpu.source_sample_count == EXPECTED["engine_rows"]
    assert (
        window.measurements["client.frames_decoded_rate_fps"].summary.source_sample_count
        == (EXPECTED["browser_rows"])
    )
    rate = window.measurements["encoder.frames_in_rate_fps"].summary
    assert rate.value == EXPECTED["encoder_input_rate_fps"][phase]
    with tarfile.open(ROOT / f"{phase}.tar") as archive:
        manifest = json.load(archive.extractfile("bundle-manifest.json"))
    assert (
        manifest["sourceLocalPhase"]["evidenceSha256"]
        == "sha256:" + hashlib.sha256((ROOT / f"{phase}-acquisition.json").read_bytes()).hexdigest()
    )


def test_three_phase_exports_support_n2_pair_without_inventing_restoration_or_labels():
    degraded, relief, recovery = (adopt(p) for p in ("degraded", "relief", "recovery"))
    assert degraded.context == relief.context == recovery.context
    changed = sorted(
        k
        for k in degraded.effective_settings
        if degraded.effective_settings[k] != relief.effective_settings[k]
    )
    assert changed == EXPECTED["changed_settings"]
    assert degraded.effective_settings == recovery.effective_settings
    # This intervention declaration is invented test evidence. Exporting recovery
    # does not supply it; a real runtime must independently prove its own outcome.
    pair = ObservationRecordV2.model_validate(
        dict(
            schema_version="observation-v2",
            contract_version="2.0.0",
            observation_id="invented-paired-export-fixture",
            comparison_case_id=EXPECTED["comparison_case_id"],
            degraded_window=degraded,
            relief_window=relief,
            intervention=dict(
                probe_id="invented-cadence-declaration",
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
    )
    policy = FeaturePolicyV1.model_validate_json(
        Path("docs/analysis/N3_FEATURE_POLICY_SPEC.json").read_bytes()
    )
    response = derive_analytical_response(pair, policy)
    feature = response.features["encoder.frames_in_rate_fps"]
    assert feature.state == "eligible"
    assert feature.normalized_value == pytest.approx(EXPECTED["relative_encoder_input_response"])
    assert response.features["client.available_incoming_bitrate_kbps"].state == "excluded"


def test_paired_export_fixture_inventory_is_frozen():
    inventory = (ROOT / "inventory.json").read_bytes()
    assert hashlib.sha256(inventory).hexdigest() == (
        "0213666fcc3729d94fb6f6125ef2d0703302c71c883760c86e80f1332a8418a3"
    )
    hashes = json.loads(inventory)
    assert {p.name for p in ROOT.iterdir()} == {*hashes, "inventory.json"}
    for name, expected in hashes.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
