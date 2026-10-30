"""Public JSON/CLI and strict container limits, independent of artifact inspection."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from latency_fingerprinting.calibration import CalibrationDataset, CalibrationReport
from latency_fingerprinting.cli import main
from latency_fingerprinting.schemas import render_schema

from .cases import canonical, dataset, report, seal_dataset


@pytest.mark.parametrize(
    "cls,factory", [(CalibrationDataset, dataset), (CalibrationReport, report)]
)
def test_generic_validate_accepts_new_roots_and_rejects_duplicate_or_deep_json(
    tmp_path, capsys, cls, factory
):
    p = tmp_path / "input.json"
    payload = factory()
    p.write_bytes(canonical(payload))
    assert main(["validate", str(p)]) == 0
    assert capsys.readouterr().out == canonical(payload).decode()
    p.write_text('{"schema_version":"' + payload["schema_version"] + '","schema_version":"x"}')
    assert main(["validate", str(p)]) == 1
    assert capsys.readouterr().out == ""
    with pytest.raises(ValueError):
        cls.model_validate_json(p.read_bytes())
    with pytest.raises(ValueError):
        cls.model_validate_json("[" * 33 + "0" + "]" * 33)
    with pytest.raises(ValueError):
        cls.model_validate_json(b"\xff")
    with pytest.raises(ValueError):
        cls.model_validate_json('{"x":NaN}')
    with pytest.raises(ValueError):
        cls.model_validate_json(b" " * (10 * 1024 * 1024 + 1))


def test_collection_bounds_reject_257_before_nested_validation():
    for field in ("sources", "artifacts", "entries", "reviews"):
        p = dataset()
        p[field] = [None] * 257
        with pytest.raises(ValidationError, match="container exceeds"):
            CalibrationDataset.model_validate(p)
    p = dataset()
    p["derivations"] = [None] * 513
    with pytest.raises(ValidationError, match="container exceeds"):
        CalibrationDataset.model_validate(p)


def test_source_alias_contradiction_is_intrinsic_even_with_valid_hash():
    p = dataset()
    p["sources"].append({**p["sources"][0], "source_id": "source-c", "session_id": "contradictory"})
    p["derivations"] = [dict(parent_source_id="source-a", child_source_id="source-c")]
    with pytest.raises(ValidationError, match="contradict"):
        CalibrationDataset.model_validate(seal_dataset(p))


def test_schema_additions_are_deterministic_and_old_schema_bytes_are_unchanged():
    from latency_fingerprinting.schemas import SCHEMA_MODELS

    for name, model in SCHEMA_MODELS.items():
        if name.startswith("calibration-"):
            continue
        assert Path("schemas", name).read_text() == render_schema(model)
    for cls in (CalibrationDataset, CalibrationReport):
        assert render_schema(cls) == render_schema(cls)
        schema = json.loads(render_schema(cls))
        assert schema["additionalProperties"] is False
        assert schema["properties"]["schema_version"]["const"].startswith("calibration-")


def test_review_subjects_must_exist_and_match_reference_kind():
    p = dataset()
    p["reviews"] = [
        dict(
            review_id="review-a",
            reviewer_id="reviewer-a",
            kind="independence",
            subject_ids=["source-b"],
            outcome="confirmed",
            evidence_sha256="sha256:" + "a" * 64,
        )
    ]
    p["sources"][0]["review_id"] = "review-a"
    with pytest.raises(ValidationError, match="subject"):
        CalibrationDataset.model_validate(seal_dataset(p))


def test_nested_copy_cannot_bypass_split_or_report_counts():
    model = CalibrationDataset.model_validate(dataset())
    forged = model.split.model_copy(update={"mode": "prospective"})
    with pytest.raises(ValidationError):
        CalibrationDataset.model_validate(model.model_copy(update={"split": forged}))
    result = CalibrationReport.model_validate(report())
    counts = result.counts.model_copy(update={"eligible_entries": True})
    with pytest.raises(ValidationError):
        CalibrationReport.model_validate(result.model_copy(update={"counts": counts}))
