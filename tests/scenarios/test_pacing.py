"""Independent additive pacing thresholds; no producer exporter or live fault."""

import hashlib
import json

import pytest

from latency_fingerprinting.scenarios import inspect_experiment_bundle
from latency_fingerprinting.scenarios.pacing import ExperimentManifestV2
from tests.scenarios.test_bundle import directory, encoded, members


def pacing_members(delay=50_000_000, recovered=1_000_000, pairs=30, claimed=None):
    files = members()
    manifest = json.loads(files["experiment-manifest.json"])
    manifest.update(
        schema_version="experiment-manifest-v2",
        method_release="n5-capture-pacing-v1",
        scenario="render_capture_slowdown",
        adapter=dict(adapter_id="bounded_capture_pacing", state="available", reason=None),
    )
    manifest["actions"][0].update(kind="capture_pacing", workers=0, delay_us=50000)
    files["experiment-manifest.json"] = encoded(manifest)
    digest = hashlib.sha256(files["experiment-manifest.json"]).hexdigest()
    result = json.loads(files["experiment-result.json"])
    result.update(
        schema_version="experiment-result-v2",
        method_release="n5-capture-pacing-v1",
        manifest_sha256=digest,
    )
    reason = (
        "pacing_not_observed"
        if delay < 41_000_000
        else "recovery_not_observed"
        if recovered > 11_000_000
        else None
    )
    result["effect"].update(
        state="failed" if reason else "verified",
        reason=reason,
        pressure_cpu_percent=None,
        capture_delay_ns=delay,
    )
    if pairs < 30:
        result["effect"] = dict(
            state="unavailable",
            reason="insufficient_evidence",
            healthy_fps=None,
            degraded_fps=None,
            recovery_fps=None,
            pressure_cpu_percent=None,
            capture_delay_ns=None,
        )
    if claimed:
        result["effect"].update(claimed)
    for ref in result["artifacts"]:
        root = json.loads(files[ref["file_name"]])
        if ref["role"] == "phase_evidence":
            root.update(
                schema_version="experiment-phase-evidence-v2",
                method_release="n5-capture-pacing-v1",
                manifest_sha256=digest,
            )
            ref["schema_version"] = root["schema_version"]
            for row in root["intervals"]:
                row.update(active_workers=0, worker_cpu_ns=0)
        else:
            stream = root["streams"][0]
            phase_delay = (
                delay
                if ref["phase"] == "degraded"
                else recovered
                if ref["phase"] == "recovery"
                else 1_000_000
            )
            stream["frames"] = [
                dict(frame_id=f"frame-{i + 1}", source_sequence=i + 1, correlation="exact")
                for i in range(pairs)
            ]
            stream["events"] = [
                dict(
                    frame_id=f"frame-{i + 1}",
                    boundary=boundary,
                    sequence=5 * i + j + 1,
                    timestamp_ns=i * 100_000_000 + offset,
                )
                for i in range(pairs)
                for j, (boundary, offset) in enumerate(
                    zip(
                        (
                            "capture_output",
                            "pre_encode_queue_enter",
                            "pre_encode_queue_exit",
                            "encode_input",
                            "encode_output",
                        ),
                        (
                            0,
                            phase_delay,
                            phase_delay + 1_000_000,
                            phase_delay + 2_000_000,
                            phase_delay + 6_000_000,
                        ),
                        strict=True,
                    )
                )
            ]
            stream["loss"].update(
                offered_frames=pairs,
                sampled_frames=pairs,
                attempted_events=5 * pairs,
                retained_events=5 * pairs,
            )
        payload = encoded(root)
        files[ref["file_name"]] = payload
        ref.update(bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
    files["experiment-result.json"] = encoded(result)
    return files


@pytest.mark.parametrize(
    "delay,recovered,pairs,reason",
    [
        (50_000_000, 1_000_000, 30, None),
        (41_000_000, 11_000_000, 30, None),
        (40_999_999, 1_000_000, 30, "pacing_not_observed"),
        (50_000_000, 11_000_001, 30, "recovery_not_observed"),
        (50_000_000, 1_000_000, 29, "insufficient_evidence"),
    ],
)
def test_independent_pacing_predicates(tmp_path, delay, recovered, pairs, reason):
    inspected = inspect_experiment_bundle(
        directory(tmp_path / "bundle", pacing_members(delay, recovered, pairs))
    )
    assert inspected.effect.reason == reason


def test_requested_sleep_is_not_measured_effect(tmp_path):
    files = pacing_members(1_000_000, claimed=dict(state="verified", reason=None))
    with pytest.raises(ValueError, match="invalid_experiment_bundle"):
        inspect_experiment_bundle(directory(tmp_path / "bundle", files))


@pytest.mark.parametrize(
    "key,value", [("workers", False), ("workers", 1), ("delay_us", 49999), ("kind", "cpu_pressure")]
)
def test_pacing_action_is_strict_and_additive(key, value):
    manifest = json.loads(pacing_members()["experiment-manifest.json"])
    manifest["actions"][0][key] = value
    with pytest.raises(ValueError):
        ExperimentManifestV2.model_validate(manifest)
