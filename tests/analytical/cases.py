"""Explicit synthetic analytical inputs; expectations never call root validators."""

import hashlib
import json
from pathlib import Path

from latency_fingerprinting.models import ObservationRecordV2
from tests.models.v2_cases import pair_payload, window_payload

POLICY_SPEC = Path(__file__).parents[2] / "docs/analysis/N3_FEATURE_POLICY_SPEC.json"


def policy_payload():
    return json.loads(POLICY_SPEC.read_text())


def canonical(payload):
    return (
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode()


def response_payload(
    *, degraded=(0, 60, 120), relief=(0, 30, 60), confounder=None, source_state=None, rejected=False
):
    pair = pair_payload()
    pair["degraded_window"] = window_payload(values=degraded)
    pair["relief_window"] = window_payload(phase="relief", values=relief)
    if confounder:
        pair[confounder]["confounder_codes"] = ["operator_declared"]
    if source_state:
        phase, state = source_state
        window = pair[phase]
        window["sources"]["browser_webrtc"].update(
            state=state, declared_state=state, basis="source_declaration", available_row_count=0
        )
        for item in window["measurements"].values():
            if item["summary"]["source"] == "browser_webrtc":
                item["support"].update(state=state, declared_state=None, basis="source_support")
    if rejected:
        for item in pair["degraded_window"]["measurements"].values():
            item["summary"].update(
                status="rejected",
                missing_reasons=(),
                rejected_reasons=("Rejected source evidence.",),
            )
    observation = ObservationRecordV2.model_validate(pair).model_dump(mode="json", by_alias=True)
    policy = policy_payload()
    features = {}
    for name, parameter in policy["features"].items():
        evidence = {}
        exclusions = []
        for phase, key in [("degraded", "degradedWindow"), ("relief", "reliefWindow")]:
            window = observation[key]
            item = window["measurements"][name]
            summary = item["summary"]
            primary = summary["aggregates"].get(parameter["aggregation"])
            evidence[phase] = {
                "windowId": window["windowId"],
                "supportState": item["support"]["state"],
                "summaryStatus": summary["status"],
                "primaryValue": primary,
                **{
                    field: summary[field]
                    for field in (
                        "sourceSampleCount",
                        "usableSampleCount",
                        "acceptedIntervalCount",
                        "observedDurationMs",
                        "coverage",
                    )
                },
            }
            if item["support"]["state"] != "supported":
                exclusions.append(phase + "_" + item["support"]["state"])
            elif summary["status"] != "complete":
                exclusions.append(phase + "_" + summary["status"])
        if confounder:
            exclusions = ["confounded_pair"]
        reference = evidence["degraded"]["primaryValue"]
        delta = evidence["relief"]["primaryValue"] - reference if not exclusions else None
        features[name] = {
            "unit": parameter["unit"],
            "aggregation": parameter["aggregation"],
            "state": "excluded" if exclusions else "eligible",
            **evidence,
            "exclusionCodes": exclusions,
            "rawDelta": delta,
            "referenceValue": reference if not exclusions else None,
            "denominator": max(reference, 1.0) if not exclusions else None,
            "normalizedValue": delta / max(reference, 1.0) if not exclusions else None,
            "wasClipped": False,
            "unclippedValue": None,
        }
    reasons = (
        ["confounded_pair"]
        if confounder
        else (
            ["no_eligible_features"]
            if all(f["state"] == "excluded" for f in features.values())
            else []
        )
    )
    digest = hashlib.sha256(canonical({"observation": observation, "policy": policy})).hexdigest()
    return {
        "schemaVersion": "analytical-response-v2",
        "contractVersion": "2.0.0",
        "responseId": "response-v2-" + digest,
        "observation": observation,
        "policy": policy,
        "features": features,
        "isValid": not reasons,
        "invalidReasonCodes": reasons,
    }
