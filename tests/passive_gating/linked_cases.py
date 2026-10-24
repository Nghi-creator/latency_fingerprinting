"""Artificial on-disk N2/N6 operands; producer provenance is a model branch only."""

import copy
import hashlib

from latency_fingerprinting.models import ObservationWindowV2
from tests.calibration.cases import seal_dataset, seal_report

from .cases import baseline, canonical, evidence, replay_payload, window


def source_case():
    ev, windows = evidence(
        [
            window("q0", query=True, fps=40.0),
            window("q1", query=True, start=2000, end=4000, fps=40.0),
            window("q2", query=True, start=4000, end=6000, fps=40.0),
        ]
    )
    return ev, windows


def write_source(directory, ev, windows, *, wire_aliases=False):
    ev = copy.deepcopy(ev)
    d, report = ev["dataset"], ev["report"]
    directory.mkdir()
    originals = {
        entry["artifact_id"]: windows[entry["entry_id"]]
        for entry in d["entries"]
        if entry["input_kind"] == "healthy_window"
    }
    for artifact in d["artifacts"]:
        payload = originals[artifact["artifact_id"]]
        if wire_aliases:
            payload = ObservationWindowV2.model_validate(payload).model_dump(
                mode="json", by_alias=True
            )
        raw = canonical(payload)
        artifact.update(bytes=len(raw), sha256="sha256:" + hashlib.sha256(raw).hexdigest())
        (directory / artifact["file_name"]).write_bytes(raw)
    seal_dataset(d)
    for review in d["reviews"]:
        if review["kind"] == "split_freeze":
            review["subject_ids"] = [d["split"]["split_id"]]
    seal_dataset(d)
    report.update(
        dataset_id=d["dataset_id"],
        dataset_content_hash=d["content_hash"],
        split_id=d["split"]["split_id"],
        artifact_receipts=copy.deepcopy(d["artifacts"]),
    )
    seal_report(report)
    (directory / "calibration-dataset.json").write_bytes(canonical(d))
    b = baseline(ev, windows)
    return ev, b, replay_payload(b, windows)
