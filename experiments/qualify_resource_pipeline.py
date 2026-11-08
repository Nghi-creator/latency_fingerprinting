#!/usr/bin/env python3
"""Engineering-only projection, fitting and truth-free scoring for a bounded pipeline drill."""

import argparse
import hashlib
import json
from itertools import permutations
from pathlib import Path

from latency_fingerprinting.analytical.policy_release import payload_hash
from latency_fingerprinting.evaluation.counter_specific_candidate import (
    counter_specific_candidate_spec,
    declare_counter_specific_binding,
    fit_counter_specific_candidate,
    score_counter_specific_candidate,
)
from latency_fingerprinting.evaluation.counter_specific_projection import (
    project_counter_specific_resource,
)
from latency_fingerprinting.evaluation.fixture_conditions import CONDITIONS, _hash
from latency_fingerprinting.evaluation.median_response import _alias
from latency_fingerprinting.json_io import strict_json_loads

RELEASE = "n11-engineering-pipeline-qualification-v1"


def load(path):
    return strict_json_loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_at(directory):
    directory = Path(directory)
    return {
        "acquisition_json": (directory / "acquisition.json").read_text(encoding="utf-8"),
        "resource_artifact": load(directory / "resource-observation.json"),
    }


def inspect_config(config):
    if (
        config["pipelineQualification"] != RELEASE
        or config["scope"] != "engineering_only_no_study_admission"
        or config["retryAllowed"] is not False
        or type(config["maximumAcquisitions"]) is not int
        or config["maximumAcquisitions"] != 36
        or len(config["cases"]) != 36
    ):
        raise ValueError("invalid pipeline qualification scope/cap")
    _alias(config["sessionId"])
    _hash(config["contextHash"])
    _hash(config["sourceManifestHash"])
    _hash(config["imageSha256"])
    if payload_hash(config["sessionContext"]) != config["contextHash"]:
        raise ValueError("changed engineering context")
    context = config["sessionContext"]
    if (
        context["session_id"] != config["sessionId"]
        or type(context["session_components"]) is not int
        or context["session_components"] != 1
        or type(context["independent_support_groups"]) is not int
        or context["independent_support_groups"] != 0
    ):
        raise ValueError("invalid correlated engineering session")
    excluded = config["excludedCaseIds"]
    if type(excluded) is not list or excluded != sorted(set(excluded)):
        raise ValueError("invalid exclusions")
    for identifier in excluded:
        _alias(identifier)
    identifiers, blocks, orders = set(), set(), []
    directory = Path(config["directory"])
    if not directory.is_absolute():
        raise ValueError("absolute engineering directory required")
    for index in range(12):
        slots = config["cases"][index * 3 : index * 3 + 3]
        block = slots[0]["block_id"]
        _alias(block)
        if block in blocks:
            raise ValueError("repeated block")
        blocks.add(block)
        order = tuple(s["condition"] for s in slots)
        if set(order) != set(CONDITIONS):
            raise ValueError("incomplete condition block")
        orders.append(order)
        for ordinal, slot in enumerate(slots):
            identifier = slot["id"]
            _alias(identifier)
            _hash(slot["planSha256"])
            if (
                not identifier.startswith("n11-raw-eng-")
                or identifier in identifiers
                or identifier in excluded
                or slot["block_id"] != block
                or slot["role"] != ("fitting" if index < 6 else "query")
                or Path(slot["output"]) != directory / "cases" / str(index * 3 + ordinal + 1)
                or not Path(slot["plan"]).is_absolute()
            ):
                raise ValueError("invalid engineering case")
            identifiers.add(identifier)
    if set(orders[:6]) != set(permutations(CONDITIONS)) or orders[6:] != orders[:6][::-1]:
        raise ValueError("unbalanced declared order")
    return {
        "state": "engineering_pipeline_declarations_valid",
        "method_content_hash": counter_specific_candidate_spec()["content_hash"],
        "acquisitions": 36,
        "fitting_cases": 18,
        "query_cases": 18,
        "study_admission": False,
        "accuracy_gate": False,
    }


