"""Verify the published ledger and file integrity; does not replay private telemetry."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

CONDITIONS = {"no_injected_fault", "owned_identity_delay", "owned_cpu_pressure"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(directory: Path) -> dict:
    directory = Path(directory)
    checksums = json.loads((directory / "checksums.json").read_text())
    require(checksums["schema_version"] == "sha256-file-manifest-v1", "checksum schema")
    files = checksums["files"]
    expected = {
        "README.md",
        "protocol.json",
        "calibration.json",
        "outcomes.json",
        "verification.json",
        "provenance.json",
        "history.json",
        "verify_results.py",
    }
    require(set(files) == expected, "published file set")
    for name, digest in files.items():
        actual = "sha256:" + hashlib.sha256((directory / name).read_bytes()).hexdigest()
        require(actual == digest, "checksum mismatch: " + name)

    def load(name):
        return json.loads((directory / (name + ".json")).read_text())

    protocol, cal, outcomes = load("protocol"), load("calibration"), load("outcomes")
    verification, provenance, history = load("verification"), load("provenance"), load("history")
    require(
        protocol["session_components"] == 1 and protocol["independent_support_groups"] == 0,
        "single-session scope",
    )
    require(
        protocol["maximum_acquisitions"] == 36 and protocol["retries"] is False, "collection cap"
    )
    blocks = protocol["blocks"]
    require(len(blocks) == 12 and len({b["block_id"] for b in blocks}) == 12, "block inventory")
    slots, training, evaluation = {}, set(), set()
    for index, block in enumerate(blocks):
        role = "training" if index < 6 else "evaluation"
        require(block["role"] == role, "training must precede evaluation")
        require(
            set(block["condition_order"]) == CONDITIONS and len(block["condition_order"]) == 3,
            "complete condition block",
        )
        require(set(block["acquisition_ids"]) == CONDITIONS, "condition mapping")
        for condition, identifier in block["acquisition_ids"].items():
            require(identifier not in slots, "duplicate acquisition")
            slots[identifier] = (block["block_id"], condition, role)
            if role == "training":
                training.add(block["block_id"])
            else:
                evaluation.add(identifier)
    require(len(slots) == 36 and len(evaluation) == 18, "planned denominator")
    require(cal["state"] == "candidate_calibration_available", "calibration availability")
    require(cal["evaluation_acquisitions_started_at_freeze"] == 0, "fit freeze order")
    require(len(cal["folds"]) == 6 and cal["certificate_count"] == 18, "calibration counts")
    require({f["held_out_block_id"] for f in cal["folds"]} == training, "fold coverage")
    for fold in cal["folds"]:
        require(
            set(fold["training_block_ids"]) == training - {fold["held_out_block_id"]}, "fold split"
        )
        require(fold["complete_and_correct"] is True, "fold outcome")
        require(
            len(fold["certificates"]) == 3
            and {c["condition"] for c in fold["certificates"]} == CONDITIONS,
            "certificate coverage",
        )
        require(
            all(c["uniquely_correct"] is True for c in fold["certificates"]), "certificate outcome"
        )
    require(protocol["method_content_hash"] == cal["method_content_hash"], "method identity")
    require(
        cal["frozen_fit_sha256"]
        == provenance["frozen_fit_sha256"]
        == verification["frozen_fit_sha256"],
        "fit identity",
    )
    require(
        protocol["source_manifest_sha256"]
        == provenance["source_manifest_sha256"]
        == verification["source_manifest_sha256"],
        "source identity",
    )
    seen, counts, by_condition = set(), Counter(), {c: Counter() for c in CONDITIONS}
    for query in outcomes["queries"]:
        identifier = query["acquisition_id"]
        require(identifier in evaluation and identifier not in seen, "held-out query inventory")
        seen.add(identifier)
        block, condition, _ = slots[identifier]
        require(
            query["block_id"] == block and query["declared_fixture_condition"] == condition,
            "query condition or block differs from protocol",
        )
        reasons = query["reason_codes"]
        require(
            type(reasons) is list and all(type(r) is str and r for r in reasons), "reason codes"
        )
        if query["state"] == "abstain":
            require(query["predicted_condition"] is None and reasons, "abstention must be explicit")
            outcome = "abstain"
        else:
            require(
                query["state"] == "candidate_condition_prediction" and not reasons,
                "prediction state",
            )
            require(query["predicted_condition"] in CONDITIONS, "predicted condition")
            outcome = "correct" if query["predicted_condition"] == condition else "incorrect"
        for key in ("original_prediction_sha256", "original_acquisition_sha256"):
            require(
                re.fullmatch(r"sha256:[a-f0-9]{64}", query[key]) is not None,
                "original artifact hash",
            )
        counts[outcome] += 1
        by_condition[condition][outcome] += 1
    require(seen == evaluation, "missing evaluation outcome")
    for key, count in (
        ("correct_queries", counts["correct"]),
        ("abstentions", counts["abstain"]),
        ("incorrect_predictions", counts["incorrect"]),
    ):
        require(verification[key] == count, "summary differs from outcomes")
    require(
        verification["verified_acquisitions"] == 36
        and verification["training_verified"] == 18
        and verification["evaluation_verified"] == 18,
        "verified denominator",
    )
    require(
        verification["phase_replays"] == 108 and verification["verified_restorations"] == 36,
        "phase/restoration summary",
    )
    require(
        verification["fit_bytes_identical"] is True
        and verification["prediction_bytes_identical"] == 18,
        "reported private replay summary",
    )
    require(
        verification["failed_acquisitions"] == 0 and verification["unstarted"] == 0,
        "incomplete cohort",
    )
    require(
        verification["empirical_acceptance"] is False
        and verification["full_raw_replay_publicly_available"] is False,
        "public assurance limits",
    )
    require(history["pooling_allowed"] is False, "source versions must remain separate")
    for cohort in history["cohorts"]:
        require(
            cohort["verified_acquisitions"]
            + cohort["failed_acquisitions"]
            + cohort["unstarted_acquisitions"]
            == cohort["planned_acquisitions"],
            "history denominator",
        )
    return dict(
        scope="published ledger and checksum consistency; private raw replay not performed",
        files_verified=len(files),
        queries=len(seen),
        correct=counts["correct"],
        abstain=counts["abstain"],
        incorrect=counts["incorrect"],
        by_condition={k: dict(v) for k, v in by_condition.items()},
    )


if __name__ == "__main__":
    print(json.dumps(verify(Path(__file__).resolve().parent), indent=2))
