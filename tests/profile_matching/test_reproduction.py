"""Frozen N8 oracles, exact inventories, source pins and API/CLI drift detection."""

import copy
import hashlib
import json
import os
import shutil

import pytest

from . import check_reproduction as module
from .cases import canonical

RELEASE, PAYLOADS = module.load_release()


def corpus(tmp_path):
    root = tmp_path / "matching"
    shutil.copytree(module.FIXTURES, root)
    return root


def test_release_is_read_only_and_reports_software_provenance(capsys):
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in module.FIXTURES.iterdir()}
    assert module.main() == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out) == dict(
        status="current",
        fixtureRelease="1.0.0",
        cases=75,
        provenance="synthetic_and_model_only",
        producerIntegration="not_run",
        releaseSha256=module.RELEASE_SHA256,
    )
    assert before == {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in module.FIXTURES.iterdir()
    }


@pytest.mark.parametrize("name", sorted(RELEASE["cases"]))
def test_every_frozen_case_matches_api_and_cli(name, tmp_path, capsys):
    module.check_case(RELEASE["cases"][name], PAYLOADS, tmp_path / "out.json")
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("name", sorted(RELEASE["sha256"]))
def test_every_operand_is_pinned(name, tmp_path):
    root = corpus(tmp_path)
    p = root / name
    p.write_bytes(p.read_bytes() + b" ")
    with pytest.raises(ValueError, match="fixture release pin mismatch"):
        module.load_release(root)


@pytest.mark.parametrize(
    "kind",
    [
        "missing",
        "extra",
        "directory",
        "symlink",
        "fifo",
        "release",
        "release-fifo",
        "release-directory",
        "flood",
        "root-symlink",
    ],
)
def test_inventory_and_release_integrity(kind, tmp_path):
    root = corpus(tmp_path)
    path = root / "policy.json"
    if kind == "missing":
        path.unlink()
    elif kind == "extra":
        (root / "extra.json").write_bytes(b"{}")
    elif kind in {"directory", "symlink", "fifo"}:
        path.unlink()
        if kind == "directory":
            path.mkdir()
        elif kind == "symlink":
            path.symlink_to(module.FIXTURES / path.name)
        else:
            os.mkfifo(path)
    elif kind.startswith("release"):
        path = root / "release.json"
        if kind == "release":
            path.write_bytes(path.read_bytes() + b" ")
        else:
            path.unlink()
            if kind == "release-fifo":
                os.mkfifo(path)
            else:
                path.mkdir()
    elif kind == "root-symlink":
        alias = tmp_path / "alias"
        alias.symlink_to(root, target_is_directory=True)
        root = alias
    else:
        for index in range(module.MAX_FILES + 1):
            (root / f"extra-{index}.json").write_bytes(b"{}")
    with pytest.raises((OSError, ValueError)):
        module.load_release(root)


@pytest.mark.parametrize("name", ["release.json", "policy.json"])
@pytest.mark.parametrize("kind", ["fifo", "symlink", "growth"])
def test_post_inventory_replacement_is_bounded(name, kind, tmp_path, monkeypatch):
    root = corpus(tmp_path)
    original = module.read_at

    def replace(parent, leaf, maximum):
        if leaf == name:
            path = root / leaf
            if kind == "growth":
                with path.open("ab") as target:
                    target.truncate(maximum + 1)
            else:
                path.unlink()
                if kind == "fifo":
                    os.mkfifo(path)
                else:
                    path.symlink_to(module.FIXTURES / name)
        return original(parent, leaf, maximum)

    monkeypatch.setattr(module, "read_at", replace)
    with pytest.raises((OSError, ValueError)):
        module.load_release(root)


def test_pinned_root_survives_path_replacement(tmp_path, monkeypatch):
    root = corpus(tmp_path)
    original = module.read_at

    def rename(parent, name, maximum):
        if name == "release.json":
            root.rename(tmp_path / "retained")
            root.mkdir()
            (root / "policy.json").write_bytes(b"unrelated")
        return original(parent, name, maximum)

    monkeypatch.setattr(module, "read_at", rename)
    assert module.load_release(root) == (RELEASE, PAYLOADS)


def test_inventory_mutation_is_detected_and_descriptors_closed(tmp_path, monkeypatch):
    root = corpus(tmp_path)
    original = module.read_at
    descriptors = set()

    def mutate(parent, name, maximum):
        descriptors.add(parent)
        if name == "policy.json":
            (root / "extra.json").write_bytes(b"{}")
        return original(parent, name, maximum)

    monkeypatch.setattr(module, "read_at", mutate)
    with pytest.raises(ValueError, match="inventory changed"):
        module.load_release(root)
    for fd in descriptors:
        with pytest.raises(OSError):
            os.fstat(fd)


@pytest.mark.parametrize("maximum", [1, 1000000])
def test_aggregate_byte_limit(maximum, monkeypatch):
    monkeypatch.setattr(module, "MAX_TOTAL_BYTES", maximum)
    with pytest.raises(ValueError):
        module.load_release()


@pytest.mark.parametrize(
    "field",
    ["n6_release_sha256", "n7_release_sha256", "policy_content_hash", "design_vectors_sha256"],
)
def test_dependency_pins_are_checked_even_with_faulty_release_pin(field, tmp_path, monkeypatch):
    root = corpus(tmp_path)
    release = copy.deepcopy(RELEASE)
    release[field] = "0" * 64
    raw = canonical(release)
    (root / "release.json").write_bytes(raw)
    monkeypatch.setattr(module, "RELEASE_SHA256", hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError, match="dependency pin mismatch"):
        module.load_release(root)


