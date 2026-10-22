"""Linked inspection, training verification and source extraction; positives are model-only."""

import copy
from types import SimpleNamespace

import pytest

from latency_fingerprinting.calibration import CalibrationDataset, CalibrationReport
from latency_fingerprinting.calibration.inspection import InspectedCalibration, ValidatedArtifact
from latency_fingerprinting.profile_matching import (
    evaluate_profile_snapshot,
    match_profile_snapshot,
    operations,
)
from latency_fingerprinting.profiles import create_profile_snapshot, transition_profile_snapshot
from tests.calibration.check_reproduction import FIXTURES
from tests.profiles.cases import NAMES, seal
from tests.profiles.test_operations import VALID_CASES, review

from .cases import canonical, evaluation, match, policy
from .test_synthetic_inputs import source, unknown


def artificial_inspection(monkeypatch, ev, *, query_value=None):
    """Fake the inspection boundary explicitly; never label these as real acquisitions."""
    n = ev["snapshot"]["counts"]["selected_entries"] // 2
    records = []
    values = {row["entry_id"]: row["feature_values"] for row in ev["snapshot"]["inputs"]}
    for declaration in ev["dataset"]["entries"]:
        vector = values[declaration["entry_id"]]
        if vector is None:
            vector = dict.fromkeys(
                NAMES, query_value if query_value is not None else (2.0 if n == 5 else 2.5)
            )
        record = SimpleNamespace(
            response_id="response-v2-" + "e" * 64,
            policy=SimpleNamespace(content_hash=ev["snapshot"]["policy"]["response_policy_hash"]),
            observation=SimpleNamespace(
                degraded_window=SimpleNamespace(
                    registry=SimpleNamespace(
                        model_dump=lambda **kw: ev["snapshot"]["policy"]["registry"]
                    )
                )
            ),
            features={
                name: SimpleNamespace(state="eligible", normalized_value=v)
                for name, v in vector.items()
            },
        )
        records.append(ValidatedArtifact(declaration["artifact_id"], record))
    inspected = InspectedCalibration(
        CalibrationDataset.model_validate(ev["dataset"]),
        CalibrationReport.model_validate(ev["report"]),
        tuple(records),
    )
    calls = []

    def inspect(directory, **anchors):
        calls.append((directory, anchors))
        return inspected, (10, 20)

    monkeypatch.setattr(operations, "_inspect_calibration_snapshot", inspect)
    return inspected, calls


@pytest.mark.parametrize("n", [5, 6])
def test_one_inspection_matches_independent_positive_and_exact_anchors(monkeypatch, n):
    expected = match(n)
    ev = expected["evidence"]
    _, calls = artificial_inspection(monkeypatch, ev)
    result = match_profile_snapshot(
        "model-only",
        ev["snapshot"],
        policy(),
        query_entry_id=expected["decision"]["query_entry_id"],
        expected_split_id=ev["report"]["split_id"],
        expected_dataset_content_hash=ev["dataset"]["content_hash"],
    )
    assert canonical(result.model_dump(mode="json")) == canonical(expected)
    assert calls == [
        (
            "model-only",
            dict(
                expected_split_id=ev["report"]["split_id"],
                expected_dataset_content_hash=ev["dataset"]["content_hash"],
            ),
        )
    ]


@pytest.mark.parametrize(
    "mode,n",
    [
        ("validation", 5),
        ("final_test", 5),
        ("leave_training_group_out", 5),
        ("leave_training_group_out", 6),
    ],
)
def test_evaluations_refit_whole_groups_against_independent_oracle(monkeypatch, mode, n):
    expected = evaluation(mode, n)
    ev = expected["evidence"]
    _, calls = artificial_inspection(monkeypatch, ev)
    result = evaluate_profile_snapshot("model-only", ev["snapshot"], policy(), mode=mode)
    assert canonical(result.model_dump(mode="json")) == canonical(expected)
    assert len(calls) == 1
    assert ev == expected["evidence"]


