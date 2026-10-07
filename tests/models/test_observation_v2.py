"""Registry meaning, source capability and finite immutable N2 windows."""

import json
from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from latency_fingerprinting.cli import main
from latency_fingerprinting.json_io import load_model_file
from latency_fingerprinting.models import (
    ObservationRecord,
    ObservationWindow,
    ObservationWindowV2,
    StageTiming,
)
from latency_fingerprinting.models.measurement import AggregationKind
from latency_fingerprinting.models.v2_support import SourceSupport, resolve_metric_support

from .v2_cases import timing_payload, window_payload


@pytest.mark.parametrize("value", [False, "0"])
def test_reused_n1_summary_cannot_bypass_strict_aggregate_types(value):
    model = ObservationWindowV2.model_validate(window_payload())
    summary = model.measurements["transport.jitter_ms"].summary
    aggregates = dict(summary.aggregates)
    aggregates[AggregationKind.MINIMUM] = value
    payload = window_payload()
    payload["measurements"]["transport.jitter_ms"]["summary"] = summary.model_copy(
        update={"aggregates": aggregates}
    )
    with pytest.raises(ValidationError):
        ObservationWindowV2.model_validate(payload)


def test_reused_summary_is_snapshotted_and_refrozen():
    model = ObservationWindowV2.model_validate(window_payload())
    summary = model.measurements["transport.jitter_ms"].summary
    mutable = dict(summary.aggregates)
    copied = summary.model_copy(update={"aggregates": mutable})
    payload = window_payload()
    payload["measurements"]["transport.jitter_ms"]["summary"] = copied
    result = ObservationWindowV2.model_validate(payload)
    retained = result.measurements["transport.jitter_ms"].summary
    mutable[AggregationKind.MINIMUM] = 10
    assert retained.aggregates[AggregationKind.MINIMUM] == 0
    with pytest.raises(TypeError):
        retained.aggregates[AggregationKind.MINIMUM] = 10


def test_reused_counter_interval_is_revalidated_with_summary():
    model = ObservationWindowV2.model_validate(window_payload())
    name = "client.frames_decoded_rate_fps"
    summary = model.measurements[name].summary
    intervals = list(summary.counter_intervals)
    intervals[0] = intervals[0].model_copy(update={"wrapped": 0})
    payload = window_payload()
    payload["measurements"][name]["summary"] = summary.model_copy(
        update={"counter_intervals": tuple(intervals)}
    )
    with pytest.raises(ValidationError):
        ObservationWindowV2.model_validate(payload)


@pytest.mark.parametrize("real", [False, True])
def test_window_roundtrip_schema_and_zero_are_valid(real):
    model = ObservationWindowV2.model_validate(window_payload(real=real, values=(0, 0, 0)))
    assert all(item.summary.value == 0 for item in model.measurements.values())
    payload = model.model_dump(mode="json", by_alias=True)
    Draft202012Validator(model.model_json_schema(by_alias=True)).validate(payload)
    assert ObservationWindowV2.model_validate_json(model.model_dump_json(by_alias=True)) == model
    assert ObservationWindowV2.model_validate(model) == model
    assert tuple(model.measurements) == tuple(sorted(model.measurements))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "observation-v1"),
        ("contract_version", "1.0.0"),
        ("comparison_case_id", ""),
        ("effective_settings", {}),
        ("provenance", "organic_real"),
        ("confounder_codes", ["operator_declared", "operator_declared"]),
        ("confounder_codes", {"operator_declared"}),
        ("extra", True),
    ],
)
def test_window_rejects_invalid_roots_and_state(field, value):
    with pytest.raises(ValidationError):
        ObservationWindowV2.model_validate({**window_payload(), field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("content_hash", "sha256:" + "f" * 64),
        ("registry_version", "latency-metrics-v2.0.1"),
        ("content_hash", "sha256:" + "A" * 64),
    ],
)
def test_registry_pair_is_trusted_only(field, value):
    payload = window_payload()
    payload["registry"][field] = value
    with pytest.raises(ValidationError):
        ObservationWindowV2.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("semantic_version", "1.0.1"),
        ("source", "encoder_pipeline"),
        ("raw_fields", ("other",)),
        ("canonical_unit", "fps"),
        ("registry_version", "latency-metrics-v3.0.0"),
        ("primary_aggregation", "maximum"),
        ("available_aggregations", ("median",)),
        ("window_end_ms", 3000),
        ("metric_name", "client.received_fps"),
    ],
)
def test_summary_must_match_registered_meaning_and_window(field, value):
    payload = window_payload()
    summary = payload["measurements"]["transport.jitter_ms"]["summary"]
    summary[field] = value
    with pytest.raises(ValidationError):
        ObservationWindowV2.model_validate(payload)


