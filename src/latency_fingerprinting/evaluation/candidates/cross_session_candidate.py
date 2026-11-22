"""Frozen condition calibration applied to documented later fixture sessions."""

import hashlib
from copy import deepcopy
from datetime import datetime
from fractions import Fraction
from functools import partial

from latency_fingerprinting.analytical.policy_release import payload_hash
from latency_fingerprinting.evaluation.candidates.combined_interval_candidate import (
    _classify_candidate,
    _distance_report,
)
from latency_fingerprinting.evaluation.candidates.shared_window_candidate import (
    _evaluate,
    _project,
    fit_shared_window_candidate,
    shared_window_candidate_spec,
)
from latency_fingerprinting.evaluation.projections.combined_resource_projection import _exact
from latency_fingerprinting.evaluation.responses.fixture_conditions import _hash
from latency_fingerprinting.evaluation.responses.median_response import _alias
from latency_fingerprinting.json_io import strict_json_loads

RELEASE = "n11-condition-specific-event-span-cross-session-candidate-v1"
ERROR = "invalid_cross_session_candidate"
MAX_FIT_BYTES = 16 * 1024 * 1024
MAX_PRIOR_QUERIES = 256
_SPEC = dict(
    release=RELEASE,
    baseline_method_hash=shared_window_candidate_spec(condition_specific=True)["content_hash"],
    calibration="rebuild_and_exactly_match_canonical_frozen_calibration",
    query="documented_later_session_exact_runtime_context_fresh_id_source_clocks_and_block",
    decision="existing_condition_certificate_nine_coordinate_radius_and_fitted_minimum_gap",
    session_authenticity="external_boundary_record_and_custody_review_required",
    independent_support_groups=0,
    empirical_acceptance=False,
    acquisition_authority=False,
)


def cross_session_candidate_spec():
    return {**deepcopy(_SPEC), "content_hash": payload_hash(_SPEC)}


def _timestamp(value):
    if type(value) is not str:
        raise ValueError(ERROR)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(ERROR)
    return parsed


def _session(record, expected_hash, calibration_session):
    _hash(expected_hash)
    if payload_hash(record) != expected_hash:
        raise ValueError(ERROR)
    _exact(
        record,
        (
            "schema_version",
            "calibration_session_id",
            "session_id",
            "host_id",
            "prior_session_ended_at_utc",
            "started_at_utc",
            "documented_by",
            "boundary_description",
            "observed_context",
        ),
    )
    if record["schema_version"] != "n11-transfer-session-record-v1":
        raise ValueError(ERROR)
    for key in ("calibration_session_id", "session_id", "host_id"):
        _alias(record[key])
    if record["calibration_session_id"] != calibration_session:
        raise ValueError(ERROR)
    if _timestamp(record["prior_session_ended_at_utc"]) >= _timestamp(record["started_at_utc"]):
        raise ValueError(ERROR)
    for key in ("documented_by", "boundary_description"):
        value = record[key]
        if type(value) is not str or not value.strip() or len(value) > 4096:
            raise ValueError(ERROR)
    context = record["observed_context"]
    _exact(
        context,
        (
            "boot_identity",
            "browser_version",
            "background_load_description",
            "source_manifest_hash",
            "runtime_context_hash",
            "image_sha256",
            "host_platform",
            "host_arch",
        ),
    )
    for key in ("source_manifest_hash", "runtime_context_hash", "image_sha256"):
        _hash(context[key])
    for key in (
        "boot_identity",
        "browser_version",
        "background_load_description",
        "host_platform",
        "host_arch",
    ):
        if type(context[key]) is not str or not context[key].strip() or len(context[key]) > 4096:
            raise ValueError(ERROR)
    return record["session_id"]


