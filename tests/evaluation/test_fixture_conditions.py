"""Invented condition/binding/block declarations; never measured truth or independence."""

import copy
import hashlib
from types import SimpleNamespace

import pytest

from latency_fingerprinting.evaluation import fixture_conditions as method
from latency_fingerprinting.profiles.selection import selection_reasons
from tests.evaluation.test_median_response import response


def digest(value):
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


def slot(identifier, condition, *, relief=(0, 60, 120), missing=False, workload=None):
    record = response(identifier, relief=relief, missing=missing, workload=workload)
    binding = method.declare_fixture_condition_binding(
        record,
        condition=condition,
        witness_acquisition_sha256=digest(identifier + "native"),
        witness_inspection_sha256=digest(identifier + "inspection"),
    )
    return dict(response=record, binding=binding)


def blocks(count=6, *, identical=False, missing=False):
    return {
        f"block-{i}": {
            c: slot(
                f"block-{i}-condition-{j}",
                c,
                relief=(0, 60, 120) if identical else [(0, 60, 120), (0, 30, 60), (0, 0, 0)][j],
                missing=missing,
            )
            for j, c in enumerate(method.CONDITIONS)
        }
        for i in range(count)
    }


def query(**kwargs):
    return response("fresh-query", **kwargs)


def test_complete_correlated_blocks_are_left_out_together_with_exact_thresholds():
    fitted = method.fit_fixture_condition_experiment(blocks())
    assert fitted["state"] == "experimental_calibration_available"
    assert fitted["calibration_block_count"] == 6 and fitted["calibration_query_count"] == 18
    assert fitted["input_provenance_kinds"] == ["synthetic"]
    assert len(fitted["fixed_feature_mask"]) == 22
    assert fitted["thresholds"] == dict(
        class_radius={c: 0.0 for c in method.CONDITIONS}, minimum_gap=0.5
    )
    for fold in fitted["folds"]:
        assert len(fold["training_block_ids"]) == 5
        assert fold["held_out_block_id"] not in fold["training_block_ids"]
        assert [r["condition"] for r in fold["queries"]] == list(method.CONDITIONS)
        assert fold["complete_and_correct"] is True
    assert fitted["accepted_diagnostic_groups"] == 0 and fitted["diagnostic_label"] is None
    assert fitted["acquisition_authority"] is False


def test_separate_block_semantics_do_not_change_legacy_mixed_label_exclusion():
    rows = [
        SimpleNamespace(
            entry_id=c,
            representative_entry_id=c,
            input_kind="response",
            role="training",
            eligible=True,
            label=c,
            partition_id="partition",
            group_id="one-shared-block",
        )
        for c in method.CONDITIONS
    ]
    reasons, mixed = selection_reasons(rows)
    assert len(mixed) == 1 and all(r == ["mixed_group_labels"] for r in reasons.values())
    assert (
        method.fit_fixture_condition_experiment(blocks())["state"]
        == "experimental_calibration_available"
    )


def test_five_blocks_are_insufficient_for_five_group_leave_block_out_support():
    result = method.fit_fixture_condition_experiment(blocks(5))
    assert result["state"] == "unavailable" and result["thresholds"] is None
    assert result["reason_codes"] == ["insufficient_training_blocks"]
    assert result["folds"] == []


def test_missing_slots_stay_retained_and_never_add_a_zero_or_drop_a_block():
    data = blocks()
    data["block-3"][method.CONDITIONS[1]] = None
    result = method.fit_fixture_condition_experiment(data)
    assert result["calibration_block_count"] == 6 and result["state"] == "unavailable"
    assert result["missing_slots"] == [dict(block_id="block-3", condition=method.CONDITIONS[1])]
    assert "incomplete_blocks" in result["reason_codes"] and result["thresholds"] is None


def test_equal_class_centers_retain_every_failed_fold_and_no_calibration():
    result = method.fit_fixture_condition_experiment(blocks(identical=True))
    assert result["state"] == "unavailable" and result["thresholds"] is None
    assert result["reason_codes"] == ["calibration_folds_not_all_uniquely_correct"]
    assert len(result["folds"]) == 6 and result["calibration_query_count"] == 18
    assert all(not fold["complete_and_correct"] for fold in result["folds"])


def test_missing_feature_mask_is_fixed_from_training_support_without_imputation():
    result = method.fit_fixture_condition_experiment(blocks(missing=True))
    assert result["state"] == "unavailable"
    assert result["reason_codes"] == ["insufficient_fixed_features"]
    assert len(result["fixed_feature_mask"]) < 17


@pytest.mark.parametrize(
    "relief,expected",
    [
        ((0, 60, 120), "no_injected_fault"),
        ((0, 30, 60), "owned_identity_delay"),
        ((0, 0, 0), "owned_cpu_pressure"),
    ],
)
def test_query_has_no_truth_input_and_can_only_predict_a_fixture_condition(relief, expected):
    result = method.score_fixture_condition_experiment(
        query(relief=relief), blocks(), query_block_id="new-block"
    )
    assert result["state"] == "experimental_condition_prediction"
    assert result["predicted_condition"] == expected
    assert result["diagnostic_label"] is None and result["confidence"] is None
    assert result["accepted_diagnostic_groups"] == 0 and result["acquisition_authority"] is False