def fit_config(path):
    config = load(path)
    inspect_config(config)
    training = {}
    # Never open a query directory, its receipt, or any query measurement here.
    for slot in config["cases"][:18]:
        directory = Path(slot["output"])
        plan = load(directory / "plan.json")
        receipt = load(directory / "control-receipt.json")
        verified = load(directory / "engineering-verification.stdout")
        if (
            sha(slot["plan"]) != slot["planSha256"]
            or sha(directory / "plan.json") != slot["planSha256"]
            or plan["acquisition_id"] != slot["id"]
            or plan["condition"]["name"] != slot["condition"]
            or plan["source_manifest_hash"] != config["sourceManifestHash"]
            or plan["image"] != config["imageSha256"]
            or receipt["condition"] != slot["condition"]
            or receipt["condition_integrity"] != "verified_declared_internal_evidence"
            or receipt["resource_integrity"] != "verified_declared_internal_evidence"
            or verified["acquisition_id"] != slot["id"]
            or verified["source_manifest"] != config["sourceManifestHash"]
            or verified["native_sha256"] != sha(directory / "acquisition.json")
            or verified["sdk_cli_equal_phases"] != 3
            or verified["pipeline_projection"]["method_content_hash"]
            != counter_specific_candidate_spec()["content_hash"]
            or (directory / "failure.json").exists()
        ):
            raise ValueError("invalid engineering training witness")
        source = source_at(directory)
        if (
            strict_json_loads(source["acquisition_json"])["context"]["image"]
            != config["imageSha256"]
        ):
            raise ValueError("changed engineering runtime image")
        binding = declare_counter_specific_binding(
            source,
            condition=slot["condition"],
            context_hash=config["contextHash"],
            inspection_sha256=sha(directory / "control-receipt.json"),
        )
        training.setdefault(slot["block_id"], {})[slot["condition"]] = {
            "source": source,
            "binding": binding,
        }
    return {
        "scope": RELEASE,
        "method_content_hash": counter_specific_candidate_spec()["content_hash"],
        "configuration_sha256": sha(path),
        "session_id": config["sessionId"],
        "context_hash": config["contextHash"],
        "training": training,
        "calibration": fit_counter_specific_candidate(training, session_id=config["sessionId"]),
        "study_admission": False,
    }


def project_case(path):
    result = project_counter_specific_resource(source_at(path))
    return {
        "state": result["state"],
        "coordinates": len(result["features"]),
        "unavailable_components": result["unavailable_components"],
        "method_content_hash": counter_specific_candidate_spec()["content_hash"],
        "response_id": result["response_id"],
    }


def score_case(fitted, path, *, block, session):
    if (
        fitted["scope"] != RELEASE
        or fitted["method_content_hash"] != counter_specific_candidate_spec()["content_hash"]
        or fitted["study_admission"] is not False
    ):
        raise ValueError("wrong engineering training method")
    rebuilt = fit_counter_specific_candidate(fitted["training"], session_id=fitted["session_id"])
    if payload_hash(rebuilt) != payload_hash(fitted["calibration"]):
        raise ValueError("changed engineering calibration")
    # Deliberately do not open query plan, receipt or expected-condition bindings.
    return score_counter_specific_candidate(
        source_at(path),
        fitted["training"],
        session_id=fitted["session_id"],
        query_session_id=session,
        query_block_id=block,
        context_hash=fitted["context_hash"],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    for name in ("inspect", "fit", "project"):
        modes.add_parser(name).add_argument("path", type=Path)
    score = modes.add_parser("score")
    score.add_argument("--training", type=Path, required=True)
    score.add_argument("--case", type=Path, required=True)
    score.add_argument("--block", required=True)
    score.add_argument("--session", required=True)
    args = parser.parse_args()
    if args.mode == "inspect":
        result = inspect_config(load(args.path))
    elif args.mode == "fit":
        result = fit_config(args.path)
    elif args.mode == "project":
        result = project_case(args.path)
    else:
        result = score_case(load(args.training), args.case, block=args.block, session=args.session)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
