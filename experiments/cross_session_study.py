#!/usr/bin/env python3
"""Inspect a pinned transfer protocol and score its next declared query."""

import argparse
import hashlib
import json
from pathlib import Path

from latency_fingerprinting.analytical.policy_release import payload_hash
from latency_fingerprinting.evaluation.candidates.cross_session_candidate import (
    cross_session_candidate_spec,
    score_cross_session_candidate,
)
from latency_fingerprinting.evaluation.responses.fixture_conditions import CONDITIONS, _hash
from latency_fingerprinting.evaluation.responses.median_response import _alias
from latency_fingerprinting.json_io import strict_json_loads


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def load(path):
    return strict_json_loads(path.read_text())


def inspect_protocol(path, expected_sha256):
    raw = path.read_bytes()
    if sha(raw) != expected_sha256:
        raise ValueError("protocol file hash differs")
    protocol = strict_json_loads(raw.decode())
    if protocol["content_hash"] != payload_hash(
        {k: v for k, v in protocol.items() if k != "content_hash"}
    ):
        raise ValueError("protocol content differs")
    implementation = protocol["implementation"]
    if protocol["state"] != "prepared_session_records_pending":
        raise ValueError("unsupported protocol state")
    if implementation["method_spec"] != cross_session_candidate_spec():
        raise ValueError("scorer contract differs")
    if sha(Path(__file__).read_bytes()) != implementation["processor_sha256"]:
        raise ValueError("processor bytes differ")
    dependencies = implementation["dependency_sha256"]
    if type(dependencies) is not dict or not dependencies:
        raise ValueError("scorer dependency pins required")
    if any(sha(Path(file).read_bytes()) != digest for file, digest in dependencies.items()):
        raise ValueError("scorer dependency differs")
    if (
        protocol["execution"]["acquisition_cap"] != 18
        or protocol["execution"]["retries"] is not False
    ):
        raise ValueError("transfer scope differs")
    fit = protocol["frozen_calibration"]
    if sha(Path(fit["file"]).read_bytes()) != fit["sha256"]:
        raise ValueError("frozen fit differs")
    sessions = protocol["reserved_sessions"]
    if len(sessions) != 3 or len({s["session_id"] for s in sessions}) != 3:
        raise ValueError("three distinct session groups required")
    slots = []
    for session in sessions:
        _alias(session["session_id"])
        if len(session["blocks"]) != 2:
            raise ValueError("two complete blocks per session required")
        for block in session["blocks"]:
            _alias(block["block_id"])
            if (
                set(block["condition_order"]) != set(CONDITIONS)
                or len(block["condition_order"]) != 3
            ):
                raise ValueError("complete condition order required")
            if set(block["acquisition_ids"]) != set(CONDITIONS):
                raise ValueError("complete acquisition mapping required")
            slots.extend(
                dict(
                    query_id=block["acquisition_ids"][c],
                    block_id=block["block_id"],
                    session_id=session["session_id"],
                )
                for c in block["condition_order"]
            )
    excluded = protocol["excluded_new_case_ids"]
    if len(slots) != 18 or len({s["query_id"] for s in slots}) != 18:
        raise ValueError("18 unique query IDs required")
    if {s["query_id"] for s in slots} & set(excluded):
        raise ValueError("reserved query overlaps exclusions")
    for slot in slots:
        _alias(slot["query_id"])
    _hash(protocol["source_manifest_hash"])
    return protocol, slots


def score_next(protocol, slots, *, session_file, session_hash, case, query_id, history):
    if len(history) >= len(slots):
        raise ValueError("all planned query slots already used")
    prior = []
    for slot, path in zip(slots, history, strict=False):
        row = load(path)
        if (
            row["result_id"]
            != "cross-session-query-"
            + payload_hash({k: v for k, v in row.items() if k != "result_id"})[7:]
        ):
            raise ValueError("prior prediction content differs")
        if row["query_id"] != slot["query_id"] or row["query_session_id"] != slot["session_id"]:
            raise ValueError("query ledger order differs")
        if row["query_block_id"] != slot["block_id"]:
            raise ValueError("query ledger block differs")
        prior.append(row)
    slot = slots[len(history)]
    record = load(session_file)
    if slot["query_id"] != query_id or record["session_id"] != slot["session_id"]:
        raise ValueError("next declared query required")
    context = record["observed_context"]
    if context["source_manifest_hash"] != protocol["source_manifest_hash"]:
        raise ValueError("session source manifest differs")
    frozen = protocol["frozen_calibration"]
    fitted = strict_json_loads(Path(frozen["file"]).read_text())
    if record["host_id"] != protocol["transfer_host_id"]:
        raise ValueError("session host differs")
    if context["runtime_context_hash"] != fitted["calibration"]["runtime_context_hash"]:
        raise ValueError("session runtime differs")
    from latency_fingerprinting.evaluation.candidates.cross_session_candidate import _timestamp

    if _timestamp(record["prior_session_ended_at_utc"]) < _timestamp(
        protocol["calibration_session_ended_at_utc"]
    ):
        raise ValueError("session boundary precedes baseline end")
    return score_cross_session_candidate(
        dict(
            acquisition_json=(case / "acquisition.json").read_text(),
            resource_artifact=load(case / "resource-observation.json"),
        ),
        frozen_fit_json=Path(frozen["file"]).read_text(),
        expected_fit_sha256=frozen["sha256"],
        session_record=record,
        expected_session_record_hash=session_hash,
        query_id=query_id,
        query_block_id=slot["block_id"],
        prior_queries=prior,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("inspect", "score"))
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--session-record", type=Path)
    parser.add_argument("--expected-session-record-hash")
    parser.add_argument("--case", type=Path)
    parser.add_argument("--query-id")
    parser.add_argument("--prior-prediction", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    protocol, slots = inspect_protocol(args.protocol, args.expected_protocol_sha256)
    if args.mode == "inspect":
        result = dict(
            state="prepared_session_records_pending",
            planned_query_count=len(slots),
            calibration_queries=0,
            session_groups=3,
            independent_support_groups=0,
            acquisition_authority=False,
        )
    else:
        if any(
            value is None
            for value in (
                args.session_record,
                args.expected_session_record_hash,
                args.case,
                args.query_id,
                args.output,
            )
        ):
            parser.error("score requires session record/hash, case, query ID and exclusive output")
        result = score_next(
            protocol,
            slots,
            session_file=args.session_record,
            session_hash=args.expected_session_record_hash,
            case=args.case,
            query_id=args.query_id,
            history=args.prior_prediction,
        )
        with args.output.open("x") as file:
            file.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
