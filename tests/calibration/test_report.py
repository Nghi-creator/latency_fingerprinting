"""Independent report count, role and eligibility consistency checks."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from latency_fingerprinting.calibration import CalibrationReport

from .cases import group_id, report, seal_report


@pytest.mark.parametrize(
    "change",
    [
        "global_count",
        "role_count",
        "partition_count",
        "partition_kind",
        "missing_partition",
        "group_role",
        "group_hash",
        "group_overlap",
        "group_review",
        "duplicate_entries",
        "representative",
        "eligible_bool",
        "eligible_reasons",
        "feature_count",
        "source_order",
        "missing_label",
        "baseline_vector",
        "retrospective",
        "dataset_hash",
    ],
)
def test_forged_report_relations_fail_even_when_report_identity_is_rehashed(change):
    p = report()
    if change == "global_count":
        p["counts"]["eligible_entries"] = 3
    elif change == "role_count":
        p["counts"]["by_role"]["training"]["eligible_entries"] = 1
    elif change == "partition_count":
        p["partitions"][0]["eligible_groups"] = 2
    elif change == "partition_kind":
        p["partitions"][0]["input_kind"] = "healthy_window"
    elif change == "missing_partition":
        p["partitions"].pop()
    elif change == "group_role":
        p["groups"][0]["role"] = "engineering"
    elif change == "group_hash":
        p["groups"][0]["group_id"] = "group-" + "0" * 64
    elif change == "group_overlap":
        first = p["groups"][0]["source_ids"][0]
        p["groups"][1]["source_ids"].append(first)
        p["groups"][1]["source_ids"].sort()
        p["groups"][1]["group_id"] = group_id(p["groups"][1]["source_ids"])
        p["groups"].sort(key=lambda g: g["group_id"])
    elif change == "group_review":
        p["groups"][0]["independence_review_state"] = "uncertain"
    elif change == "duplicate_entries":
        p["entries"].append(deepcopy(p["entries"][-1]))
    elif change == "representative":
        p["entries"][0]["representative_entry_id"] = "missing"
    elif change == "eligible_bool":
        p["entries"][0]["eligible"] = 1
    elif change == "eligible_reasons":
        p["entries"][0]["reason_codes"] = ["label_unverified"]
    elif change == "feature_count":
        p["entries"][0]["eligible_feature_count"] = 16
    elif change == "source_order":
        p["groups"][0]["source_ids"].reverse()
    elif change == "missing_label":
        p["entries"][0]["label"] = None
    elif change == "baseline_vector":
        p["entries"][3]["eligible_feature_count"] = 22
    elif change == "retrospective":
        p["split_mode"] = "retrospective"
    elif change == "dataset_hash":
        p["dataset_content_hash"] = "sha256:" + "0" * 64
    with pytest.raises(ValidationError):
        CalibrationReport.model_validate(seal_report(p))


def test_duplicate_alias_is_retained_without_extra_independent_count():
    p = report()
    duplicate = {
        **p["entries"][0],
        "entry_id": "e6",
        "eligible": False,
        "reason_codes": ["duplicate_evidence"],
        "representative_entry_id": "e1",
    }
    p["entries"].append(duplicate)
    p["counts"].update(retained_entries=6, excluded_entries=2)
    p["counts"]["by_role"]["training"].update(retained_entries=3, excluded_entries=1)
    p["partitions"][0]["retained_entries"] = 4
    result = CalibrationReport.model_validate(seal_report(p))
    assert result.counts.eligible_entries == 4 and result.counts.eligible_groups == 4
    assert result.counts.retained_entries == 6


def test_multiple_windows_in_one_group_do_not_add_independent_support():
    p = report()
    p["entries"].append({**p["entries"][0], "entry_id": "e6", "representative_entry_id": "e6"})
    p["counts"].update(retained_entries=6, eligible_entries=5)
    p["counts"]["by_role"]["training"].update(retained_entries=3, eligible_entries=3)
    p["partitions"][0].update(retained_entries=4, eligible_entries=4)
    result = CalibrationReport.model_validate(seal_report(p))
    assert result.counts.eligible_entries == 5 and result.counts.eligible_groups == 4


@pytest.mark.parametrize(
    "reasons",
    [
        ["duplicate_evidence", "label_unverified"],
        ["label_unverified", "label_unverified"],
        ["unknown"],
    ],
)
def test_exclusion_order_and_vocabulary(reasons):
    p = report()
    p["entries"][0].update(eligible=False, reason_codes=reasons)
    with pytest.raises(ValidationError):
        CalibrationReport.model_validate(seal_report(p))


@pytest.mark.parametrize(
    "field,value",
    [
        ("role", "training"),
        ("group_id", "group-" + "a" * 64),
        ("label", "healthy"),
        ("eligible_feature_count", 0),
    ],
)
def test_missing_measurements_cannot_invent_evidence(field, value):
    p = report()
    p["entries"][-1][field] = value
    with pytest.raises(ValidationError):
        CalibrationReport.model_validate(seal_report(p))


def test_all_missing_report_preserves_global_denominator_without_invented_roles():
    p = report()
    p["groups"], p["partitions"] = [], []
    p["entries"] = [p["entries"][-1]]
    p["counts"].update(
        retained_entries=1,
        eligible_entries=0,
        excluded_entries=1,
        retained_groups=0,
        eligible_groups=0,
    )
    for role in p["counts"]["by_role"]:
        p["counts"]["by_role"][role] = dict(
            retained_entries=0,
            eligible_entries=0,
            excluded_entries=0,
            retained_groups=0,
            eligible_groups=0,
        )
    assert CalibrationReport.model_validate(seal_report(p)).counts.retained_entries == 1


@pytest.mark.parametrize(
    "change",
    ["confounded_features", "freeze_disagreement", "retrospective_freeze", "partition_impossible"],
)
def test_report_cannot_forge_confounded_or_global_split_support(change):
    p = report()
    if change == "confounded_features":
        p["entries"][0].update(eligible=False, reason_codes=["confounded_response"])
    elif change == "freeze_disagreement":
        p["entries"][0].update(eligible=False, reason_codes=["split_unverified"])
    elif change == "retrospective_freeze":
        p["split_mode"] = "retrospective"
        for entry in p["entries"][:-1]:
            entry.update(eligible=False, reason_codes=["retrospective_split", "split_unverified"])
    else:
        p["partitions"][0]["eligible_groups"] = 4
    with pytest.raises(ValidationError):
        CalibrationReport.model_validate(seal_report(p))
