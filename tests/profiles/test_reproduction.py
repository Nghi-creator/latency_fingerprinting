"""Frozen independent N7 release, bounded readers and meaningful oracle/CLI drift."""

import copy
import hashlib
import json
import os
import shutil

import pytest

from . import check_reproduction as module

RELEASE, PAYLOADS = module.load_release()


def corpus(tmp_path):
    root = tmp_path / "profiles"
    shutil.copytree(module.FIXTURES, root)
    return root


def test_complete_release_is_read_only_and_reports_limits(capsys):
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in module.FIXTURES.iterdir()}
    assert module.main() == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    result = json.loads(captured.out)
    assert result == dict(
        status="current",
        fixtureRelease="1.0.0",
        cases=34,
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
def test_every_frozen_operand_pin_detects_changes(name, tmp_path):
    root = corpus(tmp_path)
    path = root / name
    path.write_bytes(path.read_bytes() + b" ")
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
def test_exact_inventory_and_release_integrity(kind, tmp_path):
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
        for index in range(33):
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


def test_inventory_mutation_is_detected_and_parent_closed(tmp_path, monkeypatch):
    root = corpus(tmp_path)
    original = module.read_at
    parents = []

    def mutate(parent, name, maximum):
        parents.append(parent)
        if name == "policy.json":
            (root / "extra.json").write_bytes(b"{}")
        return original(parent, name, maximum)

    monkeypatch.setattr(module, "read_at", mutate)
    with pytest.raises(ValueError, match="inventory changed"):
        module.load_release(root)
    for parent in set(parents):
        with pytest.raises(OSError):
            os.fstat(parent)


@pytest.mark.parametrize("maximum", [1, 300_000])
def test_aggregate_byte_budget_is_enforced(maximum, monkeypatch):
    monkeypatch.setattr(module, "MAX_TOTAL_BYTES", maximum)
    with pytest.raises(ValueError):
        module.load_release()


def test_independent_group_and_gate_facts_are_frozen():
    names = list(PAYLOADS["policy.json"]["feature_names"])
    p = PAYLOADS["group-votes.json"]
    assert p["counts"]["selected_entries"] == 8
    assert p["counts"]["selected_groups"] == 5
    assert p["profiles"][0]["features"][names[0]]["center"] == 2.0
    assert p["profiles"][0]["features"][names[0]]["dispersion"] == 1.0
    for case, numerator, center, reasons in (
        ("availability-4of5", 4, 1.5, ["insufficient_group_support"]),
        ("availability-3of5", 3, 1.0, ["insufficient_group_support", "insufficient_availability"]),
    ):
        feature = PAYLOADS[case + ".json"]["profiles"][0]["features"][names[-1]]
        assert feature["availability"] == dict(
            numerator=numerator, denominator=5, value=numerator / 5
        )
        assert feature["center"] == center
        assert feature["dispersion"] == 1.0
        assert feature["reason_codes"] == reasons
    for case, active, state in (
        ("coverage-17", 17, "provisional"),
        ("coverage-16", 16, "rejected"),
        ("zero-dispersion", 0, "rejected"),
        ("insufficient-groups", 0, "rejected"),
    ):
        p = PAYLOADS[case + ".json"]
        assert p["profiles"][0]["active_feature_count"] == active
        assert p["lifecycle"]["state"] == state


def test_linked_sources_never_become_selected_model_examples():
    for name, case in RELEASE["cases"].items():
        if not name.startswith("linked-") or "error" in case:
            continue
        expected = case["expected"]
        assert expected["counts"]["selected_entries"] == 0
        assert expected["lifecycle"]["state"] == "rejected"
        assert all(not i["selected"] and i["feature_values"] is None for i in expected["inputs"])
        assert all(p["active_feature_count"] == 0 for p in expected["profiles"])


@pytest.mark.parametrize("kind", ["build", "snapshot", "source"])
def test_wrong_independent_expectations_are_not_accepted(kind, tmp_path):
    case = copy.deepcopy(
        RELEASE["cases"]["linked-reviewed-roles" if kind != "snapshot" else "create"]
    )
    payloads = copy.deepcopy(PAYLOADS)
    n6 = module.load_n6_release()
    if kind == "build":
        case["expected"]["counts"]["selected_entries"] = 1
    elif kind == "snapshot":
        payloads["draft.json"]["counts"]["selected_entries"] = 1
    else:
        n6["cases"][case["source"]]["counts"]["eligible_entries"] = 1
    with pytest.raises(ValueError, match="expectation mismatch"):
        module.check_case(case, payloads, tmp_path / "out.json", n6_release=n6)


@pytest.mark.parametrize("kind", ["stdout", "stderr", "code", "output"])
def test_cli_drift_is_detected(kind, tmp_path):
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
            RELEASE["cases"]["create"], PAYLOADS, tmp_path / "out.json", invoke=invoke
        )


def test_invalid_case_must_preserve_output(tmp_path):
    def invoke(arguments):
        result = module.invoke_local(arguments)
        (tmp_path / "out.json").write_bytes(b"lost output")
        return result

    with pytest.raises(ValueError, match="output/preservation drift"):
        module.check_case(
            RELEASE["cases"]["wrong-review-subject"], PAYLOADS, tmp_path / "out.json", invoke=invoke
        )


def test_main_failure_is_private(monkeypatch, capsys):
    def fail():
        raise ValueError("private path")

    monkeypatch.setattr(module, "check_reproduction", fail)
    assert module.main() == 1
    assert capsys.readouterr() == ("", "error: N7 reproduction failed\n")


@pytest.mark.parametrize("family", ["profiles", "n6"])
def test_post_execution_source_mutation_is_detected(family, tmp_path):
    root = corpus(tmp_path)
    n6 = tmp_path / "calibration"
    shutil.copytree(module.N6_FIXTURES, n6)
    calls = 0

    def invoke(arguments):
        nonlocal calls
        result = module.invoke_local(arguments)
        calls += 1
        if calls == len(RELEASE["cases"]):
            target = (
                root / "policy.json" if family == "profiles" else n6 / "baseline/response-a.json"
            )
            target.write_bytes(target.read_bytes() + b" ")
        return result

    with pytest.raises(ValueError, match="release pin mismatch"):
        module.check_reproduction(root, n6_directory=n6, invoke=invoke)
    assert calls == len(RELEASE["cases"])
