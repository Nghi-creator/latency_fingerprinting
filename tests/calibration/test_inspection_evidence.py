"""Unsupported support remains visible; known ownership contradictions cannot label inputs."""

import gzip
import json

import pytest

from latency_fingerprinting.calibration import inspect_calibration_dataset
from tests.scenarios.test_bundle import archive
from tests.scenarios.test_pacing import pacing_members

from .cases import canonical
from .inspection_cases import case, write
from .test_inspection import rebuild


@pytest.mark.parametrize(
    "change,reason",
    [
        ("engineering", "engineering_only"),
        ("freeze", "split_unverified"),
        ("independence", "independence_unverified"),
        ("label", "label_unverified"),
    ],
)
def test_external_reviews_and_assignment_remain_explicit(tmp_path, change, reason):
    p, files = case(real=True, confirmed=True)
    if change == "engineering":
        p["split"]["assignments"][0]["role"] = "engineering"
        # The trusted freeze must name the new split, calculated independently below.
        from .cases import seal_dataset

        seal_dataset(p)
        p["reviews"][0]["subject_ids"] = [p["split"]["split_id"]]
    else:
        next(r for r in p["reviews"] if r["review_id"] == change)["outcome"] = "uncertain"
    report = inspect_calibration_dataset(write(tmp_path, p, files)).report
    assert report.entries[0].reason_codes == (reason,)
    assert report.counts.eligible_entries == 0


def test_invalid_baseline_is_retained(tmp_path):
    p, files = case(healthy=True, real=True, confirmed=True)
    w = json.loads(files["response-a.json"])
    w["confounder_codes"] = ["operator_declared"]
    files["response-a.json"] = canonical(w)
    assert inspect_calibration_dataset(write(tmp_path, p, files)).report.entries[
        0
    ].reason_codes == ("baseline_invalid",)


def test_healthy_binding_cannot_claim_degraded_phase(tmp_path):
    p, files = case(healthy=True)
    w = json.loads(files["response-a.json"])
    w["phase"] = "degraded"
    files["response-a.json"] = canonical(w)
    with pytest.raises(ValueError, match="^invalid_calibration_dataset$"):
        inspect_calibration_dataset(write(tmp_path, p, files))


@pytest.mark.parametrize("change", ["scenario", "revision", "fps", "provenance"])
def test_known_controlled_ownership_mismatch_is_rejected(tmp_path, change):
    p, files = case(controlled=True, confirmed=True)
    if change == "scenario":
        p["entries"][0]["label"] = "render_capture_slowdown"
    elif change == "provenance":
        # Artificial real-provenance model branch cannot borrow a synthetic experiment.
        from .inspection_cases import response

        files["response-a.json"] = canonical(response(real=True, controlled=True))
    else:
        r = json.loads(files["response-a.json"])
        for w in (r["observation"]["degradedWindow"], r["observation"]["reliefWindow"]):
            if change == "revision":
                w["context"]["versions"]["pixelatedSourceRevision"] = "b" * 40
            elif w["phase"] == "degraded":
                w["effectiveSettings"]["targetFps"] += 1
        files["response-a.json"] = rebuild(r)
    with pytest.raises(ValueError, match="^invalid_calibration_dataset$"):
        inspect_calibration_dataset(write(tmp_path, p, files))


@pytest.mark.parametrize("delay,extra", [(50_000_000, ()), (1_000_000, ("effect_unverified",))])
def test_pacing_release_dispatch_and_label_mapping(tmp_path, delay, extra):
    p, files = case(controlled=True, confirmed=True)
    p["entries"][0]["label"] = "render_capture_slowdown"
    files["experiment-a.tar.gz"] = gzip.compress(
        archive(pacing_members(delay=delay).items()), mtime=0
    )
    assert inspect_calibration_dataset(write(tmp_path, p, files)).report.entries[
        0
    ].reason_codes == ("synthetic_only", *extra)


def test_controlled_unconfirmed_review_cannot_bind_experiment(tmp_path):
    p, files = case(controlled=True, confirmed=True)
    next(r for r in p["reviews"] if r["review_id"] == "label")["outcome"] = "rejected"
    report = inspect_calibration_dataset(write(tmp_path, p, files)).report
    assert report.entries[0].reason_codes == (
        "synthetic_only",
        "label_unverified",
        "binding_unverified",
    )
