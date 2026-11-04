"""Artificial review/provenance branches, never measured or independently reviewed data."""

import hashlib
import json
import shutil

import pytest

from latency_fingerprinting.analytical.responses import derive_analytical_response
from latency_fingerprinting.evaluation.median_readiness import (
    ERROR,
    LABELS,
    inspect_reviewed_median_readiness,
)
from latency_fingerprinting.models import FeaturePolicyV1, ObservationRecordV2
from tests.analytical.cases import policy_payload
from tests.calibration.cases import HASH, canonical, group_id, seal_dataset
from tests.calibration.check_reproduction import FIXTURES
from tests.calibration.inspection_cases import write
from tests.models.v2_cases import pair_payload, window_payload


def source_dataset(
    path,
    *,
    count=5,
    confirmed=True,
    real=True,
    heldout=True,
    heldout_values=(0, 60, 120),
    shared_case=False,
    partitioned=False,
):
    """Invented content and external-review declarations, not genuine acquisitions."""
    artifacts, sources, entries, assignments, reviews, files = [], [], [], [], [], {}
    labels = list(LABELS) + (["healthy"] if heldout else [])
    for label_index, label in enumerate(labels):
        role = "final_test" if label_index == 3 else "training"
        for i in range(count if role == "training" else 1):
            alias = f"case-{label_index}-{i}"
            pair = pair_payload(real=real)
            pair.update(
                comparison_case_id="shared-case" if shared_case else alias,
                observation_id=alias + "-observation",
            )
            pair["relief_window"] = window_payload(
                phase="relief",
                real=real,
                values=heldout_values
                if role == "final_test"
                else (0, 30, 60)
                if label_index == 1
                else (0, 60, 120),
            )
            ids = []
            bindings = []
            for phase in ("degraded", "relief"):
                window = pair[phase + "_window"]
                window.update(
                    comparison_case_id="shared-case" if shared_case else alias,
                    run_id=alias + "-" + phase,
                )
                if partitioned:
                    window["context"]["workloadId"] = alias
                window["source_artifact"]["content_hash"] = (
                    "sha256:" + hashlib.sha256(("invented " + alias + phase).encode()).hexdigest()
                )
                identity = alias + "-" + phase
                ids.append(identity)
                source = window["source_artifact"]
                sources.append(
                    dict(
                        source_id=identity,
                        acquisition_namespace="artificial-branch",
                        run_id=window["run_id"],
                        session_id=alias,
                        independence_group=alias,
                        source_type=source["source_type"],
                        source_content_hash=source["content_hash"],
                        bundle_schema_version=source["bundle_schema_version"],
                        review_id=alias + "-independence" if confirmed else None,
                    )
                )
                bindings.append(
                    dict(source_id=identity, window_id=window["window_id"], window_role=phase)
                )
            response = derive_analytical_response(
                ObservationRecordV2.model_validate(pair),
                FeaturePolicyV1.model_validate(policy_payload()),
            )
            files[alias + ".json"] = canonical(response.model_dump(mode="json", by_alias=True))
            artifacts.append(
                dict(
                    artifact_id=alias,
                    kind="analytical_response",
                    file_name=alias + ".json",
                    sha256=HASH,
                    bytes=1,
                )
            )
            entries.append(
                dict(
                    entry_id=alias,
                    input_kind="response",
                    artifact_id=alias,
                    source_bindings=bindings,
                    label=label,
                    label_basis="external_confirmation" if confirmed else "declared_only",
                    label_review_id=alias + "-label" if confirmed else None,
                    experiment_artifact_id=None,
                    experiment_phase=None,
                )
            )
            assignments.append(dict(group_id=group_id(ids), role=role))
            if confirmed:
                for kind, subjects in (("independence", sorted(ids)), ("label_binding", [alias])):
                    reviews.append(
                        dict(
                            review_id=alias
                            + ("-label" if kind == "label_binding" else "-independence"),
                            reviewer_id="artificial-reviewer",
                            kind=kind,
                            subject_ids=subjects,
                            outcome="confirmed",
                            evidence_sha256=HASH,
                        )
                    )
    payload = dict(
        schema_version="calibration-dataset-v1",
        method_release="n6-calibration-evidence-v1",
        dataset_id="dataset-" + "0" * 64,
        content_hash=HASH,
        artifacts=sorted(artifacts, key=lambda r: r["artifact_id"]),
        sources=sorted(sources, key=lambda r: r["source_id"]),
        derivations=[],
        reviews=[],
        split=dict(
            split_id="split-" + "0" * 64,
            mode="prospective" if confirmed else "retrospective",
            protocol_sha256=HASH,
            assignments=sorted(assignments, key=lambda r: r["group_id"]),
            freeze_review_id="freeze" if confirmed else None,
        ),
        entries=sorted(entries, key=lambda r: r["entry_id"]),
    )
    seal_dataset(payload)
    if confirmed:
        reviews.append(
            dict(
                review_id="freeze",
                reviewer_id="artificial-reviewer",
                kind="split_freeze",
                subject_ids=[payload["split"]["split_id"]],
                outcome="confirmed",
                evidence_sha256=HASH,
            )
        )
    payload["reviews"] = sorted(reviews, key=lambda r: r["review_id"])
    write(path, payload, files)
    return payload


