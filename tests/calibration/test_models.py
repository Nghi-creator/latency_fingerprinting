"""Standalone N6 invariants and adversarial reused-instance validation."""

from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from latency_fingerprinting.calibration import (
    CalibrationArtifact,
    CalibrationDataset,
    CalibrationEntry,
    CalibrationReport,
    CalibrationSource,
    EvidenceReview,
    SourceEdge,
)
from latency_fingerprinting.calibration.contracts import ARCHIVE_BYTES, JSON_BYTES
from latency_fingerprinting.models import CalibrationDataset as PublicDataset

from .cases import HASH, canonical, dataset, report, seal_dataset


def test_independent_roots_round_trip_schema_aliases_counts_and_no_file_access(monkeypatch):
    def forbid(*args, **kwargs):
        raise AssertionError("standalone model must not read files")

    monkeypatch.setattr(Path, "open", forbid)
    assert PublicDataset is CalibrationDataset
    for cls, payload in ((CalibrationDataset, dataset()), (CalibrationReport, report())):
        model = cls.model_validate(payload)
        assert model.model_dump(mode="json") == payload
        assert cls.model_validate_json(canonical(payload)) == model
        Draft202012Validator(cls.model_json_schema()).validate(payload)
        assert "schemaVersion" not in cls.model_json_schema()["properties"]
    result = CalibrationReport.model_validate(report())
    assert result.counts.eligible_groups == 4
    assert result.counts.by_role.training.eligible_entries == 2
    assert result.entries[-1].role is None


@pytest.mark.parametrize(
    "cls,factory", [(CalibrationDataset, dataset), (CalibrationReport, report)]
)
def test_required_keys_extra_fields_closed_versions_and_rehashed_identity(cls, factory):
    payload = factory()
    for field in payload:
        changed = deepcopy(payload)
        del changed[field]
        with pytest.raises(ValidationError):
            cls.model_validate(changed)
    for field, value in (
        ("schema_version", "unknown"),
        ("method_release", "unknown"),
        ("extra", 0),
    ):
        with pytest.raises(ValidationError):
            cls.model_validate({**payload, field: value})
    field = "dataset_id" if cls is CalibrationDataset else "report_id"
    with pytest.raises(ValidationError):
        cls.model_validate({**payload, field: payload[field][:-1] + "z"})
    with pytest.raises(ValidationError):
        cls.model_validate(
            {**payload, field: payload[field][:-1] + ("0" if payload[field][-1] != "0" else "1")}
        )


def test_missing_dataset_is_retained_without_invented_sources():
    model = CalibrationDataset.model_validate(dataset(missing=True))
    assert model.sources == () and model.entries[0].input_kind == "missing"
    assert model.entries[0].label is None


@pytest.mark.parametrize("bad", [True, 0, -1, 1.0, float("nan"), float("inf"), JSON_BYTES + 1])
def test_artifact_bytes_strict_and_kind_bounded(bad):
    payload = dataset()["artifacts"][0]
    with pytest.raises(ValidationError):
        CalibrationArtifact.model_validate({**payload, "bytes": bad})


def test_artifact_limits_and_filenames():
    payload = dataset()["artifacts"][0]
    assert CalibrationArtifact.model_validate({**payload, "bytes": JSON_BYTES}).bytes == JSON_BYTES
    archive = {
        **payload,
        "kind": "experiment_bundle",
        "file_name": "response-a.tar.gz",
        "bytes": ARCHIVE_BYTES,
    }
    assert CalibrationArtifact.model_validate(archive).bytes == ARCHIVE_BYTES
    for name in ("../response-a.json", "other.json", "response-a.json\n", "/response-a.json"):
        with pytest.raises(ValidationError):
            CalibrationArtifact.model_validate({**payload, "file_name": name})
    with pytest.raises(ValidationError):
        CalibrationArtifact.model_validate({**archive, "bytes": ARCHIVE_BYTES + 1})


@pytest.mark.parametrize("bad", ["bad id", "bad/id", "a\n", " a", "a" * 129, "é", ""])
def test_aliases_are_closed_without_whitespace_coercion(bad):
    payload = dataset()["sources"][0]
    with pytest.raises(ValidationError):
        CalibrationSource.model_validate({**payload, "source_id": bad})


def test_original_ids_bound_utf8_and_source_type_consistency():
    payload = dataset()["sources"][0]
    assert CalibrationSource.model_validate({**payload, "run_id": "é" * 128}).run_id == "é" * 128
    for value in ("é" * 129, " ", 42):
        with pytest.raises(ValidationError):
            CalibrationSource.model_validate({**payload, "run_id": value})
    with pytest.raises(ValidationError):
        CalibrationSource.model_validate({**payload, "bundle_schema_version": "2"})
    with pytest.raises(ValidationError):
        CalibrationSource.model_validate({**payload, "source_type": "pixelated_bundle"})


