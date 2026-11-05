"""Synthetic correlated repetitions; no native evidence or independent performance."""

from copy import deepcopy
from itertools import permutations

import pytest

from latency_fingerprinting.evaluation import within_session as method
from latency_fingerprinting.evaluation import within_session_protocol as protocol
from latency_fingerprinting.evaluation.fixture_conditions import CONDITIONS
from tests.evaluation.test_fixture_conditions import blocks, query


def draft():
    orders = list(permutations(CONDITIONS))
    rows = []
    for index in range(12):
        role = "training" if index < 6 else "evaluation"
        rows.append(
            dict(
                block_id=f"block-{index}",
                role=role,
                host_id="host",
                session_id="one-session",
                condition_order=list(orders[index if index < 6 else 11 - index]),
                acquisition_ids={c: f"n11-raw-ss-{index}-{j}" for j, c in enumerate(CONDITIONS)},
            )
        )
    return protocol.create_within_session_protocol(
        blocks=rows,
        excluded_case_ids=["n11-raw-old"],
        source_manifest_hash="sha256:" + "a" * 64,
        image_sha256="sha256:" + "b" * 64,
    )


def reseal(p):
    p["protocol_id"] = protocol._identity(p)
    p["review"]["subject_protocol_id"] = p["protocol_id"]
    p["content_hash"] = protocol._content(p)
    return p


def test_correlated_blocks_never_become_independent_groups():
    fitted = method.fit_within_session(blocks(), session_id="one-session")
    assert fitted["state"] == "experimental_calibration_available"
    assert fitted["repeated_training_block_count"] == 6
    assert fitted["session_components"] == 1 and fitted["independent_support_groups"] == 0
    assert fitted["independent_performance"] == "not_estimated_same_session_only"
    assert fitted["method_release"] == method.RELEASE
    assert fitted["method_spec"]["content_hash"] == method.METHOD_CONTENT_HASH
    assert not fitted["empirical_acceptance"] and fitted["diagnostic_label"] is None
    assert fitted["thresholds"]["minimum_gap"] == 0.5


def test_partial_and_failed_training_are_retained_not_replaced():
    result = method.fit_within_session(blocks(5), session_id="session")
    assert result["state"] == "unavailable" and result["thresholds"] is None
    failed = method.fit_within_session(blocks(identical=True), session_id="session")
    assert failed["state"] == "unavailable" and len(failed["folds"]) == 6
    assert all(not fold["complete_and_correct"] for fold in failed["folds"])
    with pytest.raises(ValueError):
        method.fit_within_session(blocks(7), session_id="session")


def test_truth_free_query_is_bound_to_same_session_and_training_experiment():
    data = blocks()
    kwargs = dict(session_id="one-session", query_session_id="one-session", query_block_id="fresh")
    fitted = method.fit_within_session(data, session_id="one-session")
    result = method.score_within_session(query(), data, **kwargs)
    assert result["state"] == "experimental_condition_prediction"
    assert result["experiment_id"] == fitted["experiment_id"]
    result = method.score_within_session(query(), data, **{**kwargs, "query_session_id": "other"})
    assert result["state"] == "abstain" and result["predicted_condition"] is None
    assert "different_query_session" in result["reason_codes"]
    with pytest.raises(TypeError):
        method.score_within_session(query(), data, truth=CONDITIONS[0], **kwargs)


def test_source_reuse_and_missing_query_features_still_abstain():
    data = blocks()
    reused = data["block-0"][CONDITIONS[0]]["response"]
    result = method.score_within_session(
        reused, data, session_id="s", query_session_id="s", query_block_id="new"
    )
    assert "query_source_overlap" in result["reason_codes"]
    missing = method.score_within_session(
        query(missing=True), data, session_id="s", query_session_id="s", query_block_id="new"
    )
    assert "query_missing_fixed_features" in missing["reason_codes"]


def test_pending_and_confirmed_protocol_report_exactly_one_component():
    p = draft()
    result = protocol.inspect_within_session_protocol(p)
    assert result["reason_codes"] == ["protocol_review_pending"]
    p["review"].update(
        state="confirmed", reviewer_id="operator", evidence_sha256="sha256:" + "c" * 64
    )
    p["content_hash"] = protocol._content(p)
    result = protocol.inspect_within_session_protocol(p)
    assert result["state"] == "reviewed_within_session_declarations_complete"
    assert result["session_components"] == 1 and result["independent_support_groups"] == 0
    assert result["maximum_acquisitions"] == 36 and not result["acquisition_authority"]
    assert p["review"]["subject_protocol_id"] == p["protocol_id"]


@pytest.mark.parametrize(
    "change",
    ["sessions", "roles", "order", "reuse", "excluded", "method", "scope", "count", "review"],
)
def test_protocol_rejects_semantic_mutations_even_after_rehashing(change):
    p = deepcopy(draft())
    if change == "sessions":
        p["blocks"][1]["session_id"] = "another-session"
    if change == "roles":
        p["blocks"][0]["role"] = "evaluation"
    if change == "order":
        p["blocks"][6]["condition_order"] = p["blocks"][0]["condition_order"]
    if change == "reuse":
        p["blocks"][1]["acquisition_ids"] = p["blocks"][0]["acquisition_ids"]
    if change == "excluded":
        p["excluded_case_ids"] = sorted(p["blocks"][0]["acquisition_ids"].values())
    if change == "method":
        p["method_content_hash"] = "sha256:" + "d" * 64
    if change == "scope":
        p["scope"] = "independent_validation"
    if change == "count":
        p["session_components"] = 12
    if change == "review":
        p["review"]["reviewer_id"] = "fabricated-pending-review"
    with pytest.raises(ValueError):
        protocol.inspect_within_session_protocol(reseal(p))
