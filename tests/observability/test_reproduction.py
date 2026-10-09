"""Pinned expectations, full CLI handoff and read-only release drift failures."""

import io
import shutil
import tarfile

import pytest

from latency_fingerprinting.cli import main
from tests.observability.check_reproduction import CASES, FIXTURES, check_reproduction


def test_release_reproduces_without_mutating_fixtures():
    before = {path: path.read_bytes() for path in FIXTURES.rglob("*.json")}
    assert check_reproduction()["status"] == "current"
    assert before == {path: path.read_bytes() for path in before}


@pytest.mark.parametrize("case", ["changed", "missing", "extra"])
def test_release_pins_detect_drift(tmp_path, case):
    directory = tmp_path / "fixtures"
    shutil.copytree(FIXTURES, directory)
    target = directory / "host/trace-record.json"
    if case == "missing":
        target.unlink()
    elif case == "extra":
        (directory / "extra.json").write_text("{}")
    else:
        target.write_bytes(target.read_bytes() + b" ")
    with pytest.raises(ValueError, match="pin mismatch"):
        check_reproduction(directory)


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("kind", ["directory", "archive"])
def test_independent_export_to_inspection_cli(tmp_path, capsys, case, kind):
    source = FIXTURES / case
    if kind == "directory":
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        for name in ("trace-record.json", "trace-manifest.json"):
            shutil.copyfile(source / name, bundle / name)
    else:
        bundle = tmp_path / "bundle.tar.gz"
        with tarfile.open(bundle, "w:gz", format=tarfile.USTAR_FORMAT) as archive:
            for name in ("trace-record.json", "trace-manifest.json"):
                payload = (source / name).read_bytes()
                member = tarfile.TarInfo(name)
                member.size = len(payload)
                archive.addfile(member, io.BytesIO(payload))
    record, summary = tmp_path / "record.json", tmp_path / "summary.json"
    assert main(["ingest-trace", "--bundle", str(bundle), "--output", str(record)]) == 0
    assert main(["inspect-trace", "--trace", str(record), "--output", str(summary)]) == 0
    assert record.read_bytes() == (source / "trace-record.json").read_bytes()
    assert summary.read_bytes() == (source / "expected-summary.json").read_bytes()
    assert capsys.readouterr().out == ""
