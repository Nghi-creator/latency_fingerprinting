"""Total planned denominators, actual linked inspection and hostile custody edits."""

import json
import os
from types import SimpleNamespace

import pytest

from latency_fingerprinting.cli import main
from latency_fingerprinting.evaluation import (
    EvaluationManifest,
    EvaluationReport,
    run_evaluation,
    seal_manifest,
    verify_evaluation_report,
)
from latency_fingerprinting.evaluation.lineage import verify_study_groups
from tests.calibration.cases import group_id

from .support import base, canonical, linked_case, slot


def test_missing_and_failed_slots_remain_in_planned_denominator(tmp_path):
    payload, paths = base(tmp_path)
    payload["slots"] = [slot("a", state="failed"), slot("b", state="not_started")]
    manifest = seal_manifest(payload)
    execution = run_evaluation(manifest, paths)
    result = execution.report
    assert result.counts.planned_slots == result.counts.held_out_slots == 2
    assert result.counts.failed_slots == result.counts.not_started_slots == 1
    assert result.counts.profile_correct.value == 0
    assert result.counts.profile_unknown.value == 1
    assert result.counts.point_unknown.value == 1
    assert [r.slot_id for r in result.rows] == ["a", "b"]
    assert result.rows[0].reason_codes == ("acquisition_failed",)
    assert result.rows[1].reason_codes == ("acquisition_not_started",)
    assert result.empirical_acceptance == "unavailable_not_a_frozen_real_study"
    assert verify_evaluation_report(result, paths) == result
    assert run_evaluation(manifest, paths).report == result
    with pytest.raises(ValueError):
        result.rows[0].point_label = "healthy"


def test_actual_linked_synthetic_sources_stay_unknown_and_unavailable(tmp_path):
    manifest, paths = linked_case(tmp_path)
    result = run_evaluation(manifest, paths)
    assert result.report.counts.planned_slots == 3
    assert result.report.counts.held_out_slots == 2
    assert result.report.counts.profile_unknown.value == 1
    assert result.report.counts.point_unknown.value == 1
    assert len(result.artifacts) == 2
    assert all(row.profile_label is None and row.point_label is None for row in result.report.rows)
    assert sum("raw_sources_unverified" in r.reason_codes for r in result.report.rows) == 2
    assert verify_evaluation_report(result.report, paths) == result.report


@pytest.mark.parametrize(
    "change", ["duplicate_group", "mode", "reorder", "extra_receipt", "alter_hash"]
)
def test_manifest_does_not_silently_accept_unsupported_or_duplicated_design(tmp_path, change):
    payload, _ = base(tmp_path)
    payload["slots"] = [slot("a"), slot("b")]
    if change == "duplicate_group":
        payload["slots"][1]["study_group"] = payload["slots"][0]["study_group"]
    elif change == "mode":
        payload["study_mode"] = "prospective_final"
    elif change == "reorder":
        payload["slots"].reverse()
    elif change == "extra_receipt":
        payload["receipts"].append({**payload["receipts"][0], "receipt_id": "unused"})
    elif change == "alter_hash":
        sealed = seal_manifest(payload).model_dump(mode="json")
        sealed["content_hash"] = "sha256:" + "0" * 64
        with pytest.raises(ValueError):
            EvaluationManifest.model_validate(sealed)
        return
    with pytest.raises(ValueError):
        seal_manifest(payload)


def test_changed_source_and_path_aliases_fail_with_fixed_private_api_error(tmp_path):
    manifest, paths = linked_case(tmp_path)
    target = paths["dataset"].parent / "response-a.json"
    target.write_bytes(target.read_bytes() + b" ")
    with pytest.raises(ValueError, match="^invalid_evaluation$"):
        run_evaluation(manifest, paths)


def test_rehashed_report_denominators_cannot_be_forged(tmp_path):
    from latency_fingerprinting.analytical.policy_release import payload_hash

    payload, paths = base(tmp_path)
    payload["slots"] = [slot("a", state="failed")]
    result = run_evaluation(seal_manifest(payload), paths).report.model_dump(mode="json")
    result["counts"]["held_out_slots"] = 0
    digest = payload_hash(
        {k: v for k, v in result.items() if k not in ("report_id", "content_hash")}
    )
    result.update(content_hash=digest, report_id="evaluation-report-" + digest[7:])
    with pytest.raises(ValueError):
        EvaluationReport.model_validate(result)


def test_cross_dataset_byte_alias_cannot_create_two_independent_groups():
    source = SimpleNamespace(
        source_id="s",
        source_type="pixelated_bundle",
        source_content_hash="sha256:" + "a" * 64,
        acquisition_namespace="one",
        run_id="run",
        session_id="session",
        independence_group="independent",
    )
    group = group_id(["s"])
    inspected = SimpleNamespace(
        dataset=SimpleNamespace(sources=[source]),
        report=SimpleNamespace(
            groups=[SimpleNamespace(group_id=group, source_ids=["s"], role="training")]
        ),
    )
    manifest = SimpleNamespace(
        groups=[
            SimpleNamespace(dataset_key="a", group_id=group, study_group="a"),
            SimpleNamespace(dataset_key="b", group_id=group, study_group="b"),
        ],
        slots=[
            SimpleNamespace(study_group="a", role="training"),
            SimpleNamespace(study_group="b", role="training"),
        ],
    )
    with pytest.raises(ValueError, match="component divided"):
        verify_study_groups(manifest, {"a": inspected, "b": inspected})
    manifest.groups[1].study_group = "a"
    assert len(verify_study_groups(manifest, {"a": inspected, "b": inspected})) == 2


def test_cli_atomic_private_output_and_protected_operands(tmp_path, capsys):
    manifest, paths = linked_case(tmp_path)
    declaration = tmp_path / "manifest.json"
    declaration.write_bytes(canonical(manifest.model_dump(mode="json")))
    operands = tmp_path / "paths.json"
    operands.write_bytes(canonical(dict(paths={k: str(v) for k, v in paths.items()})))
    output = tmp_path / "report.json"
    args = ["evaluate-study", "--manifest", str(declaration), "--operands", str(operands)]
    assert main([*args, "--output", str(output)]) == 0
    assert capsys.readouterr() == ("", "")
    assert output.stat().st_mode & 0o777 == 0o600
    expected = run_evaluation(manifest, paths).report.model_dump(mode="json")
    assert json.loads(output.read_bytes()) == expected
    for path in [declaration, operands, *paths.values(), paths["dataset"].parent / "new.json"]:
        before = path.read_bytes() if path.exists() else None
        assert main([*args, "--output", str(path)]) == 1
        assert capsys.readouterr() == ("", "error: evaluate-study: invalid_input_or_output\n")
        assert (path.read_bytes() if path.exists() else None) == before
    alias = tmp_path / "hardlink"
    os.link(paths["dataset"].parent / "response-a.json", alias)
    assert main([*args, "--output", str(alias)]) == 1
    assert capsys.readouterr() == ("", "error: evaluate-study: invalid_input_or_output\n")
    assert (
        main([*args, "--verify-report", str(output), "--output", str(tmp_path / "verified.json")])
        == 0
    )
    assert capsys.readouterr() == ("", "")