def test_models_detach_containers_freeze_and_revalidate_copied_nested_instances():
    payload = dataset()
    model = CalibrationDataset.model_validate(payload)
    payload["sources"][0]["session_id"] = "changed"
    assert model.sources[0].session_id != "changed"
    with pytest.raises(ValidationError):
        model.sources[0].session_id = "changed"
    forged = model.artifacts[0].model_copy(update={"bytes": True})
    with pytest.raises(ValidationError):
        CalibrationDataset.model_validate(model.model_copy(update={"artifacts": (forged,)}))
    forged_report = CalibrationReport.model_validate(report())
    with pytest.raises(ValidationError):
        CalibrationReport.model_validate(
            forged_report.model_copy(
                update={"entries": (forged_report.entries[0].model_copy(update={"eligible": 1}),)}
            )
        )


@pytest.mark.parametrize(
    "change",
    [
        "duplicate_source",
        "unsorted_sources",
        "bad_artifact",
        "dangling_source",
        "dangling_edge",
        "self_edge",
        "unreachable_source",
        "unreachable_artifact",
        "wrong_review",
        "bad_split_hash",
        "bad_content_hash",
    ],
)
def test_intrinsic_dataset_relations_reject_even_after_root_rehash(change):
    p = dataset()
    if change == "duplicate_source":
        p["sources"].append(deepcopy(p["sources"][0]))
    elif change == "unsorted_sources":
        p["sources"].reverse()
    elif change == "bad_artifact":
        p["entries"][0]["artifact_id"] = "missing"
    elif change == "dangling_source":
        p["entries"][0]["source_bindings"][0]["source_id"] = "missing"
    elif change == "dangling_edge":
        p["derivations"] = [dict(parent_source_id="source-a", child_source_id="missing")]
    elif change == "self_edge":
        p["derivations"] = [dict(parent_source_id="source-a", child_source_id="source-a")]
    elif change == "unreachable_source":
        p["sources"].append({**p["sources"][0], "source_id": "source-c"})
    elif change == "unreachable_artifact":
        p["artifacts"].append(
            {**p["artifacts"][0], "artifact_id": "response-b", "file_name": "response-b.json"}
        )
    elif change == "wrong_review":
        p["sources"][0]["review_id"] = "missing"
    seal_dataset(p)
    if change == "bad_split_hash":
        p["split"]["split_id"] = "split-" + "0" * 64
    if change == "bad_content_hash":
        p["content_hash"] = "sha256:" + "0" * 64
    with pytest.raises(ValidationError):
        CalibrationDataset.model_validate(p)


def test_review_references_and_uncertain_support_are_retained():
    p = dataset()
    p["reviews"] = [
        dict(
            review_id="review-a",
            reviewer_id="reviewer-a",
            kind="label_binding",
            subject_ids=["entry-a"],
            outcome="uncertain",
            evidence_sha256=HASH,
        )
    ]
    p["entries"][0].update(label_basis="external_confirmation", label_review_id="review-a")
    assert CalibrationDataset.model_validate(seal_dataset(p)).reviews[0].outcome == "uncertain"
    for change in ("kind", "subjects"):
        bad = deepcopy(p)
        if change == "kind":
            bad["reviews"][0]["kind"] = "independence"
        else:
            bad["reviews"][0]["subject_ids"] = ["missing"]
        with pytest.raises(ValidationError):
            CalibrationDataset.model_validate(seal_dataset(bad))


@pytest.mark.parametrize(
    "change",
    [
        "missing_artifact",
        "roles",
        "unknown_label",
        "healthy_fault",
        "missing_claim",
        "controlled_without_bundle",
        "borrowed_bundle",
    ],
)
def test_entry_roles_and_label_basis(change):
    p = dataset()["entries"][0]
    if change == "missing_artifact":
        p["artifact_id"] = None
    elif change == "roles":
        p["source_bindings"].reverse()
    elif change == "unknown_label":
        p["label"] = None
    elif change == "healthy_fault":
        p.update(
            input_kind="healthy_window",
            source_bindings=[dict(window_role="healthy", source_id="source-a", window_id="w")],
        )
    elif change == "missing_claim":
        p.update(input_kind="missing", artifact_id=None, source_bindings=[])
    elif change == "controlled_without_bundle":
        p["label_basis"] = "controlled_effect"
    else:
        p["experiment_artifact_id"] = "bundle-a"
    with pytest.raises(ValidationError):
        CalibrationEntry.model_validate(p)


