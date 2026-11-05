#!/usr/bin/env python3
"""Metadata inspection, training-only fitting and truth-free scoring for one-session studies."""

import argparse
import hashlib
import json
from pathlib import Path

from latency_fingerprinting.evaluation.fixture_conditions import declare_fixture_condition_binding
from latency_fingerprinting.evaluation.within_session import (
    fit_within_session,
    score_within_session,
)
from latency_fingerprinting.evaluation.within_session_protocol import (
    inspect_within_session_protocol,
)
from latency_fingerprinting.json_io import strict_json_loads
from latency_fingerprinting.models import AnalyticalResponseV2


def load(path):
    return strict_json_loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fit_allocation(path):
    path = Path(path).resolve()
    allocation = load(path)
    protocol = load(path.parent / "protocol.json")
    if (
        inspect_within_session_protocol(protocol)["state"]
        != "reviewed_within_session_declarations_complete"
    ):
        raise ValueError("protocol not reviewed")
    if allocation["protocol_id"] != protocol["protocol_id"]:
        raise ValueError("wrong allocation protocol")
    training = {}
    for declared in protocol["blocks"][:6]:
        block = next(b for b in allocation["sessions"] if b["block_id"] == declared["block_id"])
        if block["role"] != "training":
            raise ValueError("wrong training role")
        rows = {}
        for slot in block["slots"]:
            directory = Path(slot["output"])
            plan = load(directory / "plan.json")
            receipt = load(directory / "control-receipt.json")
            condition = slot["condition"]
            if (
                plan["acquisition_id"] != declared["acquisition_ids"][condition]
                or plan["condition"]["name"] != condition
                or plan["source_manifest_hash"] != protocol["source_manifest_hash"]
                or receipt["condition"] != condition
                or receipt["condition_integrity"] != "verified_declared_internal_evidence"
                or (directory / "failure.json").exists()
            ):
                raise ValueError("invalid training witness")
            response = AnalyticalResponseV2.model_validate(load(directory / "response.json"))
            if response.observation.comparison_case_id != plan["acquisition_id"]:
                raise ValueError("wrong training response")
            binding = declare_fixture_condition_binding(
                response,
                condition=condition,
                witness_acquisition_sha256=sha(directory / "acquisition.json"),
                witness_inspection_sha256=sha(directory / "control-receipt.json"),
            )
            rows[condition] = dict(
                response=response.model_dump(mode="json", by_alias=True), binding=binding
            )
        training[block["block_id"]] = rows
    session = protocol["blocks"][0]["session_id"]
    return dict(
        training=training,
        session_id=session,
        calibration=fit_within_session(training, session_id=session),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("inspect").add_argument("protocol", type=Path)
    sub.add_parser("fit").add_argument("allocation", type=Path)
    score = sub.add_parser("score")
    score.add_argument("--training", type=Path, required=True)
    score.add_argument("--response", type=Path, required=True)
    score.add_argument("--block", required=True)
    score.add_argument("--session", required=True)
    args = parser.parse_args()
    if args.mode == "inspect":
        result = inspect_within_session_protocol(load(args.protocol))
    elif args.mode == "fit":
        result = fit_allocation(args.allocation)
    else:
        fitted = load(args.training)
        rebuilt = fit_within_session(fitted["training"], session_id=fitted["session_id"])
        if rebuilt != fitted["calibration"]:
            raise ValueError("changed calibration")
        result = score_within_session(
            load(args.response),
            fitted["training"],
            session_id=fitted["session_id"],
            query_session_id=args.session,
            query_block_id=args.block,
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
