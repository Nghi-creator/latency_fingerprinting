"""Independent Step 2 totals, linked contradictions and bounded hostile containers."""

import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest

from latency_fingerprinting.cli import main
from latency_fingerprinting.json_io import canonical_json
from latency_fingerprinting.scenarios import bundle_io, inspect_experiment_bundle
from tests.scenarios import cases

TRACE = Path(__file__).resolve().parents[2] / "fixtures/observability/host/trace-record.json"


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def members(*, unsupported=False, cpu=600_000_000):
    manifest, result = cases.manifest(), cases.result()
    manifest["producer_version"] = "a" * 40
    if unsupported:
        manifest["adapter"].update(state="unavailable", reason="runtime_unavailable")
        result = cases.unsupported()
        result["reason"] = "runtime_unavailable"
    declaration = encoded(manifest)
    digest = hashlib.sha256(declaration).hexdigest()
    result["manifest_sha256"] = digest
    files = {"experiment-manifest.json": declaration}
    for reference in result["artifacts"]:
        if reference["role"] == "stage_trace":
            payload = TRACE.read_bytes()
        else:
            evidence = cases.evidence(reference["phase"])
            evidence["manifest_sha256"] = digest
            if reference["phase"] in ("degraded", "probe"):
                for row in evidence["intervals"]:
                    row["worker_cpu_ns"] = cpu
            payload = encoded(evidence)
        files[reference["file_name"]] = payload
        reference.update(bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
    if not unsupported:
        result["effect"]["pressure_cpu_percent"] = cpu / 10_000_000
    if cpu < 500_000_000 and not unsupported:
        result["effect"].update(
            state="failed", reason="pressure_not_observed", pressure_cpu_percent=cpu / 10_000_000
        )
    files["experiment-result.json"] = encoded(result)
    return files


def edit(files, name, change, *, bind=True):
    value = json.loads(files[name])
    change(value)
    files[name] = encoded(value)
    if name.startswith("artifact-") and bind:
        result = json.loads(files["experiment-result.json"])
        reference = next(a for a in result["artifacts"] if a["file_name"] == name)
        reference.update(bytes=len(files[name]), sha256=hashlib.sha256(files[name]).hexdigest())
        files["experiment-result.json"] = encoded(result)


def directory(path, files):
    path.mkdir()
    for name, data in files.items():
        (path / name).write_bytes(data)
    return path


def archive(files, *, format=tarfile.USTAR_FORMAT, kind=None):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=format) as out:
        for name, payload in files:
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            if kind:
                info.type = kind
                info.linkname = "experiment-result.json"
            out.addfile(info, io.BytesIO(payload) if info.isfile() else None)
    return buffer.getvalue()


@pytest.mark.parametrize(
    "unsupported,cpu", [(False, 600_000_000), (False, 500_000_000), (False, 400_000_000), (True, 0)]
)
@pytest.mark.parametrize("container", ["directory", "gzip"])
def test_verified_failed_and_unsupported_offline_cli(tmp_path, capsys, unsupported, cpu, container):
    files = members(unsupported=unsupported, cpu=cpu)
    if container == "directory":
        path = directory(tmp_path / "bundle", files)
    else:
        path = tmp_path / "bundle.gz"
        path.write_bytes(gzip.compress(archive(files.items()), mtime=0))
    inspected = inspect_experiment_bundle(path)
    assert inspected.effect == inspected.result.effect
    target = tmp_path / "result.json"
    assert main(["inspect-experiment", "--bundle", str(path), "--output", str(target)]) == 0
    assert target.read_bytes() == canonical_json(inspected.result).encode()
    assert target.stat().st_mode & 0o777 == 0o600
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize(
    "name,change,bind",
    [
        ("experiment-result.json", lambda r: r.update(manifest_sha256="0" * 64), True),
        ("experiment-result.json", lambda r: r.update(run_id="run-2"), True),
        ("experiment-result.json", lambda r: r["effect"].update(degraded_fps=25.0), True),
        ("experiment-result.json", lambda r: r["actions"][0].update(action_id="action-2"), True),
        (
            "experiment-result.json",
            lambda r: r["actions"][0].update(started_ns=29_000_000_000),
            True,
        ),
        ("artifact-1.json", lambda e: e.update(clock_id="clock-2"), True),
        ("artifact-2.json", lambda e: e.update(run_id="run-2"), True),
        ("artifact-3.json", lambda e: e.update(manifest_sha256="0" * 64), True),
        ("artifact-3.json", lambda e: e["intervals"][0].update(active_workers=2), True),
        ("artifact-3.json", lambda e: e["intervals"][0].update(worker_cpu_ns=0), False),
        ("artifact-7.json", lambda t: t.update(producer_version="b" * 40), True),
        ("artifact-7.json", lambda t: t.update(provenance="producer_capture"), True),
        ("artifact-7.json", lambda t: t["streams"][0]["limits"].update(max_frames=1999), True),
    ],
)
def test_linked_contradictions_are_rejected_without_output(tmp_path, capsys, name, change, bind):
    files = members()
    edit(files, name, change, bind=bind)
    path = directory(tmp_path / "bundle", files)
    output = tmp_path / "preserved.json"
    output.write_bytes(b"previous\n")
    with pytest.raises(ValueError, match="^invalid_experiment_bundle$"):
        inspect_experiment_bundle(path)
    assert main(["inspect-experiment", "--bundle", str(path), "--output", str(output)]) == 1
    assert output.read_bytes() == b"previous\n"
    assert capsys.readouterr() == ("", "error: inspect-experiment: invalid_input_or_output\n")