@pytest.mark.parametrize(
    "model,payload",
    [
        (SourceEdge, dict(parent_source_id="a", child_source_id="a")),
        (
            EvidenceReview,
            dict(
                review_id="r",
                reviewer_id="v",
                kind="label_binding",
                subject_ids=["a", "b"],
                outcome="confirmed",
                evidence_sha256=HASH,
            ),
        ),
    ],
)
def test_edges_and_single_subject_reviews(model, payload):
    with pytest.raises(ValidationError):
        model.model_validate(payload)


@pytest.mark.parametrize("field", ["sources", "artifacts", "entries", "reviews", "derivations"])
def test_collections_reject_lazy_or_unordered_inputs_before_consuming(field):
    p = dataset()

    def poison():
        raise AssertionError("generator must not be consumed")
        yield

    with pytest.raises(ValidationError):
        CalibrationDataset.model_validate({**p, field: poison()})
    with pytest.raises(ValidationError):
        CalibrationDataset.model_validate({**p, field: set()})


def test_directed_cycles_reject_but_declared_ancestors_are_retained():
    payload = dataset()
    payload["sources"].append({**payload["sources"][0], "source_id": "source-c"})
    payload["derivations"] = [dict(parent_source_id="source-a", child_source_id="source-c")]
    assert len(CalibrationDataset.model_validate(seal_dataset(payload)).sources) == 3
    payload["derivations"].append(dict(parent_source_id="source-c", child_source_id="source-a"))
    with pytest.raises(ValidationError, match="cycle"):
        CalibrationDataset.model_validate(seal_dataset(payload))


def test_declared_aggregate_bound_before_any_artifact_is_opened():
    payload = dataset()
    payload["entries"][0].update(
        label_basis="controlled_effect",
        experiment_artifact_id="z-bundle",
        experiment_phase="degraded",
    )
    payload["artifacts"].append(
        dict(
            artifact_id="z-bundle",
            kind="experiment_bundle",
            file_name="z-bundle.tar.gz",
            sha256=HASH,
            bytes=ARCHIVE_BYTES,
        )
    )
    for i in range(4):
        name = f"response-{i}"
        entry = {**deepcopy(payload["entries"][0]), "entry_id": f"entry-{i}", "artifact_id": name}
        artifact = {
            **payload["artifacts"][0],
            "artifact_id": name,
            "file_name": name + ".json",
            "bytes": JSON_BYTES,
        }
        payload["entries"].append(entry)
        payload["artifacts"].append(artifact)
    payload["entries"].sort(key=lambda item: item["entry_id"])
    payload["artifacts"].sort(key=lambda item: item["artifact_id"])
    assert CalibrationDataset.model_validate(seal_dataset(payload))
    # Four distinct 64 MiB bundles exceed the aggregate once JSON and manifest are included.
    for i in range(3):
        name = f"z-extra-{i}"
        payload["artifacts"].append(
            dict(
                artifact_id=name,
                kind="experiment_bundle",
                file_name=name + ".tar.gz",
                sha256=HASH,
                bytes=ARCHIVE_BYTES,
            )
        )
        payload["entries"][i]["experiment_artifact_id"] = name
    payload["artifacts"].sort(key=lambda item: item["artifact_id"])
    with pytest.raises(ValidationError, match="aggregate"):
        CalibrationDataset.model_validate(seal_dataset(payload))


def test_prospective_split_can_retain_explicit_external_review_declarations():
    p = dataset()
    p["split"]["mode"] = "prospective"
    seal_dataset(p)
    p["split"]["freeze_review_id"] = "freeze-review"
    p["reviews"] = [
        dict(
            review_id="freeze-review",
            reviewer_id="reviewer",
            kind="split_freeze",
            subject_ids=[p["split"]["split_id"]],
            outcome="confirmed",
            evidence_sha256=HASH,
        )
    ]
    # This is a well-formed declaration; models do not authenticate the reviewer.
    assert CalibrationDataset.model_validate(seal_dataset(p)).split.mode == "prospective"
    p["split"]["mode"] = "retrospective"
    with pytest.raises(ValidationError, match="retrospective"):
        CalibrationDataset.model_validate(seal_dataset(p))


def test_confirmed_controlled_label_is_only_a_declaration_until_linked_inspection():
    p = dataset()
    p["entries"][0].update(
        label_basis="controlled_effect",
        experiment_artifact_id="z-bundle",
        experiment_phase="degraded",
    )
    p["artifacts"].append(
        dict(
            artifact_id="z-bundle",
            kind="experiment_bundle",
            file_name="z-bundle.tar.gz",
            sha256=HASH,
            bytes=100,
        )
    )
    assert (
        CalibrationDataset.model_validate(seal_dataset(p)).entries[0].label_basis
        == "controlled_effect"
    )
    p["entries"][0]["experiment_phase"] = "healthy"
    with pytest.raises(ValidationError, match="phase"):
        CalibrationDataset.model_validate(seal_dataset(p))