def inspect(path, payload):
    return inspect_reviewed_median_readiness(
        path,
        expected_dataset_content_hash=payload["content_hash"],
        expected_split_id=payload["split"]["split_id"],
    )


def test_linked_reviewed_training_only_and_stable_features_are_numeric(tmp_path):
    payload = source_dataset(tmp_path)
    result = inspect(tmp_path, payload)
    assert result["state"] == "reviewed_training_summaries_available"
    assert len(result["selected_group_ids"]) == 15
    assert [c["reviewed_label"] for c in result["candidates"]] == list(LABELS)
    assert all(c["summary"]["numeric_feature_count"] == 22 for c in result["candidates"])
    assert all(
        c["summary"]["features"]["host.node_cpu_percent"]["raw_mad"] == 0
        for c in result["candidates"]
    )
    assert result["exclusions"] == [
        dict(entry_id="case-3-0", selection_reason_codes=["not_training"], n6_reason_codes=[])
    ]
    assert result["diagnostic_label"] is None and result["accepted_diagnostic_groups"] == 0
    assert result["decision_method"].startswith("unavailable")
    assert result["assurance"] == "external_review_declarations_not_authenticated"
    result["method_spec"]["required_labels"].clear()
    assert inspect(tmp_path, payload)["method_spec"]["required_labels"] == list(LABELS)


@pytest.mark.parametrize(
    "case",
    ["missing", "baseline", "declared", "controlled-host", "reviewed-response", "reviewed-roles"],
)
def test_existing_n6_exclusions_cannot_be_bypassed(case):
    path = FIXTURES / case
    payload = json.loads((path / "calibration-dataset.json").read_bytes())
    result = inspect(path, payload)
    assert result["state"] == "unavailable" and not result["selected_entry_ids"]
    assert result["candidates"] == [] and result["exclusions"]


@pytest.mark.parametrize("confirmed,real", [(False, True), (True, False)])
def test_unreviewed_or_synthetic_measurements_never_become_selected(tmp_path, confirmed, real):
    payload = source_dataset(tmp_path, count=1, confirmed=confirmed, real=real, heldout=False)
    result = inspect(tmp_path, payload)
    assert result["state"] == "unavailable" and result["selected_entry_ids"] == []
    assert all("n6_excluded" in e["selection_reason_codes"] for e in result["exclusions"])


def test_four_reviewed_groups_per_label_remain_insufficient(tmp_path):
    payload = source_dataset(tmp_path, count=4, heldout=False)
    result = inspect(tmp_path, payload)
    assert result["state"] == "unavailable" and len(result["selected_group_ids"]) == 12
    assert all(c["summary"]["state"] == "unavailable" for c in result["candidates"])
    assert result["label_coverage"][0]["missing_numeric_labels"] == list(LABELS)


