"""N2 public ingestion retains bounded-reader failures without partial records."""

import io
import tarfile

import pytest

from latency_fingerprinting import json_io
from latency_fingerprinting.adapters import pixelated_bundle_io as bundle_io
from latency_fingerprinting.cli import main
from tests.pixelated.support import FIXTURE_ROOT, copy_v2_bundle, write_tar


def args(bundle, context):
    return [
        "ingest-pixelated-v2",
        str(bundle),
        "--context",
        str(context),
        "--phase",
        "degraded",
        "--comparison-case-id",
        "controlled-case-001",
    ]


@pytest.mark.parametrize(
    "fault,message",
    [
        ("context_bytes", "too large"),
        ("context_depth", "maximum depth"),
        ("bundle_bytes", "bundle size limit"),
        ("archive_bytes", "TAR archive is too large"),
        ("archive_members", "more than 1 members"),
        ("csv_header", "duplicate"),
        ("csv_rows", "more than 5 data rows"),
        ("traversal", "unsafe TAR member path"),
        ("absolute", "unsafe TAR member path"),
    ],
)
def test_public_n2_boundary_failure_is_repeatable(tmp_path, monkeypatch, capsys, fault, message):
    bundle = copy_v2_bundle(tmp_path)
    context = tmp_path / "context.json"
    context.write_bytes((FIXTURE_ROOT / "context-v2.json").read_bytes())
    if fault == "context_bytes":
        context.write_bytes(b" " * (json_io.MAX_CONTRACT_JSON_BYTES + 1))
    elif fault == "context_depth":
        context.write_text("[" * 129 + "0" + "]" * 129)
    elif fault == "bundle_bytes":
        monkeypatch.setattr(bundle_io, "MAX_BUNDLE_BYTES", 10)
    elif fault == "csv_rows":
        monkeypatch.setattr(bundle_io, "MAX_CSV_ROWS", 5)
    elif fault == "csv_header":
        path = bundle / "stream-telemetry.csv"
        path.write_text(path.read_text().replace("captured_at,", "elapsed_ms,", 1))
    else:
        archive = tmp_path / "bundle.tar"
        if fault in {"traversal", "absolute"}:
            with tarfile.open(archive, "w") as file:
                info = tarfile.TarInfo(
                    "../run-metadata.json" if fault == "traversal" else "/run-metadata.json"
                )
                info.size = 2
                file.addfile(info, io.BytesIO(b"{}"))
        else:
            write_tar(bundle, archive)
            if fault == "archive_bytes":
                monkeypatch.setattr(bundle_io, "MAX_ARCHIVE_BYTES", 10)
            else:
                monkeypatch.setattr(bundle_io, "MAX_ARCHIVE_MEMBERS", 1)
        bundle = archive
    previous = None
    for _ in range(2):
        assert main(args(bundle, context)) == 1
        output = capsys.readouterr()
        assert output.out == "" and "Traceback" not in output.err
        assert message in output.err
        assert previous is None or previous == output.err
        previous = output.err


def test_n2_cli_accepts_exact_row_limit(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(bundle_io, "MAX_CSV_ROWS", 6)
    assert main(args(copy_v2_bundle(tmp_path), FIXTURE_ROOT / "context-v2.json")) == 0
    output = capsys.readouterr()
    assert '"schemaVersion": "observation-window-v2"' in output.out and output.err == ""
