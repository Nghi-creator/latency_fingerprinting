"""Replay guard failures must not overwrite or promote original cases."""

import hashlib
import json

import pytest

from experiments.n11.physical_challenges.qualify import (
    REQUIRED,
    main,
    qualify_case,
    source_path,
    verify_sources,
)


def test_failed_overall_case_cannot_be_promoted_by_component_success(tmp_path):
    (tmp_path / "failure.json").write_text('{"status":"failed"}')
    with pytest.raises(ValueError, match="failed overall"):
        qualify_case(tmp_path, tmp_path)


def test_current_and_frozen_sources_are_both_required_and_changes_are_rejected(tmp_path):
    case, producer = tmp_path / "case", tmp_path / "producer"
    pins = {}
    for name in REQUIRED:
        for root in (case / "sources", producer / "engine/runtime"):
            p = root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"fixture")
        pins[name] = hashlib.sha256(b"fixture").hexdigest()
    verify_sources(case, producer, pins)
    (case / "sources" / REQUIRED[0]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed frozen/current"):
        verify_sources(case, producer, pins)
    (case / "sources" / REQUIRED[0]).write_bytes(b"fixture")
    (producer / "engine/runtime" / REQUIRED[0]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed frozen/current"):
        verify_sources(case, producer, pins)


def test_replay_paths_reject_traversal_and_symlink_parents(tmp_path):
    for name in ("../outside", "/outside", "scripts/../outside", "scripts\\outside"):
        with pytest.raises(ValueError):
            source_path(tmp_path, name)
    (tmp_path / "link").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        source_path(tmp_path, "link/file")


def test_cli_retains_failure_report_and_refuses_to_overwrite_it(tmp_path):
    case = tmp_path / "case"
    case.mkdir()
    (case / "failure.json").write_text("{}")
    output = tmp_path / "qualification.json"
    args = ["--case-directory", str(case), "--producer", str(tmp_path), "--output", str(output)]
    assert main(args) == 1
    assert json.loads(output.read_bytes())["state"] == "qualification_failed"
    original = output.read_bytes()
    with pytest.raises(FileExistsError):
        main(args)
    assert output.read_bytes() == original
