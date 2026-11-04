"""Artificial protocol/review declarations, not actual sessions or authorization."""

from copy import deepcopy
from itertools import permutations

import pytest

from latency_fingerprinting.analytical.policy_release import payload_hash
from latency_fingerprinting.evaluation import fixture_protocol as protocol
from latency_fingerprinting.evaluation.fixture_conditions import CONDITIONS

HASH = "sha256:" + "a" * 64


def draft():
    orders = list(permutations(CONDITIONS))
    blocks = []
    for role, prefix in (("training", "cal"), ("evaluation", "eval")):
        for i in range(6):
            alias = f"{prefix}-{i + 1:02d}"
            blocks.append(
                dict(
                    block_id=alias,
                    role=role,
                    host_id="same-host",
                    session_id="planned-session-" + alias,
                    condition_order=list(orders[i if role == "training" else 5 - i]),
                    acquisition_ids={
                        c: f"n11-raw-fixture-{alias}-{j}" for j, c in enumerate(CONDITIONS)
                    },
                )
            )
    return protocol.create_fixture_protocol_draft(
        blocks=blocks,
        correlation_edges=[],
        excluded_case_ids=["n11-raw-inspected-case"],
        source_manifest_hash=HASH,
        image_sha256=HASH,
    )


def reseal(plan, *, keep_subject=False):
    plan["protocol_id"] = protocol._identity(plan)
    if not keep_subject:
        plan["review"]["subject_protocol_id"] = plan["protocol_id"]
    plan["content_hash"] = protocol._content(plan)
    return plan


def reviewed():
    plan = draft()
    plan["review"].update(
        state="confirmed", reviewer_id="artificial-reviewer", evidence_sha256=HASH
    )
    return reseal(plan)


def test_pending_draft_counts_are_concrete_without_inventing_authority():
    plan = draft()
    report = protocol.inspect_fixture_protocol(plan)
    assert report["state"] == "unavailable"
    assert report["reason_codes"] == ["protocol_review_pending"]
    assert report["declared_component_counts"] == dict(training=6, evaluation=6)
    assert report["acquisition_counts"] == dict(training=18, evaluation=18)
    assert all(
        len(orders) == 6 and all(o["count"] == 1 for o in orders)
        for orders in report["arm_order_counts"].values()
    )
    assert report["acquisition_authority"] is report["empirical_acceptance"] is False
    with pytest.raises(ValueError, match=protocol.ERROR):
        protocol.fixture_protocol_training_blocks(plan)


def test_reviewed_metadata_selects_only_training_ids_without_any_feature_values():
    plan = reviewed()
    report = protocol.inspect_fixture_protocol(plan)
    assert report["state"] == "reviewed_protocol_declarations_complete"
    assert protocol.fixture_protocol_training_blocks(plan) == tuple(
        f"cal-{i:02d}" for i in range(1, 7)
    )
    assert report["diagnostic_label"] is None and report["accepted_diagnostic_groups"] == 0
    assert "not_authenticated" in report["assurance"] and report["acquisition_authority"] is False


@pytest.mark.parametrize("cross_role", [False, True])
def test_aliases_cannot_split_one_declared_host_session(cross_role):
    plan = reviewed()
    plan["blocks"][6 if cross_role else 1]["session_id"] = plan["blocks"][0]["session_id"]
    report = protocol.inspect_fixture_protocol(reseal(plan))
    assert report["state"] == "unavailable"
    assert "correlated_blocks_require_preallocation_merge" in report["reason_codes"]
    assert ("cross_role_correlation" in report["reason_codes"]) == cross_role


def test_explicit_correlations_are_transitive_and_do_not_inflate_support():
    plan = reviewed()
    plan["correlation_edges"] = [["cal-01", "cal-02"], ["cal-02", "eval-01"]]
    report = protocol.inspect_fixture_protocol(reseal(plan))
    assert [g for g in report["declared_components"] if len(g["block_ids"]) > 1] == [
        dict(block_ids=["cal-01", "cal-02", "eval-01"], roles=["evaluation", "training"])
    ]
    assert report["declared_component_counts"] == dict(training=4, evaluation=5)
    assert "cross_role_correlation" in report["reason_codes"]


