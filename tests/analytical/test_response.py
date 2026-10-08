"""Reconstruction, strict values, exclusions and public analytical root boundaries."""

import json
from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from latency_fingerprinting.cli import main
from latency_fingerprinting.json_io import load_model_file
from latency_fingerprinting.models import AnalyticalResponseV2
from latency_fingerprinting.pipeline import canonical_json

from .cases import response_payload

FEATURE = "transport.jitter_ms"


def test_response_roundtrip_schema_cli_and_signed_primary_values(tmp_path, capsys):
    payload = response_payload()
    model = AnalyticalResponseV2.model_validate(payload)
    assert model.is_valid and len(model.features) == 22
    feature = model.features[FEATURE]
    assert (feature.degraded.primary_value, feature.relief.primary_value) == (60, 30)
    assert (feature.raw_delta, feature.denominator, feature.normalized_value) == (-30, 60, -0.5)
    assert model.features["client.frames_decoded_rate_fps"].normalized_value == -0.5
    assert model.features["client.freeze_count_rate_per_min"].reference_value == 3600
    assert not any(n.endswith("window_total") for n in model.features)
    assert "encoder.pipeline_delay_proxy_ms" not in model.features
    Draft202012Validator(AnalyticalResponseV2.model_json_schema()).validate(payload)
    assert AnalyticalResponseV2.model_validate_json(canonical_json(model)) == model
    assert AnalyticalResponseV2.model_validate(model.model_dump()) == model
    path = tmp_path / "response.json"
    path.write_text(canonical_json(model))
    assert load_model_file(path, AnalyticalResponseV2) == model
    assert main(["validate", str(path)]) == 0
    output = capsys.readouterr()
    assert output.out == canonical_json(model) and output.err == ""


@pytest.mark.parametrize(
    "degraded,relief,expected",
    [
        ((0, 0, 0), (0, 0, 0), 0),
        ((0, 0, 0), (0, 2, 4), 2),
        ((0, 30, 60), (0, 60, 120), 1),
        ((0, 60, 120), (0, 30, 60), -0.5),
    ],
)
def test_zero_and_signed_responses_use_numeric_floor_without_clipping(degraded, relief, expected):
    model = AnalyticalResponseV2.model_validate(response_payload(degraded=degraded, relief=relief))
    feature = model.features[FEATURE]
    assert feature.normalized_value == expected and feature.state == "eligible"
    assert not feature.was_clipped and feature.unclipped_value is None


@pytest.mark.parametrize("phase", ["degraded_window", "relief_window"])
@pytest.mark.parametrize("state", ["unsupported", "unavailable"])
def test_source_absence_overrides_missing_cells_without_inventing_zero(phase, state):
    payload = response_payload(
        degraded=(None, None, None), relief=(None, None, None), source_state=(phase, state)
    )
    model = AnalyticalResponseV2.model_validate(payload)
    feature = model.features[FEATURE]
    expected = (
        ("degraded_" + state, "relief_missing")
        if phase == "degraded_window"
        else ("degraded_missing", "relief_" + state)
    )
    assert feature.exclusion_codes == expected
    assert feature.normalized_value is None and feature.raw_delta is None
    assert not model.is_valid and model.invalid_reason_codes == ("no_eligible_features",)


@pytest.mark.parametrize(
    "degraded,relief,codes",
    [
        ((None, None, None), (0, 30, 60), ("degraded_missing",)),
        ((0, 60, 120), (None, None, None), ("relief_missing",)),
        ((0, 60, None), (0, 30, 60), ("degraded_incomplete",)),
        ((None, None, None), (None, None, None), ("degraded_missing", "relief_missing")),
    ],
)
def test_exclusion_priority_and_phase_order_follow_embedded_evidence(degraded, relief, codes):
    model = AnalyticalResponseV2.model_validate(response_payload(degraded=degraded, relief=relief))
    assert model.features[FEATURE].exclusion_codes == codes
    assert model.features[FEATURE].reference_value is None


def test_rejected_series_is_distinct_from_missing_support():
    model = AnalyticalResponseV2.model_validate(
        response_payload(degraded=(None, None, None), rejected=True)
    )
    assert model.features[FEATURE].exclusion_codes == ("degraded_rejected",)
    assert model.features[FEATURE].degraded.support_state == "supported"


@pytest.mark.parametrize("location", ["degraded_window", "relief_window", "intervention"])
def test_confounder_short_circuits_all_calculations_with_retained_evidence(location):
    model = AnalyticalResponseV2.model_validate(response_payload(confounder=location))
    assert not model.is_valid and model.invalid_reason_codes == ("confounded_pair",)
    for feature in model.features.values():
        assert feature.exclusion_codes == ("confounded_pair",) and feature.raw_delta is None
        assert feature.degraded.primary_value is not None


