"""Synthetic matching inputs with independently chosen feature changes."""

from latency_fingerprinting.analytical.fingerprints import create_fingerprint_v2
from latency_fingerprinting.analytical.matching import match_response_v2
from latency_fingerprinting.analytical.repository import FingerprintRepositoryV2
from latency_fingerprinting.analytical.responses import derive_analytical_response
from latency_fingerprinting.models import FeaturePolicyV1, ObservationRecordV2
from tests.models.v2_cases import pair_payload, window_payload

from .cases import policy_payload


def response(*, normalized=0, excluded=(), changes=None, real=False, confounded=False):
    pair = pair_payload(real=real)
    pair["relief_window"] = window_payload(
        phase="relief", real=real, values=(0, 60 * (1 + normalized), 120 * (1 + normalized))
    )
    missing = window_payload(values=(None, None, None))
    for name in excluded:
        selected = missing["measurements"][name]["summary"]
        for linked, item in missing["measurements"].items():
            summary = item["summary"]
            if (summary["source"], summary["raw_fields"]) == (
                selected["source"],
                selected["raw_fields"],
            ):
                pair["degraded_window"]["measurements"][linked] = item
    if confounded:
        pair["intervention"]["confounder_codes"] = ["operator_declared"]
    if changes:
        changes(pair)
    return derive_analytical_response(
        ObservationRecordV2.model_validate(pair), FeaturePolicyV1.model_validate(policy_payload())
    )


def fingerprint(*, label="declared", status="software_checked", **kwargs):
    return create_fingerprint_v2(
        response(**kwargs), bottleneck_label=label, validation_status=status
    )


def jitter_response(delta):
    """Keep all other features equal while retaining a small, nonzero delta."""

    def change(pair):
        for phase, values in (("degraded", (0, 0, 0)), ("relief", (0, delta, 2 * delta))):
            pair[phase + "_window"]["measurements"]["transport.jitter_ms"] = window_payload(
                phase=phase, values=values
            )["measurements"]["transport.jitter_ms"]

    return response(changes=change)


def match(query=None, records=()):
    query = response() if query is None else query
    return match_response_v2(query, query.policy, FingerprintRepositoryV2(tuple(records)))
