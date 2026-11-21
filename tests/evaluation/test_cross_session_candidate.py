"""Synthetic later-session scoring and frozen-calibration checks."""

import hashlib
import json

import pytest

from latency_fingerprinting.analytical.policy_release import payload_hash
from latency_fingerprinting.evaluation import cross_session_candidate as method
from latency_fingerprinting.evaluation.shared_window_candidate import (
    declare_shared_window_binding,
    fit_shared_window_candidate,
)
from tests.evaluation.test_combined_interval_candidate import CONTEXT
from tests.evaluation.test_event_span_projection import event_source

CONDITIONS = ("no_injected_fault", "owned_identity_delay", "owned_cpu_pressure")


@pytest.fixture(scope="module")
def setup():
    blocks = {}
    for i in range(6):
        rows = {}
        for arm, condition in enumerate(CONDITIONS):
            identifier = f"xs-fit-{i}-{arm}"
            source = event_source(identifier, arm)
            rows[condition] = dict(
                source=source,
                binding=declare_shared_window_binding(
                    source,
                    condition=condition,
                    context_hash=CONTEXT,
                    inspection_sha256="sha256:" + hashlib.sha256(identifier.encode()).hexdigest(),
                    condition_specific=True,
                ),
            )
        blocks[f"fit-block-{i}"] = rows
    fitted = dict(
        training=blocks,
        session_id="cal-session",
        calibration=fit_shared_window_candidate(
            blocks, session_id="cal-session", condition_specific=True
        ),
    )
    raw = json.dumps(fitted)
    record = dict(
        schema_version="n11-transfer-session-record-v1",
        calibration_session_id="cal-session",
        session_id="later-session",
        host_id="one-host",
        prior_session_ended_at_utc="2026-11-16T17:00:00Z",
        started_at_utc="2026-11-20T01:00:00Z",
        documented_by="synthetic-test",
        boundary_description="Invented ended and resumed session for software tests",
        observed_context=dict(
            boot_identity="test-boot",
            browser_version="test",
            background_load_description="synthetic fixture",
            source_manifest_hash="sha256:" + "c" * 64,
            runtime_context_hash=fitted["calibration"]["runtime_context_hash"],
            image_sha256="sha256:" + "a" * 64,
            host_platform="test",
            host_arch="test",
        ),
    )
    return raw, record


def score(setup, source=None, **overrides):
    raw, record = setup
    args = dict(
        frozen_fit_json=raw,
        expected_fit_sha256="sha256:" + hashlib.sha256(raw.encode()).hexdigest(),
        session_record=record,
        expected_session_record_hash=payload_hash(record),
        query_id="fresh-case",
        query_block_id="later-block",
        prior_queries=[],
    )
    return method.score_cross_session_candidate(
        source or event_source("xs-fresh", 1), **(args | overrides)
    )


def test_frozen_model_scores_later_session_and_keeps_both_identities(setup):
    result = score(setup)
    assert result["predicted_condition"] == "owned_identity_delay"
    assert result["calibration_session_id"] == "cal-session"
    assert result["query_session_id"] == "later-session"
    assert result["independent_support_groups"] == 0
    assert result["empirical_acceptance"] is False
    assert result["state"] == "candidate_condition_prediction"
    assert result["method_release"] == method.RELEASE


@pytest.mark.parametrize(
    "damage", ["fit_bytes", "fit_threshold", "record_hash", "missing_boundary", "reversed_boundary"]
)
def test_changed_fit_or_unverified_session_is_rejected(setup, damage):
    from copy import deepcopy

    raw, record = setup
    record = deepcopy(record)
    overrides = {}
    if damage == "fit_bytes":
        overrides["frozen_fit_json"] = raw + " "
    elif damage == "fit_threshold":
        fitted = json.loads(raw)
        fitted["calibration"]["thresholds"]["minimum_gap"]["numerator"] = 0
        changed = json.dumps(fitted)
        overrides.update(
            frozen_fit_json=changed,
            expected_fit_sha256="sha256:" + hashlib.sha256(changed.encode()).hexdigest(),
        )
    else:
        if damage == "record_hash":
            record["boundary_description"] = "changed"
        elif damage == "missing_boundary":
            record["boundary_description"] = ""
        else:
            record["started_at_utc"] = record["prior_session_ended_at_utc"]
        overrides["session_record"] = record
        if damage != "record_hash":
            overrides["expected_session_record_hash"] = payload_hash(record)
    with pytest.raises(ValueError, match=method.ERROR):
        score(setup, **overrides)


def test_calibration_session_cannot_be_relabelled_as_transfer(setup):
    from copy import deepcopy

    record = deepcopy(setup[1])
    record["session_id"] = "cal-session"
    result = score(setup, session_record=record, expected_session_record_hash=payload_hash(record))
    assert result["state"] == "abstain"
    assert result["reason_codes"] == ["query_session_matches_calibration"]


def test_fitting_and_prior_query_source_reuse_abstains(setup):
    fitted = json.loads(setup[0])
    source = fitted["training"]["fit-block-0"]["owned_identity_delay"]["source"]
    result = score(setup, source)
    assert "query_source_or_clock_overlap" in result["reason_codes"]

    first = score(setup)
    result = score(setup, prior_queries=[first])
    assert result["state"] == "abstain"
    assert "query_id_reused" in result["reason_codes"]
    assert "prior_query_source_or_clock_overlap" in result["reason_codes"]


def test_context_mismatch_and_incomplete_query_abstain(setup):
    from tests.evaluation.test_counter_specific_projection import seal

    value = event_source("xs-context", 1)
    raw = json.loads(value["acquisition_json"])
    raw["context"]["host_arch"] = "other-architecture"
    result = score(setup, seal(value, raw))
    assert result["reason_codes"] == ["incompatible_query_context"]
    assert not result["distances"]

    value = event_source("xs-missing", 1)
    raw = json.loads(value["acquisition_json"])
    raw["events"] = [e for e in raw["events"] if e["kind"] != "n11_encoded_event_trace"]
    result = score(setup, seal(value, raw))
    assert result["reason_codes"] == ["query_response_unavailable"]
    assert result["predicted_condition"] is None


def test_result_is_detached_from_prior_query_receipts(setup):
    from copy import deepcopy

    prior = score(setup)
    before = deepcopy(prior)
    query = event_source("xs-another", 0)
    result = score(
        setup, query, query_id="another-id", query_block_id="another-block", prior_queries=[prior]
    )
    assert result["predicted_condition"] == "no_injected_fault"
    assert prior == before
