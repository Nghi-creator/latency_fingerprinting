"""Read-only N8 release pins and independent standalone/linked result expectations."""

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

from latency_fingerprinting.adapters.pixelated_bundle_io import _open_bundle
from latency_fingerprinting.calibration.bundle_io import read_at
from latency_fingerprinting.profile_matching import (
    ProfileEvaluationResult,
    ProfileMatchPolicy,
    ProfileMatchResult,
    evaluate_profile_snapshot,
    match_profile_snapshot,
)
from tests.calibration.check_reproduction import (
    FIXTURES as N6_FIXTURES,
)
from tests.calibration.check_reproduction import (
    RELEASE_SHA256 as N6_RELEASE_SHA256,
)
from tests.calibration.check_reproduction import (
    load_release as load_n6_release,
)
from tests.calibration.check_reproduction import report_projection
from tests.profiles.check_reproduction import (
    FIXTURES as N7_FIXTURES,
)
from tests.profiles.check_reproduction import (
    RELEASE_SHA256 as N7_RELEASE_SHA256,
)
from tests.profiles.check_reproduction import (
    RETAINED,
    build_projection,
    invoke_local,
)
from tests.profiles.check_reproduction import (
    load_release as load_n7_release,
)

from .cases import canonical

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures/profile-matching-v1"
RELEASE_SHA256 = "e5a17e88381104d5120acf316e6fbccf93a2ac20db03e96dea7c2ee14aff96a7"
POLICY_HASH = "sha256:b296df5c172d19e9470f64b3546fcb7af54c6623dd5951bc0c652a94e87b95db"
DESIGN_SHA256 = "42b2bb4d483f3605122a8aa2090153f200470f03466163f552e0ef8497e35c65"
MAX_FILES = 96
MAX_TOTAL_BYTES = 16 * 1024 * 1024
MAX_FILE_BYTES = 10 * 1024 * 1024
MODELS = {
    "profile-match-policy-v1": ProfileMatchPolicy,
    "profile-match-result-v1": ProfileMatchResult,
    "profile-evaluation-result-v1": ProfileEvaluationResult,
}


def _inventory(parent):
    names = set()
    with os.scandir(parent) as entries:
        for entry in entries:
            if len(names) >= MAX_FILES:
                raise ValueError("N8 fixture inventory mismatch")
            names.add(entry.name)
    return names


def load_release(directory=FIXTURES):
    """Bound every no-follow read and pin the exact flat inventory before execution."""
    parent = _open_bundle(Path(directory))
    try:
        names = _inventory(parent)
        raw = read_at(parent, "release.json", 1024 * 1024)
        if hashlib.sha256(raw).hexdigest() != RELEASE_SHA256:
            raise ValueError("N8 release pin mismatch")
        release = json.loads(raw)
        if names != set(release["sha256"]) | {"release.json"}:
            raise ValueError("N8 fixture inventory mismatch")
        if (
            release["n6_release_sha256"] != N6_RELEASE_SHA256
            or release["n7_release_sha256"] != N7_RELEASE_SHA256
            or release["policy_content_hash"] != POLICY_HASH
            or release["design_vectors_sha256"] != DESIGN_SHA256
        ):
            raise ValueError("N8 dependency pin mismatch")
        payloads, total = {}, len(raw)
        if total > MAX_TOTAL_BYTES:
            raise ValueError("N8 fixture byte budget exceeded")
        for name, expected in release["sha256"].items():
            if not name or Path(name).name != name:
                raise ValueError("N8 fixture inventory mismatch")
            content = read_at(parent, name, min(MAX_FILE_BYTES, MAX_TOTAL_BYTES - total))
            total += len(content)
            if hashlib.sha256(content).hexdigest() != expected:
                raise ValueError("N8 fixture release pin mismatch")
            payloads[name] = json.loads(content)
        if _inventory(parent) != names:
            raise ValueError("N8 fixture inventory changed")
        return release, payloads
    finally:
        os.close(parent)


