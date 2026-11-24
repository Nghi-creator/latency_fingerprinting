"""Raw custody and lifecycle checks on invented media, never scientific admission."""

import hashlib
import json
from pathlib import Path

import pytest

from latency_fingerprinting.evaluation.protocols.physical_challenge_raw import (
    inspect_challenge_raw_export,
)


def render(v):
    return (json.dumps(v, indent=2, ensure_ascii=False) + "\n").encode()


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def operands(recipe="delay_to_pressure"):
    transcript = json.loads(
        (Path("fixtures/physical-challenge-v1/transcripts") / (recipe + ".json")).read_bytes()
    )
    excluded = dict(excluded_case_ids=["n11-raw-previous"], retry_allowed=False)
    sources = {"research/unit.py": "f" * 64}
    p = dict(
        schema_version="n11-physical-challenge-plan-v1",
        recipe=recipe,
        acquisition_id="n11-raw-unit-raw",
        image="sha256:" + "a" * 64,
        native_software_hash="b" * 64,
        source_sha256=sources,
        source_manifest_hash=sha(render(sources)),
        excluded_case_ids=excluded["excluded_case_ids"],
        exclusion_receipt_sha256=sha(render(excluded)),
        mode="engineering-n11-physical-challenge-" + recipe,
        pair_semantics="changing_between_phases_not_stable_pair"
        if "_to_" in recipe
        else "unqualified_raw_phases",
        retry_allowed=False,
        labels="unavailable",
        n2_pair_admitted=False,
        empirical_acceptance=False,
    )
    a = dict(
        status="passed",
        method="n11-physical-challenge-acquisition-v1",
        role="engineering_challenge_raw_phases_no_pair_or_diagnostic_label",
        mode=p["mode"],
        challenge_recipe=recipe,
        live_authority=False,
        context=dict(image=p["image"], software_hash=p["native_software_hash"]),
        paired_observation=dict(
            phases=[
                dict(
                    version="n11-contained-raw-samples-v1",
                    phase=phase,
                    comparison_case_id=p["acquisition_id"],
                    failure=None,
                    browser_samples=[{}, {}, {}, {}],
                    engine_snapshots=[],
                )
                for phase in ("degraded", "relief", "recovery")
            ]
        ),
        events=[
            dict(
                kind="n11_challenge_command_transcript", live_authority=False, transcript=transcript
            )
        ],
    )
    e = dict(
        schema_version="n11-physical-challenge-raw-export-v1",
        scope="raw_custody_requires_separate_source_qualification",
        acquisition_sha256=sha(render(a)),
        plan_sha256=sha(render(p)),
        recipe=recipe,
        image=p["image"],
        native_software_hash=p["native_software_hash"],
        source_manifest_hash=p["source_manifest_hash"],
        transcript_json=render(transcript).decode(),
        transcript_sha256=sha(render(transcript)),
        phases=[
            dict(phase=c["phase"], capture_json=render(c).decode(), capture_sha256=sha(render(c)))
            for c in a["paired_observation"]["phases"]
        ],
        source_media_verified=False,
        resource_dose_verified=False,
        n2_pair_admitted=False,
        empirical_acceptance=False,
    )
    return a, p, e, excluded


@pytest.mark.parametrize(
    "recipe",
    ["mixed_delay_pressure", "delay_to_pressure", "pressure_to_delay", "control_no_injected_fault"],
)
def test_raw_replay_binds_all_original_bytes_without_admitting_media(recipe):
    result = inspect_challenge_raw_export(*map(render, operands(recipe)))
    assert result["raw_phases_bound"] == 3
    assert result["lifecycle"]["commands_verified"] == 10
    assert result["source_media_verified"] is False
    assert result["n2_pair_admitted"] is False
    assert result["empirical_acceptance"] is False


@pytest.mark.parametrize(
    "change",
    [
        "capture",
        "source_hash",
        "excluded_id",
        "stable",
        "failed_source",
        "image",
        "omission",
        "transcript",
        "flags",
    ],
)
def test_individually_rehashed_exports_cannot_change_source_or_scope(change):
    a, p, e, excluded = operands()
    if change == "capture":
        capture = json.loads(e["phases"][0]["capture_json"])
        capture["comparison_case_id"] = "other"
        e["phases"][0].update(
            capture_json=render(capture).decode(), capture_sha256=sha(render(capture))
        )
    elif change == "source_hash":
        p["source_sha256"]["research/unit.py"] = "e" * 64
        e["plan_sha256"] = sha(render(p))
    elif change == "excluded_id":
        excluded["excluded_case_ids"].append(p["acquisition_id"])
        p["exclusion_receipt_sha256"] = sha(render(excluded))
        e["plan_sha256"] = sha(render(p))
    elif change == "stable":
        p["pair_semantics"] = "stable_pair"
        e["plan_sha256"] = sha(render(p))
    elif change == "failed_source":
        a["status"] = "failed"
        e["acquisition_sha256"] = sha(render(a))
    elif change == "image":
        e["image"] = "sha256:" + "f" * 64
    elif change == "omission":
        e["phases"].pop()
    elif change == "transcript":
        t = json.loads(e["transcript_json"])
        t["records"].pop()
        e["transcript_json"] = render(t).decode()
        e["transcript_sha256"] = sha(render(t))
    else:
        e["source_media_verified"] = True
    with pytest.raises(ValueError, match="invalid_challenge_raw_export"):
        inspect_challenge_raw_export(*map(render, (a, p, e, excluded)))
