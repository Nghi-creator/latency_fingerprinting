"""Pinned old schemas and independent negative integrity/resource checks."""

import hashlib
import json
from pathlib import Path

import pytest

from latency_fingerprinting.cli import main
from latency_fingerprinting.evaluation import inputs, run_evaluation, seal_manifest

from .support import base, canonical, slot


def test_all_forty_old_schema_bytes_remain_pinned():
    old = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in Path("schemas").rglob("*.schema.json")
        if p.parent.name != "evaluation"
    }
    assert len(old) == 40
    assert (
        hashlib.sha256(json.dumps(old, sort_keys=True).encode()).hexdigest()
        == "ac428fe73226bf8a3e27f2b32cd6d7b05dc56e9efc699a62b7b9a0a7319ecb87"
    )


def test_input_budget_is_rejected_before_opening_any_receipt(tmp_path, monkeypatch):
    payload, paths = base(tmp_path)
    payload["slots"] = [slot("failure", state="failed")]
    manifest = seal_manifest(payload)
    monkeypatch.setattr(inputs, "MAX_INPUT_BYTES", 1)
    monkeypatch.setattr(inputs.Inputs, "read", lambda *a: pytest.fail("opened over-budget input"))
    with pytest.raises(ValueError, match="^invalid_evaluation$"):
        run_evaluation(manifest, paths)


@pytest.mark.parametrize("kind", ["symlink", "fifo", "directory", "changed", "extra_path"])
def test_bad_receipt_operands_are_fixed_private_errors(tmp_path, kind):
    import os

    payload, paths = base(tmp_path)
    payload["slots"] = [slot("failure", state="failed")]
    manifest = seal_manifest(payload)
    original = paths["protocol"]
    bad = tmp_path / "bad"
    if kind == "symlink":
        bad.symlink_to(original)
    elif kind == "fifo":
        os.mkfifo(bad)
    elif kind == "directory":
        bad.mkdir()
    elif kind == "changed":
        bad.write_bytes(b"private substituted contents")
    elif kind == "extra_path":
        paths["extra"] = original
        bad = original
    paths["protocol"] = bad
    with pytest.raises(ValueError, match="^invalid_evaluation$"):
        run_evaluation(manifest, paths)


def test_generic_validation_accepts_both_new_roots(tmp_path, capsys):
    import jsonschema

    from latency_fingerprinting.schemas import render_schema

    payload, paths = base(tmp_path)
    payload["slots"] = [slot("missing", state="not_started")]
    manifest = seal_manifest(payload)
    report = run_evaluation(manifest, paths).report
    for root in (manifest, report):
        body = root.model_dump(mode="json")
        jsonschema.validate(body, json.loads(render_schema(type(root))))
        p = tmp_path / (root.schema_version + ".json")
        p.write_bytes(canonical(body))
        assert main(["validate", str(p)]) == 0
        output = capsys.readouterr()
        assert not output.err
        assert json.loads(output.out) == body


def test_duplicate_operands_json_is_rejected_and_old_output_preserved(tmp_path, capsys):
    payload, paths = base(tmp_path)
    payload["slots"] = [slot("missing", state="not_started")]
    manifest = tmp_path / "manifest.json"
    manifest.write_bytes(canonical(seal_manifest(payload).model_dump(mode="json")))
    operands = tmp_path / "operands.json"
    operands.write_text(
        '{"paths":{},"paths":' + json.dumps({k: str(v) for k, v in paths.items()}) + "}"
    )
    output = tmp_path / "output.json"
    output.write_bytes(b"preserved output")
    assert (
        main(
            [
                "evaluate-study",
                "--manifest",
                str(manifest),
                "--operands",
                str(operands),
                "--output",
                str(output),
            ]
        )
        == 1
    )
    assert output.read_bytes() == b"preserved output"
    assert capsys.readouterr() == ("", "error: evaluate-study: invalid_input_or_output\n")
