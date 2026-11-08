"""Invented counter timing for contract checks; never real calibration or performance data."""

import hashlib
import json
from copy import deepcopy

import pytest

from latency_fingerprinting.evaluation.combined_resource_projection import (
    combined_resource_projection_spec,
    project_combined_resource,
)
from latency_fingerprinting.evaluation.counter_specific_projection import (
    counter_specific_projection_spec,
    project_counter_specific_resource,
)
from tests.evaluation.test_combined_interval_candidate import source


def rows(raw):
    for event in raw["events"]:
        if event["kind"] == "n11_pacing_reference":
            yield from event["samples"]
        elif event["kind"] == "n11_pair_native":
            yield event


def seal(value, raw):
    value["acquisition_json"] = json.dumps(raw, indent=2) + "\n"
    value["resource_artifact"]["source_payload_sha256"] = (
        "sha256:" + hashlib.sha256(value["acquisition_json"].encode()).hexdigest()
    )
    return value


def with_points():
    value = source("point-fixture")
    raw = json.loads(value["acquisition_json"])
    for row in rows(raw):
        native = row["native_read"]
        row["encoded_counter_read"] = dict(
            method="native-encoded-counter-read-brackets-v1",
            clock_id=native["clock_id"],
            basis=native["basis"],
            read_start_ns=native["read_start_ns"],
            read_end_ns=native["read_end_ns"],
            value=row["encoded_buffers"],
            scope="reported_encoded_counter_only_not_other_snapshot_fields",
            underlying_counter_freshness="not_authenticated_by_read_brackets",
            live_authority=False,
        )
    return seal(value, raw)


def middle_degraded(raw):
    return [
        e for e in raw["events"] if e["kind"] == "n11_pair_native" and e["phase"] == "degraded"
    ][3]


def test_legacy_projection_is_byte_identified_and_spec_unchanged():
    assert project_combined_resource(source("legacy-freeze"))["response_id"] == (
        "combined-resource-c728d3b77d69af53ad293cb540d87bb1ae24adc7338abcad46eadf9a869b36b1"
    )
    assert combined_resource_projection_spec()["content_hash"] == (
        "sha256:ca797f8ed9220c3bcc6b7ba47dc216e3b40ddaaca8c5fe9fe76ec3ab6764bc32"
    )


def test_same_recorded_bounds_have_same_values_but_separate_method_identity():
    value = with_points()
    legacy, point = project_combined_resource(value), project_counter_specific_resource(value)
    assert point["features"] == legacy["features"]
    assert len(point["features"]) == 9
    assert point["response_id"] != legacy["response_id"]
    assert point["spec"]["content_hash"] != legacy["spec"]["content_hash"]
    assert point["spec"] == counter_specific_projection_spec()
    assert point["acquisition_authority"] is point["empirical_acceptance"] is False


def test_slow_unrelated_metadata_does_not_change_counter_point_or_legacy_gate():
    value = with_points()
    raw = json.loads(value["acquisition_json"])
    row = middle_degraded(raw)
    row["native_read"]["read_end_ns"] = row["native_read"]["read_start_ns"] + 120000000
    value = seal(value, raw)
    assert project_combined_resource(value)["state"] == "unavailable"
    assert (
        project_counter_specific_resource(value)["state"] == "candidate_combined_response_available"
    )
    assert row["encoded_counter_read"]["read_end_ns"] == row["native_read"]["read_start_ns"] + 100


def test_actual_getter_over_100ms_remains_unavailable_without_clipping_or_dropping():
    value = with_points()
    raw = json.loads(value["acquisition_json"])
    row = middle_degraded(raw)
    row["native_read"]["read_end_ns"] = row["native_read"]["read_start_ns"] + 120000000
    row["encoded_counter_read"]["read_end_ns"] = row["native_read"]["read_start_ns"] + 101000000
    result = project_counter_specific_resource(seal(value, raw))
    assert result["state"] == "unavailable"
    assert result["unavailable_components"] == ["encoded"]
    assert result["features"] == {}


def test_cpu_50ms_read_gate_is_unchanged():
    value = with_points()
    raw = json.loads(value["acquisition_json"])
    row = next(
        e for e in raw["events"] if e["kind"] == "n11_pacing_reference" and e["phase"] == "healthy"
    )["samples"][3]
    end = row["container_cpu_read"]["read_start_ns"] + 60000000
    row["container_cpu_read"]["read_end_ns"] = end
    value["resource_artifact"]["samples"]["healthy"][3]["read_end_ns"] = end
    result = project_counter_specific_resource(seal(value, raw))
    assert result["state"] == "unavailable"
    assert result["unavailable_components"] == ["cpu"]


def test_legacy_source_cannot_gain_unrecorded_counter_times():
    with pytest.raises(ValueError, match="invalid_counter_specific_combined_projection"):
        project_counter_specific_resource(source("legacy-no-points"))


@pytest.mark.parametrize("phase", ["healthy", "degraded", "relief", "recovery", "post"])
def test_all_five_phases_require_recorded_counter_reads(phase):
    value = with_points()
    raw = json.loads(value["acquisition_json"])
    if phase in ("healthy", "post"):
        row = next(
            e for e in raw["events"] if e["kind"] == "n11_pacing_reference" and e["phase"] == phase
        )["samples"][0]
    else:
        row = next(
            e for e in raw["events"] if e["kind"] == "n11_pair_native" and e["phase"] == phase
        )
    del row["encoded_counter_read"]
    with pytest.raises(ValueError):
        project_counter_specific_resource(seal(value, raw))


@pytest.mark.parametrize(
    "change",
    [
        {"method": "old"},
        {"clock_id": "foreign"},
        {"basis": "wall_clock"},
        {"scope": "full_snapshot"},
        {"underlying_counter_freshness": "authenticated"},
        {"live_authority": True},
        {"value": True},
        {"value": 123456},
        {"read_start_ns": -1},
        {"read_end_ns": False},
        {"unexpected": 1},
    ],
)
def test_foreign_or_malformed_point_evidence_cannot_be_substituted(change):
    value = with_points()
    raw = json.loads(value["acquisition_json"])
    middle_degraded(raw)["encoded_counter_read"].update(change)
    with pytest.raises(ValueError):
        project_counter_specific_resource(seal(value, raw))


def test_point_read_must_stay_inside_original_metadata_bounds():
    value = with_points()
    raw = json.loads(value["acquisition_json"])
    row = middle_degraded(raw)
    row["encoded_counter_read"]["read_end_ns"] = row["native_read"]["read_end_ns"] + 1
    with pytest.raises(ValueError):
        project_counter_specific_resource(seal(value, raw))


def test_raw_bytes_and_cpu_artifact_remain_bound():
    value = with_points()
    value["acquisition_json"] += " "
    with pytest.raises(ValueError):
        project_counter_specific_resource(value)
    value = with_points()
    modified = deepcopy(value)
    modified["resource_artifact"]["samples"]["healthy"][3]["counters"]["usage_usec"] += 1
    with pytest.raises(ValueError):
        project_counter_specific_resource(modified)
