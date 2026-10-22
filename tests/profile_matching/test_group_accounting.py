"""Artificial multi-window components: independent group-vote and refit expectations."""

import copy

import pytest

from latency_fingerprinting.calibration.dataset import CalibrationDataset
from latency_fingerprinting.calibration.inspection import _build_report
from latency_fingerprinting.calibration.lineage import validate_calibration_lineage
from latency_fingerprinting.profile_matching import (
    ProfileEvaluationResult,
    evaluate_profile_snapshot,
)
from latency_fingerprinting.profiles.operations import _fit_inspected_profile_snapshot
from latency_fingerprinting.profiles.policy import ProfilePolicy
from tests.calibration.cases import seal_dataset
from tests.profiles.cases import NAMES

from .cases import digest, evidence, policy, root_seal
from .test_operations import ForbiddenFeatures, artificial_inspection


def component(monkeypatch, *, training=False, mixed=False, unverified=False, duplicate=False):
    """Use N6 metadata validators only; these have no inspected physical acquisition."""
    ev = evidence(6 if training else 5)
    dataset = ev["dataset"]
    indices = (0, 1) if training else (-2, -1)
    members = [ev["report"]["entries"][i] for i in indices]
    old_groups = {e["group_id"] for e in members}
    ids = {e["entry_id"] for e in members}
    groups = [g for g in ev["report"]["groups"] if g["group_id"] in old_groups]
    sources = sorted(s for g in groups for s in g["source_ids"])
    group_id = "group-" + digest(dict(source_ids=sources))[7:]
    source_rows = [s for s in dataset["sources"] if s["source_id"] in sources]
    review_ids = {s["review_id"] for s in source_rows}
    review_id = sorted(review_ids)[0]
    for s in source_rows:
        s.update(session_id="shared-model-only-session", review_id=review_id)
    dataset["reviews"] = [
        r for r in dataset["reviews"] if r["review_id"] not in review_ids - {review_id}
    ]
    next(r for r in dataset["reviews"] if r["review_id"] == review_id)["subject_ids"] = sources
    role = "training" if training else "validation"
    dataset["split"]["assignments"] = sorted(
        [
            *[a for a in dataset["split"]["assignments"] if a["group_id"] not in old_groups],
            dict(group_id=group_id, role=role),
        ],
        key=lambda a: a["group_id"],
    )
    for e in members:
        e.update(group_id=group_id, role=role)
    target = next(e for e in dataset["entries"] if e["entry_id"] == members[1]["entry_id"])
    if mixed:
        target["label"] = members[1]["label"] = "healthy"
    if unverified:
        next(r for r in dataset["reviews"] if r["review_id"] == target["label_review_id"])[
            "outcome"
        ] = "uncertain"
        members[1].update(eligible=False, reason_codes=["label_unverified"])
    if duplicate:
        members[1].update(
            eligible=False,
            reason_codes=["duplicate_evidence"],
            representative_entry_id=members[0]["entry_id"],
        )
    seal_dataset(dataset)
    next(r for r in dataset["reviews"] if r["review_id"] == "freeze")["subject_ids"] = [
        dataset["split"]["split_id"]
    ]
    seal_dataset(dataset)
    declared = CalibrationDataset.model_validate(dataset)
    report = _build_report(
        declared, validate_calibration_lineage(declared), ev["report"]["entries"]
    )
    ev["report"] = report.model_dump(mode="json")
    inspected, calls = artificial_inspection(monkeypatch, ev)
    snapshot = _fit_inspected_profile_snapshot(
        inspected, ProfilePolicy.model_validate(ev["snapshot"]["policy"])
    )
    records = {a.artifact_id: a.record for a in inspected.artifacts}
    query_records = [records[e["artifact_id"]] for e in dataset["entries"] if e["entry_id"] in ids]
    return inspected, snapshot, query_records, group_id, sorted(ids), calls


def set_values(records, values):
    for record, value in zip(records, values, strict=True):
        for feature in record.features.values():
            feature.normalized_value = value


@pytest.mark.parametrize(
    "values,chosen,reasons",
    [
        ((2.0, 2.0), "healthy", []),
        ((2.0, 6.0), None, ["entry_disagreement"]),
        ((2.0, 4.0), None, ["entry_unknown"]),
    ],
)
def test_one_group_one_outcome_requires_unanimous_known_predictions(
    monkeypatch, values, chosen, reasons
):
    _, snapshot, records, group, ids, calls = component(monkeypatch)
    set_values(records, values)
    result = evaluate_profile_snapshot("model-only", snapshot, policy(), mode="validation")
    assert len(calls) == 1
    assert len(result.decisions) == 2
    assert result.counts.evaluated_entries == result.counts.response_entries == 2
    assert result.counts.classification_groups == result.counts.known_truth_groups == 1
    outcome = result.group_outcomes[0]
    assert outcome.group_id == group
    assert list(outcome.entry_ids) == list(outcome.representative_entry_ids) == ids
    assert outcome.truth_label == "host_contention"
    assert outcome.predicted_label == chosen
    assert list(outcome.prediction_reason_codes) == reasons
    assert result.confusion_matrix["host_contention"][chosen or "unknown"] == 1
    assert sum(sum(row.values()) for row in result.confusion_matrix.values()) == 1
    assert result.counts.unknown_groups == int(chosen is None)
    assert result.counts.incorrect_groups == int(chosen is not None)
    assert result.metrics.accuracy.model_dump() == dict(numerator=0, denominator=1, value=0.0)
    forged = result.model_dump(mode="json")
    forged["group_outcomes"][0]["predicted_label"] = "render_capture_slowdown"
    with pytest.raises(ValueError, match="does not reconstruct"):
        ProfileEvaluationResult.model_validate(root_seal(forged))