@pytest.mark.parametrize(
    "change", ["omit", "unknown", "key_mismatch", "role", "unsafe_reason", "negative", "statistics"]
)
def test_measurement_inventory_and_evidence_cannot_be_forged(change):
    payload = window_payload()
    item = payload["measurements"]["transport.jitter_ms"]
    if change == "omit":
        del payload["measurements"]["transport.jitter_ms"]
    elif change == "unknown":
        payload["measurements"]["other.metric"] = deepcopy(item)
    elif change == "key_mismatch":
        item["summary"]["metric_name"] = "client.received_fps"
    elif change == "role":
        item["role"] = "audit_only"
    elif change == "unsafe_reason":
        item["summary"]["warnings"] = ("secret producer text",)
    elif change == "negative":
        item["summary"]["aggregates"] = {key: -1 for key in item["summary"]["aggregates"]}
    else:
        item["summary"]["aggregates"]["minimum"] = 100
    with pytest.raises(ValidationError):
        ObservationWindowV2.model_validate(payload)


@pytest.mark.parametrize(
    "change",
    ["rows", "available", "state", "basis", "file", "sources", "metric_support", "declared"],
)
def test_support_contradictions_reject_window(change):
    payload = window_payload()
    source = payload["sources"]["browser_webrtc"]
    if change == "rows":
        source["row_count"] = 4
    elif change == "available":
        source["available_row_count"] = 2
    elif change == "state":
        source["state"] = "unsupported"
    elif change == "basis":
        source["basis"] = "source_absent"
    elif change == "file":
        source["source_file"] = "stream-telemetry.csv"
    elif change == "sources":
        del payload["sources"]["engine_runtime"]
    elif change == "declared":
        source["declared_state"] = "unavailable"
    else:
        payload["measurements"]["transport.jitter_ms"]["support"]["state"] = "unsupported"
    with pytest.raises(ValidationError):
        ObservationWindowV2.model_validate(payload)


@pytest.mark.parametrize("state", ["supported", "unsupported", "unavailable"])
@pytest.mark.parametrize("declaration", [None, "supported", "unsupported", "unavailable"])
def test_typed_support_priority_and_basis(state, declaration):
    source = SourceSupport(
        state=state,
        declared_state=state,
        basis="source_declaration",
        source_file=None,
        row_count=3,
        available_row_count=3 if state == "supported" else 0,
    )
    expected = next(
        candidate
        for candidate in ("unsupported", "unavailable", "supported")
        if candidate in (state, declaration)
    )
    result, basis = resolve_metric_support(source, declaration)
    assert result == expected
    assert basis == ("measurement_declaration" if declaration == expected else "source_support")


@pytest.mark.parametrize("change", ["support", "interval", "counts", "coverage", "reset"])
def test_counter_rate_total_evidence_must_agree(change):
    payload = window_payload()
    item = payload["measurements"]["client.frames_decoded_window_total"]
    if change == "support":
        item["support"].update(declared_state="supported", basis="measurement_declaration")
    elif change == "interval":
        item["summary"]["counter_intervals"][0]["delta"] = 30
        item["summary"]["counter_intervals"][0]["rate"] = 30
        item["summary"]["aggregates"]["window_total"] = 90
    elif change == "counts":
        item["summary"]["source_sample_count"] = 4
    elif change == "coverage":
        item["summary"]["coverage"] = 0.5
    else:
        item["summary"]["reset_source_rows"] = (3,)
    with pytest.raises(ValidationError):
        ObservationWindowV2.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("state", "measured"),
        ("state", "estimated"),
        ("value", 0),
        ("value", True),
        ("value", "0"),
        ("value", float("inf")),
        ("value", 10**1000),
        ("sample_count", 1),
        ("sample_count", True),
        ("reason_code", None),
        ("method_id", "proxy"),
        ("method_version", "1.0.0"),
        ("statistic", "sample_mean"),
        ("unit", "seconds"),
        ("clock_domain_id", "domain"),
    ],
)
def test_timing_cannot_claim_unsupplied_evidence(field, value):
    with pytest.raises(ValidationError):
        StageTiming.model_validate(timing_payload(**{field: value}))


def test_unavailable_timing_and_unique_stages():
    payload = window_payload()
    payload["stage_timings"] = [timing_payload()]
    model = ObservationWindowV2.model_validate(payload)
    assert model.stage_timings[0].value is None
    payload["stage_timings"].append(timing_payload())
    with pytest.raises(ValidationError):
        ObservationWindowV2.model_validate(payload)


@pytest.mark.parametrize(
    "key",
    ["hostName", "raw_peer_id", "notes", "absolutePath", "username", "engineToken", "shareUrl"],
)
def test_private_nested_keys_rejected(key):
    payload = window_payload()
    payload["effective_settings"]["nested"] = [{key: "private"}]
    with pytest.raises(ValidationError, match="private metadata"):
        ObservationWindowV2.model_validate(payload)


