"""Actual frozen synthetic N6 evidence stays unknown; no model-only positive is relabelled real."""

import copy

import pytest

from latency_fingerprinting.calibration import inspect_calibration_dataset
from latency_fingerprinting.profile_matching import ProfileEvaluationResult, ProfileMatchResult
from latency_fingerprinting.profiles import build_profile_snapshot
from tests.calibration.check_reproduction import FIXTURES
from tests.profiles.cases import policy as profile_policy
from tests.profiles.test_operations import VALID_CASES

from .cases import digest, policy, root_seal


def source(name):
    inspected = inspect_calibration_dataset(FIXTURES / name)
    ev = dict(
        dataset=inspected.dataset.model_dump(mode="json"),
        report=inspected.report.model_dump(mode="json"),
        snapshot=build_profile_snapshot(FIXTURES / name, profile_policy()).model_dump(mode="json"),
    )
    records = {a.artifact_id: a.record for a in inspected.artifacts}
    return ev, records


def unknown(ev, entry, records, fold=False):
    declaration = next(e for e in ev["dataset"]["entries"] if e["entry_id"] == entry["entry_id"])
    reasons = ["snapshot_unavailable"]
    if entry["input_kind"] == "missing":
        reasons.append("missing_measurements")
    else:
        if entry["input_kind"] == "healthy_window":
            reasons.append("baseline_only")
        if entry["role"] not in (("training",) if fold else ("validation", "final_test")):
            reasons.append("not_held_out")
        reasons.append("n6_excluded")
        if entry["representative_entry_id"] != entry["entry_id"]:
            reasons.append("duplicate_evidence")
    identifier = None
    if declaration["artifact_id"] is not None:
        record = records[declaration["artifact_id"]]
        identifier = record.response_id if entry["input_kind"] == "response" else record.window_id
    rows = []
    for profile in ev["snapshot"]["profiles"]:
        codes = ["snapshot_unavailable", "query_unavailable"]
        if profile["partition_id"] != entry["partition_id"]:
            codes.append("partition_mismatch")
        codes.append("profile_rejected")
        rows.append(
            dict(
                profile_id=profile["profile_id"],
                partition_id=profile["partition_id"],
                label=profile["label"],
                state="excluded",
                reason_codes=codes,
                features=None,
                weight_sum=None,
                distance=None,
            )
        )
    return dict(
        query_entry_id=entry["entry_id"],
        query_artifact_id=declaration["artifact_id"],
        query_record_id=identifier,
        query_mode="leave_training_group_out" if fold else "held_out",
        excluded_group_id=entry["group_id"] if fold else None,
        refit_id=None,
        query_feature_values=None,
        candidates=rows,
        common_feature_names=[],
        common_coverage=dict(numerator=0, denominator=22, value=0.0),
        ranked_profile_ids=[],
        best_label=None,
        runner_up_label=None,
        best_distance=None,
        runner_up_distance=None,
        margin=None,
        state="unknown",
        chosen_label=None,
        reason_codes=reasons,
    )


@pytest.mark.parametrize("name", VALID_CASES)
def test_every_actual_synthetic_source_remains_unknown(name):
    ev, records = source(name)
    payload = root_seal(
        dict(
            schema_version="profile-match-result-v1",
            method_release="n8-profile-matching-v1",
            policy=policy(),
            evidence=ev,
            decision=unknown(ev, ev["report"]["entries"][0], records),
            assurance=ev["snapshot"]["assurance"],
        )
    )
    result = ProfileMatchResult.model_validate(payload)
    assert result.model_dump(mode="json") == payload
    assert result.decision.query_feature_values is None
    assert result.decision.chosen_label is None


