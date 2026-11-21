#!/usr/bin/env python3
"""Replay a frozen event-span fit against derived source challenges."""

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path

from latency_fingerprinting.analytical.policy_release import payload_hash
from latency_fingerprinting.evaluation.shared_window_candidate import (
    score_shared_window_candidate,
)
from latency_fingerprinting.evaluation.shared_window_projection import project_shared_window_source
from latency_fingerprinting.evaluation.shared_window_separation import (
    _interval,
    _ratio,
    compare_shared_window_centers,
)
from latency_fingerprinting.json_io import strict_json_loads


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def derived_source(source, change):
    value = deepcopy(source)
    acquisition = strict_json_loads(value["acquisition_json"])
    change(acquisition)
    value["acquisition_json"] = json.dumps(acquisition, indent=2) + "\n"
    value["resource_artifact"]["source_payload_sha256"] = sha(value["acquisition_json"].encode())
    return value


def missing_trace(raw):
    raw["events"] = [e for e in raw["events"] if e["kind"] != "n11_encoded_event_trace"]


def unreconciled_trace(raw):
    report = next(e for e in raw["events"] if e["kind"] == "n11_encoded_event_trace")
    report["trace"]["identity_read"]["count"] -= 1
    report.update(state="unavailable", reason_codes=["identity_prefix_not_reconciled"], windows={})


def mismatched_namespace(raw):
    report = next(e for e in raw["events"] if e["kind"] == "n11_encoded_event_trace")
    report["controller_time_namespace"] = "time:[0]"
    report.update(state="unavailable", reason_codes=["time_namespace_mismatch"], windows={})


def missing_recovery(raw):
    report = next(e for e in raw["events"] if e["kind"] == "n11_encoded_event_trace")
    del report["windows"]["recovery"]


def changed_clock(raw):
    report = next(e for e in raw["events"] if e["kind"] == "n11_encoded_event_trace")
    report["worker_clock_id"] = "worker-monotonic-" + "0" * 64


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--expected-fit-sha256", required=True)
    args = parser.parse_args()
    study = args.study.resolve()
    fit_file = study / "training-fit.json"
    frozen = fit_file.read_bytes()
    if sha(frozen) != args.expected_fit_sha256:
        raise ValueError("fitting artifact hash differs")
    fitted = strict_json_loads(frozen.decode())
    allocation = strict_json_loads((study / "allocation.json").read_text())
    cases = []
    captured = {}

    def read(file):
        raw = file.read_bytes()
        captured[file] = raw
        return raw

    for block in allocation["sessions"][6:]:
        for slot in block["slots"]:
            directory = Path(slot["output"])
            source = dict(
                acquisition_json=read(directory / "acquisition.json").decode(),
                resource_artifact=strict_json_loads(
                    read(directory / "resource-observation.json").decode()
                ),
            )
            options = dict(
                session_id=fitted["session_id"],
                query_session_id=block["session_id"],
                query_block_id=block["block_id"],
                context_hash=fitted["context_hash"],
                condition_specific=True,
            )
            original = score_shared_window_candidate(source, fitted["training"], **options)
            expected = strict_json_loads(read(directory / "prediction.json").decode())
            if original != expected:
                raise ValueError("original prediction differs")
            cases.append(dict(id=slot["acquisition_id"], source=source, options=options))

    first = cases[0]
    checks = []
    transformations = (
        ("missing_trace", missing_trace, "abstain", "query_response_unavailable"),
        ("unreconciled_trace", unreconciled_trace, "abstain", "query_response_unavailable"),
        ("namespace_mismatch", mismatched_namespace, "abstain", "query_response_unavailable"),
        ("missing_recovery", missing_recovery, "reject", None),
        ("foreign_worker_clock", changed_clock, "reject", None),
    )
    for name, change, expected_state, reason in transformations:
        source = derived_source(first["source"], change)
        try:
            result = score_shared_window_candidate(source, fitted["training"], **first["options"])
        except ValueError as exc:
            if expected_state != "reject":
                raise
            result = dict(state="reject", reason=str(exc), predicted_condition=None)
        if result["state"] != expected_state or (
            reason is not None and reason not in result["reason_codes"]
        ):
            raise ValueError("challenge produced an unexpected outcome")
        checks.append(
            dict(
                challenge=name,
                input_sha256=sha(source["acquisition_json"].encode()),
                resource_artifact_hash=payload_hash(source["resource_artifact"]),
                expected_state=expected_state,
                expected_reason=reason,
                result=result,
            )
        )

    corrupt = deepcopy(first["source"])
    corrupt["acquisition_json"] += " "
    try:
        score_shared_window_candidate(corrupt, fitted["training"], **first["options"])
    except ValueError as exc:
        checks.append(
            dict(challenge="broken_raw_byte_binding", result=dict(state="reject", reason=str(exc)))
        )
    else:
        raise ValueError("corrupt source binding accepted")

    groups = [
        project_shared_window_source(case["source"], event_span=True)["phase_rates"]
        for case in cases
    ]
    hull = {}
    for group, phases in groups[0].items():
        hull[group] = {}
        for phase in phases:
            bounds = [_interval(rates[group][phase]) for rates in groups]
            hull[group][phase] = dict(
                lower=_ratio(min(lo for lo, _ in bounds)),
                upper=_ratio(max(hi for _, hi in bounds)),
            )
    certificate = compare_shared_window_centers(
        hull, fitted["calibration"]["centers"], condition_specific=True
    )
    if certificate["state"] != "abstain":
        raise ValueError("uncertain multi-condition rate hull did not abstain")
    if fit_file.read_bytes() != frozen or any(p.read_bytes() != raw for p, raw in captured.items()):
        raise ValueError("frozen evidence changed during replay")
    print(
        json.dumps(
            dict(
                scope="derived_source_and_arithmetic_challenge_replay",
                fit_sha256=sha(frozen),
                original_predictions_reproduced=len(cases),
                raw_files_checked_unchanged=len(captured) + 1,
                source_challenges=checks,
                synthetic_uncertain_rate_hull=dict(phase_rates=hull, result=certificate),
                real_mixed_condition_cases=0,
                new_acquisitions=0,
                empirical_acceptance=False,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
