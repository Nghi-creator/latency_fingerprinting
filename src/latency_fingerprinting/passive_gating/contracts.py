"""Closed N9 vocabulary and pre-validation resource limits; no live authority."""

import json
import math
from collections.abc import Mapping
from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from ..calibration.contracts import exact_string
from ..observability.contracts import TraceModel

RELEASE = "n9-passive-gating-v1"
ASSURANCE = "software_provisional_declared_elapsed_not_live_authority"
METRIC = "client.received_fps"
MAX_TIME = 2**53 - 1
MAX_BYTES = 10 * 1024 * 1024
Time = Annotated[int, Field(strict=True, ge=0, le=MAX_TIME)]
Duration = Annotated[int, Field(strict=True, ge=0, le=2560000)]
Nonnegative = Annotated[float, Field(strict=True, allow_inf_nan=False, ge=0)]
BaselineID = exact_string(r"passive-baseline-[a-f0-9]{64}")
StratumID = exact_string(r"passive-stratum-[a-f0-9]{64}")
StreamID = exact_string(r"passive-stream-[a-f0-9]{64}")
EventID = exact_string(r"passive-event-[a-f0-9]{64}")
NoveltyID = exact_string(r"passive-window-[a-f0-9]{64}")
Mode = Literal["validation", "final_test"]
METADATA_REASONS = (
    "missing_measurements",
    "not_baseline_window",
    "not_training",
    "not_confirmed_healthy",
    "n6_excluded",
    "duplicate_evidence",
    "group_not_explicitly_healthy",
)
QUALITY_REASONS = (
    "unsupported_metric",
    "incomplete_metric",
    "rejected_samples",
    "insufficient_samples",
    "unsupported_window_duration",
)
STRATUM_REASONS = (
    "insufficient_training_groups",
    "insufficient_metric_groups",
    "insufficient_availability",
    "baseline_center_not_positive",
)
ROW_REASONS = (
    "stream_invalidated",
    "stream_reset",
    "clock_reversed",
    "stale",
    "tick_only",
    "missing_measurements",
    "not_passive_window",
    "clock_scope_changed",
    "duplicate_window",
    "out_of_order",
    "scope_changed",
    "overlapping_window",
    "pre_barrier_window",
    "gap_reset",
    "not_requested_role",
    "n6_excluded",
    "baseline_unavailable",
    "source_overlap",
    *QUALITY_REASONS,
    "entry_pending",
    "proposal_budget_exhausted",
    "cooldown_active",
    "persistent_degradation",
    "recovery_pending",
    "healthy",
    "hysteresis_band",
)


def field(value, name, default=None):
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default) if isinstance(value, BaseModel) else default


def sequence(value, maximum=256):
    if not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValueError("N9 collection exceeds bound")
    return value


def tree_budget(value):
    """Count formatted JSON bytes/depth incrementally, before dumps or model copies.

    Traversal uses only a depth-bounded call stack. Unchecked copied models are
    walked via declared fields, never dumped before their children are bounded.
    Normal validation and canonical-size checks still follow this early guard.
    """
    total = 1  # final LF
    ancestors = set()

    def charge(size):
        nonlocal total
        total += size
        if total > MAX_BYTES:
            raise ValueError("N9 JSON exceeds byte limit")

    def scalar(item):
        if isinstance(item, Enum):
            item = item.value
        if isinstance(item, datetime):
            item = item.isoformat().replace("+00:00", "Z")
        if not isinstance(item, (str, int, float, bool, type(None))):
            raise ValueError("N9 requires JSON values")
        if isinstance(item, str) and len(item) > MAX_BYTES:
            raise ValueError("N9 JSON exceeds byte limit")
        if type(item) is int and item.bit_length() > 1024:
            raise ValueError("N9 integer exceeds numeric bound")
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError("N9 requires finite numbers")
        charge(len(json.dumps(item, ensure_ascii=False, allow_nan=False).encode("utf-8")))

    def walk(item, depth):
        model = isinstance(item, BaseModel)
        mapping = isinstance(item, Mapping)
        if not model and not mapping and not isinstance(item, (list, tuple)):
            scalar(item)
            return
        if depth >= 32 or id(item) in ancestors:
            raise ValueError("N9 JSON exceeds depth or contains a cycle")
        ancestors.add(id(item))
        size = len(type(item).model_fields) if model else len(item)
        charge(2 if not size else 3 + 2 * depth)
        if model:
            children = ((name, getattr(item, name, None)) for name in type(item).model_fields)
        elif mapping:
            children = item.items()
        else:
            children = ((None, child) for child in item)
        for index, (key, child) in enumerate(children):
            if size:
                charge(2 * (depth + 1) + 1 + (index < size - 1))
            if model or mapping:
                if not isinstance(key, str):
                    raise ValueError("N9 JSON requires string keys")
                scalar(key)
                charge(2)
            walk(child, depth + 1)
        ancestors.remove(id(item))

    walk(value, 0)
    return value


def root_budget(value):
    """Reject aggregate groups/references before constructing any nested models."""
    for name in ("inputs", "strata", "windows", "events", "rows"):
        sequence(field(value, name, ()))
    groups = references = selected_references = 0
    for stratum in sequence(field(value, "strata", ())):
        rows = sequence(field(stratum, "groups", ()))
        groups += len(rows)
        if groups > 256:
            raise ValueError("N9 global group budget exceeded")
        for row in rows:
            references += len(sequence(field(row, "entry_ids", ())))
            selected_references += len(sequence(field(row, "selected_entry_ids", ())))
            if references > 256 or selected_references > 256:
                raise ValueError("N9 global reference budget exceeded")
    baseline = field(value, "baseline")
    if baseline is not None:
        root_budget(baseline)
    return value


class GateModel(TraceModel):
    collection_limits = {
        "inputs": 256,
        "strata": 256,
        "groups": 256,
        "windows": 256,
        "events": 256,
        "rows": 256,
        "entry_ids": 256,
        "selected_entry_ids": 256,
        "reason_codes": 30,
    }

    @field_validator("*", mode="after")
    @classmethod
    def normalize_zero(cls, value, info):
        if info.field_name == "observed_fps":
            return value
        return 0.0 if isinstance(value, float) and value == 0 else value


class RootModel(GateModel):
    @model_validator(mode="before")
    @classmethod
    def budget(cls, value):
        tree_budget(value)
        root_budget(value)
        return value