@pytest.mark.parametrize("case", VALID_CASES)
def test_actual_sources_use_real_record_ids_and_never_resurrect_synthetic_evidence(case):
    ev, records = source(case)
    for entry in ev["report"]["entries"]:
        result = match_profile_snapshot(
            FIXTURES / case, ev["snapshot"], policy(), query_entry_id=entry["entry_id"]
        )
        assert result.decision.model_dump(mode="json") == unknown(ev, entry, records)
    for mode in ("validation", "final_test", "leave_training_group_out"):
        result = evaluate_profile_snapshot(FIXTURES / case, ev["snapshot"], policy(), mode=mode)
        assert all(
            d.state == "unknown" and d.query_feature_values is None for d in result.decisions
        )
        assert result.counts.provisional_match_groups == 0


def test_fresh_query_values_are_extracted_instead_of_supplied_snapshot_values(monkeypatch):
    expected = match()
    ev = expected["evidence"]
    artificial_inspection(monkeypatch, ev, query_value=6.0)
    result = match_profile_snapshot(
        "model-only",
        ev["snapshot"],
        policy(),
        query_entry_id=expected["decision"]["query_entry_id"],
    )
    assert result.decision.chosen_label == "host_contention"
    assert set(result.decision.query_feature_values.values()) == {6.0}


@pytest.mark.parametrize("field", ["policy", "registry", "training_value"])
def test_actual_source_disagreement_rejects_built_snapshot(monkeypatch, field):
    payload = match()
    ev = payload["evidence"]
    inspected, _ = artificial_inspection(monkeypatch, ev)
    record = inspected.artifacts[0].record
    if field == "policy":
        record.policy.content_hash = "sha256:" + "0" * 64
    elif field == "registry":
        record.observation.degraded_window.registry.model_dump = lambda **kw: {}
    else:
        for f in record.features.values():
            f.normalized_value += 1.0
    with pytest.raises(ValueError, match="^invalid_profile_match$"):
        match_profile_snapshot(
            "model-only",
            ev["snapshot"],
            policy(),
            query_entry_id=payload["decision"]["query_entry_id"],
        )


@pytest.mark.parametrize("field", ["policy", "registry"])
def test_actual_query_policy_and_registry_are_verified(monkeypatch, field):
    payload = match()
    ev = payload["evidence"]
    inspected, _ = artificial_inspection(monkeypatch, ev)
    record = inspected.artifacts[-2].record
    if field == "policy":
        record.policy.content_hash = "sha256:" + "0" * 64
    else:
        record.observation.degraded_window.registry.model_dump = lambda **kw: {}
    with pytest.raises(ValueError, match="^invalid_profile_match$"):
        match_profile_snapshot(
            "model-only",
            ev["snapshot"],
            policy(),
            query_entry_id=payload["decision"]["query_entry_id"],
        )


class ForbiddenFeatures:
    def __getitem__(self, name):
        raise AssertionError("unavailable query feature was accessed")


@pytest.mark.parametrize("state", ["draft", "stale", "rejected"])
def test_withdrawn_and_unbuilt_revisions_do_not_access_query_features(monkeypatch, state):
    payload = match()
    ev = payload["evidence"]
    inspected, _ = artificial_inspection(monkeypatch, ev)
    snapshot = ev["snapshot"]
    if state == "draft":
        snapshot = create_profile_snapshot(snapshot["policy"])
    else:
        op = "mark_stale" if state == "stale" else "reject"
        from latency_fingerprinting.profiles import ProfileSnapshot

        parent = ProfileSnapshot.model_validate(snapshot)
        declaration = review(parent, op)
        snapshot = transition_profile_snapshot(
            parent, operation=op, reason_code=declaration["reason_code"], review=declaration
        )
    inspected.artifacts[-2].record.features = ForbiddenFeatures()
    result = match_profile_snapshot(
        "model-only", snapshot, policy(), query_entry_id=payload["decision"]["query_entry_id"]
    )
    assert result.decision.reason_codes == ("snapshot_unavailable",)
    assert result.decision.query_feature_values is None


