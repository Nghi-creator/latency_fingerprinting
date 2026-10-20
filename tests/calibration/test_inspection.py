"""Linked inspector decisions and CLI behavior, with independently asserted denominators."""

import copy
import json
from dataclasses import FrozenInstanceError

import pytest

from latency_fingerprinting.calibration import inspect_calibration_dataset
from latency_fingerprinting.calibration.records import partition_id
from latency_fingerprinting.cli import main
from latency_fingerprinting.models import AnalyticalResponseV2, ObservationWindowV2

from .cases import canonical, dataset
from .inspection_cases import case, response, write


@pytest.mark.parametrize("healthy", [False, True])
@pytest.mark.parametrize("real", [False, True])
@pytest.mark.parametrize("confirmed", [False, True])
def test_retained_eligibility_and_counts(tmp_path, healthy, real, confirmed):
    p, files = case(healthy=healthy, real=real, confirmed=confirmed)
    result = inspect_calibration_dataset(write(tmp_path, p, files))
    report = result.report
    expected = [] if confirmed else ["retrospective_split", "independence_unverified"]
    if not real:
        expected.append("synthetic_only")
    if not confirmed:
        expected.append("label_unverified")
    assert list(report.entries[0].reason_codes) == expected
    assert report.entries[0].eligible is (not expected)
    assert report.entries[0].eligible_feature_count == (None if healthy else 22)
    assert report.counts.retained_entries == 1
    assert report.counts.retained_groups == 1
    assert report.counts.eligible_entries == report.counts.eligible_groups == int(not expected)
    assert report.counts.by_role.training.retained_entries == 1
    assert len(report.partitions) == 1
    assert report.artifact_receipts == result.dataset.artifacts
    with pytest.raises(FrozenInstanceError):
        result.report = None


def test_missing_only_reason_and_no_partition(tmp_path):
    report = inspect_calibration_dataset(write(tmp_path, dataset(missing=True), {})).report
    assert report.entries[0].reason_codes == ("missing_measurements",)
    assert report.partitions == report.groups == ()
    assert report.counts.retained_entries == report.counts.excluded_entries == 1
    assert report.counts.retained_groups == 0


@pytest.mark.parametrize(
    "cpu,expected",
    [(600_000_000, ("synthetic_only",)), (400_000_000, ("synthetic_only", "effect_unverified"))],
)
def test_controlled_effect_is_recomputed_and_failed_support_retained(tmp_path, cpu, expected):
    p, files = case(controlled=True, confirmed=True, cpu=cpu)
    result = inspect_calibration_dataset(write(tmp_path, p, files))
    assert result.report.entries[0].reason_codes == expected
    assert len(result.artifacts) == 2


@pytest.mark.parametrize("field,value", [("workloadId", "unrelated"), ("encoderFamily", "h264")])
def test_known_experiment_context_mismatch_fails(tmp_path, field, value):
    p, files = case(controlled=True, confirmed=True)
    r = json.loads(files["response-a.json"])
    # Rebuild through the N3 builder after modifying observation context below.
    for window in (r["observation"]["degradedWindow"], r["observation"]["reliefWindow"]):
        window["context"][field] = value
    files["response-a.json"] = rebuild(r)
    with pytest.raises(ValueError, match="^invalid_calibration_dataset$"):
        inspect_calibration_dataset(write(tmp_path, p, files))


def rebuild(r):
    from latency_fingerprinting.analytical.responses import derive_analytical_response
    from latency_fingerprinting.models import FeaturePolicyV1, ObservationRecordV2

    return canonical(
        derive_analytical_response(
            ObservationRecordV2.model_validate(r["observation"]),
            FeaturePolicyV1.model_validate(r["policy"]),
        ).model_dump(mode="json", by_alias=True)
    )


@pytest.mark.parametrize(
    "producer,reason", [(None, ("synthetic_only", "binding_unverified")), ("b" * 40, None)]
)
def test_absent_producer_retains_but_known_wrong_producer_rejects(tmp_path, producer, reason):
    p, files = case(controlled=True, confirmed=True)
    r = json.loads(files["response-a.json"])
    for window in (r["observation"]["degradedWindow"], r["observation"]["reliefWindow"]):
        window["captureMethod"]["producerVersion"] = producer
    files["response-a.json"] = rebuild(r)
    path = write(tmp_path, p, files)
    if reason is None:
        with pytest.raises(ValueError, match="^invalid_calibration_dataset$"):
            inspect_calibration_dataset(path)
    else:
        assert inspect_calibration_dataset(path).report.entries[0].reason_codes == reason


def test_confounded_response_retains_both_reasons(tmp_path):
    p, files = case()
    files["response-a.json"] = canonical(response(confounded=True))
    report = inspect_calibration_dataset(write(tmp_path, p, files)).report
    assert report.entries[0].reason_codes == (
        "retrospective_split",
        "independence_unverified",
        "synthetic_only",
        "confounded_response",
        "insufficient_response_features",
        "label_unverified",
    )
    assert report.entries[0].eligible_feature_count == 0


