"""Invented counter sources; no worker/media qualification or scientific admission."""

import hashlib
import json

import pytest

from latency_fingerprinting.evaluation.protocols.physical_challenge_measurements import (
    inspect_challenge_measurements,
)
from tests.evaluation.projections.test_event_span_projection import event_source


def source(recipe="mixed_delay_pressure"):
    a = json.loads(event_source()["acquisition_json"])
    a.update(
        method="n11-physical-challenge-acquisition-v1",
        role="engineering_challenge_raw_phases_no_pair_or_diagnostic_label",
        status="passed",
        live_authority=False,
        challenge_recipe=recipe,
        mode="engineering-n11-physical-challenge-" + recipe,
    )
    for e in a["events"]:
        if e["kind"] == "n11_pacing_reference":
            e["kind"] = "n11_challenge_reference"
        if e["kind"] == "n11_resource_context":
            e["kind"] = "n11_challenge_resource_context"
            e["context"]["method"] = "n11-physical-challenge-observation-v1"
            e["clock_id"] = (
                "controller-monotonic-"
                + hashlib.sha256(
                    json.dumps(e["context"], sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
            )
            clock = e["clock_id"]
    for e in a["events"]:
        rows = (
            e.get("samples", [])
            if e["kind"] == "n11_challenge_reference"
            else [e]
            if e["kind"] == "n11_pair_native"
            else []
        )
        for row in rows:
            row["container_cpu_read"]["clock_id"] = clock
    return a


def inspect(value):
    return inspect_challenge_measurements(json.dumps(value).encode())


@pytest.mark.parametrize(
    "recipe",
    [
        "mixed_delay_pressure",
        "delay_to_pressure",
        "pressure_to_delay",
        "control_no_injected_fault",
        "control_owned_identity_delay",
        "control_owned_cpu_pressure",
    ],
)
def test_all_recipes_rebuild_generic_windows_without_admission(recipe):
    result = inspect(source(recipe))
    assert result["state"] == "counter_windows_reconstructed"
    assert len(result["encoded_event_spans"]) == 5
    assert result["cpu_response"]["state"] == "candidate_response_available"
    assert result["stable_condition"] == ("_to_" not in recipe)
    assert not any(
        result[k]
        for k in (
            "stable_pair_admitted",
            "n2_pair_admitted",
            "source_media_verified",
            "resource_dose_verified",
            "empirical_acceptance",
        )
    )


@pytest.mark.parametrize(
    "change",
    [
        "phase",
        "cpu_clock",
        "counter",
        "encoded_clock",
        "sequence",
        "generation",
        "cpu_source",
        "trace_bounds",
        "legacy",
    ],
)
def test_source_splicing_missing_timing_and_changed_phase_are_rejected(change):
    a = source()
    row = next(e for e in a["events"] if e["kind"] == "n11_pair_native")
    if change == "phase":
        del row["container_cpu_read"]["phase"]
    elif change == "cpu_clock":
        row["container_cpu_read"]["clock_id"] = "controller-monotonic-" + "0" * 64
    elif change == "counter":
        row["encoded_counter_read"]["value"] += 1
    elif change == "encoded_clock":
        row["encoded_counter_read"]["clock_id"] = "worker-monotonic-" + "0" * 64
    elif change == "sequence":
        row["sequence"] = 0
    elif change == "generation":
        next(e for e in a["events"] if e["kind"] == "n11_pair_dispatched")["request"]["generation"][
            "peer"
        ] = "foreign"
    elif change == "cpu_source":
        row["container_cpu_read"]["source_identity"]["cgroup"]["inode"] += 1
    elif change == "trace_bounds":
        next(e for e in a["events"] if e["kind"] == "n11_encoded_event_trace")[
            "controller_boundaries"
        ][0]["at_ns"] += 1
    else:
        a["method"] = "n11-contained-condition-resource-candidate-v1"
    with pytest.raises(ValueError, match="invalid_challenge_measurements"):
        inspect(a)


def test_valid_missing_trace_remains_unavailable_instead_of_becoming_abstention():
    a = source()
    a["events"] = [e for e in a["events"] if e["kind"] != "n11_encoded_event_trace"]
    result = inspect(a)
    assert result["state"] == "unavailable"
    assert result["encoded_reason_codes"] == ["encoded_event_trace_missing"]
    assert result["n2_pair_admitted"] is False


def test_slow_getter_is_preserved_as_measurement_unavailable():
    a = source()
    row = next(e for e in a["events"] if e["kind"] == "n11_challenge_reference")["samples"][0]
    row["encoded_counter_read"]["read_end_ns"] += 101_000_000
    row["native_read"]["read_end_ns"] = row["encoded_counter_read"]["read_end_ns"]
    result = inspect(a)
    assert result["state"] == "unavailable"
    assert "encoded_read_span_too_wide" in result["encoded_reason_codes"]