@pytest.mark.parametrize("operation", ["match", "evaluate"])
@pytest.mark.parametrize("bad", ["wrong-binding", "split-leakage", "release.json", "absent"])
def test_broken_or_report_only_sources_fail_privately(operation, bad):
    ev, _ = source("reviewed-roles")
    with pytest.raises(
        ValueError, match=f"^invalid_profile_{'match' if operation == 'match' else 'evaluation'}$"
    ):
        if operation == "match":
            match_profile_snapshot(FIXTURES / bad, ev["snapshot"], policy(), query_entry_id="entry")
        else:
            evaluate_profile_snapshot(FIXTURES / bad, ev["snapshot"], policy(), mode="validation")


@pytest.mark.parametrize("anchor", ["expected_split_id", "expected_dataset_content_hash"])
def test_anchor_changes_and_unrelated_snapshot_fail(anchor):
    ev, _ = source("reviewed-roles")
    with pytest.raises(ValueError, match="^invalid_profile_evaluation$"):
        evaluate_profile_snapshot(
            FIXTURES / "reviewed-roles",
            ev["snapshot"],
            policy(),
            mode="validation",
            **{anchor: "invalid"},
        )
    other, _ = source("missing")
    with pytest.raises(ValueError, match="^invalid_profile_evaluation$"):
        evaluate_profile_snapshot(
            FIXTURES / "reviewed-roles", other["snapshot"], policy(), mode="validation"
        )


@pytest.mark.parametrize("mode", [None, True, [], {}, "training", "all"])
def test_mode_is_explicit_closed_input(mode):
    with pytest.raises(ValueError, match="^invalid_profile_evaluation$"):
        evaluate_profile_snapshot("unused", {}, policy(), mode=mode)


def test_rehashed_fitted_value_forgery_fails_fresh_verification(monkeypatch):
    ev = match()["evidence"]
    artificial_inspection(monkeypatch, ev)
    forged = copy.deepcopy(ev["snapshot"])
    # A valid declaration from another numeric cohort still cannot bind these source records.
    for item in forged["inputs"]:
        if item["selected"]:
            for name in NAMES:
                item["feature_values"][name] += 1.0
    from latency_fingerprinting.calibration.report import CalibrationReport
    from latency_fingerprinting.profiles.evidence import InputSelection
    from latency_fingerprinting.profiles.reconstruction import reconstruct

    forged["profiles"], forged["counts"] = reconstruct(
        CalibrationReport.model_validate(forged["source_report"]),
        [InputSelection.model_validate(i) for i in forged["inputs"]],
        forged["policy"]["content_hash"],
    )
    seal(forged)
    with pytest.raises(ValueError, match="^invalid_profile_evaluation$"):
        evaluate_profile_snapshot("model-only", forged, policy(), mode="validation")


@pytest.mark.parametrize("n", [20, 33])
def test_actual_global_refit_budgets_fail_before_any_fold_is_materialized(monkeypatch, n):
    ev = match(n)["evidence"]
    artificial_inspection(monkeypatch, ev)

    def forbidden(*args, **kwargs):
        raise AssertionError("fold was fit before the global budget check")

    monkeypatch.setattr(operations, "refit_profiles", forbidden)
    with pytest.raises(ValueError, match="^invalid_profile_evaluation$"):
        evaluate_profile_snapshot(
            "model-only", ev["snapshot"], policy(), mode="leave_training_group_out"
        )


def test_arithmetic_failure_is_wrapped_without_partial_scores(monkeypatch):
    payload = match()
    ev = payload["evidence"]
    artificial_inspection(monkeypatch, ev)

    def arithmetic(*args, **kwargs):
        raise ValueError("invalid_profile_match_arithmetic")

    monkeypatch.setattr(operations, "reconstruct_decision", arithmetic)
    with pytest.raises(ValueError, match="^invalid_profile_match$"):
        match_profile_snapshot(
            "model-only",
            ev["snapshot"],
            policy(),
            query_entry_id=payload["decision"]["query_entry_id"],
        )
    with pytest.raises(ValueError, match="^invalid_profile_evaluation$"):
        evaluate_profile_snapshot("model-only", ev["snapshot"], policy(), mode="validation")
