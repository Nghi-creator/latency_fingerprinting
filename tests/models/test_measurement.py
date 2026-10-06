"""Strictness, semantics, serialization and safe file boundaries for N1 registries."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from latency_fingerprinting.json_io import load_model_file
from latency_fingerprinting.models import (
    AggregationKind,
    CounterResetPolicy,
    MetricDefinition,
    MetricKind,
    MetricRegistry,
    MetricUnit,
    MissingDataPolicy,
)


def gauge_payload(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "transport.jitter_ms",
        "semanticVersion": "1.0.0",
        "source": "browser_webrtc",
        "rawFields": ["jitter_ms"],
        "kind": "gauge",
        "canonicalUnit": "ms",
        "primaryAggregation": "median",
        "availableAggregations": ["median", "nearest_rank_p95", "minimum", "maximum"],
        "clockBasis": "source_elapsed_ms",
        "expectedCadenceMs": None,
        "cadenceToleranceRatio": None,
        "missingDataPolicy": "omit_missing_samples",
        "counterResetPolicy": None,
        "nonNegative": True,
        "description": "Maximum supported inbound RTP jitter in milliseconds",
    }
    payload.update(changes)
    return payload


def counter_payload(**changes: object) -> dict[str, object]:
    return gauge_payload(
        **{
            "name": "client.frames_decoded_rate_fps",
            "rawFields": ["frames_decoded"],
            "kind": "cumulative_counter",
            "canonicalUnit": "frames/s",
            "primaryAggregation": "time_weighted_rate",
            "availableAggregations": ["time_weighted_rate"],
            "missingDataPolicy": "break_counter_continuity",
            "counterResetPolicy": "reject_segment",
            "description": "Decoded video frames per accepted elapsed second",
            **changes,
        }
    )


def registry_payload(**changes: object) -> dict[str, object]:
    return {
        "schemaVersion": "metric-registry-v1",
        "registryVersion": "latency-metrics-v2.0.0",
        "createdAt": "2026-10-06T00:00:00Z",
        "definitions": [gauge_payload(), counter_payload()],
        **changes,
    }


def test_registry_round_trip_has_canonical_order_and_camel_case_aliases() -> None:
    registry = MetricRegistry.model_validate(registry_payload())
    rendered = registry.model_dump_json(by_alias=True)
    assert MetricRegistry.model_validate_json(rendered) == registry
    assert MetricRegistry.model_validate(json.loads(rendered)) == registry
    assert [item.name for item in registry.definitions] == [
        "client.frames_decoded_rate_fps",
        "transport.jitter_ms",
    ]
    payload = registry.model_dump(mode="json", by_alias=True)
    assert set(payload) == {"schemaVersion", "registryVersion", "createdAt", "definitions"}
    assert set(payload["definitions"][0]) == {
        "name",
        "semanticVersion",
        "source",
        "rawFields",
        "kind",
        "canonicalUnit",
        "primaryAggregation",
        "availableAggregations",
        "clockBasis",
        "expectedCadenceMs",
        "cadenceToleranceRatio",
        "missingDataPolicy",
        "counterResetPolicy",
        "nonNegative",
        "description",
        "counterWidthBits",
    }


def test_definition_accepts_python_names_and_trims_strings() -> None:
    payload = gauge_payload(name=" transport.jitter_ms ", description=" jitter ")
    payload["rawFields"] = [" jitter_ms "]
    model = MetricDefinition.model_validate(payload)
    assert model.name == "transport.jitter_ms"
    assert model.description == "jitter"
    assert model.raw_fields == ("jitter_ms",)
    assert MetricDefinition.model_validate(model.model_dump()) == model


def test_canonical_order_does_not_mutate_inputs() -> None:
    payload = registry_payload()
    before = json.dumps(payload)
    registry = MetricRegistry.model_validate(payload)
    reversed_payload = registry_payload(definitions=[counter_payload(), gauge_payload()])
    reversed_payload["definitions"][1]["availableAggregations"].reverse()
    assert registry.model_dump_json(by_alias=True) == MetricRegistry.model_validate(
        reversed_payload
    ).model_dump_json(by_alias=True)
    assert json.dumps(payload) == before


def test_models_and_sequences_are_immutable_and_detached_from_input() -> None:
    payload = registry_payload()
    registry = MetricRegistry.model_validate(payload)
    payload["definitions"][0]["rawFields"].append("other")
    assert registry.definitions[1].raw_fields == ("jitter_ms",)
    assert isinstance(registry.definitions, tuple)
    assert isinstance(registry.definitions[0].available_aggregations, tuple)
    with pytest.raises(ValidationError, match="frozen"):
        registry.registry_version = "latency-metrics-v3.0.0"
    with pytest.raises(ValidationError, match="frozen"):
        registry.definitions[0].description = "changed"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", ""),
        ("name", "   "),
        ("name", "Jitter"),
        ("name", 42),
        ("semanticVersion", "1"),
        ("semanticVersion", "01.0.0"),
        ("semanticVersion", "1.0.0-beta"),
        ("semanticVersion", 1),
        ("description", ""),
        ("description", "   "),
        ("description", 5),
        ("source", "unknown"),
        ("kind", "unknown"),
        ("canonicalUnit", "unknown"),
        ("clockBasis", "utc"),
        ("primaryAggregation", "average"),
        ("availableAggregations", ["average"]),
        ("availableAggregations", []),
        ("availableAggregations", ["median", "median"]),
        ("availableAggregations", "median"),
        ("availableAggregations", {"median"}),
        ("rawFields", []),
        ("rawFields", [""]),
        ("rawFields", ["   "]),
        ("rawFields", ["jitter_ms", " jitter_ms "]),
        ("rawFields", [1]),
        ("rawFields", "jitter_ms"),
        ("rawFields", {"jitter_ms"}),
        ("missingDataPolicy", "zero_fill"),
        ("counterResetPolicy", "unknown"),
        ("nonNegative", "true"),
        ("nonNegative", 1),
        ("undeclared", "extra"),
    ],
)
def test_definition_rejects_invalid_scalar_and_sequence_fields(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        MetricDefinition.model_validate(gauge_payload(**{field: value}))


@pytest.mark.parametrize("field", ["expectedCadenceMs", "cadenceToleranceRatio"])
@pytest.mark.parametrize(
    "value", [0, -1, True, False, "1000", float("nan"), float("inf"), -float("inf"), 10**1000]
)
def test_cadence_rejects_invalid_numbers_without_arithmetic_exceptions(
    field: str, value: object
) -> None:
    with pytest.raises(ValidationError):
        MetricDefinition.model_validate(gauge_payload(**{"expectedCadenceMs": 1000, field: value}))


def test_cadence_tolerance_requires_expected_cadence() -> None:
    with pytest.raises(ValidationError, match="requires expected_cadence"):
        MetricDefinition.model_validate(gauge_payload(cadenceToleranceRatio=0.1))
    model = MetricDefinition.model_validate(
        gauge_payload(expectedCadenceMs=1000, cadenceToleranceRatio=0.1)
    )
    assert model.expected_cadence_ms == 1000
    assert model.cadence_tolerance_ratio == 0.1


def test_primary_aggregation_must_be_available() -> None:
    with pytest.raises(ValidationError, match="must belong"):
        MetricDefinition.model_validate(gauge_payload(availableAggregations=["maximum"]))


@pytest.mark.parametrize(
    "changes",
    [
        {"counterResetPolicy": "reject_segment"},
        {"counterWidthBits": 32},
        {"missingDataPolicy": "break_counter_continuity"},
        {"primaryAggregation": "window_total", "availableAggregations": ["window_total"]},
        {"canonicalUnit": "frames/s"},
    ],
)
def test_gauges_reject_counter_only_configuration(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        MetricDefinition.model_validate(gauge_payload(**changes))


@pytest.mark.parametrize(
    "changes",
    [
        {"counterResetPolicy": None},
        {"missingDataPolicy": "omit_missing_samples"},
        {"nonNegative": False},
        {"primaryAggregation": "median", "availableAggregations": ["median"]},
        {"availableAggregations": ["window_total", "time_weighted_rate"]},
        {"canonicalUnit": "frames"},
        {"counterResetPolicy": "allow_declared_wraparound"},
        {"counterWidthBits": 32},
    ],
)
def test_counters_reject_incompatible_semantics(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        MetricDefinition.model_validate(counter_payload(**changes))


@pytest.mark.parametrize("bits", [0, -1, 65, True, 32.0, "32", 10**1000])
def test_counter_width_is_a_bounded_strict_integer(bits: object) -> None:
    with pytest.raises(ValidationError):
        MetricDefinition.model_validate(
            counter_payload(counterResetPolicy="allow_declared_wraparound", counterWidthBits=bits)
        )


@pytest.mark.parametrize("bits", [1, 32, 64])
def test_wraparound_can_only_be_declared_with_a_width(bits: int) -> None:
    model = MetricDefinition.model_validate(
        counter_payload(counterResetPolicy="allow_declared_wraparound", counterWidthBits=bits)
    )
    assert model.counter_width_bits == bits


@pytest.mark.parametrize("kind", ["event_count", "derived"])
def test_unimplemented_kinds_are_reserved(kind: str) -> None:
    assert MetricKind(kind).value == kind
    with pytest.raises(ValidationError, match="reserved beyond N1"):
        MetricDefinition.model_validate(gauge_payload(kind=kind))


@pytest.mark.parametrize("policy", ["reject_segment", "reject_series"])
def test_counter_reset_policies_and_total_definition(policy: str) -> None:
    model = MetricDefinition.model_validate(
        counter_payload(
            name="client.frames_decoded_window_total",
            primaryAggregation="window_total",
            availableAggregations=["window_total"],
            canonicalUnit="frames",
            counterResetPolicy=policy,
        )
    )
    assert model.primary_aggregation is AggregationKind.WINDOW_TOTAL
    assert model.canonical_unit is MetricUnit.FRAMES
    assert model.counter_reset_policy is CounterResetPolicy(policy)
    with pytest.raises(ValidationError, match="unit must match"):
        MetricDefinition.model_validate(
            counter_payload(
                primaryAggregation="window_total",
                availableAggregations=["window_total"],
            )
        )


def test_reject_series_missing_policy_is_valid_for_gauges_and_counters() -> None:
    for factory in (gauge_payload, counter_payload):
        model = MetricDefinition.model_validate(
            factory(missingDataPolicy="reject_series_on_any_invalid_sample")
        )
        assert model.missing_data_policy is MissingDataPolicy.REJECT_SERIES_ON_ANY_INVALID_SAMPLE
    assert not MetricDefinition.model_validate(gauge_payload(nonNegative=False)).non_negative


@pytest.mark.parametrize(
    "changes",
    [
        {"definitions": []},
        {"definitions": [gauge_payload(), gauge_payload()]},
        {"definitions": [gauge_payload(), gauge_payload(semanticVersion="2.0.0")]},
        {"definitions": "bad"},
        {"schemaVersion": "metric-registry-v2"},
        {"registryVersion": "2.0.0"},
        {"registryVersion": "latency-metrics-v02.0.0"},
        {"registryVersion": 2},
        {"createdAt": "2026-10-06T00:00:00"},
        {"createdAt": "2026-10-06T00:00:00+07:00"},
        {"createdAt": datetime(2026, 10, 6)},
        {"createdAt": datetime(2026, 10, 6, tzinfo=timezone(timedelta(hours=7)))},
        {"createdAt": 1791244800},
        {"createdAt": "1791244800"},
        {"createdAt": "not-a-timestamp"},
        {"createdAt": True},
        {"extraField": "extra"},
    ],
)
def test_registry_rejects_invalid_states(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        MetricRegistry.model_validate(registry_payload(**changes))


def test_utc_datetime_and_tuple_definitions_are_accepted() -> None:
    definition = MetricDefinition.model_validate(gauge_payload())
    registry = MetricRegistry.model_validate(
        registry_payload(createdAt=datetime(2026, 10, 6, tzinfo=UTC), definitions=(definition,))
    )
    assert registry.created_at.utcoffset() == timedelta(0)
    assert registry.definitions == (definition,)


@pytest.mark.parametrize(
    "field",
    [
        "name",
        "semanticVersion",
        "source",
        "rawFields",
        "kind",
        "canonicalUnit",
        "primaryAggregation",
        "availableAggregations",
        "clockBasis",
        "expectedCadenceMs",
        "cadenceToleranceRatio",
        "missingDataPolicy",
        "counterResetPolicy",
        "nonNegative",
        "description",
    ],
)
def test_definition_requires_even_nullable_contract_fields(field: str) -> None:
    payload = gauge_payload()
    del payload[field]
    with pytest.raises(ValidationError):
        MetricDefinition.model_validate(payload)


def test_registry_schema_exposes_aliases_closed_enums_and_forbids_extra_fields() -> None:
    schema = MetricRegistry.model_json_schema(by_alias=True)
    assert schema["additionalProperties"] is False
    assert schema["properties"]["schemaVersion"]["const"] == "metric-registry-v1"
    assert schema["properties"]["definitions"]["minItems"] == 1
    definition = schema["$defs"]["MetricDefinition"]
    assert definition["additionalProperties"] is False
    assert "primaryAggregation" in definition["required"]
    assert "counterResetPolicy" in definition["required"]
    assert schema["$defs"]["MetricKind"]["enum"] == [kind.value for kind in MetricKind]


def test_registry_public_file_boundary_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(registry_payload()), encoding="utf-8")
    assert load_model_file(path, MetricRegistry) == MetricRegistry.model_validate(
        registry_payload()
    )


@pytest.mark.parametrize("nested", [False, True])
def test_registry_public_file_boundary_rejects_duplicate_keys(tmp_path: Path, nested: bool) -> None:
    text = json.dumps(registry_payload())
    if nested:
        text = text.replace('"rawFields":', '"rawFields": ["fake"], "rawFields":', 1)
    else:
        text = text.replace('"registryVersion":', '"registryVersion": "fake", "registryVersion":')
    path = tmp_path / "registry.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON object key"):
        load_model_file(path, MetricRegistry)


@pytest.mark.parametrize("number", ["NaN", "Infinity", "1e10000", "-1e10000", "1" + "0" * 1000])
def test_registry_public_file_boundary_rejects_non_finite_and_overflow_numbers(
    tmp_path: Path, number: str
) -> None:
    text = json.dumps(registry_payload()).replace(
        '"expectedCadenceMs": null', f'"expectedCadenceMs": {number}', 1
    )
    path = tmp_path / "registry.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        load_model_file(path, MetricRegistry)