def test_partial_evidence_retained_with_insufficient_effect(tmp_path):
    files = members()
    edit(
        files,
        "artifact-3.json",
        lambda e: e.update(state="partial", reason="collection_gap", intervals=e["intervals"][:29]),
    )
    edit(
        files,
        "experiment-result.json",
        lambda r: r.update(
            effect=dict(
                state="unavailable",
                reason="insufficient_evidence",
                healthy_fps=None,
                degraded_fps=None,
                recovery_fps=None,
                pressure_cpu_percent=None,
            )
        ),
    )
    inspected = inspect_experiment_bundle(directory(tmp_path / "bundle", files))
    assert len(inspected.artifacts[2].intervals) == 29
    assert inspected.effect.reason == "insufficient_evidence"


@pytest.mark.parametrize(
    "attack", ["extra", "missing", "duplicate", "symlink", "pax", "trailer", "truncated", "empty"]
)
def test_hostile_archives_fail_closed(tmp_path, attack):
    files = list(members().items())
    kind, format = None, tarfile.USTAR_FORMAT
    if attack == "extra":
        files.append(("private-secret.json", b"secret"))
    elif attack == "missing":
        files.pop()
    elif attack == "duplicate":
        files.append(files[-1])
    elif attack == "symlink":
        kind = tarfile.SYMTYPE
    elif attack == "pax":
        files[0] = ("a" * 120, files[0][1])
        format = tarfile.PAX_FORMAT
    raw = archive(files, format=format, kind=kind)
    if attack == "trailer":
        raw += b"secret" + bytes(506)
    elif attack == "truncated":
        raw = raw[:512]
    elif attack == "empty":
        raw = b""
    path = tmp_path / "bad.gz"
    path.write_bytes(gzip.compress(raw))
    with pytest.raises(ValueError, match="^invalid_experiment_bundle$"):
        inspect_experiment_bundle(path)


def test_duplicate_json_keys_paths_specials_and_bounds(tmp_path, monkeypatch):
    files = members()
    files["experiment-result.json"] = b'{"status":"completed","status":"aborted"}'
    path = directory(tmp_path / "bundle", files)
    with pytest.raises(ValueError):
        inspect_experiment_bundle(path)
    alias = tmp_path / "alias"
    alias.symlink_to(path, target_is_directory=True)
    with pytest.raises(ValueError):
        inspect_experiment_bundle(alias)
    monkeypatch.setattr(bundle_io, "MAX_JSON_BYTES", 10)
    with pytest.raises(ValueError):
        inspect_experiment_bundle(path)


def test_optional_observation_preserves_existing_clock_phase_and_aliases(tmp_path):
    files = members()
    window = json.loads((TRACE.parents[2] / "observation-v2/synthetic-pair.json").read_bytes())[
        "reliefWindow"
    ]
    payload = encoded(window)
    files["artifact-11.json"] = payload
    edit(
        files,
        "experiment-result.json",
        lambda r: r["artifacts"].append(
            dict(
                artifact_id="artifact-11",
                file_name="artifact-11.json",
                phase="recovery",
                role="observation_window",
                schema_version="observation-window-v2",
                bytes=len(payload),
                sha256=hashlib.sha256(payload).hexdigest(),
            )
        ),
    )
    inspected = inspect_experiment_bundle(directory(tmp_path / "bundle", files))
    assert inspected.artifacts[-1].phase.value == "relief"
    assert inspected.artifacts[-1].clock.domain_id == "domain-relief"


