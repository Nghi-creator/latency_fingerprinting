"""Read-only N6 release pins and independently authored eligibility expectations."""

import hashlib
import io
import json
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from latency_fingerprinting.calibration import inspect_calibration_dataset
from latency_fingerprinting.cli import main as cli_main
from tests.calibration.cases import canonical

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures/calibration-v1"
RELEASE_SHA256 = "f2ff8d1060571096743289cbe28641a9a881c0b76a79787d697452c97b03f823"
CASES = (
    "baseline",
    "confounded",
    "controlled-healthy",
    "controlled-host",
    "controlled-pacing",
    "declared",
    "duplicate",
    "failed-effect",
    "missing",
    "mixed-settings",
    "reviewed-response",
    "reviewed-roles",
    "split-leakage",
    "wrong-binding",
)


def load_release(directory=FIXTURES):
    """Check the complete exact inventory before consuming any declared case paths."""
    directory = Path(directory)
    paths = []
    if directory.is_symlink():
        raise ValueError("N6 fixture inventory mismatch")
    for path in directory.rglob("*"):
        if len(paths) >= 64 or path.is_symlink():
            raise ValueError("N6 fixture inventory mismatch")
        paths.append(path)
    release_path = directory / "release.json"
    if release_path.stat().st_size > 1024 * 1024:
        raise ValueError("N6 release exceeds bound")
    raw = release_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != RELEASE_SHA256:
        raise ValueError("N6 release pin mismatch")
    release = json.loads(raw)
    files = {p.relative_to(directory).as_posix(): p for p in paths if p.is_file()}
    directories = {p.relative_to(directory).as_posix() for p in paths if p.is_dir()}
    if (
        set(files) != set(release["sha256"]) | {"release.json"}
        or directories != set(CASES)
        or set(release["cases"]) != set(CASES)
        or len(files) + len(directories) != len(paths)
    ):
        raise ValueError("N6 fixture inventory mismatch")
    for name, expected in release["sha256"].items():
        path = files[name]
        if path.stat().st_size > 10 * 1024 * 1024:
            raise ValueError("N6 fixture exceeds bound")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("N6 fixture release pin mismatch")
    return release


def report_projection(report):
    """Compare scientific decisions/denominators, not a self-generated report oracle."""
    payload = report.model_dump(mode="json") if hasattr(report, "model_dump") else report
    members = {}
    entries = []
    for entry in payload["entries"]:
        item = {key: value for key, value in entry.items() if key != "partition_id"}
        entries.append(item)
        if entry["partition_id"] is not None:
            members.setdefault(entry["partition_id"], []).append(entry["entry_id"])
    return dict(
        entries=entries,
        groups=payload["groups"],
        counts=payload["counts"],
        partition_members=sorted(members.values()),
        assurance=payload["assurance"],
    )


def check_case(source, expected, output):
    """Exercise API and CLI; an excluded valid dataset still succeeds as a whole."""
    args = ["inspect-calibration", "--directory", str(source), "--output", str(output)]

    def invoke(code):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            actual = cli_main(args)
        message = "error: inspect-calibration: invalid_input_or_output\n" if code else ""
        if actual != code or stdout.getvalue() or stderr.getvalue() != message:
            raise ValueError("N6 CLI status/privacy drift")

    if "error" in expected:
        try:
            inspect_calibration_dataset(source)
        except ValueError as error:
            if str(error) != expected["error"]:
                raise ValueError("N6 invalid case error drift") from None
        else:
            raise ValueError("N6 invalid case accepted")
        output.write_bytes(b"retained output\n")
        invoke(1)
        if output.read_bytes() != b"retained output\n":
            raise ValueError("N6 invalid case CLI drift")
        return
    result = inspect_calibration_dataset(source)
    if report_projection(result.report) != expected:
        raise ValueError("N6 independent eligibility expectation mismatch")
    if cli_main(args) != 0 or output.read_bytes() != canonical(
        result.report.model_dump(mode="json")
    ):
        raise ValueError("N6 API/CLI drift")
    # Generic public dispatch revalidates canonical inspection output.
    from latency_fingerprinting.calibration import CalibrationReport

    if CalibrationReport.model_validate_json(output.read_bytes()) != result.report:
        raise ValueError("N6 report dispatch drift")


def check_reproduction(directory=FIXTURES):
    release = load_release(directory)
    with tempfile.TemporaryDirectory(prefix="n6-reproduction-") as temporary:
        output = Path(temporary).resolve() / "report.json"
        for name in CASES:
            check_case(Path(directory) / name, release["cases"][name], output)
    # Detect any unexpected input mutation during inspection.
    load_release(directory)
    return dict(
        status="current",
        fixtureRelease=release["fixture_release"],
        cases=len(CASES),
        provenance=release["provenance"],
        releaseSha256=RELEASE_SHA256,
        producerIntegration="not_run",
    )


def main():
    try:
        result = check_reproduction()
    except (OSError, ValueError):
        print("error: N6 reproduction failed", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
