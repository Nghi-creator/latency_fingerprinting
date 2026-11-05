"""Prospective metadata for one-session recognition; original separate-session API is unchanged."""

from copy import deepcopy
from itertools import permutations

from ..analytical.policy_release import payload_hash
from .fixture_conditions import CONDITIONS, _hash
from .median_response import _alias
from .within_session import METHOD_CONTENT_HASH

RELEASE = "n11-within-session-protocol-v1"
ERROR = "invalid_within_session_protocol"
KEYS = {
    "schema_version",
    "method_content_hash",
    "source_manifest_hash",
    "image_sha256",
    "condition_protocol",
    "blocks",
    "excluded_case_ids",
    "session_components",
    "scope",
    "execution_rule",
    "protocol_id",
    "content_hash",
    "review",
}
SCOPE = "one_correlated_host_session_later_block_condition_recognition_only"
EXECUTION = "stop_entire_suffix_no_retries_no_evaluation_if_calibration_unavailable"


def _identity(plan):
    return (
        "within-session-protocol-"
        + payload_hash(
            {k: v for k, v in plan.items() if k not in {"protocol_id", "content_hash", "review"}}
        )[7:]
    )


def _content(plan):
    return payload_hash({k: v for k, v in plan.items() if k not in {"protocol_id", "content_hash"}})


def create_within_session_protocol(
    *, blocks, excluded_case_ids, source_manifest_hash, image_sha256
):
    plan = deepcopy(
        dict(
            schema_version=RELEASE,
            method_content_hash=METHOD_CONTENT_HASH,
            source_manifest_hash=source_manifest_hash,
            image_sha256=image_sha256,
            condition_protocol="n11-contained-condition-witness-v1",
            blocks=blocks,
            excluded_case_ids=excluded_case_ids,
            session_components=1,
            scope=SCOPE,
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
    inspect_within_session_protocol(plan)
    return plan


def inspect_within_session_protocol(plan):
    """Validate declarations only. Never authorize collection or authenticate a session."""
    try:

        def require(ok):
            if not ok:
                raise ValueError(ERROR)

        require(type(plan) is dict and set(plan) == KEYS)
        require(
            plan["schema_version"] == RELEASE and plan["method_content_hash"] == METHOD_CONTENT_HASH
        )
        require(plan["protocol_id"] == _identity(plan) and plan["content_hash"] == _content(plan))
        require(plan["condition_protocol"] == "n11-contained-condition-witness-v1")
        require(type(plan["session_components"]) is int and plan["session_components"] == 1)
        require(plan["scope"] == SCOPE and plan["execution_rule"] == EXECUTION)
        _hash(plan["source_manifest_hash"])
        _hash(plan["image_sha256"])
        excluded = plan["excluded_case_ids"]
        require(
            type(excluded) is list and len(excluded) <= 256 and excluded == sorted(set(excluded))
        )
        for identifier in excluded:
            _alias(identifier)
        blocks = plan["blocks"]
        require(type(blocks) is list and len(blocks) == 12)
        ids, aliases, sessions, orders = set(), set(), set(), []
        for index, block in enumerate(blocks):
            require(
                type(block) is dict
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
            require(block["block_id"] not in aliases)
            aliases.add(block["block_id"])
            sessions.add((block["host_id"], block["session_id"]))
            require(block["role"] == ("training" if index < 6 else "evaluation"))
            order = block["condition_order"]
            require(type(order) is list and len(order) == 3 and set(order) == set(CONDITIONS))
            orders.append(tuple(order))
            require(
                type(block["acquisition_ids"]) is dict
                and set(block["acquisition_ids"]) == set(CONDITIONS)
            )
            for identifier in block["acquisition_ids"].values():
                _alias(identifier)
                require(identifier.startswith("n11-raw-ss-") and len(identifier) <= 48)
                require(identifier not in ids and identifier not in excluded)
                ids.add(identifier)
        require(len(sessions) == 1)
        require(set(orders[:6]) == set(permutations(CONDITIONS)))
        require(orders[6:] == orders[:6][::-1])
        review = plan["review"]
        require(
            type(review) is dict
            and set(review)
            == {
                "subject_protocol_id",
                "state",
                "reviewer_id",
                "evidence_sha256",
            }
        )
        require(review["subject_protocol_id"] == plan["protocol_id"])
        require(review["state"] in {"pending", "confirmed", "rejected"})
        if review["state"] == "pending":
            require(review["reviewer_id"] is None and review["evidence_sha256"] is None)
        else:
            _alias(review["reviewer_id"])
            _hash(review["evidence_sha256"])
        available = review["state"] == "confirmed"
        return dict(
            method_release=RELEASE,
            protocol_id=plan["protocol_id"],
            state="reviewed_within_session_declarations_complete" if available else "unavailable",
            reason_codes=[] if available else ["protocol_review_" + review["state"]],
            repeated_training_blocks=6,
            repeated_evaluation_blocks=6,
            maximum_acquisitions=36,
            session_components=1,
            independent_support_groups=0,
            independent_performance="not_estimated_same_session_only",
            acquisition_authority=False,
            empirical_acceptance=False,
            diagnostic_label=None,
            accepted_diagnostic_groups=0,
        )
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError(ERROR) from None
