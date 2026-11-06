#!/usr/bin/env python3
"""Combined-candidate declarations, training-only fitting and truth-free case scoring."""

import argparse
import hashlib
import json
from pathlib import Path

from latency_fingerprinting.analytical.policy_release import payload_hash
from latency_fingerprinting.evaluation.combined_interval_candidate import (
    declare_combined_condition_binding,
    fit_combined_interval_candidate,
    score_combined_interval_candidate,
)
from latency_fingerprinting.evaluation.combined_study_protocol import (
    inspect_combined_study_protocol,
)
from latency_fingerprinting.json_io import strict_json_loads


def load(path):
    return strict_json_loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_at(directory):
    directory = Path(directory)
    return dict(
        acquisition_json=(directory / "acquisition.json").read_text(encoding="utf-8"),
        resource_artifact=load(directory / "resource-observation.json"),
    )


def fit_allocation(path):
    path = Path(path).resolve()
    allocation, protocol = load(path), load(path.parent / "protocol.json")
    if (
        inspect_combined_study_protocol(protocol)["state"]
        != "reviewed_combined_study_declarations_complete"
    ):
        raise ValueError("protocol not reviewed")
    if (
        allocation["protocol_id"] != protocol["protocol_id"]
        or sha(path.parent / "protocol.json") != allocation["protocol_file_sha256"]
    ):
        raise ValueError("wrong allocation protocol")
    if len(allocation["sessions"]) != 12:
        raise ValueError("wrong allocation blocks")
    # Protocol identity binds declared method/source/image/session/order/exclusions/tools.
    context_hash = payload_hash(dict(protocol_id=protocol["protocol_id"], scope=protocol["scope"]))
    if sha(Path(__file__)) != protocol["tool_hashes"]["processor"]:
        raise ValueError("changed processor tool")
    training = {}
    for index, declared in enumerate(protocol["blocks"][:6]):
        block = allocation["sessions"][index]
        if (
            any(
                block[key] != declared[key] for key in ("block_id", "role", "host_id", "session_id")
            )
            or block["role"] != "training"
        ):
            raise ValueError("wrong training block")
        if (
            len(block["slots"]) != 3
            or [s["condition"] for s in block["slots"]] != declared["condition_order"]
        ):
            raise ValueError("wrong training slots")
        rows = {}
        for slot in block["slots"]:
            directory = Path(slot["output"])
            plan, receipt = load(directory / "plan.json"), load(directory / "control-receipt.json")
            verified = load(directory / "verification-command.stdout")
            condition = slot["condition"]
            identifier = declared["acquisition_ids"][condition]
            if (
                slot["acquisition_id"] != identifier
                or plan["acquisition_id"] != identifier
                or plan["schema_version"] != "n11-contained-resource-condition-plan-v1"
                or plan["condition"]["name"] != condition
                or plan["source_manifest_hash"] != protocol["source_manifest_hash"]
                or plan["image"] != protocol["image_sha256"]
                or receipt["condition"] != condition
                or receipt["condition_integrity"] != "verified_declared_internal_evidence"
                or receipt["resource_integrity"] != "verified_declared_internal_evidence"
                or verified["acquisition_id"] != identifier
                or verified["sdk_cli_equal_phases"] != 3
                or verified["source_manifest"] != protocol["source_manifest_hash"]
                or verified["native_sha256"] != sha(directory / "acquisition.json")
                or sha(directory / "plan.json") != slot["plan_sha256"]
                or (directory / "failure.json").exists()
            ):
                raise ValueError("invalid training witness")
            source = source_at(directory)
            if (
                strict_json_loads(source["acquisition_json"])["context"]["image"]
                != protocol["image_sha256"]
            ):
                raise ValueError("source image differs from protocol")
            binding = declare_combined_condition_binding(
                source,
                condition=condition,
                context_hash=context_hash,
                inspection_sha256=sha(directory / "control-receipt.json"),
            )
            rows[condition] = dict(source=source, binding=binding)
        training[block["block_id"]] = rows
    session_id = protocol["blocks"][0]["session_id"]
    return dict(
        training=training,
        session_id=session_id,
        context_hash=context_hash,
        protocol_id=protocol["protocol_id"],
        calibration=fit_combined_interval_candidate(training, session_id=session_id),
    )


def score_case(fitted, directory, *, block_id, session_id):
    rebuilt = fit_combined_interval_candidate(fitted["training"], session_id=fitted["session_id"])
    if payload_hash(rebuilt) != payload_hash(fitted["calibration"]):
        raise ValueError("changed calibration")
    # Query plan, receipt and condition truth are deliberately not opened here.
    return score_combined_interval_candidate(
        source_at(directory),
        fitted["training"],
        session_id=fitted["session_id"],
        query_session_id=session_id,
        query_block_id=block_id,
        context_hash=fitted["context_hash"],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("inspect").add_argument("protocol", type=Path)
    sub.add_parser("fit").add_argument("allocation", type=Path)
    score = sub.add_parser("score")
    score.add_argument("--training", type=Path, required=True)
    score.add_argument("--case", type=Path, required=True)
    score.add_argument("--block", required=True)
    score.add_argument("--session", required=True)
    args = parser.parse_args()
    if args.mode == "inspect":
        result = inspect_combined_study_protocol(load(args.protocol))
    elif args.mode == "fit":
        result = fit_allocation(args.allocation)
    else:
        result = score_case(
            load(args.training), args.case, block_id=args.block, session_id=args.session
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
