"""N1 CI reproduction and public CLI failure/resource boundaries."""

import csv
import io
import json
import shutil
import tarfile
from pathlib import Path

import pytest

from latency_fingerprinting.adapters import pixelated_bundle_io as bundle_io
from latency_fingerprinting.cli import main
from latency_fingerprinting.json_io import MAX_CONTRACT_JSON_BYTES, MAX_JSON_NESTING_DEPTH

from . import check_reproduction as reproduction

FIXTURES = Path(__file__).resolve().parents[1] / "data/pixelated_bundle"


def copy_bundle(tmp_path):
    path = tmp_path / "bundle"
    shutil.copytree(FIXTURES / "valid-v2", path)
    return path


def args(bundle, context=FIXTURES / "context-v2.json"):
    return [
        "inspect-measurements",
        str(bundle),
        "--context",
        str(context),
        "--phase",
        "degraded",
        "--comparison-case-id",
        "controlled-case-001",
    ]


def assert_failure_is_repeatable(command, message, capsys):
    errors = []
    for _ in range(2):
        assert main(command) == 1
        output = capsys.readouterr()
        assert output.out == ""
        assert output.err.startswith("error:")
        assert message in output.err
        assert "Traceback" not in output.err
        errors.append(output.err)
    assert errors[0] == errors[1]


@pytest.mark.parametrize(
    "kind,message",
    [
        ("duplicate", "duplicate JSON object key"),
        ("nested_duplicate", "duplicate JSON object key"),
        ("depth", "nesting exceeds"),
        ("nan", "must be finite"),
        ("float_overflow", "must be finite"),
        ("integer_overflow", "integer string conversion"),
        ("wrong_root", "JSON root must be an object"),
        ("invalid_utf8", "not valid UTF-8"),
    ],
)
def test_inspection_cli_rejects_pathological_bundle_json_without_partial_output(
    tmp_path, capsys, kind, message
):
    bundle = copy_bundle(tmp_path)
    payloads = {
        "duplicate": '{"schemaVersion":2,"schemaVersion":2}',
        "nested_duplicate": '{"nested":{"same":1,"same":2}}',
        "depth": "[" * (MAX_JSON_NESTING_DEPTH + 1) + "0" + "]" * (MAX_JSON_NESTING_DEPTH + 1),
        "nan": '{"number":NaN}',
        "float_overflow": '{"number":1e10000}',
        "integer_overflow": '{"number":' + "9" * 10000 + "}",
        "wrong_root": "[]",
    }
    path = bundle / "run-metadata.json"
    path.write_bytes(b"\xff" if kind == "invalid_utf8" else payloads[kind].encode())
    assert_failure_is_repeatable(args(bundle), message, capsys)


def test_inspection_cli_rejects_oversized_context_before_reading(tmp_path, capsys):
    path = tmp_path / "oversized-context.json"
    with path.open("wb") as file:
        file.truncate(MAX_CONTRACT_JSON_BYTES + 1)
    assert_failure_is_repeatable(
        args(FIXTURES / "valid-v2", path), "JSON file is too large", capsys
    )


def test_inspection_cli_context_duplicate_keys_remain_rejected(tmp_path, capsys):
    path = tmp_path / "context.json"
    path.write_text('{"contextId":"one","contextId":"two"}')
    assert_failure_is_repeatable(
        args(FIXTURES / "valid-v2", path), "duplicate JSON object key", capsys
    )


def test_inspection_cli_bundle_file_bound_is_preserved(monkeypatch, capsys):
    monkeypatch.setattr(bundle_io, "MAX_TEXT_FILE_BYTES", 10)
    assert_failure_is_repeatable(args(FIXTURES / "valid-v2"), "file is too large", capsys)


def test_inspection_cli_total_bundle_bound_is_preserved(monkeypatch, capsys):
    monkeypatch.setattr(bundle_io, "MAX_BUNDLE_BYTES", 10)
    assert_failure_is_repeatable(args(FIXTURES / "valid-v2"), "bundle size limit", capsys)


