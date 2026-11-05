#!/usr/bin/env python3
"""Replay N11 condition exports; optionally create missing derived files, never acquire."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from latency_fingerprinting.adapters import ingest_pixelated_source_local
from latency_fingerprinting.analytical.responses import derive_analytical_response
from latency_fingerprinting.calibration.records import partition_id
from latency_fingerprinting.json_io import strict_json_loads
from latency_fingerprinting.models import (
    AnalyticalResponseV2,
    ContextKey,
    FeaturePolicyV1,
    ObservationRecordV2,
)

PHASES = ("degraded", "relief", "recovery")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load(path: Path):
    return strict_json_loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def beneath(root: Path, relative: str) -> Path:
    """Reject manifest paths escaping their declared source root, including symlinks."""
    require(isinstance(relative, str) and bool(relative), "invalid source path")
    candidate = root / relative
    require(not Path(relative).is_absolute(), "absolute source path")
    require(".." not in Path(relative).parts, "parent traversal in source path")
    require(candidate.resolve().is_relative_to(root.resolve()), "source path escapes root")
    return candidate


def phase_manifest(path: Path) -> dict:
    with tarfile.open(path) as archive:
        matches = [m for m in archive.getmembers() if m.name == "bundle-manifest.json"]
        require(len(matches) == 1, "exactly one bundle manifest required")
        member = matches[0]
        require(member.isfile() and member.size <= 1024 * 1024, "invalid bundle manifest")
        stream = archive.extractfile(member)
        require(stream is not None, "unreadable bundle manifest")
        with stream:
            value = strict_json_loads(stream.read(1024 * 1024 + 1).decode("utf-8"))
        require(isinstance(value, dict), "bundle manifest must be an object")
        return value


def verify_case(case: Path, *, producer: Path, policy: Path, write_derived: bool = False) -> dict:
    """Replay existing artifacts; CLI outputs are written only to a temporary directory.

    By default derived artifacts must already exist. Explicit write_derived creates
    missing derived files only for the fixed condition-plan recipe.
    Current producer sources must match each source declared by the original plan.
    Extra files in a newer checkout do not authenticate the original dependency closure.
    """
    case, producer = case.resolve(), producer.resolve()
    plan, receipt = load(case / "plan.json"), load(case / "control-receipt.json")
    require(not (case / "failure.json").exists(), "failed acquisition")
    require(receipt["result"]["restoration"] == "verified_by_port", "unverified restoration")
    require(receipt["ledger_state"] == "clean", "unclean control ledger")
    require(bool(plan["source_sha256"]), "empty source manifest")
    for relative, expected in plan["source_sha256"].items():
        require(digest(beneath(case / "sources", relative)) == expected, "frozen source changed")
        base = producer / ("apps" if relative.startswith("web/") else "engine/runtime")
        require(digest(beneath(base, relative)) == expected, "current declared source changed")
    source_bytes = (json.dumps(plan["source_sha256"], indent=2) + "\n").encode()
    source_hash = "sha256:" + hashlib.sha256(source_bytes).hexdigest()
    require(source_hash == plan["source_manifest_hash"], "source manifest hash mismatch")
    require(bool(plan.get("condition")), "condition-witness case required")
    # Reuse the producer inspector rather than copying its ownership/timing semantics.
    inspector = producer / "engine/runtime/scripts/research/n11/conditionReceipt.mjs"
    script = (
        "import fs from 'node:fs';import assert from 'node:assert/strict';"
        "const {inspectConditionAcquisition}=await import(process.argv[1]);"
        "const d=process.argv[2],p=JSON.parse(fs.readFileSync(d+'/plan.json'));"
        "assert.deepEqual(inspectConditionAcquisition("
        "JSON.parse(fs.readFileSync(d+'/acquisition.json')),{condition:p.condition.name}),"
        "JSON.parse(fs.readFileSync(d+'/control-receipt.json')));"
    )
    node = shutil.which("node")
    require(node is not None, "Node.js executable required")
    # Explicit caller-selected checkout; argument vector, never a shell command.
    subprocess.run(  # noqa: S603
        [node, "--input-type=module", "-e", script, inspector.as_uri(), str(case)],
        check=True,
        timeout=30,
    )
    whole = "sha256:" + digest(case / "acquisition.json")
    windows = {}
    derived = {}
    with tempfile.TemporaryDirectory(prefix="n11-export-verification-") as temporary:
        for phase in PHASES:
            directory = case / phase
            raw = directory / "acquisition.json"
            require(load(raw)["native_receipt_sha256"] == whole, "native receipt link mismatch")
            manifest = phase_manifest(directory / "bundle.tar")
            require(
                manifest["sourceLocalPhase"]["evidenceSha256"] == "sha256:" + digest(raw),
                "phase receipt link mismatch",
            )
            window = ingest_pixelated_source_local(
                directory / "bundle.tar",
                context=ContextKey.model_validate(load(directory / "context.json")),
                phase=phase,
                comparison_case_id=plan["acquisition_id"],
            )
            expected = window.model_dump(mode="json", by_alias=True)
            stored_window = directory / "window.json"
            if stored_window.exists():
                require(load(stored_window) == expected, "stored SDK window changed")
            else:
                require(write_derived, "missing stored SDK window")
                derived[stored_window] = expected
            output = Path(temporary).resolve() / f"{phase}.json"
            subprocess.run(  # noqa: S603 -- current interpreter; fixed CLI argument vector
                [
                    sys.executable,
                    "-m",
                    "latency_fingerprinting",
                    "ingest-pixelated-source-local",
                    "--bundle",
                    str(directory / "bundle.tar"),
                    "--context",
                    str(directory / "context.json"),
                    "--phase",
                    phase,
                    "--comparison-case-id",
                    plan["acquisition_id"],
                    "--output",
                    str(output),
                ],
                check=True,
                timeout=60,
                stdout=subprocess.DEVNULL,
            )
            require(load(output) == expected, "SDK/CLI window mismatch")
            windows[phase] = window
    a, b, c = (windows[p] for p in PHASES)
    require(a.context == b.context == c.context, "phase contexts differ")
    require(a.effective_settings == c.effective_settings, "recovery settings differ")
    require(
        a.context.versions.get("n11ConditionProtocol") == plan["condition"]["recipe"],
        "condition protocol context mismatch",
    )
    observation_file = case / "observation.json"
    require(
        plan["schema_version"] == "n11-contained-condition-plan-v1"
        and plan["target_fps"] == [30, 24, 30]
        and plan["action_duration_ms"] == 5000,
        "unsupported condition-plan derivation recipe",
    )
    observation = ObservationRecordV2.model_validate(
        dict(
            schema_version="observation-v2",
            contract_version="2.0.0",
            observation_id=plan["acquisition_id"] + "-observation",
            comparison_case_id=plan["acquisition_id"],
            degraded_window=a,
            relief_window=b,
            intervention=dict(
                probe_id=receipt["controller_request"]["request_id"],
                probe_type="stream_profile_relief",
                probe_version="1.0.0",
                requested_settings=dict(fps=24, targetFps=24),
                observed_settings=dict(fps=24, targetFps=24),
                intensity=(30 - 24) / 30,
                application_method="paired_run",
                execution_status="executed",
                restoration_status="restored",
                degraded_window_id=a.window_id,
                relief_window_id=b.window_id,
                paired_window_order=["degraded", "relief"],
                confounder_codes=[],
            ),
        )
    )
    if observation_file.exists():
        stored_observation = ObservationRecordV2.model_validate(load(observation_file))
        require(stored_observation == observation, "observation differs from native recipe")
    else:
        require(write_derived, "missing observation")
        derived[observation_file] = observation.model_dump(mode="json", by_alias=True)
    require(observation.comparison_case_id == plan["acquisition_id"], "wrong observation case")
    require(observation.degraded_window == a, "observation degraded window mismatch")
    require(observation.relief_window == b, "observation relief window mismatch")
    response = derive_analytical_response(observation, FeaturePolicyV1.model_validate(load(policy)))
    response_file = case / "response.json"
    require(response.is_valid, "invalid analytical response")
    if response_file.exists():
        stored = AnalyticalResponseV2.model_validate(load(response_file))
        require(response == stored, "changed analytical response")
    else:
        require(write_derived, "missing analytical response")
        derived[response_file] = response.model_dump(mode="json", by_alias=True)
    for target, payload in derived.items():
        with target.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2)
            stream.write("\n")
    return dict(
        acquisition_id=plan["acquisition_id"],
        declared_source_files=len(plan["source_sha256"]),
        source_manifest=source_hash,
        native_sha256=whole,
        sdk_cli_equal_phases=3,
        derived_files_created=len(derived),
        eligible_features=sum(f.state == "eligible" for f in response.features.values()),
        partition=partition_id(response, "response"),
        accepted_diagnostic_groups=0,
        acquisition_authority=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path)
    parser.add_argument("--producer", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument(
        "--write-derived",
        action="store_true",
        help="exclusively create missing derived windows/observation/response",
    )
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                verify_case(
                    args.case,
                    producer=args.producer,
                    policy=args.policy,
                    write_derived=args.write_derived,
                ),
                indent=2,
            )
        )
    except (
        ValueError,
        OSError,
        KeyError,
        TypeError,
        tarfile.TarError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"verification failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
