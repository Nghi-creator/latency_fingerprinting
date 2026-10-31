"""Frozen P0 versions and P0-only decision/probe vocabulary."""

from enum import StrEnum

CONTRACT_VERSION = "1.0.0"
OBSERVATION_SCHEMA_VERSION = "observation-v1"
FINGERPRINT_SCHEMA_VERSION = "fingerprint-v1"
MATCH_RESULT_SCHEMA_VERSION = "match-result-v1"


class ProbeApplicationMethod(StrEnum):
    SIMULATED_PAIR = "simulated_pair"
    PAIRED_RUN = "paired_run"
    LIVE_BOUNDED_PROBE = "live_bounded_probe"


class ProbeExecutionStatus(StrEnum):
    NOT_EXECUTED = "not_executed"
    EXECUTED = "executed"
    FAILED = "failed"


class ValidationStatus(StrEnum):
    UNVALIDATED = "unvalidated"
    SOFTWARE_TEST_REFERENCE = "software_test_reference"
    VALIDATED = "validated"
    REJECTED = "rejected"


class MatchDecision(StrEnum):
    MATCHED = "matched"
    UNKNOWN = "unknown"


class UnknownReason(StrEnum):
    INCOMPATIBLE_CONTEXT = "incompatible_context"
    UNSUPPORTED_PROBE = "unsupported_probe"
    INSUFFICIENT_FEATURE_COVERAGE = "insufficient_feature_coverage"
    DEGENERATE_VECTOR = "degenerate_vector"
    WEAK_MATCH = "weak_match"
    AMBIGUOUS_MARGIN = "ambiguous_margin"
    INVALID_OBSERVATION = "invalid_observation"
    CONFLICTING_EVIDENCE = "conflicting_evidence"


class OutcomeResult(StrEnum):
    IMPROVED = "improved"
    UNCHANGED = "unchanged"
    WORSENED = "worsened"
    INCONCLUSIVE = "inconclusive"
