"""Prospective metadata tests only; no counts, session or collection authentication."""

from copy import deepcopy
from itertools import permutations

import pytest

from latency_fingerprinting.evaluation import combined_study_protocol as protocol
from latency_fingerprinting.evaluation.fixture_conditions import CONDITIONS
from latency_fingerprinting.evaluation.within_session_protocol import (
    inspect_within_session_protocol,
)


def draft():
    orders = list(permutations(CONDITIONS))
    blocks = []
    for i in range(12):
        blocks.append(
            dict(
                block_id=f"block-{i}",
                role="training" if i < 6 else "evaluation",
                host_id="one-host",
                session_id="one-session",
                condition_order=list(orders[i if i < 6 else 11 - i]),
                acquisition_ids={c: f"n11-raw-cs-{i}-{j}" for j, c in enumerate(CONDITIONS)},
            )
        )
    return protocol.create_combined_study_protocol(
        blocks=blocks,
        excluded_case_ids=["n11-raw-old"],
        source_manifest_hash="sha256:" + "a" * 64,
        image_sha256="sha256:" + "b" * 64,
        tool_hashes={
            role: "sha256:" + "c" * 64 for role in ("processor", "verifier", "runner", "supervisor")
        },
    )


def reseal(value):
    value["protocol_id"] = protocol._identity(value)
    value["review"]["subject_protocol_id"] = value["protocol_id"]
    value["content_hash"] = protocol._content(value)
    return value


def confirmed():
    value = draft()
    value["review"].update(
        state="confirmed", reviewer_id="synthetic", evidence_sha256="sha256:" + "d" * 64
    )
    return reseal(value)


def test_drafts_and_rejections_remain_unavailable_without_acquisition_authority():
    value = draft()
    result = protocol.inspect_combined_study_protocol(value)
    assert result["reason_codes"] == ["protocol_review_pending"]
    assert result["maximum_acquisitions"] == 36 and result["independent_support_groups"] == 0
    assert not result["acquisition_authority"] and not result["empirical_acceptance"]
    value["review"].update(
        state="rejected", reviewer_id="synthetic", evidence_sha256="sha256:" + "e" * 64
    )
    assert protocol.inspect_combined_study_protocol(reseal(value))["reason_codes"] == [
        "protocol_review_rejected"
    ]


def test_confirmed_exact_subject_and_tools_still_cannot_authenticate_authorization():
    value = confirmed()
    result = protocol.inspect_combined_study_protocol(value)
    assert result["state"] == "reviewed_combined_study_declarations_complete"
    assert result["session_components"] == 1 and result["independent_support_groups"] == 0
    assert not result["acquisition_authority"]
    with pytest.raises(ValueError):
        inspect_within_session_protocol(value)
    old = value["protocol_id"]
    value["tool_hashes"]["processor"] = "sha256:" + "f" * 64
    assert protocol._identity(value) != old
    with pytest.raises(ValueError):
        protocol.inspect_combined_study_protocol(value)


@pytest.mark.parametrize(
    "kind",
    [
        "old_method",
        "source_protocol",
        "query_first",
        "session",
        "orders",
        "excluded",
        "duplicate",
        "wrong_prefix",
        "missing_tool",
        "bad_tool",
        "review_subject",
        "block_count",
    ],
)
def test_incompatible_or_incomplete_declarations_rejected(kind):
    value = confirmed()
    if kind == "old_method":
        value["method_content_hash"] = "sha256:" + "0" * 64
    elif kind == "source_protocol":
        value["condition_protocol"] = "n11-contained-condition-witness-v1"
    elif kind == "query_first":
        value["blocks"][0]["role"] = "evaluation"
    elif kind == "session":
        value["blocks"][-1]["session_id"] = "different"
    elif kind == "orders":
        value["blocks"][1]["condition_order"] = value["blocks"][0]["condition_order"]
    elif kind == "excluded":
        value["excluded_case_ids"].append(value["blocks"][0]["acquisition_ids"][CONDITIONS[0]])
        value["excluded_case_ids"].sort()
    elif kind == "duplicate":
        value["blocks"][1]["acquisition_ids"][CONDITIONS[0]] = value["blocks"][0][
            "acquisition_ids"
        ][CONDITIONS[0]]
    elif kind == "wrong_prefix":
        value["blocks"][0]["acquisition_ids"][CONDITIONS[0]] = "n11-raw-ss-old"
    elif kind == "missing_tool":
        del value["tool_hashes"]["supervisor"]
    elif kind == "bad_tool":
        value["tool_hashes"]["runner"] = "bad"
    elif kind == "block_count":
        value["blocks"].pop()
    else:
        value["review"]["subject_protocol_id"] = "other"
    if kind != "review_subject":
        reseal(value)
    else:
        value["content_hash"] = protocol._content(value)
    with pytest.raises(ValueError):
        protocol.inspect_combined_study_protocol(value)


def test_proposal_detaches_inputs_and_supports_complete_historical_exclusion_budget():
    value = draft()
    before = deepcopy(value)
    value["excluded_case_ids"] = [f"old-{i}" for i in range(500)]
    value["excluded_case_ids"].sort()
    reseal(value)
    assert protocol.inspect_combined_study_protocol(value)["state"] == "unavailable"
    assert before["excluded_case_ids"] == ["n11-raw-old"]