@pytest.mark.parametrize(
    "case,reason",
    [
        ("block", "query_block_overlap"),
        ("source", "query_source_overlap"),
        ("context", "incompatible_query_partition"),
        ("missing", "query_missing_fixed_features"),
        ("outside", "outside_condition_radius"),
        ("tie", "equal_query_distances"),
        ("gap", "insufficient_query_gap"),
        ("insufficient", "calibration_unavailable"),
    ],
)
def test_conservative_query_abstention_never_adapts_the_mask_or_radius(case, reason):
    data = blocks()
    q, block = query(), "new-block"
    if case == "block":
        block = "block-0"
    elif case == "source":
        q = data["block-0"][method.CONDITIONS[0]]["response"]
    elif case == "context":
        q = query(workload="foreign-workload")
    elif case == "missing":
        q = query(missing=True)
    elif case == "outside":
        q = query(relief=(0, 45, 90))
    elif case == "tie":
        q = query(relief=(0, 15, 30))
    elif case == "gap":
        q = query(relief=(0, 48, 96))
    else:
        data = blocks(5)
    result = method.score_fixture_condition_experiment(q, data, query_block_id=block)
    assert result["state"] == "abstain" and result["predicted_condition"] is None
    assert reason in result["reason_codes"]
    assert (
        result["fixed_feature_mask"]
        == method.fit_fixture_condition_experiment(data)["fixed_feature_mask"]
    )


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["block-0"].pop(method.CONDITIONS[0]),
        lambda d: d["block-0"].update(healthy=d["block-0"][method.CONDITIONS[0]]),
        lambda d: d["block-0"][method.CONDITIONS[0]]["binding"].update(condition="healthy"),
        lambda d: d["block-0"][method.CONDITIONS[0]]["binding"].update(response_id="foreign"),
        lambda d: d["block-0"][method.CONDITIONS[0]]["binding"].update(
            witness_acquisition_sha256=None
        ),
        lambda d: d["block-0"][method.CONDITIONS[0]]["binding"].update(extra="field"),
        lambda d: d["block-0"][method.CONDITIONS[0]]["binding"]["source_hashes"].update(
            degraded=digest("foreign")
        ),
        lambda d: d["block-1"][method.CONDITIONS[0]]["binding"].update(
            witness_acquisition_sha256=d["block-0"][method.CONDITIONS[0]]["binding"][
                "witness_acquisition_sha256"
            ]
        ),
        lambda d: d["block-1"][method.CONDITIONS[0]]["binding"].update(
            witness_inspection_sha256=d["block-0"][method.CONDITIONS[0]]["binding"][
                "witness_inspection_sha256"
            ]
        ),
    ],
)
def test_partial_wrong_role_or_foreign_bindings_fail(change):
    data = blocks(2)
    change(data)
    with pytest.raises(ValueError, match=method.ERROR):
        method.fit_fixture_condition_experiment(data)


def test_known_source_or_case_cannot_be_reused_across_conditions_or_blocks():
    data = blocks(2)
    first = data["block-0"][method.CONDITIONS[0]]["response"]
    binding = method.declare_fixture_condition_binding(
        first,
        condition=method.CONDITIONS[1],
        witness_acquisition_sha256=digest("different-native"),
        witness_inspection_sha256=digest("different-inspection"),
    )
    data["block-1"][method.CONDITIONS[1]] = dict(response=first, binding=binding)
    with pytest.raises(ValueError, match=method.ERROR):
        method.fit_fixture_condition_experiment(data)


@pytest.mark.parametrize("data", [{}, {True: {}}, {str(i): {} for i in range(33)}])
def test_block_names_and_counts_are_bounded(data):
    with pytest.raises(ValueError, match=method.ERROR):
        method.fit_fixture_condition_experiment(data)


def test_provenance_changes_pin_the_fit_and_detached_outputs_cannot_change_scoring():
    data = blocks()
    fitted = method.fit_fixture_condition_experiment(data)
    changed = {
        b: {
            c: dict(response=slot["response"], binding=copy.deepcopy(slot["binding"]))
            for c, slot in rows.items()
        }
        for b, rows in data.items()
    }
    changed["block-0"][method.CONDITIONS[0]]["binding"]["witness_inspection_sha256"] = digest(
        "new-inspection"
    )
    assert (
        method.fit_fixture_condition_experiment(changed)["experiment_id"] != fitted["experiment_id"]
    )
    fitted["thresholds"]["class_radius"][method.CONDITIONS[0]] = 1.0
    fitted["method_spec"]["conditions"].clear()
    result = method.score_fixture_condition_experiment(
        query(relief=(0, 48, 96)), data, query_block_id="new-block"
    )
    assert result["state"] == "abstain"
    assert method.fixture_condition_method_spec()["conditions"] == list(method.CONDITIONS)


def test_method_spec_drift_is_rejected(monkeypatch):
    monkeypatch.setitem(method._METHOD, "minimum_training_blocks", 1)
    with pytest.raises(ValueError, match=method.ERROR):
        method.fit_fixture_condition_experiment(blocks(1))


def test_one_bad_block_is_retained_and_prevents_calibration():
    data = blocks()
    c = method.CONDITIONS[0]
    data["block-5"][c] = slot("one-bad-block", c, relief=(0, 30, 60))
    fitted = method.fit_fixture_condition_experiment(data)
    assert fitted["state"] == "unavailable" and fitted["thresholds"] is None
    assert len(fitted["folds"]) == 6 and fitted["calibration_query_count"] == 18
    assert [f["held_out_block_id"] for f in fitted["folds"] if not f["complete_and_correct"]] == [
        "block-5"
    ]