@pytest.mark.parametrize("kind", ["result", "source", "fit"])
def test_wrong_independent_expectations_fail(kind, tmp_path):
    case = RELEASE["cases"]["linked-match-reviewed-roles"]
    payloads = copy.deepcopy(PAYLOADS)
    n6 = module.load_n6_release()
    n7, _ = module.load_n7_release()
    if kind == "result":
        payloads[case["expected_file"]]["decision"]["reason_codes"] = []
    elif kind == "source":
        n6["cases"][case["source"]]["counts"]["eligible_entries"] = 1
    else:
        n7["cases"]["linked-" + case["source"]]["expected"]["counts"]["selected_entries"] = 1
    with pytest.raises(ValueError, match="expectation mismatch"):
        module.check_case(case, payloads, tmp_path / "out.json", n6_release=n6, n7_release=n7)


@pytest.mark.parametrize("kind", ["stdout", "stderr", "code", "output"])
@pytest.mark.parametrize("case_name", ["match-supported", "linked-match-reviewed-roles"])
def test_cli_drift_is_detected(kind, case_name, tmp_path):
    def invoke(arguments):
        code, stdout, stderr = module.invoke_local(arguments)
        if kind == "stdout":
            stdout += b"private diagnostic"
        elif kind == "stderr":
            stderr += b"private diagnostic"
        elif kind == "code":
            code = 1
        else:
            (tmp_path / "out.json").write_bytes(b"wrong output")
        return code, stdout, stderr

    with pytest.raises(ValueError, match="CLI (status/privacy|output/preservation) drift"):
        module.check_case(
            RELEASE["cases"][case_name], PAYLOADS, tmp_path / "out.json", invoke=invoke
        )


def test_invalid_case_must_preserve_output(tmp_path):
    def invoke(arguments):
        result = module.invoke_local(arguments)
        (tmp_path / "out.json").write_bytes(b"lost output")
        return result

    with pytest.raises(ValueError, match="output/preservation drift"):
        module.check_case(
            RELEASE["cases"]["unknown-query"], PAYLOADS, tmp_path / "out.json", invoke=invoke
        )


@pytest.mark.parametrize("fault", ["accept", "wrong_error"])
def test_faulty_api_errors_cannot_pass(fault, tmp_path, monkeypatch):
    def broken(*args, **kwargs):
        if fault == "wrong_error":
            raise ValueError("private failure")
        return module.ProfileMatchResult.model_validate(PAYLOADS["match-supported.json"])

    monkeypatch.setattr(module, "match_profile_snapshot", broken)
    with pytest.raises(ValueError, match="N8 (invalid case accepted|API error drift)"):
        module.check_case(RELEASE["cases"]["unknown-query"], PAYLOADS, tmp_path / "out.json")


def test_main_failure_is_private(monkeypatch, capsys):
    def fail():
        raise ValueError("private path")

    monkeypatch.setattr(module, "check_reproduction", fail)
    assert module.main() == 1
    assert capsys.readouterr() == ("", "error: N8 reproduction failed\n")


@pytest.mark.parametrize("family", ["n8", "n7", "n6"])
def test_post_execution_dependency_mutation_is_detected(family, tmp_path):
    root = corpus(tmp_path)
    n6, n7 = tmp_path / "calibration", tmp_path / "profiles"
    shutil.copytree(module.N6_FIXTURES, n6)
    shutil.copytree(module.N7_FIXTURES, n7)
    calls = 0

    def invoke(arguments):
        nonlocal calls
        result = module.invoke_local(arguments)
        calls += 1
        if calls == len(RELEASE["cases"]):
            target = dict(
                n8=root / "policy.json", n7=n7 / "policy.json", n6=n6 / "baseline/response-a.json"
            )[family]
            target.write_bytes(target.read_bytes() + b" ")
        return result

    with pytest.raises(ValueError, match="release pin mismatch"):
        module.check_reproduction(root, n6_directory=n6, n7_directory=n7, invoke=invoke)
    assert calls == len(RELEASE["cases"])


def test_independent_scoring_and_refit_facts_remain_frozen():
    assert PAYLOADS["margin-boundary.json"]["decision"]["margin"] == 0.25
    assert PAYLOADS["tie.json"]["decision"]["chosen_label"] is None
    assert PAYLOADS["distance-boundary.json"]["decision"]["best_distance"] == 3.0
    assert all(
        value.hex().startswith("-0x0")
        for value in PAYLOADS["signed-zero.json"]["decision"]["query_feature_values"].values()
    )
    assert PAYLOADS["refits-supported.json"]["counts"]["computed_refits"] == 12
    assert PAYLOADS["refits-supported.json"]["counts"]["correct_groups"] == 8
    assert PAYLOADS["refits-unsupported.json"]["counts"]["unknown_groups"] == 10
    assert PAYLOADS["evaluate-reviewed-roles-leave_training_group_out.json"]["metrics"][
        "accuracy"
    ] == dict(numerator=0, denominator=1, value=0.0)
    assert PAYLOADS["evaluate-missing-validation.json"]["metrics"]["accuracy"]["value"] is None
    for name, case in RELEASE["cases"].items():
        if name.startswith("linked-"):
            result = PAYLOADS[case["expected_file"]]
            decisions = (
                [result["decision"]] if case["operation"] == "match" else result["decisions"]
            )
            assert all(
                d["chosen_label"] is None and d["query_feature_values"] is None for d in decisions
            )
