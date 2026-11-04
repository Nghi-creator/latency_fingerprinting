"""Metadata-only fixture-study planning; declarations never authorize acquisition."""

import re
from collections import Counter
from collections.abc import Mapping
from copy import deepcopy

from ..analytical.policy_release import payload_hash
from .fixture_conditions import CONDITIONS, fixture_condition_method_spec
from .median_response import _alias

RELEASE = "n11-fixture-protocol-experiment-v1"
ERROR = "invalid_fixture_protocol"
BOUNDARY = "one_complete_documented_host_research_session"
EVALUATION = "descriptive_counts_no_empirical_acceptance"
EXECUTION = "stop_failed_suffix_no_retries_evaluate_only_if_calibration_available"
KEYS = {
    "schema_version",
    "protocol_id",
    "content_hash",
    "method_content_hash",
    "condition_protocol",
    "source_manifest_hash",
    "image_sha256",
    "block_boundary_rule",
    "blocks",
    "correlation_edges",
    "excluded_case_ids",
    "review",
    "evaluation_mode",
    "execution_rule",
}


def _require(condition):
    if not condition:
        raise ValueError(ERROR)


def _sha(value):
    from .fixture_conditions import _hash

    _hash(value)


def _identity(plan):
    return (
        "fixture-protocol-"
        + payload_hash(
            {k: v for k, v in plan.items() if k not in {"protocol_id", "content_hash", "review"}}
        )[7:]
    )


def _content(plan):
    return payload_hash({k: v for k, v in plan.items() if k not in {"protocol_id", "content_hash"}})


def create_fixture_protocol_draft(
    *, blocks, correlation_edges, excluded_case_ids, source_manifest_hash, image_sha256
):
    """Create only a pending draft; never invent a confirmed review or real sessions."""
    try:
        plan = deepcopy(
            dict(
                schema_version=RELEASE,
                method_content_hash=fixture_condition_method_spec()["content_hash"],
                condition_protocol="n11-contained-condition-witness-v1",
                source_manifest_hash=source_manifest_hash,
                image_sha256=image_sha256,
                block_boundary_rule=BOUNDARY,
                blocks=blocks,
                correlation_edges=correlation_edges,
                excluded_case_ids=excluded_case_ids,
                evaluation_mode=EVALUATION,
                execution_rule=EXECUTION,
            )
        )
        plan["protocol_id"] = _identity(plan)
        plan["review"] = dict(
            subject_protocol_id=plan["protocol_id"],
            state="pending",
            reviewer_id=None,
            evidence_sha256=None,
        )
        plan["content_hash"] = _content(plan)
        inspect_fixture_protocol(plan)
        return plan
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError(ERROR) from None