@pytest.mark.parametrize("number", [float("nan"), float("inf"), 10**1000])
def test_nested_json_numbers_must_be_finite(number):
    payload = window_payload()
    payload["context"]["nominalStreamProfile"]["nested"] = [number]
    with pytest.raises(ValidationError):
        ObservationWindowV2.model_validate(payload)


def test_nested_json_detaches_freezes_and_preserves_boolean_identity():
    payload = window_payload()
    payload["effective_settings"]["nested"] = [{"value": True}]
    model = ObservationWindowV2.model_validate(payload)
    payload["effective_settings"]["nested"][0]["value"] = False
    assert model.effective_settings["nested"][0]["value"] is True
    with pytest.raises(TypeError):
        model.effective_settings["nested"][0]["value"] = 0
    with pytest.raises(TypeError):
        model.measurements["new"] = None
    with pytest.raises(ValidationError):
        model.run_id = "other"
    assert model.model_dump(mode="json")["effective_settings"]["nested"] == [{"value": True}]


def test_cli_validate_and_p0_commands_remain_isolated(tmp_path, capsys):
    model = ObservationWindowV2.model_validate(window_payload())
    path = tmp_path / "window.json"
    path.write_text(model.model_dump_json(by_alias=True))
    assert load_model_file(path, ObservationWindowV2) == model
    assert main(["validate", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["schemaVersion"] == "observation-window-v2"
    assert main(["match", str(path), "--fingerprints", "fixtures/reference_cases"]) == 1
    output = capsys.readouterr()
    assert not output.out and "Traceback" not in output.err
    for p0 in (ObservationWindow, ObservationRecord):
        with pytest.raises(ValidationError):
            p0.model_validate(model.model_dump(mode="json", by_alias=True))


def test_duplicate_keys_rejected_before_model_validation(tmp_path):
    model = ObservationWindowV2.model_validate(window_payload())
    text = model.model_dump_json(by_alias=True)
    for original in ('"schemaVersion":', '"registryVersion":', '"state":'):
        path = tmp_path / "duplicate.json"
        path.write_text(text.replace(original, original + '"duplicate",' + original, 1))
        with pytest.raises(ValueError, match="duplicate JSON"):
            load_model_file(path, ObservationWindowV2)


@pytest.mark.parametrize("support_state", ["unsupported", "unavailable"])
def test_declared_metric_absence_is_explicit_and_never_zero(support_state):
    payload = window_payload()
    missing = window_payload(values=(None, None, None))
    name = "transport.jitter_ms"
    payload["measurements"][name] = missing["measurements"][name]
    payload["measurements"][name]["support"] = {
        "state": support_state,
        "declared_state": support_state,
        "basis": "measurement_declaration",
    }
    model = ObservationWindowV2.model_validate(payload)
    assert model.measurements[name].summary.value is None
    assert model.measurements[name].summary.status == "missing"
    assert model.measurements[name].summary.source_sample_count == 3


def test_missing_capable_source_and_rejected_evidence_remain_distinct():
    payload = window_payload(values=(None, None, None))
    model = ObservationWindowV2.model_validate(payload)
    assert all(
        m.support.state == "supported" and m.summary.status == "missing"
        for m in model.measurements.values()
    )
    name = "transport.jitter_ms"
    payload["measurements"][name]["summary"].update(
        status="rejected", missing_reasons=(), rejected_reasons=("Rejected source evidence.",)
    )
    model = ObservationWindowV2.model_validate(payload)
    assert model.measurements[name].summary.status == "rejected"
    assert model.measurements[name].summary.value is None


def test_absent_sources_and_empty_summaries_agree():
    from latency_fingerprinting.measurement.aggregation import aggregate_counter, aggregate_gauge
    from latency_fingerprinting.measurement.metric_registry import CANONICAL_METRIC_REGISTRY
    from latency_fingerprinting.models import MetricKind

    payload = window_payload()
    for source in payload["sources"].values():
        source.update(
            state="unavailable", basis="source_absent", row_count=0, available_row_count=0
        )
    for definition in CANONICAL_METRIC_REGISTRY.definitions:
        aggregate = aggregate_gauge if definition.kind is MetricKind.GAUGE else aggregate_counter
        summary = aggregate(
            definition,
            (),
            window_start_ms=0,
            window_end_ms=2000,
            registry_version=CANONICAL_METRIC_REGISTRY.registry_version,
        ).model_dump()
        summary["missing_reasons"] = ("Missing source evidence.",)
        payload["measurements"][definition.name]["summary"] = summary
        payload["measurements"][definition.name]["support"]["state"] = "unavailable"
    model = ObservationWindowV2.model_validate(payload)
    assert all(m.summary.source_sample_count == 0 for m in model.measurements.values())


@pytest.mark.parametrize("reason", ["unsupported_source", "source_unavailable"])
def test_stage_reason_must_agree_with_source_state(reason):
    payload = window_payload()
    payload["stage_timings"] = [timing_payload(reason_code=reason)]
    with pytest.raises(ValidationError, match="source support"):
        ObservationWindowV2.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("method_version", "1.0.1"),
        ("method_id", "other"),
        ("producer_version", ""),
    ],
)
def test_capture_method_version_is_explicit_and_known(field, value):
    payload = window_payload()
    payload["capture_method"][field] = value
    with pytest.raises(ValidationError):
        ObservationWindowV2.model_validate(payload)


