"""Artificial inspection inputs; real provenance here is a model branch, not measured data."""

import gzip
import hashlib

from latency_fingerprinting.analytical.responses import derive_analytical_response
from latency_fingerprinting.models import FeaturePolicyV1, ObservationRecordV2
from tests.analytical.cases import policy_payload, response_payload
from tests.models.v2_cases import pair_payload, window_payload
from tests.scenarios.test_bundle import archive, members

from .cases import HASH, canonical, dataset, group_id, seal_dataset


def response(*, real=False, controlled=False, confounded=False):
    if not real and not controlled:
        return response_payload(confounder="degraded_window" if confounded else None)
    pair = pair_payload(real=real)
    for key in ("degraded_window", "relief_window"):
        window = pair[key]
        window["context"]["workloadId"] = "workload-1"
        window["capture_method"]["producer_version"] = "a" * 40
    pair["degraded_window"]["effective_settings"]["targetFps"] = 30
    pair["relief_window"]["effective_settings"]["targetFps"] = 15
    pair["intervention"]["requested_settings"]["targetFps"] = 15
    if real:
        pair["intervention"]["observed_settings"]["targetFps"] = 15
    if confounded:
        pair["degraded_window"]["confounder_codes"] = ["operator_declared"]
    return derive_analytical_response(
        ObservationRecordV2.model_validate(pair), FeaturePolicyV1.model_validate(policy_payload())
    ).model_dump(mode="json", by_alias=True)


def case(*, healthy=False, real=False, confirmed=False, controlled=False, cpu=600_000_000):
    p = dataset()
    record = (
        window_payload(phase="baseline", real=real)
        if healthy
        else response(real=real, controlled=controlled)
    )
    p["entries"][0].update(
        input_kind="healthy_window" if healthy else "response",
        label="healthy" if healthy else "host_contention",
        label_basis="external_confirmation" if confirmed else "declared_only",
    )
    entry = p["entries"][0]
    if healthy:
        p["sources"] = p["sources"][:1]
        entry["source_bindings"] = [
            dict(window_role="healthy", source_id="source-a", window_id="window-baseline")
        ]
        p["artifacts"][0]["kind"] = "observation_window"
    windows = (
        [record]
        if healthy
        else [record["observation"][key] for key in ("degradedWindow", "reliefWindow")]
    )
    for source, binding, window in zip(
        p["sources"], entry["source_bindings"], windows, strict=True
    ):
        original = window["source_artifact"] if healthy else window["sourceArtifact"]
        source.update(
            run_id=window["run_id"] if healthy else window["runId"],
            source_type=original["source_type"] if healthy else original["sourceType"],
            source_content_hash=original["content_hash"] if healthy else original["contentHash"],
            bundle_schema_version=original["bundle_schema_version"]
            if healthy
            else original["bundleSchemaVersion"],
        )
        binding["window_id"] = window["window_id"] if healthy else window["windowId"]
    p["split"]["assignments"] = [
        dict(group_id=group_id([s["source_id"] for s in p["sources"]]), role="training")
    ]
    files = {"response-a.json": canonical(record)}
    if controlled:
        entry.update(
            label_basis="controlled_effect",
            experiment_artifact_id="experiment-a",
            experiment_phase="degraded",
        )
        files["experiment-a.tar.gz"] = gzip.compress(archive(members(cpu=cpu).items()), mtime=0)
        p["artifacts"].append(
            dict(
                artifact_id="experiment-a",
                kind="experiment_bundle",
                file_name="experiment-a.tar.gz",
                sha256=HASH,
                bytes=1,
            )
        )
        p["artifacts"].sort(key=lambda a: a["artifact_id"])
    if confirmed:
        p["split"].update(mode="prospective", freeze_review_id="freeze")
        seal_dataset(p)
        p["reviews"] = [
            dict(
                review_id=name,
                reviewer_id="reviewer",
                kind=kind,
                subject_ids=subjects,
                outcome="confirmed",
                evidence_sha256=HASH,
            )
            for name, kind, subjects in (
                ("freeze", "split_freeze", [p["split"]["split_id"]]),
                ("independence", "independence", [s["source_id"] for s in p["sources"]]),
                ("label", "label_binding", [entry["entry_id"]]),
            )
        ]
        for source in p["sources"]:
            source["review_id"] = "independence"
        entry["label_review_id"] = "label"
    return p, files


def write(path, p, files):
    path.mkdir(exist_ok=True)
    for artifact in p["artifacts"]:
        raw = files[artifact["file_name"]]
        artifact.update(bytes=len(raw), sha256="sha256:" + hashlib.sha256(raw).hexdigest())
    seal_dataset(p)
    (path / "calibration-dataset.json").write_bytes(canonical(p))
    for name, raw in files.items():
        (path / name).write_bytes(raw)
    return path