def test_old_review_cannot_follow_a_changed_assignment_even_after_content_rehash():
    plan = reviewed()
    old_id = plan["protocol_id"]
    plan["blocks"][0]["condition_order"].reverse()
    reseal(plan, keep_subject=True)
    assert plan["protocol_id"] != old_id
    with pytest.raises(ValueError, match=protocol.ERROR):
        protocol.inspect_fixture_protocol(plan)


def test_review_changes_only_revision_hash_not_the_review_subject():
    plan = draft()
    old = deepcopy(plan)
    plan["review"].update(
        state="confirmed", reviewer_id="artificial-reviewer", evidence_sha256=HASH
    )
    plan["content_hash"] = protocol._content(plan)
    assert plan["protocol_id"] == old["protocol_id"] and plan["content_hash"] != old["content_hash"]
    assert (
        protocol.inspect_fixture_protocol(plan)["state"]
        == "reviewed_protocol_declarations_complete"
    )


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p.update(content_hash=HASH),
        lambda p: p.update(method_content_hash=HASH),
        lambda p: p.update(source_manifest_hash="invalid"),
        lambda p: p.update(evaluation_mode="claim_accuracy_pass"),
        lambda p: p.update(extra="field"),
        lambda p: p["blocks"][0]["condition_order"].__setitem__(0, "healthy"),
        lambda p: p["blocks"][0]["acquisition_ids"].update(no_injected_fault="arbitrary"),
        lambda p: p["blocks"][0]["acquisition_ids"].update(
            no_injected_fault="n11-raw-inspected-case"
        ),
        lambda p: p["blocks"][1]["acquisition_ids"].update(
            no_injected_fault=p["blocks"][0]["acquisition_ids"]["no_injected_fault"]
        ),
        lambda p: p["blocks"][0].update(role="training_and_test"),
        lambda p: p["blocks"][0].update(responses=["heldout-feature-payload"]),
        lambda p: p["blocks"].reverse(),
        lambda p: p.update(correlation_edges=[["cal-01", "missing"]]),
        lambda p: p.update(correlation_edges=[["cal-01", "cal-02"], ["cal-01", "cal-02"]]),
        lambda p: p["review"].update(state="confirmed", reviewer_id=None, evidence_sha256=None),
    ],
)
def test_changed_foreign_ambiguous_or_reused_metadata_fails(change):
    plan = draft()
    change(plan)
    if "content_hash" not in plan or plan["content_hash"] != HASH:
        # Update identifiers so these tests exercise structural/semantic guards too.
        reseal(plan)
    with pytest.raises(ValueError, match=protocol.ERROR):
        protocol.inspect_fixture_protocol(plan)


def test_rejected_review_remains_unavailable():
    plan = reviewed()
    plan["review"]["state"] = "rejected"
    reseal(plan)
    assert protocol.inspect_fixture_protocol(plan)["reason_codes"] == ["protocol_review_rejected"]


def test_fewer_than_six_training_components_remains_unavailable():
    plan = reviewed()
    plan["blocks"].pop(0)
    reseal(plan)
    assert protocol.inspect_fixture_protocol(plan)["reason_codes"] == [
        "insufficient_or_excessive_training_components"
    ]


def test_no_evaluation_components_cannot_be_called_a_complete_study():
    plan = reviewed()
    plan["blocks"] = plan["blocks"][:6]
    reseal(plan)
    assert protocol.inspect_fixture_protocol(plan)["reason_codes"] == [
        "insufficient_or_excessive_evaluation_components"
    ]


def test_content_hash_uses_the_complete_review_revision():
    plan = reviewed()
    body = {k: v for k, v in plan.items() if k not in ("protocol_id", "content_hash")}
    assert plan["content_hash"] == payload_hash(body)
