"""Frozen complete roots plus adversarial changes independent of fixture builders."""

import shutil

import pytest

from latency_fingerprinting.evaluation import (
    EvaluationManifest,
    run_evaluation,
    seal_manifest,
)

from .check_reproduction import FIXTURES, check_reproduction, load_release, operands


def case(tmp_path):
    target = tmp_path / "case"
    shutil.copytree(FIXTURES / "raw-passive", target)
    manifest = EvaluationManifest.model_validate_json((target / "manifest.json").read_bytes())
    return manifest.model_dump(mode="json"), operands(target)


def test_frozen_roots_and_independent_expectations():
    assert check_reproduction() == dict(status="current", cases=4, provenance="software_only")


@pytest.mark.parametrize("change", ["extra", "changed", "missing", "symlink"])
def test_exact_frozen_inventory_rejects_drift(tmp_path, change):
    directory = tmp_path / "fixtures"
    shutil.copytree(FIXTURES, directory)
    target = directory / "raw-passive/manifest.json"
    if change == "extra":
        (directory / "extra").write_bytes(b"extra")
    elif change == "changed":
        target.write_bytes(target.read_bytes() + b"\n")
    elif change == "missing":
        target.unlink()
    else:
        target.unlink()
        target.symlink_to(FIXTURES / "raw-passive/manifest.json")
    with pytest.raises(ValueError):
        load_release(directory)


@pytest.mark.parametrize("change", ["omitted_group", "role_leak", "duplicate_export"])
def test_actual_inspected_groups_cannot_be_omitted_split_or_recounted(tmp_path, change):
    payload, paths = case(tmp_path)
    if change == "omitted_group":
        payload["groups"].pop()
    elif change == "role_leak":
        payload["slots"][1]["role"] = "final_test"
    else:
        # The same inspected dataset under another name is still the same runs.
        dataset = {**payload["datasets"][0], "dataset_key": "z-copy"}
        payload["datasets"].append(dataset)
        for group in list(payload["groups"]):
            alias = "copy-" + group["study_group"]
            payload["groups"].append({**group, "dataset_key": "z-copy", "study_group": alias})
            original = next(s for s in payload["slots"] if s["study_group"] == group["study_group"])
            payload["slots"].append(
                {**original, "slot_id": alias, "study_group": alias, "passive_job": None}
            )
        payload["slots"].sort(key=lambda s: s["slot_id"])
    with pytest.raises(ValueError, match="^invalid_evaluation$"):
        run_evaluation(seal_manifest(payload), paths)


@pytest.mark.parametrize("receipt", ["raw-query", "raw-train-0"])
def test_missing_query_or_training_proof_makes_passive_metric_unavailable(tmp_path, receipt):
    payload, paths = case(tmp_path)
    payload["raw_derivations"] = [
        r for r in payload["raw_derivations"] if r["raw_receipt"] != receipt
    ]
    payload["receipts"] = [r for r in payload["receipts"] if r["receipt_id"] != receipt]
    paths.pop(receipt)
    result = run_evaluation(seal_manifest(payload), paths).report
    assert result.counts.held_out_slots == 1
    assert result.rows[0].passive_state == "unavailable"
    assert result.rows[0].proposals is None
    assert result.rows[0].reason_codes == ("raw_sources_unverified",)


def test_failed_retained_stream_cannot_hide_in_successful_probe_rate(tmp_path):
    payload, paths = case(tmp_path)
    payload["slots"][0].update(state="failed", failure_code="receiver_lost")
    result = run_evaluation(seal_manifest(payload), paths).report
    assert result.counts.failed_slots == result.counts.held_out_slots == 1
    assert result.rows[0].proposals is None
    assert "acquisition_failed" in result.rows[0].reason_codes


def test_rehashed_fake_proposal_cannot_replace_linked_result(tmp_path):
    from latency_fingerprinting.analytical.policy_release import payload_hash
    from latency_fingerprinting.evaluation import EvaluationReport, verify_evaluation_report

    payload, paths = case(tmp_path)
    report = run_evaluation(seal_manifest(payload), paths).report.model_dump(mode="json")
    report["rows"][0].update(proposals=1, first_proposal_ms=5000)
    digest = payload_hash(
        {k: v for k, v in report.items() if k not in ("content_hash", "report_id")}
    )
    report.update(content_hash=digest, report_id="evaluation-report-" + digest[7:])
    # Intrinsic structure is plausible; only linked replay proves it false.
    forged = EvaluationReport.model_validate(report)
    with pytest.raises(ValueError, match="^invalid_evaluation_report$"):
        verify_evaluation_report(forged, paths)


def test_software_fixture_never_accepts_live_bridge_or_final_study(tmp_path):
    payload, _ = case(tmp_path)
    for field, value in (
        ("scope", "integrated_live_response"),
        ("study_mode", "prospective_final"),
    ):
        with pytest.raises(ValueError):
            seal_manifest({**payload, field: value})


def test_declared_truth_cannot_override_reviewed_query_truth():
    source = FIXTURES / "raw-diagnosis"
    manifest = EvaluationManifest.model_validate_json((source / "manifest.json").read_bytes())
    payload = manifest.model_dump(mode="json")
    payload["slots"][-1]["truth_label"] = "render_capture_slowdown"
    with pytest.raises(ValueError, match="^invalid_evaluation$"):
        run_evaluation(seal_manifest(payload), operands(source))


def test_frozen_diagnosis_keeps_insufficient_features_and_original_point_margin():
    from latency_fingerprinting.profiles import ProfileSnapshot

    from .check_reproduction import check_case

    release = load_release()
    execution = check_case(FIXTURES / "raw-diagnosis", release["expectations"]["raw-diagnosis"])
    snapshot = ProfileSnapshot.model_validate_json(
        (FIXTURES / "raw-diagnosis/operands/snapshot.json").read_bytes()
    )
    assert snapshot.profiles[0].state == "rejected"
    assert set(snapshot.profiles[0].reason_codes) == {
        "insufficient_active_features",
        "insufficient_active_coverage",
    }
    points = [
        a for a in execution.artifacts if getattr(a, "schema_version", None) == "match-result-v2"
    ]
    assert len(points) == 1
    assert points[0].unknown_reason == "ambiguous_margin"
    assert len(points[0].repository_references) == 5