@pytest.mark.parametrize(
    "healthy,degraded,recovery,reason",
    [
        (900, 855, 855, None),
        (900, 856, 900, "degradation_not_observed"),
        (900, 720, 854, "recovery_not_observed"),
        (809, 720, 900, "baseline_inadequate"),
    ],
)
def test_integer_effect_boundaries_from_hash_bound_intervals(
    tmp_path, healthy, degraded, recovery, reason
):
    files = members()
    counter = 0
    for number, frames in enumerate((300, healthy, degraded, 900, recovery, 300), 1):
        name = f"artifact-{number}.json"
        evidence = json.loads(files[name])
        count = len(evidence["intervals"])
        for index, row in enumerate(evidence["intervals"]):
            row.update(
                frames_start=counter + frames * index // count,
                frames_end=counter + frames * (index + 1) // count,
            )
        counter += frames
        edit(files, name, lambda e, evidence=evidence: e.update(evidence))
    edit(
        files,
        "experiment-result.json",
        lambda r: r["effect"].update(
            state="failed" if reason else "verified",
            reason=reason,
            healthy_fps=healthy / 30,
            degraded_fps=degraded / 30,
            recovery_fps=recovery / 30,
        ),
    )
    inspected = inspect_experiment_bundle(directory(tmp_path / "bundle", files))
    assert inspected.effect.reason == reason


@pytest.mark.parametrize("container", ["directory", "gzip"])
def test_aggregate_bounds_are_enforced(tmp_path, monkeypatch, container):
    files = members()
    if container == "directory":
        path = directory(tmp_path / "bundle", files)
        bound = sum(map(len, files.values())) - 1
    else:
        raw = archive(files.items())
        path = tmp_path / "bundle.gz"
        path.write_bytes(gzip.compress(raw))
        bound = len(raw) - 1
    monkeypatch.setattr(bundle_io, "MAX_BUNDLE_BYTES", bound)
    with pytest.raises(ValueError, match="^invalid_experiment_bundle$"):
        inspect_experiment_bundle(path)


def test_special_directory_member_and_duplicate_artifact_json(tmp_path):
    import os

    files = members()
    path = directory(tmp_path / "bundle", files)
    member = path / "artifact-1.json"
    member.unlink()
    os.mkfifo(member)
    with pytest.raises(ValueError, match="^invalid_experiment_bundle$"):
        inspect_experiment_bundle(path)
    member.unlink()
    payload = files["artifact-1.json"].replace(
        b'"clock_id": "clock-1",', b'"clock_id": "clock-1", "clock_id": "clock-1",'
    )
    member.write_bytes(payload)
    result = json.loads(files["experiment-result.json"])
    result["artifacts"][0].update(bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
    (path / "experiment-result.json").write_bytes(encoded(result))
    with pytest.raises(ValueError, match="^invalid_experiment_bundle$"):
        inspect_experiment_bundle(path)


@pytest.mark.parametrize("root", [None, [], True, 42, "private-manifest-marker"])
@pytest.mark.parametrize("container", ["directory", "gzip"])
def test_nonobject_manifest_root_fails_closed_without_output(tmp_path, capsys, root, container):
    files = members()
    files["experiment-manifest.json"] = encoded(root)
    if container == "directory":
        path = directory(tmp_path / "bundle", files)
    else:
        path = tmp_path / "bundle.tar.gz"
        path.write_bytes(gzip.compress(archive(files.items())))
    output = tmp_path / "preserved.json"
    output.write_bytes(b"previous\n")
    with pytest.raises(ValueError, match="^invalid_experiment_bundle$"):
        inspect_experiment_bundle(path)
    assert main(["inspect-experiment", "--bundle", str(path), "--output", str(output)]) == 1
    assert output.read_bytes() == b"previous\n"
    assert capsys.readouterr() == ("", "error: inspect-experiment: invalid_input_or_output\n")
