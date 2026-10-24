"""Bounded read-only N9 release with independent complete results and byte pins."""

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

from latency_fingerprinting.adapters.pixelated_bundle_io import _open_bundle
from latency_fingerprinting.calibration.bundle_io import read_at
from latency_fingerprinting.passive_gating import (
    PassiveBaseline,
    PassiveGatePolicy,
    PassiveGateResult,
    PassiveReplay,
    build_passive_baseline,
    replay_passive_gate,
)
from tests.calibration.check_reproduction import FIXTURES as N6_FIXTURES
from tests.calibration.check_reproduction import RELEASE_SHA256 as N6_RELEASE_SHA256
from tests.calibration.check_reproduction import load_release as load_n6_release
from tests.profile_matching.check_reproduction import FIXTURES as N8_FIXTURES
from tests.profile_matching.check_reproduction import RELEASE_SHA256 as N8_RELEASE_SHA256
from tests.profile_matching.check_reproduction import load_release as load_n8_release
from tests.profiles.check_reproduction import FIXTURES as N7_FIXTURES
from tests.profiles.check_reproduction import RELEASE_SHA256 as N7_RELEASE_SHA256
from tests.profiles.check_reproduction import RETAINED, invoke_local
from tests.profiles.check_reproduction import load_release as load_n7_release

from .cases import canonical

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures/passive-gating-v1"
RELEASE_SHA256 = "9697ffd3e1dc8922b4181471ffd8c2b6256a582718381650d5c4cfd54baa2b20"
POLICY_HASH = "sha256:07beb342e6ae7387a6edb2235ba0b26a5122fb3fffb5f83b7da2e7109f48a5ca"
DESIGN_SHA256 = "3c024642afbfe43aa9fded4cbd0202b11ec23afb7aed7fe2d7e5799bcf1e8660"
MAX_FILES = 192
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_FILE_BYTES = 10 * 1024 * 1024
MODELS = {
    "passive-gate-policy-v1": PassiveGatePolicy,
    "passive-baseline-v1": PassiveBaseline,
    "passive-replay-v1": PassiveReplay,
    "passive-gate-result-v1": PassiveGateResult,
}


def _leaf(name):
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise ValueError("N9 fixture inventory mismatch")
    return name


def _inventory(parent):
    names = set()
    with os.scandir(parent) as entries:
        for entry in entries:
            if len(names) >= MAX_FILES:
                raise ValueError("N9 fixture inventory mismatch")
            names.add(entry.name)
    return names


def load_release(directory=FIXTURES):
    """Pin the exact flat inventory with bounded no-follow reads, retaining source bytes."""
    parent = _open_bundle(Path(directory))
    try:
        names = _inventory(parent)
        raw = read_at(parent, "release.json", 1024 * 1024)
        if hashlib.sha256(raw).hexdigest() != RELEASE_SHA256:
            raise ValueError("N9 release pin mismatch")
        release = json.loads(raw)
        if names != set(release["sha256"]) | {"release.json"}:
            raise ValueError("N9 fixture inventory mismatch")
        if (
            release["n6_release_sha256"] != N6_RELEASE_SHA256
            or release["n7_release_sha256"] != N7_RELEASE_SHA256
            or release["n8_release_sha256"] != N8_RELEASE_SHA256
            or release["policy_content_hash"] != POLICY_HASH
            or release["design_vectors_sha256"] != DESIGN_SHA256
        ):
            raise ValueError("N9 dependency pin mismatch")
        payloads, total = {}, len(raw)
        if total > MAX_TOTAL_BYTES:
            raise ValueError("N9 fixture byte budget exceeded")
        for name, expected in release["sha256"].items():
            _leaf(name)
            content = read_at(parent, name, min(MAX_FILE_BYTES, MAX_TOTAL_BYTES - total))
            total += len(content)
            if hashlib.sha256(content).hexdigest() != expected:
                raise ValueError("N9 fixture release pin mismatch")
            payloads[name] = content if name.startswith("source-") else json.loads(content)
        for source, members in release["sources"].items():
            _leaf(source)
            for name, operand in members.items():
                _leaf(name)
                if not isinstance(payloads[operand], bytes):
                    raise ValueError("N9 source operand mismatch")
        if _inventory(parent) != names:
            raise ValueError("N9 fixture inventory changed")
        return release, payloads
    finally:
        os.close(parent)