def test_skipped_refits_are_total_and_keep_failed_groups_in_accuracy_denominator():
    ev, records = source("reviewed-roles")
    entry = next(e for e in ev["report"]["entries"] if e["role"] == "training")
    assert entry["input_kind"] == "response" and entry["label"] == "host_contention"
    assert entry["reason_codes"] == ["synthetic_only"]
    fold = dict(
        excluded_group_id=entry["group_id"],
        state="skipped",
        reason_codes=["snapshot_unavailable", "no_eligible_queries"],
        inputs=None,
        profiles=None,
        counts=None,
    )
    fold["refit_id"] = (
        "profile-refit-"
        + digest(
            dict(
                policy_content_hash=policy()["content_hash"],
                source_report_id=ev["report"]["report_id"],
                snapshot_id=ev["snapshot"]["snapshot_id"],
                refit=fold,
            )
        )[7:]
    )
    labels = ("healthy", "host_contention", "render_capture_slowdown")
    matrix = {
        label: dict.fromkeys((*labels, "unknown"), 0) for label in (*labels, "unverified_truth")
    }
    matrix["host_contention"]["unknown"] = 1
    payload = root_seal(
        dict(
            schema_version="profile-evaluation-result-v1",
            method_release="n8-profile-matching-v1",
            policy=policy(),
            evidence=ev,
            mode="leave_training_group_out",
            refits=[fold],
            decisions=[unknown(ev, entry, records, True)],
            group_outcomes=[
                dict(
                    group_id=entry["group_id"],
                    entry_ids=[entry["entry_id"]],
                    representative_entry_ids=[entry["entry_id"]],
                    truth_label="host_contention",
                    truth_reason_codes=[],
                    predicted_label=None,
                    prediction_reason_codes=["entry_unknown"],
                )
            ],
            confusion_matrix=matrix,
            counts=dict(
                retained_entries=3,
                global_missing_entries=0,
                evaluated_entries=1,
                response_entries=1,
                baseline_entries=0,
                n6_excluded_entries=1,
                duplicate_entries=0,
                classification_groups=1,
                baseline_only_groups=0,
                known_truth_groups=1,
                unverified_truth_groups=0,
                provisional_match_groups=0,
                unknown_groups=1,
                correct_groups=0,
                incorrect_groups=0,
                computed_refits=0,
                skipped_refits=1,
            ),
            metrics=dict(
                accuracy=dict(numerator=0, denominator=1, value=0.0),
                unknown_rate=dict(numerator=1, denominator=1, value=1.0),
                truth_coverage=dict(numerator=1, denominator=1, value=1.0),
            ),
            assurance=ev["snapshot"]["assurance"],
        )
    )
    actual = ProfileEvaluationResult.model_validate(payload)
    assert actual.model_dump(mode="json") == payload
    assert ProfileEvaluationResult.model_validate_json(__import__("json").dumps(payload)) == actual
    changed = copy.deepcopy(payload)
    changed["refits"][0]["inputs"] = []
    with pytest.raises(ValueError):
        ProfileEvaluationResult.model_validate(root_seal(changed))


@pytest.mark.parametrize(
    "name,mode,baseline",
    [("missing", "validation", False), ("baseline", "leave_training_group_out", True)],
)
def test_empty_cohorts_and_baseline_only_groups_keep_null_metrics(name, mode, baseline):
    ev, records = source(name)
    decisions = [unknown(ev, ev["report"]["entries"][0], records, True)] if baseline else []
    fields = (
        "retained_entries",
        "global_missing_entries",
        "evaluated_entries",
        "response_entries",
        "baseline_entries",
        "n6_excluded_entries",
        "duplicate_entries",
        "classification_groups",
        "baseline_only_groups",
        "known_truth_groups",
        "unverified_truth_groups",
        "provisional_match_groups",
        "unknown_groups",
        "correct_groups",
        "incorrect_groups",
        "computed_refits",
        "skipped_refits",
    )
    counts = dict.fromkeys(fields, 0)
    counts.update(
        retained_entries=1,
        global_missing_entries=0 if baseline else 1,
        evaluated_entries=int(baseline),
        baseline_entries=int(baseline),
        n6_excluded_entries=int(baseline),
        baseline_only_groups=int(baseline),
    )
    matrix = {
        label: dict.fromkeys(
            ("healthy", "host_contention", "render_capture_slowdown", "unknown"), 0
        )
        for label in ("healthy", "host_contention", "render_capture_slowdown", "unverified_truth")
    }
    metrics = {
        name: dict(numerator=0, denominator=0, value=None)
        for name in ("accuracy", "unknown_rate", "truth_coverage")
    }
    payload = root_seal(
        dict(
            schema_version="profile-evaluation-result-v1",
            method_release="n8-profile-matching-v1",
            policy=policy(),
            evidence=ev,
            mode=mode,
            refits=[],
            decisions=decisions,
            group_outcomes=[],
            confusion_matrix=matrix,
            counts=counts,
            metrics=metrics,
            assurance=ev["snapshot"]["assurance"],
        )
    )
    result = ProfileEvaluationResult.model_validate(payload)
    assert result.metrics.accuracy.value is None
    assert result.counts.classification_groups == 0
