"""Read-only browser execution release 1.0.0 pins and optional producer handoff."""

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from latency_fingerprinting.cli import main as cli_main
from latency_fingerprinting.json_io import canonical_json
from latency_fingerprinting.observability import reconstruct_trace
from latency_fingerprinting.observability.browser_v2 import StageTraceRecordV2
from latency_fingerprinting.observability.bundle import ingest_trace_bundle

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures/browser-execution-v1"
PINS = {
    "paired/expected-summary.json": (
        "3bdecb2aa1b4ea59ff903afe49e35756a820e4b39e9ea4a430d065eb53f7078e"
    ),
    "paired/trace-manifest.json": (
        "6ef68acddb1db1f3dfdfd1684bd1088cde319464384da1f756b6d15030048b9f"
    ),
    "paired/trace-record.json": (
        "ac735e7f7c6fb0e3e3bce6f644cd11cc5b45d04f3de90c7f65a12948bd854fd5"
    ),
    "partial/expected-summary.json": (
        "3e0270fd3f3e2d3b76b633f42e5f881bb86e3a3eb9d7815ac53170debe754eef"
    ),
    "partial/trace-manifest.json": (
        "cc80acf72cd1968a8278f7df527893bf33f84cb9a2546422b3ea82174d5fe3a8"
    ),
    "partial/trace-record.json": (
        "6dcbcd108a5e2c8791426fdbb826226f098c53d4a28994d8f4ba6bbc0c4f0e65"
    ),
    "unavailable/expected-summary.json": (
        "87ef2eb7a200939a8d38affcc47110a22f96d0315d00e6eb79319aff1d142b10"
    ),
    "unavailable/trace-manifest.json": (
        "594880c4440abe96697fcf71c6ff3bf9db548cc5ec152ca4227812b2aa54c6c9"
    ),
    "unavailable/trace-record.json": (
        "d93c613ddcdb527ab834f47753b7659c5cfcb8da17de69657e981940e63907fb"
    ),
}


def check_reproduction(directory=FIXTURES, producer_bundles=None):
    hashes = {
        p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(directory.rglob("*.json"))
    }
    if hashes != PINS:
        raise ValueError("browser execution fixture release pin mismatch")
    for case in ("paired", "partial", "unavailable"):
        source = directory / case
        payload = (source / "trace-record.json").read_bytes()
        expected = (source / "expected-summary.json").read_bytes()
        record = StageTraceRecordV2.model_validate_json(payload)
        if (
            canonical_json(record).encode() != payload
            or canonical_json(reconstruct_trace(record)).encode() != expected
        ):
            raise ValueError("browser execution independent expectation mismatch")
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary).resolve()
            if producer_bundles is None:
                bundle = output / "bundle"
                bundle.mkdir()
                for name in ("trace-record.json", "trace-manifest.json"):
                    (bundle / name).write_bytes((source / name).read_bytes())
            else:
                bundle = producer_bundles / f"{case}.tar.gz"
            if canonical_json(ingest_trace_bundle(bundle)).encode() != payload:
                raise ValueError("browser execution producer record drift")
            adopted, inspected = output / "record.json", output / "summary.json"
            if cli_main(
                ["ingest-trace", "--bundle", str(bundle), "--output", str(adopted)]
            ) or cli_main(["inspect-trace", "--trace", str(adopted), "--output", str(inspected)]):
                raise ValueError("browser execution CLI failure")
            if adopted.read_bytes() != payload or inspected.read_bytes() != expected:
                raise ValueError("browser execution CLI parity drift")
    return {
        "status": "current",
        "fixtureRelease": "1.0.0",
        "fixtureSha256": hashes,
        "producerIntegration": "passed" if producer_bundles is not None else "not_run",
        "provenance": "synthetic",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--producer-bundles", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            check_reproduction(producer_bundles=args.producer_bundles), indent=2, sort_keys=True
        )
    )