@pytest.mark.parametrize("unverified", [False, True])
def test_mixed_or_unverified_truth_stays_out_of_accuracy_but_in_group_denominators(
    monkeypatch, unverified
):
    _, snapshot, records, _, _, _ = component(
        monkeypatch, mixed=not unverified, unverified=unverified
    )
    set_values(records, (2.0, 2.0))
    result = evaluate_profile_snapshot("model-only", snapshot, policy(), mode="validation")
    outcome = result.group_outcomes[0]
    assert outcome.truth_label is None
    assert outcome.truth_reason_codes == (
        ("label_unverified",) if unverified else ("mixed_labels",)
    )
    assert result.counts.known_truth_groups == 0
    assert result.counts.unverified_truth_groups == result.counts.classification_groups == 1
    assert result.counts.correct_groups == result.counts.incorrect_groups == 0
    assert result.metrics.accuracy.model_dump() == dict(numerator=0, denominator=0, value=None)
    assert result.metrics.truth_coverage.model_dump() == dict(numerator=0, denominator=1, value=0.0)
    assert result.metrics.unknown_rate.value == float(unverified)
    assert result.confusion_matrix["unverified_truth"]["unknown" if unverified else "healthy"] == 1


def test_semantic_duplicate_is_retained_without_a_second_prediction_vote(monkeypatch):
    _, snapshot, records, _, ids, _ = component(monkeypatch, duplicate=True)
    set_values(records, (2.0, 6.0))
    records[1].features = ForbiddenFeatures()
    result = evaluate_profile_snapshot("model-only", snapshot, policy(), mode="validation")
    assert result.counts.evaluated_entries == 2
    assert result.counts.duplicate_entries == result.counts.n6_excluded_entries == 1
    assert result.counts.classification_groups == 1
    assert result.group_outcomes[0].entry_ids == tuple(ids)
    assert result.group_outcomes[0].representative_entry_ids == (ids[0],)
    assert result.group_outcomes[0].predicted_label == "healthy"
    assert result.group_outcomes[0].prediction_reason_codes == ()
    assert result.decisions[1].query_feature_values is None
    assert result.decisions[1].reason_codes == ("n6_excluded", "duplicate_evidence")


def test_refit_removes_every_window_in_the_connected_component(monkeypatch):
    _, snapshot, _, group, ids, calls = component(monkeypatch, training=True)
    before = copy.deepcopy(snapshot.model_dump(mode="json"))
    healthy = next(p for p in snapshot.profiles if p.label == "healthy")
    # Original votes are 0.5, 2, 3, 4, 5: center 3, MAD 1, five groups.
    assert healthy.features[NAMES[0]].center == 3.0
    assert healthy.features[NAMES[0]].dispersion == 1.0
    result = evaluate_profile_snapshot(
        "model-only", snapshot, policy(), mode="leave_training_group_out"
    )
    assert len(calls) == 1
    refit = next(r for r in result.refits if r.excluded_group_id == group)
    assert refit.counts.removed_entries == 2
    assert refit.counts.selected_entries == refit.counts.selected_groups == 10
    removed = [i for i in refit.inputs if i.entry_id in ids]
    assert len(removed) == 2
    assert all(
        not i.selected
        and i.feature_values is None
        and i.reason_codes == ("leave_source_group_out",)
        for i in removed
    )
    fitted = next(p for p in refit.profiles if p.label == "healthy")
    # Remaining votes are 2, 3, 4, 5: center 3.5, MAD 1; four groups fail support.
    assert fitted.features[NAMES[0]].center == 3.5
    assert fitted.features[NAMES[0]].dispersion == 1.0
    assert fitted.features[NAMES[0]].contributing_groups == 4
    assert fitted.state == "rejected"
    assert group not in fitted.training_group_ids
    assert len({d.refit_id for d in result.decisions if d.query_entry_id in ids}) == 1
    assert all(d.refit_id == refit.refit_id for d in result.decisions if d.query_entry_id in ids)
    assert snapshot.model_dump(mode="json") == before
