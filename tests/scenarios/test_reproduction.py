"""Release drift, independently staged containers and producer-to-CLI parity."""

import gzip
import io
import json
import shutil
import tarfile

import pytest

from tests.scenarios import check_reproduction as release


def pack(source):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for path in sorted(source.glob("*.json")):
            if path.name == "expected.json":
                continue
            data = path.read_bytes()
            member = tarfile.TarInfo(path.name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    return gzip.compress(buffer.getvalue(), mtime=0)


def test_release_is_read_only_and_independent_expectations_pass(capsys):
    before = {p: p.read_bytes() for p in release.FIXTURES.rglob("*.json")}
    result = release.check_reproduction()
    assert result["status"] == "current"
    assert result["producerIntegration"] == "not_run"
    assert before == {p: p.read_bytes() for p in before}
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("drift", ["changed", "missing", "extra_json", "extra_other"])
def test_pins_reject_all_file_inventory_drift(tmp_path, drift):
    directory = tmp_path / "fixtures"
    shutil.copytree(release.FIXTURES, directory)
    target = directory / "host/experiment-result.json"
    if drift == "changed":
        target.write_bytes(target.read_bytes() + b" ")
    elif drift == "missing":
        target.unlink()
    else:
        (directory / ("extra.json" if drift == "extra_json" else "private.log")).write_bytes(b"x")
    with pytest.raises(ValueError, match="N5 fixture release pin mismatch"):
        release.check_reproduction(directory)


@pytest.mark.parametrize("state", ["valid", "missing", "wrong_case", "corrupt"])
def test_every_producer_archive_and_cli_matches(tmp_path, capsys, state):
    for case in release.CASES:
        if state == "missing" and case == "unsupported":
            continue
        source = "healthy" if state == "wrong_case" and case == "host" else case
        payload = pack(release.FIXTURES / source)
        if state == "corrupt" and case == "host":
            payload = b"invalid gzip"
        (tmp_path / f"{case}.tar.gz").write_bytes(payload)
    if state == "valid":
        assert (
            release.check_reproduction(producer_bundles=tmp_path)["producerIntegration"] == "passed"
        )
    else:
        with pytest.raises((ValueError, OSError)):
            release.check_reproduction(producer_bundles=tmp_path)
    assert capsys.readouterr() == ("", "")


def test_independent_expectation_cannot_be_derived_from_result(tmp_path, monkeypatch):
    directory = tmp_path / "fixtures"
    shutil.copytree(release.FIXTURES, directory)
    path = directory / "host/expected.json"
    expected = json.loads(path.read_bytes())
    expected["effect"]["degraded_fps"] = 25.0
    path.write_text(json.dumps(expected))
    pins = dict(release.EXPECTED_SHA256)
    pins["host/expected.json"] = release.hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(release, "EXPECTED_SHA256", pins)
    with pytest.raises(ValueError, match="independent effect/cleanup expectation mismatch"):
        release.check_reproduction(directory)


def test_reproduction_command_reports_success_and_fixed_failure(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(release.sys, "argv", ["check_reproduction"])
    assert release.main() == 0
    assert json.loads(capsys.readouterr().out)["status"] == "current"
    monkeypatch.setattr(
        release.sys, "argv", ["check_reproduction", "--producer-bundles", str(tmp_path)]
    )
    assert release.main() == 1
    assert capsys.readouterr() == ("", "error: N5 reproduction failed\n")
