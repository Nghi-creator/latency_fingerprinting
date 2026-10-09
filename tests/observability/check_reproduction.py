"""Read-only N4 release pins and independently authored timing expectations."""

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

from latency_fingerprinting.cli import main as cli_main
from latency_fingerprinting.observability import StageTraceRecord, reconstruct_trace
from latency_fingerprinting.observability.bundle import ingest_trace_bundle
from latency_fingerprinting.pipeline import canonical_json

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures/observability"
CASES = ("host", "browser", "browser-unavailable")
# Reviewed release 1.0.0 pins. No regeneration mode: fixture edits require review.
EXPECTED_SHA256 = {
    "browser/expected-summary.json": (
        "c4e28889ca1065cd1f9de26441cba62f62c6e8ce92bf649feb8dd855c62ff553"
    ),
    "browser/trace-manifest.json": (
        "528a8872b287354e9cabdea509f96843d7e13b0848ce248c5df7fb7110203b3b"
    ),
    "browser/trace-record.json": (
        "61eb52222b6e5ce12d0de65d8a3ddcea31315199766a12e1a15b373ff7910777"
    ),
    "browser-unavailable/expected-summary.json": (
        "fbc55ac6d070023ece719c469458b169ed2d9f562e4f92b1936222206566f55a"
    ),
    "browser-unavailable/trace-manifest.json": (
        "cb942b3049559d1d1ff1c7ca9bc7cd6be8b1b0ffd26e4b09354248fdb5403472"
    ),
    "browser-unavailable/trace-record.json": (
        "f5ae3caff04515f5e28fe874a717b81ab6246b8160b8f403426d3838cd192075"
    ),
    "host/expected-summary.json": (
        "684b1b166a4e188d62b887f30a44769fa2bbec843a7179e4eb895a8a29d19351"
    ),
    "host/trace-manifest.json": (
        "32b1dd4f5bd1a07adbee79fa00577250dbede498c78cc3d40f211ea841b63cc4"
    ),
    "host/trace-record.json": ("7657d2898d778e27f0ca79f96173d0ff4135f57210fe0dd749749439c578e8be"),
}


def check_reproduction(directory=FIXTURES, producer_bundles=None):
    hashes = {
        path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.rglob("*.json"))
    }
    if hashes != EXPECTED_SHA256:
        raise ValueError("N4 fixture release pin mismatch")
    for case in CASES:
        source = directory / case
        payload = (source / "trace-record.json").read_bytes()
        record = StageTraceRecord.model_validate_json(payload)
        if canonical_json(record).encode() != payload:
            raise ValueError("N4 record canonical drift")
        expected = (source / "expected-summary.json").read_bytes()
        if canonical_json(reconstruct_trace(record)).encode() != expected:
            raise ValueError("N4 independent timing expectation mismatch")
        # Fixture expectations are not bundle members. Stage exactly the two approved files.
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary).resolve()
            for name in ("trace-record.json", "trace-manifest.json"):
                (bundle / name).write_bytes((source / name).read_bytes())
            if ingest_trace_bundle(bundle) != record:
                raise ValueError("N4 directory adoption drift")
        if producer_bundles is not None:
            produced = ingest_trace_bundle(producer_bundles / f"{case}.tar.gz")
            if canonical_json(produced).encode() != payload:
                raise ValueError("N4 producer record drift")
            if canonical_json(reconstruct_trace(produced)).encode() != expected:
                raise ValueError("N4 producer inspection drift")
            with tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary).resolve()
                adopted, inspected = output / "record.json", output / "summary.json"
                if (
                    cli_main(
                        [
                            "ingest-trace",
                            "--bundle",
                            str(producer_bundles / f"{case}.tar.gz"),
                            "--output",
                            str(adopted),
                        ]
                    )
                    != 0
                ):
                    raise ValueError("N4 producer adoption CLI failed")
                if (
                    cli_main(["inspect-trace", "--trace", str(adopted), "--output", str(inspected)])
                    != 0
                ):
                    raise ValueError("N4 producer inspection CLI failed")
                if adopted.read_bytes() != payload or inspected.read_bytes() != expected:
                    raise ValueError("N4 producer CLI bytes drift")
    return {
        "status": "current",
        "fixtureRelease": "1.0.0",
        "fixtureSha256": hashes,
        "producerIntegration": "passed" if producer_bundles is not None else "not_run",
        "provenance": "synthetic",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--producer-bundles", type=Path)
    args = parser.parse_args()
    try:
        result = check_reproduction(producer_bundles=args.producer_bundles)
    except (OSError, ValueError):
        print("error: N4 reproduction failed", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