@pytest.mark.parametrize("healthy", [False, True])
def test_semantic_duplicate_different_json_bytes_is_not_another_sample(tmp_path, healthy):
    p, files = case(healthy=healthy)
    entry = copy.deepcopy(p["entries"][0])
    entry.update(entry_id="entry-b", artifact_id="response-b")
    p["entries"].append(entry)
    artifact = copy.deepcopy(p["artifacts"][0])
    artifact.update(artifact_id="response-b", file_name="response-b.json")
    p["artifacts"].append(artifact)
    files["response-b.json"] = json.dumps(
        json.loads(files["response-a.json"]), separators=(",", ":")
    ).encode()
    report = inspect_calibration_dataset(write(tmp_path, p, files)).report
    assert report.entries[1].representative_entry_id == "entry-a"
    assert report.entries[1].reason_codes[-1] == "duplicate_evidence"
    assert report.counts.retained_entries == 2
    assert report.counts.retained_groups == 1
    assert len(report.partitions) == 1


def test_semantic_duplicate_conflicting_labels_rejected(tmp_path):
    p, files = case()
    e = copy.deepcopy(p["entries"][0])
    e.update(entry_id="entry-b", artifact_id="response-b", label="render_capture_slowdown")
    p["entries"].append(e)
    a = copy.deepcopy(p["artifacts"][0])
    a.update(artifact_id="response-b", file_name="response-b.json")
    p["artifacts"].append(a)
    files["response-b.json"] = files["response-a.json"] + b" "
    with pytest.raises(ValueError, match="^invalid_calibration_dataset$"):
        inspect_calibration_dataset(write(tmp_path, p, files))


def test_partition_projection_has_independent_expected_hash():
    from .cases import digest

    r = AnalyticalResponseV2.model_validate(response())
    w = r.observation.degraded_window
    context = w.context.model_dump(mode="json")
    for key in ("context_id", "node_id", "network_scenario"):
        del context[key]
    expected = dict(
        input_kind="response",
        registry=w.registry.model_dump(mode="json"),
        policy_hash=r.policy.content_hash,
        provenance="synthetic",
        capture_method=dict(
            method_id="synthetic_series", method_version="1.0.0", producer_version=None
        ),
        clock=dict(basis="source_elapsed_ms", provenance="synthetic_elapsed"),
        context=context,
        probe=dict(
            probe_type="stream_profile_relief",
            probe_version="1.0.0",
            application_method="simulated_pair",
            intensity=1.0,
            requested_settings={"targetFps": 30},
            observed_settings=None,
        ),
        effective_settings=dict(degraded={"targetFps": 60}, relief={"targetFps": 30}),
    )
    assert partition_id(r, "response") == "partition-" + digest(expected)


@pytest.mark.parametrize(
    "key,value,same",
    [
        ("run_id", "other", True),
        ("window_id", "other", True),
        ("effective_settings", {"targetFps": 15}, False),
        ("effective_settings", {"targetFps": True}, False),
    ],
)
def test_partition_excludes_acquisition_ids_but_keeps_actual_settings(key, value, same):
    from tests.models.v2_cases import window_payload

    p = window_payload(phase="baseline")
    a = ObservationWindowV2.model_validate(p)
    p[key] = value
    b = ObservationWindowV2.model_validate(p)
    assert (partition_id(a, "healthy_window") == partition_id(b, "healthy_window")) is same


def test_cli_parity_anchors_silent_private_and_repeatable(tmp_path, capsys):
    p, files = case(real=True, confirmed=True)
    path = write(tmp_path / "input", p, files)
    output = tmp_path / "report.json"
    args = [
        "inspect-calibration",
        "--directory",
        str(path),
        "--output",
        str(output),
        "--expected-split-id",
        p["split"]["split_id"],
        "--expected-dataset-content-hash",
        p["content_hash"],
    ]
    assert main(args) == 0
    raw = output.read_bytes()
    assert raw == canonical(inspect_calibration_dataset(path).report.model_dump(mode="json"))
    assert output.stat().st_mode & 0o777 == 0o600
    assert main(args) == 0
    assert output.read_bytes() == raw
    assert capsys.readouterr() == ("", "")
    args[-1] = "sha256:" + "0" * 64
    assert main(args) == 1
    assert output.read_bytes() == raw
    assert capsys.readouterr() == ("", "error: inspect-calibration: invalid_input_or_output\n")


def test_cli_cannot_overwrite_any_input_member(tmp_path, capsys):
    p, files = case()
    write(tmp_path, p, files)
    output = tmp_path / "response-a.json"
    old = output.read_bytes()
    assert main(["inspect-calibration", "--directory", str(tmp_path), "--output", str(output)]) == 1
    assert output.read_bytes() == old
    assert capsys.readouterr() == ("", "error: inspect-calibration: invalid_input_or_output\n")
