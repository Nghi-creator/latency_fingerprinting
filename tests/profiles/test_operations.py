"""Actual N6 integration and immutable operations; eligible model-only revisions are artificial."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from latency_fingerprinting.calibration.report import CalibrationReport
from latency_fingerprinting.profiles import (
    ProfileSnapshot,
    build_profile_snapshot,
    create_profile_snapshot,
    operations,
    transition_profile_snapshot,
)
from tests.calibration.cases import HASH, seal_report
from tests.calibration.check_reproduction import FIXTURES

from .cases import NAMES, candidate_id, draft, excluded, policy, reviewed, seal, supported

VALID_CASES = (
    "baseline",
    "confounded",
    "controlled-healthy",
    "controlled-host",
    "controlled-pacing",
    "declared",
    "duplicate",
    "failed-effect",
    "missing",
    "mixed-settings",
    "reviewed-response",
    "reviewed-roles",
)


def replacement():
    p = supported()
    p["source_report"].update(
        dataset_id="dataset-" + "b" * 64, dataset_content_hash="sha256:" + "b" * 64
    )
    seal_report(p["source_report"])
    candidate_id(p["profiles"][0], p["policy"], p["source_report"])
    return ProfileSnapshot.model_validate(seal(p))


def review(parent, operation="mark_stale", reason=None, target=None):
    reason = (
        reason
        or dict(
            mark_stale="external_review",
            reject="operator_rejected",
            supersede="replacement_selected",
        )[operation]
    )
    return dict(
        actor_id="operator",
        subject_snapshot_id=parent.snapshot_id,
        replacement_snapshot_id=target.snapshot_id if target is not None else None,
        reason_code=reason,
        evidence_sha256=HASH,
    )


def test_create_equals_independently_authored_draft_and_is_immutable():
    p = policy()
    result = create_profile_snapshot(p)
    assert result.model_dump(mode="json") == draft()
    assert create_profile_snapshot(p) == result
    p["weights"]["supported"] = 9.0
    assert result.policy.weights.supported == 1.0
    with pytest.raises(ValueError, match="^invalid_profile_snapshot$"):
        create_profile_snapshot(p)
    with pytest.raises(ValueError):
        result.lifecycle.state = "trusted"


@pytest.mark.parametrize("source", VALID_CASES)
def test_linked_build_matches_independent_excluded_expectations(source):
    result = build_profile_snapshot(FIXTURES / source, policy())
    assert result.model_dump(mode="json") == excluded(source)
    assert result.lifecycle.state == "rejected"
    assert result.counts.selected_entries == 0
    assert all(item.feature_values is None for item in result.inputs)
    assert build_profile_snapshot(FIXTURES / source, policy()) == result


@pytest.mark.parametrize("source", ["wrong-binding", "split-leakage", "release.json"])
def test_invalid_or_report_only_inputs_never_become_build_evidence(source):
    with pytest.raises(ValueError, match="^invalid_profile_build$"):
        build_profile_snapshot(FIXTURES / source, policy())


def test_standalone_report_object_is_not_a_build_shortcut():
    report = CalibrationReport.model_validate(supported()["source_report"])
    with pytest.raises(ValueError, match="^invalid_profile_build$"):
        build_profile_snapshot(report, policy())


def test_build_anchors_and_parent_never_promote_synthetic_data():
    first = build_profile_snapshot(FIXTURES / "reviewed-roles", policy())
    parent = ProfileSnapshot.model_validate(supported())
    result = build_profile_snapshot(
        FIXTURES / "reviewed-roles",
        policy(),
        parent=parent,
        expected_split_id=first.source_report.split_id,
        expected_dataset_content_hash=first.source_report.dataset_content_hash,
    )
    assert result.lifecycle.parent_snapshot_id == parent.snapshot_id
    assert result.lifecycle.state == "rejected"
    assert result.counts.selected_entries == 0
    assert parent.lifecycle.state == "provisional"
    assert result.profiles != parent.profiles
    with pytest.raises(ValueError, match="^invalid_profile_build$"):
        build_profile_snapshot(
            FIXTURES / "reviewed-roles", policy(), expected_split_id="split-" + "0" * 64
        )
    with pytest.raises(ValueError, match="^invalid_profile_build$"):
        build_profile_snapshot(
            FIXTURES / "reviewed-roles",
            policy(),
            expected_dataset_content_hash="sha256:" + "0" * 64,
        )


@pytest.mark.parametrize("operation", ["mark_stale", "reject", "supersede"])
def test_transition_matches_independent_revision_and_preserves_every_evidence_field(operation):
    parent = ProfileSnapshot.model_validate(supported())
    target = replacement() if operation == "supersede" else None
    declaration = review(parent, operation, target=target)
    before = parent.model_dump(mode="json")
    result = transition_profile_snapshot(
        parent,
        operation=operation,
        reason_code=declaration["reason_code"],
        review=declaration,
        replacement=target,
    )
    expected = reviewed(
        before,
        operation,
        declaration["reason_code"],
        target.snapshot_id if target is not None else None,
    )
    assert result.model_dump(mode="json") == expected
    assert parent.model_dump(mode="json") == before
    for key in ("policy", "source_report", "inputs", "profiles", "counts", "assurance"):
        assert result.model_dump(mode="json")[key] == before[key]
    assert result.snapshot_id != parent.snapshot_id


def parents():
    created = create_profile_snapshot(policy())
    provisional = ProfileSnapshot.model_validate(supported())
    rejected = build_profile_snapshot(FIXTURES / "reviewed-response", policy())
    rejected_draft = transition_profile_snapshot(
        created,
        operation="reject",
        reason_code="operator_rejected",
        review=review(created, "reject"),
    )
    stale = transition_profile_snapshot(
        provisional,
        operation="mark_stale",
        reason_code="external_review",
        review=review(provisional),
    )
    target = replacement()
    superseded = transition_profile_snapshot(
        provisional,
        operation="supersede",
        reason_code="replacement_selected",
        review=review(provisional, "supersede", target=target),
        replacement=target,
    )
    return dict(
        created=created,
        provisional=provisional,
        rejected=rejected,
        rejected_draft=rejected_draft,
        stale=stale,
        superseded=superseded,
    )


@pytest.mark.parametrize(
    "state", ["created", "provisional", "rejected", "rejected_draft", "stale", "superseded"]
)
@pytest.mark.parametrize("operation", ["mark_stale", "reject", "supersede"])
def test_complete_transition_table(state, operation):
    parent = parents()[state]
    target = replacement() if operation == "supersede" else None
    declaration = review(parent, operation, target=target)
    allowed = dict(
        mark_stale={"provisional", "rejected"},
        reject={"created", "provisional", "stale"},
        supersede={"provisional", "rejected", "stale"},
    )
    if state not in allowed[operation]:
        with pytest.raises(ValueError, match="^invalid_profile_snapshot$"):
            transition_profile_snapshot(
                parent,
                operation=operation,
                reason_code=declaration["reason_code"],
                review=declaration,
                replacement=target,
            )
    else:
        result = transition_profile_snapshot(
            parent,
            operation=operation,
            reason_code=declaration["reason_code"],
            review=declaration,
            replacement=target,
        )
        assert (
            result.lifecycle.state
            == dict(mark_stale="stale", reject="rejected", supersede="superseded")[operation]
        )


@pytest.mark.parametrize(
    "state", ["created", "provisional", "rejected", "rejected_draft", "stale", "superseded"]
)
def test_build_parent_table_and_fresh_inspection(state):
    parent = parents()[state]
    if state == "superseded":
        with pytest.raises(ValueError, match="^invalid_profile_build$"):
            build_profile_snapshot(FIXTURES / "missing", policy(), parent=parent)
    else:
        result = build_profile_snapshot(FIXTURES / "missing", policy(), parent=parent)
        assert result.lifecycle.parent_snapshot_id == parent.snapshot_id
        assert result.source_report.entries[0].input_kind == "missing"
        assert result.profiles == ()


@pytest.mark.parametrize("operation", ["promote", "build", "create", True, None, []])
def test_unavailable_transitions_have_fixed_errors(operation):
    parent = ProfileSnapshot.model_validate(supported())
    with pytest.raises(ValueError, match="^invalid_profile_snapshot$"):
        transition_profile_snapshot(
            parent, operation=operation, reason_code="external_review", review=review(parent)
        )


@pytest.mark.parametrize(
    "change", ["subject", "reason", "replacement", "extra", "unknown_actor", "copy"]
)
def test_review_ownership_and_copied_models_are_revalidated(change):
    parent = ProfileSnapshot.model_validate(supported())
    declaration = review(parent)
    if change == "subject":
        declaration["subject_snapshot_id"] = "profile-snapshot-" + "0" * 64
    elif change == "reason":
        declaration["reason_code"] = "method_changed"
    elif change == "replacement":
        declaration["replacement_snapshot_id"] = "profile-snapshot-" + "0" * 64
    elif change == "extra":
        declaration["trusted"] = True
    elif change == "unknown_actor":
        declaration["actor_id"] = "../operator"
    else:
        parent = parent.model_copy(
            update={"counts": parent.counts.model_copy(update={"selected_entries": 1})}
        )
    with pytest.raises(ValueError, match="^invalid_profile_snapshot$"):
        transition_profile_snapshot(
            parent, operation="mark_stale", reason_code="external_review", review=declaration
        )


@pytest.mark.parametrize("target", [None, "self", "draft", "rejected", "stale", "superseded"])
def test_supersession_rejects_missing_or_unusable_replacement(target):
    parent = ProfileSnapshot.model_validate(supported())
    candidate = (
        None
        if target is None
        else parent
        if target == "self"
        else parents()["created" if target == "draft" else target]
    )
    with pytest.raises(ValueError, match="^invalid_profile_snapshot$"):
        transition_profile_snapshot(
            parent,
            operation="supersede",
            reason_code="replacement_selected",
            review=review(parent, "supersede", target=candidate),
            replacement=candidate,
        )


def test_non_supersession_rejects_unused_replacement():
    parent = ProfileSnapshot.model_validate(supported())
    with pytest.raises(ValueError, match="^invalid_profile_snapshot$"):
        transition_profile_snapshot(
            parent,
            operation="reject",
            reason_code="operator_rejected",
            review=review(parent, "reject"),
            replacement=replacement(),
        )


class UnreadableArtifact:
    def __getattr__(self, name):
        raise AssertionError("unselected feature record was accessed: " + name)


def test_artificial_inspection_boundary_fits_training_only(monkeypatch):
    """Model-only eligible reports test extraction, not an assertion of real measurements."""
    p = supported()
    report = CalibrationReport.model_validate(p["source_report"])
    records = []
    for index, entry in enumerate(report.entries):
        if entry.role != "training":
            record = UnreadableArtifact()
        else:
            record = SimpleNamespace(
                policy=SimpleNamespace(content_hash=policy()["response_policy_hash"]),
                observation=SimpleNamespace(
                    degraded_window=SimpleNamespace(
                        registry=SimpleNamespace(model_dump=lambda **kw: policy()["registry"])
                    )
                ),
                features={
                    name: SimpleNamespace(state="eligible", normalized_value=float(index))
                    for name in NAMES
                },
            )
        records.append(SimpleNamespace(artifact_id=entry.entry_id, record=record))
    inspected = SimpleNamespace(
        report=report,
        dataset=SimpleNamespace(
            entries=[
                SimpleNamespace(entry_id=e.entry_id, artifact_id=e.entry_id) for e in report.entries
            ]
        ),
        artifacts=records,
    )
    calls = []

    def inspect(directory, **anchors):
        calls.append((directory, anchors))
        return inspected, (0, 0)

    monkeypatch.setattr(operations, "_inspect_dataset", inspect)
    result = build_profile_snapshot(Path("not-a-source-fixture"), policy())
    assert result.model_dump(mode="json") == p
    assert len(calls) == 1
    assert result.counts.selected_groups == 5
    assert result.profiles[0].features[NAMES[0]].center == 2.0
    records[0].record.policy.content_hash = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="^invalid_profile_build$"):
        build_profile_snapshot("unused", policy())
