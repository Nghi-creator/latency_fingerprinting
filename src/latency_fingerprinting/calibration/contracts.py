"""Strict bounded vocabulary for additive calibration evidence records."""

import re
from typing import Annotated, Literal

from pydantic import AfterValidator, Field

from ..analytical.policy_release import canonical_payload_bytes, payload_hash
from ..observability.contracts import TraceModel, ordered

RELEASE = "n6-calibration-evidence-v1"
DATASET_SCHEMA_VERSION = "calibration-dataset-v1"
REPORT_SCHEMA_VERSION = "calibration-report-v1"
JSON_BYTES = 10 * 1024 * 1024
ARCHIVE_BYTES = 64 * 1024 * 1024
AGGREGATE_BYTES = 256 * 1024 * 1024
ROLES = ("engineering", "training", "validation", "final_test")
REASONS = (
    "missing_measurements",
    "engineering_only",
    "retrospective_split",
    "split_unverified",
    "independence_unverified",
    "synthetic_only",
    "confounded_response",
    "insufficient_response_features",
    "baseline_invalid",
    "label_unverified",
    "effect_unverified",
    "binding_unverified",
    "duplicate_evidence",
)
Role = Literal[*ROLES]
Reason = Literal[*REASONS]
Release = Literal[RELEASE]
Label = Literal["healthy", "host_contention", "render_capture_slowdown"]
InputKind = Literal["response", "healthy_window", "missing"]
SplitMode = Literal["prospective", "retrospective"]
ReviewState = Literal["confirmed", "rejected", "uncertain", "missing"]
Count = Annotated[int, Field(strict=True, ge=0, le=256)]


def exact_string(pattern):
    def validate(value):
        if re.fullmatch(pattern, value) is None:
            raise ValueError("invalid calibration identifier")
        return value

    return Annotated[
        str, Field(strict=True, pattern="^(?:" + pattern + ")$"), AfterValidator(validate)
    ]


Alias = exact_string(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")
Hash = exact_string(r"sha256:[a-f0-9]{64}")
DatasetID = exact_string(r"dataset-[a-f0-9]{64}")
SplitID = exact_string(r"split-[a-f0-9]{64}")
GroupID = exact_string(r"group-[a-f0-9]{64}")
PartitionID = exact_string(r"partition-[a-f0-9]{64}")
ReportID = exact_string(r"calibration-report-[a-f0-9]{64}")


def original_identifier(value):
    if not value.strip() or len(value.encode("utf-8")) > 256:
        raise ValueError("original identifier must be nonblank and at most 256 UTF-8 bytes")
    return value


OriginalID = Annotated[
    str, Field(strict=True, min_length=1, max_length=256), AfterValidator(original_identifier)
]


class CalibrationModel(TraceModel):
    collection_limits = {
        "artifacts": 256,
        "sources": 256,
        "derivations": 512,
        "reviews": 256,
        "entries": 256,
        "assignments": 256,
        "subject_ids": 256,
        "source_bindings": 2,
        "artifact_receipts": 256,
        "groups": 256,
        "source_ids": 256,
        "partitions": 256,
        "reason_codes": len(REASONS),
    }


def unique_order(items, key):
    ordered(items, key)


def check_identity(model, field, prefix, excluded):
    payload = model.model_dump(mode="json", exclude=set(excluded))
    digest = payload_hash(payload)
    if getattr(model, field) != prefix + digest[7:]:
        raise ValueError("calibration content identity mismatch")
    return digest


def check_json_size(model):
    if len(canonical_payload_bytes(model.model_dump(mode="json"))) > JSON_BYTES:
        raise ValueError("calibration canonical JSON exceeds byte limit")
