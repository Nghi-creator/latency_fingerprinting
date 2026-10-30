"""Known artifact aliases, frozen replay anchors and duplicate label consistency."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from latency_fingerprinting.calibration import validate_calibration_lineage
from latency_fingerprinting.calibration.report import CalibrationReport

from .cases import dataset, report, seal_dataset, seal_report
from .lineage_cases import payload


def aliases(count=2):
    p = payload([["source-a", "source-b"] for _ in range(count)], [["source-a", "source-b"]])
    for index in range(1, count):
        p["artifacts"][index]["sha256"] = p["artifacts"][0]["sha256"]
        p["entries"][index]["source_bindings"] = deepcopy(p["entries"][0]["source_bindings"])
    return seal_dataset(p)


def test_byte_identical_exports_keep_lexical_representative_without_extra_repetition():
    result = validate_calibration_lineage(aliases())
    assert len(result.groups) == 1
    assert [e.representative_entry_id for e in result.entries] == ["entry-000", "entry-000"]


@pytest.mark.parametrize("change", ["label", "binding", "bytes", "kind"])
def test_same_declared_bytes_cannot_have_conflicting_claims(change):
    p = aliases()
    if change == "label":
        p["entries"][1]["label"] = "render_capture_slowdown"
    elif change == "binding":
        p["entries"][1]["source_bindings"][0]["window_id"] = "other-window"
    elif change == "bytes":
        p["artifacts"][1]["bytes"] += 1
    else:
        p["artifacts"][1]["kind"] = "observation_window"
        p["entries"][1].update(
            input_kind="healthy_window",
            label="healthy",
            source_bindings=[dict(window_role="healthy", source_id="source-a", window_id="w")],
        )
    with pytest.raises(ValueError, match="^invalid_calibration_lineage$"):
        validate_calibration_lineage(seal_dataset(p))


def test_unknown_first_alias_does_not_hide_conflicting_later_nonnull_labels():
    p = aliases(3)
    p["entries"][0].update(label=None, label_basis="unknown")
    assert [
        e.representative_entry_id for e in validate_calibration_lineage(seal_dataset(p)).entries
    ] == ["entry-000"] * 3
    p["entries"][2]["label"] = "render_capture_slowdown"
    with pytest.raises(ValueError, match="^invalid_calibration_lineage$"):
        validate_calibration_lineage(seal_dataset(p))


def test_window_ids_are_local_not_proof_of_correlation_or_independence():
    p = payload([["source-a"], ["source-b"]], [["source-a"], ["source-b"]])
    for entry in p["entries"]:
        entry["source_bindings"][0]["window_id"] = "same-local-window"
    result = validate_calibration_lineage(seal_dataset(p))
    assert len(result.groups) == 2
    assert all(g.independence_review_state == "missing" for g in result.groups)


def test_replay_anchors_reject_reassigned_roles_and_changed_source_receipts():
    p = dataset()
    split, receipt = p["split"]["split_id"], p["content_hash"]
    validate_calibration_lineage(p, expected_split_id=split, expected_dataset_content_hash=receipt)
    p["split"]["assignments"][0]["role"] = "final_test"
    seal_dataset(p)
    with pytest.raises(ValueError, match="^invalid_calibration_lineage$"):
        validate_calibration_lineage(p, expected_split_id=split)
    p["split"]["assignments"][0]["role"] = "training"
    p["artifacts"][0]["sha256"] = "sha256:" + "0" * 64
    seal_dataset(p)
    # Frozen role assignment is unchanged, but this is not the original dataset snapshot.
    assert validate_calibration_lineage(p, expected_split_id=split)
    with pytest.raises(ValueError, match="^invalid_calibration_lineage$"):
        validate_calibration_lineage(p, expected_dataset_content_hash=receipt)
    with pytest.raises(ValueError, match="^invalid_calibration_lineage$"):
        validate_calibration_lineage(p, expected_split_id=True)


def report_with_unknown_representative():
    p = report()
    p["entries"][0].update(label=None, eligible=False, reason_codes=["label_unverified"])
    p["entries"].append(
        {
            **p["entries"][0],
            "entry_id": "e6",
            "label": "host_contention",
            "reason_codes": ["duplicate_evidence"],
            "representative_entry_id": "e1",
        }
    )
    p["counts"].update(
        retained_entries=6, eligible_entries=3, excluded_entries=3, eligible_groups=3
    )
    p["counts"]["by_role"]["training"].update(
        retained_entries=3, eligible_entries=1, excluded_entries=2, eligible_groups=1
    )
    p["partitions"][0].update(retained_entries=4, eligible_entries=2, eligible_groups=2)
    return seal_report(p)


def test_report_preserves_unknown_representative_without_transferring_its_alias_label():
    result = CalibrationReport.model_validate(report_with_unknown_representative())
    assert result.entries[0].label is None and not result.entries[0].eligible
    assert result.entries[-1].representative_entry_id == "e1"
    assert result.counts.eligible_entries == 3


def test_report_rejects_conflicting_nonnull_labels_even_when_representative_is_unknown():
    p = report_with_unknown_representative()
    p["entries"].append({**p["entries"][-1], "entry_id": "e7", "label": "render_capture_slowdown"})
    with pytest.raises(ValidationError, match="conflicting nonnull labels"):
        CalibrationReport.model_validate(seal_report(p))
