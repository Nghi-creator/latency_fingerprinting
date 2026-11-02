"""Explicit source-backed software cases; never independent real acquisitions."""

import hashlib
import json
import shutil
from pathlib import Path

from latency_fingerprinting.calibration import inspect_calibration_dataset
from latency_fingerprinting.evaluation import seal_manifest
from latency_fingerprinting.profiles import build_profile_snapshot
from tests.profiles.cases import policy

ROOT = Path(__file__).resolve().parents[2]


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def base(tmp_path):
    protocol = tmp_path / "protocol.txt"
    protocol.write_bytes(b"Software test only; numeric empirical acceptance is unapproved.\n")
    manifest = dict(
        schema_version="n11-evaluation-manifest-v1",
        method_release="n11-offline-evaluation-v1",
        study_mode="software_only",
        scope="offline_separate_tracks_no_live_response_bridge",
        protocol_receipt="protocol",
        receipts=[],
        datasets=[],
        groups=[],
        raw_derivations=[],
        diagnoses=[],
        passive=[],
        live=[],
        slots=[],
    )
    paths = {}
    add_receipt(manifest, paths, "protocol", "protocol", protocol)
    return manifest, paths


def add_receipt(manifest, paths, identifier, kind, path):
    raw = path.read_bytes()
    manifest["receipts"].append(
        dict(
            receipt_id=identifier,
            kind=kind,
            bytes=len(raw),
            sha256="sha256:" + hashlib.sha256(raw).hexdigest(),
        )
    )
    manifest["receipts"].sort(key=lambda r: r["receipt_id"])
    paths[identifier] = path


def slot(name, role="final_test", state="retained", **changes):
    return dict(
        slot_id=name,
        study_group="study-" + name,
        role=role,
        truth_label="host_contention",
        state=state,
        failure_code="test_failure" if state == "failed" else None,
        diagnosis_job=None,
        passive_job=None,
        live_job=None,
        **changes,
    )


def linked_case(tmp_path):
    manifest, paths = base(tmp_path)
    directory = tmp_path / "sources"
    shutil.copytree(ROOT / "fixtures/calibration-v1/reviewed-roles", directory)
    inspected = inspect_calibration_dataset(directory)
    d = inspected.dataset
    add_receipt(
        manifest, paths, "dataset", "dataset_manifest", directory / "calibration-dataset.json"
    )
    manifest["datasets"] = [
        dict(
            dataset_key="sources",
            manifest_receipt="dataset",
            content_hash=d.content_hash,
            split_id=d.split.split_id,
        )
    ]
    for index, group in enumerate(inspected.report.groups):
        name = "case-" + str(index)
        manifest["groups"].append(
            dict(dataset_key="sources", group_id=group.group_id, study_group="study-" + name)
        )
        row = slot(name, role=group.role)
        row["diagnosis_job"] = group.role if group.role != "training" else None
        manifest["slots"].append(row)
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_bytes(
        canonical(build_profile_snapshot(directory, policy()).model_dump(mode="json"))
    )
    add_receipt(manifest, paths, "snapshot", "profile_snapshot", snapshot)
    add_receipt(
        manifest,
        paths,
        "response-policy",
        "response_policy",
        ROOT / "docs/analysis/N3_FEATURE_POLICY_SPEC.json",
    )
    add_receipt(
        manifest,
        paths,
        "match-policy",
        "match_policy",
        ROOT / "docs/profile_matching/N8_MATCH_POLICY_SPEC.json",
    )
    manifest["diagnoses"] = [
        dict(
            job_id=mode,
            dataset_key="sources",
            snapshot_receipt="snapshot",
            response_policy_receipt="response-policy",
            match_policy_receipt="match-policy",
            mode=mode,
        )
        for mode in ("final_test", "validation")
    ]
    return seal_manifest(manifest), paths