def inspect_fixture_protocol(plan):
    """Reconstruct declared components and roles without opening feature artifacts.

    A complete reviewed declaration still does not authenticate review, realized
    sessions, physical independence or authority to execute a collection.
    """
    try:
        _require(isinstance(plan, Mapping) and set(plan) == KEYS)
        _require(
            plan["schema_version"] == RELEASE
            and plan["protocol_id"] == _identity(plan)
            and plan["content_hash"] == _content(plan)
            and plan["method_content_hash"] == fixture_condition_method_spec()["content_hash"]
            and plan["condition_protocol"] == "n11-contained-condition-witness-v1"
            and plan["block_boundary_rule"] == BOUNDARY
            and plan["evaluation_mode"] == EVALUATION
            and plan["execution_rule"] == EXECUTION
        )
        _sha(plan["source_manifest_hash"])
        _sha(plan["image_sha256"])
        blocks, edges, excluded = (
            plan[k] for k in ("blocks", "correlation_edges", "excluded_case_ids")
        )
        _require(
            type(blocks) is list
            and 1 <= len(blocks) <= 64
            and type(edges) is list
            and len(edges) <= 128
            and type(excluded) is list
            and len(excluded) <= 256
        )
        for case in excluded:
            _alias(case)
        _require(excluded == sorted(set(excluded)))
        nodes, cases = {}, set()
        for block in blocks:
            _require(
                isinstance(block, Mapping)
                and set(block)
                == {
                    "block_id",
                    "role",
                    "host_id",
                    "session_id",
                    "condition_order",
                    "acquisition_ids",
                }
            )
            for key in ("block_id", "host_id", "session_id"):
                _alias(block[key])
            _require(block["block_id"] not in nodes and block["role"] in ("training", "evaluation"))
            order, ids = block["condition_order"], block["acquisition_ids"]
            _require(
                type(order) is list
                and len(order) == 3
                and set(order) == set(CONDITIONS)
                and isinstance(ids, Mapping)
                and set(ids) == set(CONDITIONS)
            )
            for case in ids.values():
                _alias(case)
                _require(re.fullmatch(r"n11-raw-[a-z0-9-]{1,40}", case) is not None)
                _require(case not in cases and case not in excluded)
                cases.add(case)
            nodes[block["block_id"]] = block
        _require(list(nodes) == sorted(nodes))
        parents = {b: b for b in nodes}

        def root(b):
            while parents[b] != b:
                parents[b] = parents[parents[b]]
                b = parents[b]
            return b

        def join(a, b):
            a, b = root(a), root(b)
            parents[max(a, b)] = min(a, b)

        sessions = {}
        for b, row in nodes.items():
            key = row["host_id"], row["session_id"]
            join(b, sessions.setdefault(key, b))
        previous = None
        for edge in edges:
            _require(
                type(edge) is list
                and len(edge) == 2
                and edge[0] in nodes
                and edge[1] in nodes
                and edge[0] < edge[1]
            )
            _require(previous is None or previous < edge)
            previous = edge
            join(*edge)
        components = {}
        for b in nodes:
            components.setdefault(root(b), []).append(b)
        groups = [
            dict(block_ids=ids, roles=sorted({nodes[b]["role"] for b in ids}))
            for ids in components.values()
        ]
        review = plan["review"]
        _require(
            isinstance(review, Mapping)
            and set(review) == {"subject_protocol_id", "state", "reviewer_id", "evidence_sha256"}
            and review["subject_protocol_id"] == plan["protocol_id"]
        )
        _require(review["state"] in ("pending", "confirmed", "rejected"))
        if review["state"] == "pending":
            _require(review["reviewer_id"] is None and review["evidence_sha256"] is None)
        else:
            _alias(review["reviewer_id"])
            _sha(review["evidence_sha256"])
        counts = {r: sum(g["roles"] == [r] for g in groups) for r in ("training", "evaluation")}
        reasons = []
        if review["state"] != "confirmed":
            reasons.append("protocol_review_" + review["state"])
        if any(len(g["roles"]) > 1 for g in groups):
            reasons.append("cross_role_correlation")
        if any(len(g["block_ids"]) > 1 for g in groups):
            reasons.append("correlated_blocks_require_preallocation_merge")
        if not 6 <= counts["training"] <= 32:
            reasons.append("insufficient_or_excessive_training_components")
        if not 1 <= counts["evaluation"] <= 32:
            reasons.append("insufficient_or_excessive_evaluation_components")
        orders = {
            r: Counter(tuple(b["condition_order"]) for b in blocks if b["role"] == r)
            for r in counts
        }
        payload = dict(
            method_release=RELEASE,
            protocol_id=plan["protocol_id"],
            content_hash=plan["content_hash"],
            state="unavailable" if reasons else "reviewed_protocol_declarations_complete",
            reason_codes=reasons,
            declared_components=groups,
            declared_component_counts=counts,
            training_block_ids=[b for b, row in nodes.items() if row["role"] == "training"],
            evaluation_block_ids=[b for b, row in nodes.items() if row["role"] == "evaluation"],
            acquisition_counts={r: 3 * sum(b["role"] == r for b in blocks) for r in counts},
            arm_order_counts={
                r: [dict(order=list(o), count=n) for o, n in sorted(v.items())]
                for r, v in orders.items()
            },
            assurance="external_protocol_declarations_not_authenticated_realized_sessions_unverified",
            evaluation_mode=EVALUATION,
            acquisition_authority=False,
            empirical_acceptance=False,
            diagnostic_label=None,
            accepted_diagnostic_groups=0,
        )
        return {
            **payload,
            "inspection_id": "fixture-protocol-inspection-" + payload_hash(payload)[7:],
        }
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError(ERROR) from None


def fixture_protocol_training_blocks(plan):
    """Select IDs using metadata only; never accept pending or correlated plans."""
    report = inspect_fixture_protocol(plan)
    if report["state"] == "unavailable":
        raise ValueError(ERROR)
    return tuple(report["training_block_ids"])