def score_cross_session_candidate(
    source,
    *,
    frozen_fit_json,
    expected_fit_sha256,
    session_record,
    expected_session_record_hash,
    query_id,
    query_block_id,
    prior_queries,
):
    """Score without updating the calibration or reading a condition label.

    Caller custody must supply the complete earlier-query ledger and verified
    session record. This pure function checks their consistency.
    """
    try:
        _hash(expected_fit_sha256)
        _alias(query_id)
        _alias(query_block_id)
        if type(frozen_fit_json) is not str:
            raise ValueError(ERROR)
        raw = frozen_fit_json.encode("utf-8")
        if len(raw) > MAX_FIT_BYTES or (
            "sha256:" + hashlib.sha256(raw).hexdigest() != expected_fit_sha256
        ):
            raise ValueError(ERROR)
        fitted = strict_json_loads(frozen_fit_json)
        calibration_session = fitted["session_id"]
        rebuilt = fit_shared_window_candidate(
            fitted["training"], session_id=calibration_session, condition_specific=True
        )
        if payload_hash(rebuilt) != payload_hash(fitted["calibration"]):
            raise ValueError(ERROR)
        query_session = _session(session_record, expected_session_record_hash, calibration_session)
        response = _project(source, event_span=True, condition_specific=True)
        reasons = []
        if query_session == calibration_session:
            reasons.append("query_session_matches_calibration")
        observed = session_record["observed_context"]
        runtime = strict_json_loads(source["acquisition_json"])["context"]
        if (
            response["runtime_context_hash"] != rebuilt["runtime_context_hash"]
            or observed["runtime_context_hash"] != response["runtime_context_hash"]
            or observed["image_sha256"] != runtime["image"]
            or observed["host_platform"] != runtime["host_platform"]
            or observed["host_arch"] != runtime["host_arch"]
        ):
            reasons.append("incompatible_query_context")
        if query_block_id in rebuilt["training_block_ids"]:
            reasons.append("query_block_overlap")
        clocks = {response["source_worker_clock"], response["source_controller_clock"]}
        if response["source_payload_hash"] in rebuilt["source_payload_hashes"] or (
            clocks & set(rebuilt["source_clock_ids"])
        ):
            reasons.append("query_source_or_clock_overlap")
        if type(prior_queries) is not list or len(prior_queries) > MAX_PRIOR_QUERIES:
            raise ValueError(ERROR)
        for row in prior_queries:
            if (
                row["method_release"] != RELEASE
                or row["frozen_fit_sha256"] != expected_fit_sha256
                or row["calibration_session_id"] != calibration_session
            ):
                raise ValueError(ERROR)
            if row["query_id"] == query_id:
                reasons.append("query_id_reused")
            if row["query_source_payload_hash"] == response["source_payload_hash"] or (
                clocks & {row["source_worker_clock"], row["source_controller_clock"]}
            ):
                reasons.append("prior_query_source_or_clock_overlap")
            if row["query_block_id"] == query_block_id and row["query_session_id"] != query_session:
                reasons.append("query_block_session_conflict")
        if rebuilt["state"] == "unavailable":
            reasons.append("calibration_unavailable")
        if response["state"] == "unavailable":
            reasons.append("query_response_unavailable")
        distances, gap, prediction, details = {}, None, None, {}
        if not reasons:
            centers = {
                c: {
                    name: tuple(Fraction(**box[edge]) for edge in ("lower", "upper"))
                    for name, box in features.items()
                }
                for c, features in rebuilt["centers"].items()
            }
            reasons, distances, gap, prediction, details = _classify_candidate(
                response,
                centers,
                rebuilt["thresholds"],
                partial(_evaluate, condition_specific=True),
            )
        report = dict(
            method_release=RELEASE,
            method_spec=cross_session_candidate_spec(),
            frozen_fit_sha256=expected_fit_sha256,
            baseline_experiment_id=rebuilt["experiment_id"],
            calibration_session_id=calibration_session,
            query_session_id=query_session,
            session_record_hash=expected_session_record_hash,
            query_id=query_id,
            query_block_id=query_block_id,
            query_response_id=response["response_id"],
            query_source_payload_hash=response["source_payload_hash"],
            source_worker_clock=response["source_worker_clock"],
            source_controller_clock=response["source_controller_clock"],
            state="abstain" if reasons else "candidate_condition_prediction",
            reason_codes=list(dict.fromkeys(reasons)),
            predicted_condition=prediction,
            distances=_distance_report(distances),
            robust_gap=None
            if gap is None
            else dict(numerator=gap.numerator, denominator=gap.denominator),
            independent_support_groups=0,
            empirical_acceptance=False,
            acquisition_authority=False,
            **details,
        )
        return {**report, "result_id": "cross-session-query-" + payload_hash(report)[7:]}
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, UnicodeError):
        raise ValueError(ERROR) from None
