"""Pair comparability preserves identities, interventions and uncalibrated evidence."""

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from latency_fingerprinting.models import ObservationRecordV2, ObservationWindowV2, WindowClock

from .v2_cases import pair_payload, window_payload


@pytest.mark.parametrize("real", [False, True])
def test_pair_roundtrip_and_independent_clock_domains(real):
    model = ObservationRecordV2.model_validate(pair_payload(real=real))
    assert model.degraded_window.clock.domain_id != model.relief_window.clock.domain_id
    payload = model.model_dump(mode="json", by_alias=True)
    Draft202012Validator(model.model_json_schema(by_alias=True)).validate(payload)
    assert ObservationRecordV2.model_validate_json(model.model_dump_json(by_alias=True)) == model
    assert "normalizedResponse" not in payload and "responseDelta" not in payload


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema_version",), "observation-v1"),
        (("contract_version",), "1.0.0"),
        (("comparison_case_id",), "other"),
        (("relief_window", "phase"), "baseline"),
        (("relief_window", "comparison_case_id"), "other"),
        (("relief_window", "window_id"), "window-degraded"),
        (("relief_window", "context", "nodeId"), "other"),
        (("relief_window", "capture_method", "producer_version"), "producer-2"),
        (("intervention", "degraded_window_id"), "other"),
        (("intervention", "relief_window_id"), "other"),
        (("intervention", "paired_window_order"), ["relief", "degraded"]),
        (("intervention", "probe_type"), "live_probe"),
        (("intervention", "probe_version"), "invalid"),
        (("intervention", "intensity"), True),
        (("intervention", "intensity"), 0),
        (("intervention", "intensity"), float("inf")),
        (("intervention", "requested_settings"), {}),
        (("intervention", "requested_settings"), {"targetFps": True}),
        (("intervention", "requested_settings"), {"targetFps": 60}),
        (("relief_window", "effective_settings"), {"targetFps": 60}),
        (("intervention", "execution_status"), "failed"),
        (("intervention", "restoration_status"), "restored"),
        (("intervention", "observed_settings"), {"targetFps": 30}),
        (("relief_window", "validity"), {"is_valid": False, "reason_codes": ["producer_invalid"]}),
    ],
)
def test_pair_rejects_incompatible_identity_settings_and_execution(path, value):
    payload = pair_payload()
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValidationError):
        ObservationRecordV2.model_validate(payload)


@pytest.mark.parametrize("duration", [1800, 2000, 2200])
def test_duration_within_tolerance_and_partial_evidence_are_comparable(duration):
    payload = pair_payload()
    payload["relief_window"] = window_payload(
        phase="relief", duration=duration, values=(0, None, 120)
    )
    model = ObservationRecordV2.model_validate(payload)
    assert any(m.summary.coverage < 1 for m in model.relief_window.measurements.values())


def test_duration_outside_tolerance_rejected():
    payload = pair_payload()
    payload["relief_window"] = window_payload(phase="relief", duration=2300)
    with pytest.raises(ValidationError, match="10 percent"):
        ObservationRecordV2.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("execution_status", "not_executed"),
        ("observed_settings", None),
        ("observed_settings", {}),
        ("observed_settings", {"targetFps": 29}),
        ("restoration_status", "not_executed"),
        ("restoration_status", "not_applicable"),
        ("application_method", "live_bounded_probe"),
    ],
)
def test_real_intervention_requires_execution_and_observed_relief(field, value):
    payload = pair_payload(real=True)
    payload["intervention"][field] = value
    with pytest.raises(ValidationError):
        ObservationRecordV2.model_validate(payload)


def test_real_and_synthetic_cannot_be_paired():
    payload = pair_payload()
    payload["relief_window"] = window_payload(phase="relief", real=True)
    with pytest.raises(ValidationError):
        ObservationRecordV2.model_validate(payload)


def test_simulated_intervention_cannot_claim_real_windows():
    payload = pair_payload()
    payload["degraded_window"] = window_payload(real=True)
    payload["relief_window"] = window_payload(phase="relief", real=True)
    with pytest.raises(ValidationError):
        ObservationRecordV2.model_validate(payload)


def test_undeclared_settings_require_explicit_confounder():
    payload = pair_payload()
    payload["relief_window"]["effective_settings"]["targetBitrateKbps"] = 1000
    with pytest.raises(ValidationError, match="confounder"):
        ObservationRecordV2.model_validate(payload)
    payload["intervention"]["confounder_codes"] = ["other_setting_change"]
    assert ObservationRecordV2.model_validate(payload).intervention.confounder_codes == (
        "other_setting_change",
    )


def test_context_boolean_is_not_numeric_identity():
    payload = pair_payload()
    payload["degraded_window"]["context"]["nominalStreamProfile"]["flag"] = True
    payload["relief_window"]["context"]["nominalStreamProfile"]["flag"] = 1
    with pytest.raises(ValidationError, match="context identities"):
        ObservationRecordV2.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("elapsed_start_ms", -1),
        ("duration_ms", True),
        ("duration_ms", "2000"),
        ("duration_ms", float("inf")),
        ("duration_ms", 10**1000),
        ("elapsed_end_ms", 0),
        ("duration_ms", 1000),
        ("started_at", None),
        ("ended_at", "2026-10-06T00:00:03Z"),
        ("started_at", "2026-10-06T00:00:00"),
        ("started_at", "2026-10-06T00:00:00+07:00"),
        ("started_at", 1791244800),
        ("provenance", "monotonic"),
    ],
)
def test_clock_rejects_invalid_or_unsupported_bounds(field, value):
    clock = window_payload(real=True)["clock"]
    clock[field] = value
    with pytest.raises(ValidationError):
        WindowClock.model_validate(clock)


def test_synthetic_clock_rejects_utc_claim():
    payload = window_payload()
    payload["clock"]["started_at"] = "2026-10-06T00:00:00Z"
    with pytest.raises(ValidationError):
        ObservationWindowV2.model_validate(payload)


def test_pair_root_cli_and_bounded_file_roundtrip(tmp_path, capsys):
    import json

    from latency_fingerprinting.cli import main
    from latency_fingerprinting.json_io import load_model_file

    model = ObservationRecordV2.model_validate(pair_payload())
    path = tmp_path / "observation.json"
    path.write_text(model.model_dump_json(by_alias=True))
    assert load_model_file(path, ObservationRecordV2) == model
    assert main(["validate", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["schemaVersion"] == "observation-v2"
    text = path.read_text().replace(
        '"comparisonCaseId":', '"comparisonCaseId":"other","comparisonCaseId":', 1
    )
    path.write_text(text)
    with pytest.raises(ValueError, match="duplicate JSON"):
        load_model_file(path, ObservationRecordV2)


@pytest.mark.parametrize("change", ["same_reference", "duplicate_confounder", "missing_setting"])
def test_intervention_references_and_setting_availability(change):
    payload = pair_payload()
    if change == "same_reference":
        payload["intervention"]["relief_window_id"] = "window-degraded"
    elif change == "duplicate_confounder":
        payload["intervention"]["confounder_codes"] = ["operator_declared", "operator_declared"]
    else:
        payload["relief_window"]["effective_settings"] = {"targetBitrateKbps": 1000}
    with pytest.raises(ValidationError):
        ObservationRecordV2.model_validate(payload)
