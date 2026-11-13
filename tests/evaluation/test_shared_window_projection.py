"""Guarded source rate projection with exact marginal parity."""

import hashlib
import json

import pytest

from latency_fingerprinting.analytical.policy_release import payload_hash
from latency_fingerprinting.evaluation.counter_specific_projection import (
    project_counter_specific_resource,
)
from latency_fingerprinting.evaluation.shared_window_projection import (
    project_shared_window_source,
)
from latency_fingerprinting.evaluation.shared_window_separation import (
    CONDITIONS,
    compare_shared_window_centers,
)
from tests.evaluation.test_counter_specific_projection import rows, seal, with_points


def test_adapter_feeds_certificate_and_reproduces_all_nine_bounds():
    value = with_points()
    result = project_shared_window_source(value)
    prior = project_counter_specific_resource(value)
    assert result["marginal_bounds"] == prior["features"]
    assert result["counter_specific_response_id"] == prior["response_id"]
    assert result["source_bytes_sha256"] == (
        "sha256:" + hashlib.sha256(value["acquisition_json"].encode()).hexdigest()
    )
    assert result["resource_artifact_hash"] == payload_hash(value["resource_artifact"])
    centers = dict.fromkeys(CONDITIONS, prior["features"])
    assert compare_shared_window_centers(result["phase_rates"], centers)["state"] == "abstain"


@pytest.mark.parametrize("damage", ["raw_bytes", "cpu_artifact", "recovery_getter"])
def test_binding_and_recovery_checks_are_required(damage):
    value = with_points()
    if damage == "raw_bytes":
        value["acquisition_json"] += " "
    elif damage == "cpu_artifact":
        value["resource_artifact"]["samples"]["healthy"][0]["counters"]["usage_usec"] += 1
    else:
        raw = json.loads(value["acquisition_json"])
        recovery = next(row for row in rows(raw) if row.get("phase") == "recovery")
        del recovery["encoded_counter_read"]
        seal(value, raw)
    with pytest.raises(ValueError, match="invalid_shared_window_source"):
        project_shared_window_source(value)


def test_unavailable_measurements_do_not_emit_partial_rates():
    value = with_points()
    raw = json.loads(value["acquisition_json"])
    row = next(row for row in rows(raw) if row.get("phase") == "degraded")
    end = row["native_read"]["read_start_ns"] + 101_000_000
    row["native_read"]["read_end_ns"] = end
    row["encoded_counter_read"]["read_end_ns"] = end
    result = project_shared_window_source(seal(value, raw))
    assert result["state"] == "unavailable"
    assert result["unavailable_components"] == ["encoded"]
    assert result["phase_rates"] == result["marginal_bounds"] == {}