@pytest.mark.parametrize(
    "mutation", ["dataset_pin", "split_pin", "missing_pin", "raw_bytes", "symlink"]
)
def test_detached_stale_unpinned_or_changed_files_fail(tmp_path, mutation):
    payload = source_dataset(tmp_path, count=1)
    if mutation == "dataset_pin":
        payload["content_hash"] = "sha256:" + "f" * 64
    elif mutation == "split_pin":
        payload["split"]["split_id"] = "split-" + "f" * 64
    elif mutation == "missing_pin":
        payload["content_hash"] = None
    elif mutation == "raw_bytes":
        (tmp_path / "case-0-0.json").write_text("{}\n")
    else:
        original = tmp_path / "case-0-0.json"
        target = tmp_path / "outside.json"
        shutil.move(original, target)
        original.symlink_to(target)
    with pytest.raises(ValueError, match=ERROR):
        inspect(tmp_path, payload)


def test_heldout_outcomes_never_change_training_summaries(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    a = source_dataset(first)
    b = source_dataset(second, heldout_values=(0, 15, 30))
    before, after = inspect(first, a), inspect(second, b)
    assert a["content_hash"] != b["content_hash"]
    assert before["candidates"] == after["candidates"]
    assert before["selected_entry_ids"] == after["selected_entry_ids"]


def test_shared_case_cannot_hide_behind_separate_reviewed_n6_groups(tmp_path):
    payload = source_dataset(tmp_path, count=1, heldout=False, shared_case=True)
    with pytest.raises(ValueError, match=ERROR):
        inspect(tmp_path, payload)


def test_excessive_context_candidates_are_bounded(tmp_path):
    payload = source_dataset(tmp_path, count=6, heldout=False, partitioned=True)
    with pytest.raises(ValueError, match=ERROR):
        inspect(tmp_path, payload)


def test_spec_drift_is_rejected(tmp_path, monkeypatch):
    from latency_fingerprinting.evaluation import median_readiness

    payload = source_dataset(tmp_path, count=1, heldout=False)
    monkeypatch.setitem(median_readiness._METHOD, "minimum_groups_per_label", 1)
    with pytest.raises(ValueError, match=ERROR):
        inspect(tmp_path, payload)


def test_mixed_reviewed_labels_in_one_component_are_excluded(tmp_path):
    payload = source_dataset(tmp_path, count=1, heldout=False)
    members = [
        s for s in payload["sources"] if s["source_id"].startswith(("case-0-0-", "case-1-0-"))
    ]
    old_groups = {
        group_id([s["source_id"] for s in members if s["source_id"].startswith(prefix)])
        for prefix in ("case-0-0-", "case-1-0-")
    }
    for source in members:
        source.update(
            session_id="mixed-session",
            independence_group="mixed-session",
            review_id="mixed-independence",
        )
    payload["reviews"] = [
        r
        for r in payload["reviews"]
        if r["review_id"] not in ("case-0-0-independence", "case-1-0-independence")
    ]
    payload["reviews"].append(
        dict(
            review_id="mixed-independence",
            reviewer_id="artificial-reviewer",
            kind="independence",
            subject_ids=sorted(s["source_id"] for s in members),
            outcome="confirmed",
            evidence_sha256=HASH,
        )
    )
    payload["reviews"].sort(key=lambda r: r["review_id"])
    assignments = [a for a in payload["split"]["assignments"] if a["group_id"] not in old_groups]
    assignments.append(dict(group_id=group_id([s["source_id"] for s in members]), role="training"))
    payload["split"]["assignments"] = sorted(assignments, key=lambda a: a["group_id"])
    seal_dataset(payload)
    next(r for r in payload["reviews"] if r["review_id"] == "freeze")["subject_ids"] = [
        payload["split"]["split_id"]
    ]
    files = {a["file_name"]: (tmp_path / a["file_name"]).read_bytes() for a in payload["artifacts"]}
    write(tmp_path, payload, files)
    result = inspect(tmp_path, payload)
    assert result["selected_entry_ids"] == ["case-2-0"]
    assert all(
        e["selection_reason_codes"] == ["mixed_group_labels"] and e["n6_reason_codes"] == []
        for e in result["exclusions"]
    )