@pytest.mark.parametrize(
    "path,value",
    [
        (("responseId",), "response-v2-" + "0" * 64),
        (("contractVersion",), "1.0.0"),
        (("isValid",), False),
        (("isValid",), 1),
        (("invalidReasonCodes",), ["no_eligible_features"]),
        (("features", FEATURE, "unit"), "fps"),
        (("features", FEATURE, "aggregation"), "maximum"),
        (("features", FEATURE, "normalizedValue"), 0),
        (("features", FEATURE, "rawDelta"), 30),
        (("features", FEATURE, "referenceValue"), 30),
        (("features", FEATURE, "denominator"), 1),
        (("features", FEATURE, "rawDelta"), True),
        (("features", FEATURE, "rawDelta"), "-30"),
        (("features", FEATURE, "normalizedValue"), float("nan")),
        (("features", FEATURE, "denominator"), 0),
        (("features", FEATURE, "wasClipped"), True),
        (("features", FEATURE, "wasClipped"), 0),
        (("features", FEATURE, "unclippedValue"), -0.5),
        (("features", FEATURE, "exclusionCodes"), ["degraded_missing"]),
        (("features", FEATURE, "exclusionCodes"), {"degraded_missing"}),
        (("features", FEATURE, "degraded", "primaryValue"), 50),
        (("features", FEATURE, "degraded", "supportState"), "unavailable"),
        (("features", FEATURE, "degraded", "summaryStatus"), "missing"),
        (("features", FEATURE, "degraded", "sourceSampleCount"), 4),
        (("features", FEATURE, "degraded", "usableSampleCount"), True),
        (("features", FEATURE, "degraded", "coverage"), 0.5),
        (("features", FEATURE, "relief", "windowId"), "other"),
        (("unexpected",), "secret metadata"),
    ],
)
def test_tampered_response_fields_cannot_override_input_evidence(path, value):
    payload = response_payload()
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValidationError):
        AnalyticalResponseV2.model_validate(payload)


@pytest.mark.parametrize(
    "change",
    ["omit", "audit", "proxy", "extra", "excluded_number", "false_exclusion", "bad_invalidity"],
)
def test_inventory_exclusions_and_validity_cannot_be_forged(change):
    payload = (
        response_payload(degraded=(None, None, None))
        if change in {"excluded_number", "false_exclusion", "bad_invalidity"}
        else response_payload()
    )
    if change == "omit":
        del payload["features"][FEATURE]
    elif change in {"audit", "proxy", "extra"}:
        key = {
            "audit": "client.frames_decoded_window_total",
            "proxy": "encoder.pipeline_delay_proxy_ms",
            "extra": "unknown.feature",
        }[change]
        payload["features"][key] = deepcopy(payload["features"][FEATURE])
    elif change == "excluded_number":
        payload["features"][FEATURE]["normalizedValue"] = 0
    elif change == "false_exclusion":
        payload["features"][FEATURE]["exclusionCodes"] = ["degraded_unavailable"]
    else:
        payload["invalidReasonCodes"] = ["no_eligible_features", "no_eligible_features"]
    with pytest.raises(ValidationError):
        AnalyticalResponseV2.model_validate(payload)


def test_input_snapshots_and_nested_instance_revalidation():
    payload = response_payload()
    model = AnalyticalResponseV2.model_validate(payload)
    payload["features"][FEATURE]["degraded"]["primaryValue"] = 999
    payload["observation"]["degradedWindow"]["context"]["nominalStreamProfile"]["fps"] = 999
    assert model.features[FEATURE].degraded.primary_value == 60
    with pytest.raises(TypeError):
        model.features[FEATURE] = model.features[FEATURE]
    with pytest.raises(ValidationError):
        model.features[FEATURE].raw_delta = 1
    payload = response_payload()
    corrupt = model.features[FEATURE].degraded.model_copy(update={"usable_sample_count": True})
    payload["features"][FEATURE] = model.features[FEATURE].model_copy(update={"degraded": corrupt})
    with pytest.raises(ValidationError):
        AnalyticalResponseV2.model_validate(payload)
    assert "primary_value" in model.model_dump()["features"][FEATURE]["degraded"]


@pytest.mark.parametrize("fault", ["duplicate", "depth", "bytes", "non_finite", "tamper"])
def test_public_validate_failures_are_repeatable_without_partial_json(tmp_path, capsys, fault):
    path = tmp_path / "response.json"
    text = json.dumps(response_payload())
    if fault == "duplicate":
        text = text.replace('"responseId":', '"responseId":"duplicate", "responseId":', 1)
    elif fault == "depth":
        text = "[" * 129 + "0" + "]" * 129
    elif fault == "bytes":
        text = " " * (10 * 1024 * 1024 + 1)
    elif fault == "non_finite":
        text = text.replace('"rawDelta": -30.0', '"rawDelta": NaN', 1)
    else:
        text = text.replace('"normalizedValue": -0.5', '"normalizedValue": 0.0', 1)
    path.write_text(text)
    previous = None
    for _ in range(2):
        assert main(["validate", str(path)]) == 1
        output = capsys.readouterr()
        assert output.out == "" and "Traceback" not in output.err
        assert previous is None or previous == output.err
        previous = output.err


def test_existing_p0_builders_and_matcher_reject_analytical_roots(tmp_path, capsys):
    path = tmp_path / "response.json"
    path.write_text(canonical_json(AnalyticalResponseV2.model_validate(response_payload())))
    assert main(["match", str(path), "--fingerprints", "fixtures/reference_cases"]) == 1
    assert capsys.readouterr().out == ""
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
    assert capsys.readouterr().out == ""