@pytest.mark.parametrize(
    "changes",
    [
        {"is_valid": True, "reason_codes": ["producer_invalid"]},
        {"is_valid": False, "reason_codes": []},
        {"is_valid": False, "reason_codes": ["producer_invalid", "producer_invalid"]},
        {"is_valid": "true", "reason_codes": []},
        {"is_valid": False, "reason_codes": ["raw exception"]},
    ],
)
def test_validity_is_strict_and_structured(changes):
    payload = window_payload()
    payload["validity"] = changes
    with pytest.raises(ValidationError):
        ObservationWindowV2.model_validate(payload)


@pytest.mark.parametrize(
    ("record", "field"),
    [
        ("clock", "started_at"),
        ("clock", "ended_at"),
        ("capture_method", "producer_version"),
        ("source_artifact", "bundle_schema_version"),
        ("sources", "declared_state"),
    ],
)
def test_nullable_fields_are_required(record, field):
    payload = window_payload()
    target = payload[record]
    if record == "sources":
        target = target["browser_webrtc"]
    del target[field]
    with pytest.raises(ValidationError):
        ObservationWindowV2.model_validate(payload)


def test_real_bundle_version_must_agree_with_context():
    payload = window_payload(real=True)
    payload["source_artifact"]["bundle_schema_version"] = "1"
    with pytest.raises(ValidationError, match="bundle versions"):
        ObservationWindowV2.model_validate(payload)


def test_invalid_source_artifact_type_and_empty_context_profile():
    payload = window_payload()
    payload["source_artifact"]["bundle_schema_version"] = "2"
    with pytest.raises(ValidationError):
        ObservationWindowV2.model_validate(payload)
    payload = window_payload()
    payload["context"]["nominalStreamProfile"] = {}
    with pytest.raises(ValidationError):
        ObservationWindowV2.model_validate(payload)


def test_trusted_registry_pin_is_checked_against_source(monkeypatch):
    from latency_fingerprinting.measurement import metric_registry

    monkeypatch.setattr(metric_registry, "render_metric_registry", lambda: "altered registry")
    with pytest.raises(ValidationError, match="reviewed release"):
        ObservationWindowV2.model_validate(window_payload())


def test_nested_serialization_honors_alias_mode():
    model = ObservationWindowV2.model_validate(window_payload())
    plain = model.model_dump()
    aliased = model.model_dump(mode="json", by_alias=True)
    assert "row_count" in plain["sources"]["browser_webrtc"]
    assert "rowCount" in aliased["sources"]["browser_webrtc"]
    assert "metric_name" in plain["measurements"]["transport.jitter_ms"]["summary"]
    assert "metricName" in aliased["measurements"]["transport.jitter_ms"]["summary"]


def test_summary_clock_and_metric_support_basis_must_match_window():
    payload = window_payload()
    payload["clock"].update(elapsed_end_ms=3000, duration_ms=3000)
    with pytest.raises(ValidationError, match="bounds/clock"):
        ObservationWindowV2.model_validate(payload)
    payload = window_payload()
    payload["measurements"]["transport.jitter_ms"]["support"]["basis"] = "measurement_declaration"
    with pytest.raises(ValidationError, match="declaration precedence"):
        ObservationWindowV2.model_validate(payload)


def test_single_counter_baseline_is_incomplete_without_fabricated_rate():
    model = ObservationWindowV2.model_validate(window_payload(values=(None, 60, None)))
    rate = model.measurements["client.frames_decoded_rate_fps"].summary
    assert rate.status == "incomplete" and rate.value is None and rate.coverage == 0
    assert model.measurements["transport.jitter_ms"].summary.value == 60


def test_v2_window_cannot_enter_p0_response_cli(tmp_path, capsys):
    model = ObservationWindowV2.model_validate(window_payload())
    path = tmp_path / "window.json"
    path.write_text(model.model_dump_json(by_alias=True))
    assert (
        main(
            [
                "build-response",
                "--degraded",
                str(path),
                "--relief",
                str(path),
                "--probe",
                "fixtures/query_cases/similar_network/probe.json",
            ]
        )
        == 1
    )
    output = capsys.readouterr()
    assert not output.out and "Traceback" not in output.err
