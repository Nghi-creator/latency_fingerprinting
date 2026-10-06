"""Checked-in synthetic arithmetic fixtures independently lock N1 summaries."""

import json
from pathlib import Path

import pytest

from latency_fingerprinting.json_io import load_json_file
from latency_fingerprinting.measurement.aggregation import aggregate_counter, aggregate_gauge
from latency_fingerprinting.measurement.metric_registry import get_metric_definition
from latency_fingerprinting.models import MeasurementSample, MetricKind

from .fixture_cases import (
    DEFAULT_FIXTURE_DIRECTORY,
    RATE,
    TOTAL,
    fixture_cases,
    fixture_drift,
    rendered_fixture_files,
)

CASES = tuple(fixture_cases())


@pytest.mark.parametrize("name", CASES)
def test_fixture_has_explicit_synthetic_provenance_and_expected_summary(name):
    case = load_json_file(DEFAULT_FIXTURE_DIRECTORY / f"{name}.json")
    assert case["schemaVersion"] == "measurement-arithmetic-fixture-v1"
    assert case["caseId"] == name
    assert case["provenance"]["kind"] == "synthetic"
    assert case["provenance"]["controlledReal"] is False
    assert "not experimental evidence" in case["provenance"]["purpose"]
    assert case["explanation"]
    assert case["expectedSummaries"]
    assert case == fixture_cases()[name]


@pytest.mark.parametrize("name", CASES)
def test_aggregation_matches_all_authored_numerical_and_audit_expectations(name):
    case = load_json_file(DEFAULT_FIXTURE_DIRECTORY / f"{name}.json")
    samples = tuple(MeasurementSample.model_validate(row) for row in case["samples"])
    before = tuple(sample.model_dump_json() for sample in samples)
    for metric_name, expected in case["expectedSummaries"].items():
        definition = get_metric_definition(metric_name)
        aggregate = aggregate_gauge if definition.kind is MetricKind.GAUGE else aggregate_counter
        summary = aggregate(
            definition,
            samples,
            window_start_ms=case["window"]["startMs"],
            window_end_ms=case["window"]["endMs"],
            registry_version=case["registryVersion"],
            source_missing_reason=case["sourceMissingReason"],
        )
        payload = summary.model_dump(mode="json", by_alias=True)
        expected_prefixes = expected["rejectedReasonPrefixes"]
        assert len(summary.rejected_reasons) == len(expected_prefixes)
        assert all(
            actual.startswith(prefix)
            for actual, prefix in zip(summary.rejected_reasons, expected_prefixes, strict=True)
        )
        actual = {
            key: summary.value if key == "value" else payload[key]
            for key in expected
            if key != "rejectedReasonPrefixes"
        }
        assert actual == {
            key: value for key, value in expected.items() if key != "rejectedReasonPrefixes"
        }
        assert payload["metricName"] == metric_name
        assert payload["registryVersion"] == case["registryVersion"]
        assert payload["canonicalUnit"] == definition.canonical_unit
        assert payload["windowStartMs"] == case["window"]["startMs"]
        assert payload["windowEndMs"] == case["window"]["endMs"]
    assert tuple(sample.model_dump_json() for sample in samples) == before


def test_same_window_and_activity_fixture_pair_is_cadence_independent():
    cases = fixture_cases()
    first, second = cases["counter-1s-cadence"], cases["counter-5s-equivalent-cadence"]
    assert first["window"] == second["window"] == {"startMs": 0, "endMs": 10000}
    assert len(first["samples"]) == 11
    assert len(second["samples"]) == 3
    for name, expected in ((RATE, 60), (TOTAL, 600)):
        assert (
            first["expectedSummaries"][name]["value"]
            == second["expectedSummaries"][name]["value"]
            == expected
        )
        assert (
            first["expectedSummaries"][name]["coverage"]
            == second["expectedSummaries"][name]["coverage"]
            == 1
        )


def test_fixture_drift_checks_exact_bytes_without_writing(monkeypatch):
    before = {path.name: path.read_bytes() for path in DEFAULT_FIXTURE_DIRECTORY.glob("*.json")}

    def no_write(*args, **kwargs):
        pytest.fail("fixture drift checking must never write or create directories")

    monkeypatch.setattr(Path, "write_bytes", no_write)
    monkeypatch.setattr(Path, "write_text", no_write)
    monkeypatch.setattr(Path, "mkdir", no_write)
    assert fixture_drift() == {}
    assert before == {
        path.name: path.read_bytes() for path in DEFAULT_FIXTURE_DIRECTORY.glob("*.json")
    }
    assert rendered_fixture_files() == rendered_fixture_files()


def test_drift_detects_missing_directory_without_creating_it(tmp_path):
    directory = tmp_path / "missing"
    drift = fixture_drift(directory)
    assert len(drift) == len(CASES)
    assert set(drift.values()) == {"missing"}
    assert not directory.exists()


def test_drift_detects_changed_missing_and_unexpected_files(tmp_path):
    for path, content in rendered_fixture_files().items():
        (tmp_path / path).write_bytes(content)
    changed = tmp_path / "counter-gap.json"
    changed.write_bytes(changed.read_bytes().replace(b'"coverage": 0.5', b'"coverage": 1.0'))
    missing = tmp_path / "gauge-missing.json"
    missing.unlink()
    unexpected = tmp_path / "unexpected.json"
    unexpected.write_text("{}\n")
    assert fixture_drift(tmp_path) == {
        changed: "changed",
        missing: "missing",
        unexpected: "unexpected",
    }


def test_json_format_and_line_endings_are_part_of_drift_contract(tmp_path):
    for path, content in rendered_fixture_files().items():
        (tmp_path / path).write_bytes(content)
    changed = tmp_path / "gauge-regular.json"
    changed.write_bytes(changed.read_bytes().replace(b"\n", b"\r\n"))
    assert fixture_drift(tmp_path) == {changed: "changed"}
    changed.write_text(json.dumps(json.loads(changed.read_bytes())))
    assert fixture_drift(tmp_path) == {changed: "changed"}


def test_expected_generation_does_not_call_the_aggregation_implementation(monkeypatch):
    from latency_fingerprinting.measurement import aggregation

    def forbidden(*args, **kwargs):
        pytest.fail("expected summaries must be independent of the implementation")

    monkeypatch.setattr(aggregation, "aggregate_gauge", forbidden)
    monkeypatch.setattr(aggregation, "aggregate_counter", forbidden)
    assert len(rendered_fixture_files()) == 13
