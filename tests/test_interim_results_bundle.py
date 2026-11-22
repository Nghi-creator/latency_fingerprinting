"""Published result projections remain complete, bounded and independently tallyable."""

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

BUNDLE = Path(__file__).resolve().parents[1] / "experiments/n11/receiver-ack-baseline-v1"
SPEC = importlib.util.spec_from_file_location(
    "interim_results_verifier", BUNDLE / "verify_results.py"
)
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)


def rewrite(directory, name, mutate, *, reseal):
    path = directory / name
    value = json.loads(path.read_text())
    mutate(value)
    path.write_text(json.dumps(value, indent=2) + "\n")
    if reseal:
        manifest = directory / "checksums.json"
        checksums = json.loads(manifest.read_text())
        checksums["files"][name] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        manifest.write_text(json.dumps(checksums, indent=2) + "\n")


def test_complete_published_outcomes_verify():
    result = VERIFIER.verify(BUNDLE)
    assert (result["queries"], result["correct"], result["abstain"], result["incorrect"]) == (
        18,
        15,
        3,
        0,
    )
    assert result["by_condition"]["no_injected_fault"] == {"abstain": 3, "correct": 3}


@pytest.mark.parametrize(
    "name,mutate,reseal,message",
    [
        ("outcomes.json", lambda v: v["queries"].pop(), False, "checksum mismatch"),
        (
            "outcomes.json",
            lambda v: v["queries"][0].update(declared_fixture_condition="no_injected_fault"),
            True,
            "differs from protocol",
        ),
        ("verification.json", lambda v: v.update(correct_queries=18), True, "summary differs"),
        (
            "calibration.json",
            lambda v: v.update(evaluation_acquisitions_started_at_freeze=1),
            True,
            "fit freeze order",
        ),
    ],
)
def test_tampering_or_resealed_inconsistent_claims_fail(tmp_path, name, mutate, reseal, message):
    directory = tmp_path / "bundle"
    shutil.copytree(BUNDLE, directory)
    rewrite(directory, name, mutate, reseal=reseal)
    with pytest.raises(ValueError, match=message):
        VERIFIER.verify(directory)


def test_bundle_does_not_publish_private_machine_paths():
    for path in BUNDLE.iterdir():
        if path.is_file():
            text = path.read_text()
            assert not any(
                value in text for value in ("/Users/", "/private/var/", "nick_kino", "C:\\Users\\")
            )


def test_verifier_runs_standalone_outside_checkout(tmp_path):
    result = subprocess.run(  # noqa: S603 -- fixed checked-in verifier with current interpreter
        [sys.executable, "-I", str(BUNDLE / "verify_results.py")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout)["correct"] == 15
