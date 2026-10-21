"""Read-only N7 release: independent frozen arithmetic/lifecycle and linked exclusions."""

import hashlib
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from latency_fingerprinting.adapters.pixelated_bundle_io import _open_bundle
from latency_fingerprinting.calibration.bundle_io import read_at
from latency_fingerprinting.cli import main as cli_main
from latency_fingerprinting.profiles import (
    ProfilePolicy,
    ProfileSnapshot,
    build_profile_snapshot,
    create_profile_snapshot,
    transition_profile_snapshot,
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

from .cases import canonical

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures/profiles-v1"
RELEASE_SHA256 = "4fd65662be2bff3f1f87866e32c5156d2857f2728f22a1b00a803794f950a1c3"
MAX_FILES = 32
MAX_TOTAL_BYTES = 8 * 1024 * 1024
RETAINED = b"retained output\n"


def _inventory(parent):
    names = set()
    with os.scandir(parent) as entries:
        for entry in entries:
            if len(names) >= MAX_FILES:
                raise ValueError("N7 fixture inventory mismatch")
            names.add(entry.name)
    return names


def load_release(directory=FIXTURES):
    """Pin one flat inventory, bound all reads, and verify independent release bytes."""
    parent = _open_bundle(Path(directory))
    try:
        names = _inventory(parent)
        raw = read_at(parent, "release.json", 1024 * 1024)
        if hashlib.sha256(raw).hexdigest() != RELEASE_SHA256:
            raise ValueError("N7 release pin mismatch")
        release = json.loads(raw)
        if names != set(release["sha256"]) | {"release.json"}:
            raise ValueError("N7 fixture inventory mismatch")
        if release["n6_release_sha256"] != N6_RELEASE_SHA256:
            raise ValueError("N7 dependency pin mismatch")
        payloads = {}
        total = len(raw)
        if total > MAX_TOTAL_BYTES:
            raise ValueError("N7 fixture byte budget exceeded")
        for name, expected in release["sha256"].items():
            if Path(name).name != name:
                raise ValueError("N7 fixture inventory mismatch")
            content = read_at(parent, name, min(1024 * 1024, MAX_TOTAL_BYTES - total))
            total += len(content)
            if hashlib.sha256(content).hexdigest() != expected:
                raise ValueError("N7 fixture release pin mismatch")
            payloads[name] = json.loads(content)
        if _inventory(parent) != names:
            raise ValueError("N7 fixture inventory changed")
        return release, payloads
    finally:
        os.close(parent)


def build_projection(snapshot):
    """Retained decisions, complete features and denominators, excluding content IDs."""
    payload = snapshot.model_dump(mode="json")
    return dict(
        inputs=payload["inputs"],
        profiles=sorted(
            [
                {k: v for k, v in p.items() if k not in ("profile_id", "partition_id")}
                for p in payload["profiles"]
            ],
            key=lambda p: p["label"],
        ),
        counts=payload["counts"],
        lifecycle=payload["lifecycle"],
        assurance=payload["assurance"],
    )


def invoke_local(arguments):
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = cli_main(list(map(str, arguments)))
    return code, stdout.getvalue().encode(), stderr.getvalue().encode()


def check_case(
    case,
    payloads,
    output,
    *,
    directory=FIXTURES,
    n6_directory=N6_FIXTURES,
    n6_release=None,
    invoke=invoke_local,
):
    """Compare API and CLI with frozen expectations; optionally run an installed CLI."""
    directory, n6_directory = Path(directory), Path(n6_directory)
    operation = case["operation"]
    policy = payloads["policy.json"]
    if operation == "validate":
        arguments = ["validate", directory / case["snapshot"]]

        def api():
            model = ProfilePolicy if case["snapshot"] == "policy.json" else ProfileSnapshot
            return model.model_validate(payloads[case["snapshot"]])
    elif operation == "create":
        arguments = ["create-profile-snapshot", "--policy", directory / "policy.json"]

        def api():
            return create_profile_snapshot(policy)
    elif operation == "build":
        arguments = [
            "build-profiles",
            "--directory",
            n6_directory / case["source"],
            "--policy",
            directory / "policy.json",
        ]
        parent = payloads[case["parent"]] if "parent" in case else None
        if parent is not None:
            arguments += ["--parent", directory / case["parent"]]

        def api():
            return build_profile_snapshot(n6_directory / case["source"], policy, parent=parent)
    else:
        arguments = [
            "transition-profile-snapshot",
            "--snapshot",
            directory / case["snapshot"],
            "--operation",
            operation,
            "--reason",
            case["reason"],
            "--review",
            directory / case["review"],
        ]
        replacement = payloads[case["replacement"]] if "replacement" in case else None
        if replacement is not None:
            arguments += ["--replacement", directory / case["replacement"]]

        def api():
            return transition_profile_snapshot(
                payloads[case["snapshot"]],
                operation=operation,
                reason_code=case["reason"],
                review=payloads[case["review"]],
                replacement=replacement,
            )

    invalid = "error" in case
    if invalid:
        try:
            api()
        except ValueError as error:
            if str(error) != case["error"]:
                raise ValueError("N7 API error drift") from None
        else:
            raise ValueError("N7 invalid case accepted")
        expected = RETAINED
    else:
        result = api()
        payload = result.model_dump(mode="json")
        if operation == "build":
            if n6_release is None:
                n6_release = load_n6_release(n6_directory)
            if report_projection(result.source_report) != n6_release["cases"][case["source"]]:
                raise ValueError("N7 source report expectation mismatch")
            if build_projection(result) != case["expected"]:
                raise ValueError("N7 independent build expectation mismatch")
        elif payload != payloads[case["expected_file"]]:
            raise ValueError("N7 independent snapshot expectation mismatch")
        expected = canonical(payload)
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
        raise ValueError("N7 CLI status/privacy drift")
    if output.read_bytes() != (RETAINED if operation == "validate" else expected):
        raise ValueError("N7 CLI output/preservation drift")


def check_reproduction(directory=FIXTURES, *, n6_directory=N6_FIXTURES, invoke=invoke_local):
    release, payloads = load_release(directory)
    n6_release = load_n6_release(n6_directory)
    with tempfile.TemporaryDirectory(prefix="n7-reproduction-") as temporary:
        output = Path(temporary).resolve() / "snapshot.json"
        for case in release["cases"].values():
            check_case(
                case,
                payloads,
                output,
                directory=directory,
                n6_directory=n6_directory,
                n6_release=n6_release,
                invoke=invoke,
            )
    load_release(directory)
    load_n6_release(n6_directory)
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
        print("error: N7 reproduction failed", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