def check_case(
    case,
    payloads,
    output,
    *,
    directory=FIXTURES,
    n6_directory=N6_FIXTURES,
    n6_release=None,
    n7_release=None,
    invoke=invoke_local,
):
    """Compare full API/CLI bytes with frozen independent results, never bless output."""
    directory, n6_directory = Path(directory), Path(n6_directory)
    operation = case["operation"]
    if operation == "validate":
        operand = payloads[case["operand"]]
        arguments = ["validate", directory / case["operand"]]

        def api():
            return MODELS[operand["schema_version"]].model_validate(operand)
    else:
        policy_file = case.get("policy", "policy.json")
        snapshot, policy = payloads[case["snapshot"]], payloads[policy_file]
        anchors = {
            k: case[k] for k in ("expected_split_id", "expected_dataset_content_hash") if k in case
        }
        arguments = [
            "match-profiles" if operation == "match" else "evaluate-profiles",
            "--directory",
            n6_directory / case["source"],
            "--snapshot",
            directory / case["snapshot"],
            "--policy",
            directory / policy_file,
        ]
        for name, value in anchors.items():
            arguments += ["--" + name.replace("_", "-"), value]
        if operation == "match":
            arguments += ["--query-entry-id", case["query_entry_id"]]

            def api():
                return match_profile_snapshot(
                    n6_directory / case["source"],
                    snapshot,
                    policy,
                    query_entry_id=case["query_entry_id"],
                    **anchors,
                )
        else:
            arguments += ["--mode", case["mode"]]

            def api():
                return evaluate_profile_snapshot(
                    n6_directory / case["source"], snapshot, policy, mode=case["mode"], **anchors
                )

    invalid = "error" in case
    if invalid:
        try:
            api()
        except ValueError as error:
            if str(error) != case["error"]:
                raise ValueError("N8 API error drift") from None
        else:
            raise ValueError("N8 invalid case accepted")
        expected = RETAINED
    else:
        result = api()
        expected = canonical(payloads[case["expected_file"]])
        if canonical(result.model_dump(mode="json")) != expected:
            raise ValueError("N8 independent result expectation mismatch")
        if operation != "validate":
            if n6_release is None:
                n6_release = load_n6_release(n6_directory)
            if n7_release is None:
                n7_release, _ = load_n7_release()
            if report_projection(result.evidence.report) != n6_release["cases"][case["source"]]:
                raise ValueError("N8 independent N6 source expectation mismatch")
            if (
                build_projection(result.evidence.snapshot)
                != n7_release["cases"]["linked-" + case["source"]]["expected"]
            ):
                raise ValueError("N8 independent N7 fit expectation mismatch")
    output.write_bytes(RETAINED)
    if operation != "validate":
        arguments += ["--output", output]
    code, stdout, stderr = invoke(arguments)
    message = f"error: {arguments[0]}: invalid_input_or_output\n".encode() if invalid else b""
    if (
        code != int(invalid)
        or stderr != message
        or stdout != (expected if operation == "validate" else b"")
    ):
        raise ValueError("N8 CLI status/privacy drift")
    if output.read_bytes() != (RETAINED if operation == "validate" else expected):
        raise ValueError("N8 CLI output/preservation drift")


def check_reproduction(
    directory=FIXTURES,
    *,
    n6_directory=N6_FIXTURES,
    n7_directory=N7_FIXTURES,
    invoke=invoke_local,
):
    release, payloads = load_release(directory)
    n6_release = load_n6_release(n6_directory)
    n7_release, _ = load_n7_release(n7_directory)
    with tempfile.TemporaryDirectory(prefix="n8-reproduction-") as temporary:
        output = Path(temporary).resolve() / "result.json"
        for case in release["cases"].values():
            check_case(
                case,
                payloads,
                output,
                directory=directory,
                n6_directory=n6_directory,
                n6_release=n6_release,
                n7_release=n7_release,
                invoke=invoke,
            )
    load_release(directory)
    load_n6_release(n6_directory)
    load_n7_release(n7_directory)
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
        print("error: N8 reproduction failed", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