def _check_source(directory, members, payloads):
    parent = _open_bundle(directory)
    try:
        if _inventory(parent) != set(members):
            raise ValueError("N9 staged source inventory changed")
        for name, operand in members.items():
            if read_at(parent, name, MAX_FILE_BYTES) != payloads[operand]:
                raise ValueError("N9 staged source bytes changed")
        if _inventory(parent) != set(members):
            raise ValueError("N9 staged source inventory changed")
    finally:
        os.close(parent)


def check_case(case, payloads, output, *, directory=FIXTURES, release=None, invoke=invoke_local):
    """Run actual APIs and CLI against literals; never generate or overwrite expectations."""
    if release is None:
        release, _ = load_release(directory)
    directory = Path(directory)
    operation = case["operation"]
    with tempfile.TemporaryDirectory(prefix="n9-source-") as temporary:
        source = Path(temporary).resolve()
        members = release["sources"][case["source"]] if operation != "validate" else {}
        for name, operand in members.items():
            (source / _leaf(name)).write_bytes(payloads[operand])
        if operation == "validate":
            operand = payloads[case["operand"]]
            arguments = ["validate", directory / case["operand"]]

            def api():
                return MODELS[operand["schema_version"]].model_validate(operand)
        else:
            policy = payloads[case.get("policy", "policy.json")]
            anchors = {
                k: case[k]
                for k in ("expected_split_id", "expected_dataset_content_hash")
                if k in case
            }
            arguments = [
                "build-passive-baseline" if operation == "build" else "replay-passive-gate",
                "--directory",
                source,
                "--policy",
                directory / case.get("policy", "policy.json"),
            ]
            for name, value in anchors.items():
                arguments += ["--" + name.replace("_", "-"), value]
            if operation == "build":

                def api():
                    return build_passive_baseline(source, policy, **anchors)
            else:
                arguments += [
                    "--baseline",
                    directory / case["baseline"],
                    "--replay",
                    directory / case["replay"],
                ]

                def api():
                    return replay_passive_gate(
                        source,
                        payloads[case["baseline"]],
                        payloads[case["replay"]],
                        policy,
                        **anchors,
                    )

        invalid = "error" in case
        if invalid:
            try:
                api()
            except ValueError as error:
                if operation != "validate" and str(error) != case["error"]:
                    raise ValueError("N9 API error drift") from None
            else:
                raise ValueError("N9 invalid case accepted")
            expected = RETAINED
            printed = b""
        else:
            expected = canonical(payloads[case["expected_file"]])
            if canonical(api().model_dump(mode="json")) != expected:
                raise ValueError("N9 independent result expectation mismatch")
            printed = canonical(payloads[case["wire_file"]]) if operation == "validate" else b""
        output.write_bytes(RETAINED)
        if operation != "validate":
            arguments += ["--output", output]
        code, stdout, stderr = invoke(arguments)
        message = f"error: {arguments[0]}: invalid_input_or_output\n".encode() if invalid else b""
        error_matches = (
            stderr.startswith(b"error: ") and stderr.endswith(b"\n")
            if invalid and operation == "validate"
            else stderr == message
        )
        if code != int(invalid) or not error_matches or stdout != printed:
            raise ValueError("N9 CLI status/privacy drift")
        if output.read_bytes() != (RETAINED if operation == "validate" else expected):
            raise ValueError("N9 CLI output/preservation drift")
        _check_source(source, members, payloads)


def check_reproduction(
    directory=FIXTURES,
    *,
    n6_directory=N6_FIXTURES,
    n7_directory=N7_FIXTURES,
    n8_directory=N8_FIXTURES,
    invoke=invoke_local,
):
    release, payloads = load_release(directory)
    load_n6_release(n6_directory)
    load_n7_release(n7_directory)
    load_n8_release(n8_directory)
    with tempfile.TemporaryDirectory(prefix="n9-reproduction-") as temporary:
        output = Path(temporary).resolve() / "result.json"
        for case in release["cases"].values():
            check_case(case, payloads, output, directory=directory, release=release, invoke=invoke)
    load_release(directory)
    load_n6_release(n6_directory)
    load_n7_release(n7_directory)
    load_n8_release(n8_directory)
    return dict(
        status="current",
        fixtureRelease=release["fixture_release"],
        cases=len(release["cases"]),
        provenance=release["provenance"],
        releaseSha256=RELEASE_SHA256,
        producerIntegration="not_run",
    )


def main():
    try:
        result = check_reproduction()
    except (OSError, ValueError):
        print("error: N9 reproduction failed", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
