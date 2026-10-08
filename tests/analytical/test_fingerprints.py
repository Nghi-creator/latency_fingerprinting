"""Fingerprint reconstruction, declared provenance and creation boundaries."""

from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from latency_fingerprinting.analytical.fingerprints import create_fingerprint_v2
from latency_fingerprinting.analytical.responses import derive_analytical_response
from latency_fingerprinting.cli import main
from latency_fingerprinting.models import (
    AnalyticalResponseV2,
    FeaturePolicyV1,
    FingerprintV2,
    ObservationRecordV2,
)
from latency_fingerprinting.pipeline import canonical_json
from tests.models.v2_cases import pair_payload, window_payload

from .cases import fingerprint_payload, policy_payload, response_payload


def partial_response(count):
    pair = pair_payload()
    missing = window_payload(values=(None, None, None))
    names = sorted(policy_payload()["features"])
    for name in names[count:]:
        summary = missing["measurements"][name]["summary"]
        for linked_name, item in missing["measurements"].items():
            if (item["summary"]["source"], item["summary"]["raw_fields"]) == (
                summary["source"],
                summary["raw_fields"],
            ):
                pair["degraded_window"]["measurements"][linked_name] = item
    return derive_analytical_response(
        ObservationRecordV2.model_validate(pair), FeaturePolicyV1.model_validate(policy_payload())
    )


def test_independent_fingerprint_schema_creator_and_public_validation(tmp_path, capsys):
    expected = fingerprint_payload()
    model = FingerprintV2.model_validate(expected)
    created = create_fingerprint_v2(
        AnalyticalResponseV2.model_validate(expected["response"]),
        bottleneck_label="network_pressure",
    )
    assert created.model_dump(mode="json", by_alias=True) == expected
    Draft202012Validator(FingerprintV2.model_json_schema()).validate(expected)
    assert FingerprintV2.model_validate_json(canonical_json(created)) == model
    assert FingerprintV2.model_validate(created.model_dump()) == model
    assert created.model_dump(by_alias=False)["feature_vector"] == expected["featureVector"]
    path = tmp_path / "fingerprint.json"
    path.write_text(canonical_json(created))
    assert main(["validate", str(path)]) == 0
    result = capsys.readouterr()
    assert result.out == canonical_json(created) and result.err == ""
    assert main(["match", str(path), "--fingerprints", str(tmp_path)]) == 1
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "count,accepted", [(1, False), (4, False), (16, False), (17, True), (22, True)]
)
def test_software_checked_threshold_is_17_of_22(count, accepted):
    response = partial_response(count)
    if accepted:
        assert (
            len(create_fingerprint_v2(response, bottleneck_label="declared").feature_vector)
            == count
        )
    else:
        with pytest.raises(ValidationError, match="sufficient eligible"):
            create_fingerprint_v2(response, bottleneck_label="declared")


@pytest.mark.parametrize("status", ["unreviewed", "rejected"])
def test_explicit_audit_status_retains_lesser_evidence(status):
    response = partial_response(1)
    model = create_fingerprint_v2(response, bottleneck_label="audit", validation_status=status)
    assert len(model.feature_vector) == 1 and model.validation_status == status
    assert model.model_dump(mode="json", by_alias=True) == fingerprint_payload(
        label="audit", status=status, response=response.model_dump(mode="json", by_alias=True)
    )


@pytest.mark.parametrize("status", ["unreviewed", "software_checked", "rejected"])
def test_invalid_response_cannot_be_stored_even_with_audit_status(status):
    response = AnalyticalResponseV2.model_validate(response_payload(confounder="intervention"))
    with pytest.raises(ValidationError, match="valid analytical response"):
        create_fingerprint_v2(response, bottleneck_label="declared", validation_status=status)


@pytest.mark.parametrize(
    "field,value",
    [
        ("fingerprintId", "forged"),
        ("contractVersion", "1.0.0"),
        ("schemaVersion", "fingerprint-v1"),
        ("provenance", "controlled_real"),
        ("validationStatus", "validated"),
        ("validationStatus", True),
        ("bottleneckLabel", ""),
        ("bottleneckLabel", "   "),
        ("bottleneckLabel", "/private/secret"),
        ("bottleneckLabel", "https://secret"),
        ("bottleneckLabel", "label\n"),
        ("bottleneckLabel", True),
        ("notes", "private content"),
    ],
)
def test_forged_root_fields_and_unsanitized_labels_fail(field, value):
    payload = fingerprint_payload()
    payload[field] = value
    with pytest.raises(ValidationError):
        FingerprintV2.model_validate(payload)


@pytest.mark.parametrize("kind", ["changed", "missing", "extra", "bool", "nan", "null", "set"])
def test_vector_must_reconstruct_exactly(kind):
    payload = fingerprint_payload()
    name = next(iter(payload["featureVector"]))
    if kind == "missing":
        del payload["featureVector"][name]
    elif kind == "extra":
        payload["featureVector"]["client.frames_decoded_window_total"] = 1
    elif kind == "set":
        payload["featureVector"] = set(payload["featureVector"])
    else:
        payload["featureVector"][name] = {
            "changed": -0.500001,
            "bool": True,
            "nan": float("nan"),
            "null": None,
        }[kind]
    with pytest.raises(ValidationError):
        FingerprintV2.model_validate(payload)


def test_deterministic_creation_detaches_inputs_and_revalidates_nested_copies():
    payload = fingerprint_payload()
    original = deepcopy(payload)
    model = FingerprintV2.model_validate(payload)
    response = model.response
    before = canonical_json(response)
    a = create_fingerprint_v2(response, bottleneck_label="network_pressure")
    b = create_fingerprint_v2(response, bottleneck_label="network_pressure")
    assert canonical_json(a) == canonical_json(b) == canonical_json(model)
    assert before == canonical_json(response) and payload == original
    name = next(iter(payload["featureVector"]))
    payload["featureVector"][name] = 999
    assert a.feature_vector[name] == -0.5
    with pytest.raises(TypeError):
        a.feature_vector[name] = 999
    with pytest.raises(ValidationError):
        FingerprintV2.model_validate(a.model_copy(update={"feature_vector": {name: True}}))
    with pytest.raises(ValidationError):
        create_fingerprint_v2(
            response.model_copy(
                update={"is_valid": True, "invalid_reason_codes": ("confounded_pair",)}
            ),
            bottleneck_label="declared",
        )


def test_declared_label_and_status_affect_identity():
    response = AnalyticalResponseV2.model_validate(response_payload())
    records = [
        create_fingerprint_v2(response, bottleneck_label=label, validation_status=status)
        for label, status in [
            ("network_pressure", "software_checked"),
            ("encoder_pressure", "software_checked"),
            ("network_pressure", "unreviewed"),
        ]
    ]
    assert len({r.fingerprint_id for r in records}) == 3
    assert all(r.provenance.value == "synthetic" for r in records)


def test_real_provenance_is_preserved_and_cannot_be_forged():
    response = derive_analytical_response(
        ObservationRecordV2.model_validate(pair_payload(real=True)),
        FeaturePolicyV1.model_validate(policy_payload()),
    )
    fingerprint = create_fingerprint_v2(response, bottleneck_label="declared")
    assert fingerprint.provenance.value == "controlled_real"
    payload = fingerprint.model_dump(mode="json", by_alias=True)
    payload["provenance"] = "synthetic"
    with pytest.raises(ValidationError, match="provenance"):
        FingerprintV2.model_validate(payload)