@pytest.mark.parametrize(
    "kind,message",
    [
        ("field_limit", "field larger than field limit"),
        ("unterminated", "not valid CSV"),
        ("duplicate_header", "duplicate columns"),
    ],
)
def test_inspection_cli_csv_failures_are_deterministic(tmp_path, capsys, kind, message):
    bundle = copy_bundle(tmp_path)
    path = bundle / "stream-telemetry.csv"
    header = path.read_text().splitlines()[0]
    if kind == "field_limit":
        path.write_text(header + '\n"' + "x" * (csv.field_size_limit() + 1) + '"\n')
    elif kind == "unterminated":
        path.write_text(header + '\n"unterminated\n')
    else:
        path.write_text(header.replace("captured_at,", "elapsed_ms,", 1) + "\n")
    assert_failure_is_repeatable(args(bundle), message, capsys)


def test_inspection_cli_sample_limit_accepts_exact_limit_and_rejects_next_row(
    tmp_path, capsys, monkeypatch
):
    monkeypatch.setattr(bundle_io, "MAX_CSV_ROWS", 6)
    assert main(args(FIXTURES / "valid-v2")) == 0  # Exactly six interleaved engine rows.
    output = capsys.readouterr()
    assert json.loads(output.out)["p0Ingestion"] == "accepted"
    assert output.err == ""
    bundle = copy_bundle(tmp_path)
    path = bundle / "engine-telemetry.csv"
    text = path.read_text()
    path.write_text(text + text.splitlines()[-1] + "\n")
    assert_failure_is_repeatable(args(bundle), "more than 6 data rows", capsys)


@pytest.mark.parametrize("member", ["../run-metadata.json", "/run-metadata.json"])
def test_inspection_cli_tar_path_rejection_has_no_traceback(tmp_path, capsys, member):
    path = tmp_path / "unsafe.tar"
    with tarfile.open(path, "w") as file:
        info = tarfile.TarInfo(member)
        info.size = 2
        file.addfile(info, io.BytesIO(b"{}"))
    assert_failure_is_repeatable(args(path), "unsafe TAR member path", capsys)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "1e10000", "-1"])
def test_invalid_numeric_cells_remain_structured_rejections_without_fabricated_values(
    tmp_path, capsys, value
):
    bundle = copy_bundle(tmp_path)
    path = bundle / "stream-telemetry.csv"
    with path.open(newline="") as file:
        reader = csv.DictReader(file)
        columns = reader.fieldnames
        rows = list(reader)
    for row in rows:
        row["jitter_ms"] = value
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    assert main(args(bundle)) == 0
    output = capsys.readouterr()
    assert output.err == ""
    report = json.loads(output.out)
    entry = next(item for item in report["features"] if item["p0Feature"] == "transport.jitter_ms")
    assert entry["classification"] == "rejected"
    assert entry["outputs"][0]["value"] is None
    assert entry["outputs"][0]["summary"]["usableSampleCount"] == 0
    assert "Traceback" not in output.out


def test_reproduction_is_read_only_and_matches_pinned_versions(monkeypatch, capsys):
    def no_write(*args, **kwargs):
        pytest.fail("CI reproduction must not write artifacts")

    monkeypatch.setattr(Path, "write_text", no_write)
    monkeypatch.setattr(Path, "write_bytes", no_write)
    monkeypatch.setattr(Path, "mkdir", no_write)
    assert reproduction.main() == 0
    output = capsys.readouterr()
    assert output.err == ""
    result = json.loads(output.out)
    assert result["registrySha256"] == reproduction.EXPECTED_REGISTRY_SHA256
    assert result["reportSha256"] == reproduction.EXPECTED_REPORT_SHA256
    assert result["status"] == "current"


@pytest.mark.parametrize(
    "kind,message",
    [
        ("registry_artifact", "registry artifact drift"),
        ("registry_pin", "registry release pin mismatch"),
        ("report_pin", "report reproduction mismatch"),
        ("missing_fixture", "error:"),
    ],
)
def test_reproduction_drift_fails_without_traceback(monkeypatch, tmp_path, capsys, kind, message):
    if kind == "registry_artifact":
        monkeypatch.setattr(reproduction, "metric_registry_drift", lambda: True)
    elif kind == "registry_pin":
        monkeypatch.setattr(reproduction, "EXPECTED_REGISTRY_SHA256", "0" * 64)
    elif kind == "report_pin":
        monkeypatch.setattr(reproduction, "EXPECTED_REPORT_SHA256", "0" * 64)
    else:
        monkeypatch.setattr(reproduction, "FIXTURES", tmp_path / "missing")
    assert reproduction.main() == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert message in output.err
    assert "Traceback" not in output.err
