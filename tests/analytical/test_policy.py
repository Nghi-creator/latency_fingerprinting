"""Only the independently specified provisional release can enter N3 records."""

import hashlib

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from latency_fingerprinting.analytical import policy_release
from latency_fingerprinting.cli import main
from latency_fingerprinting.models import FeaturePolicyV1
from latency_fingerprinting.pipeline import canonical_json

from .cases import POLICY_SPEC, canonical, policy_payload

FEATURE = "transport.jitter_ms"


def test_approved_release_reproduces_specification_and_schema(capsys):
    payload = policy_release.approved_policy_payload()
    assert canonical(payload) == POLICY_SPEC.read_bytes()
    model = FeaturePolicyV1.model_validate(payload)
    assert len(model.features) == 22
    assert canonical_json(model).encode() == POLICY_SPEC.read_bytes()
    Draft202012Validator(FeaturePolicyV1.model_json_schema()).validate(payload)
    assert main(["validate", str(POLICY_SPEC)]) == 0
    output = capsys.readouterr()
    assert output.out.encode() == POLICY_SPEC.read_bytes() and output.err == ""


@pytest.mark.parametrize(
    "path,value",
    [
        (("policyVersion",), "2.0.0"),
        (("contentHash",), "sha256:" + "0" * 64),
        (("parameterProvenance",), "experimentally_calibrated"),
        (("responseMethod",), "other"),
        (("registry", "registryVersion"), "latency-metrics-v9.0.0"),
        (("registry", "contentHash"), "sha256:" + "0" * 64),
        (("features", FEATURE, "epsilon"), 0),
        (("features", FEATURE, "epsilon"), True),
        (("features", FEATURE, "epsilon"), 2),
        (("features", FEATURE, "epsilon"), "1"),
        (("features", FEATURE, "epsilon"), float("inf")),
        (("features", FEATURE, "weight"), 0),
        (("features", FEATURE, "weight"), True),
        (("features", FEATURE, "clipMaximum"), 4),
        (("features", FEATURE, "minimumCoverage"), 0.5),
        (("features", FEATURE, "minimumUsableSamples"), True),
        (("features", FEATURE, "minimumAcceptedIntervals"), 0),
        (("features", FEATURE, "allowedStatuses"), ["complete", "complete"]),
        (("features", FEATURE, "allowedStatuses"), {"complete"}),
        (("features", FEATURE, "unit"), "fps"),
        (("features", FEATURE, "source"), "encoder_pipeline"),
        (("features", FEATURE, "aggregation"), "maximum"),
        (("features", FEATURE, "semanticVersion"), "2.0.0"),
        (("decision", "minimumSharedFeatures"), True),
        (("decision", "minimumFeatureCoverage"), 0),
        (("decision", "minimumMatchStrength"), 1.01),
        (("maximumRankedCandidates",), 0),
        (("unexpected",), "private metadata"),
    ],
)
def test_policy_rejects_altered_release_or_strict_fields(path, value):
    payload = policy_payload()
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValidationError):
        FeaturePolicyV1.model_validate(payload)


@pytest.mark.parametrize("change", ["parameter", "omitted", "audit_total", "proxy"])
def test_recomputed_hash_does_not_approve_a_different_release(change):
    payload = policy_payload()
    if change == "parameter":
        payload["features"][FEATURE]["epsilon"] = 2.0
    elif change == "omitted":
        del payload["features"][FEATURE]
    else:
        name = (
            "client.frames_decoded_window_total"
            if change == "audit_total"
            else "encoder.pipeline_delay_proxy_ms"
        )
        payload["features"][name] = payload["features"][FEATURE].copy()
    hashed = {k: v for k, v in payload.items() if k != "contentHash"}
    payload["contentHash"] = "sha256:" + hashlib.sha256(canonical(hashed)).hexdigest()
    with pytest.raises(ValidationError, match="approved release"):
        FeaturePolicyV1.model_validate(payload)


def test_policy_detaches_maps_and_revalidates_copied_nested_models():
    payload = policy_payload()
    model = FeaturePolicyV1.model_validate(payload)
    payload["features"][FEATURE]["epsilon"] = 99
    assert model.features[FEATURE].epsilon == 1
    with pytest.raises(TypeError):
        model.features[FEATURE] = model.features[FEATURE]
    with pytest.raises(ValidationError):
        model.features[FEATURE].epsilon = 99
    copied = model.features[FEATURE].model_copy(update={"epsilon": False})
    payload = policy_payload()
    payload["features"][FEATURE] = copied
    with pytest.raises(ValidationError):
        FeaturePolicyV1.model_validate(payload)
    assert FeaturePolicyV1.model_validate_json(canonical_json(model)) == model
    assert "semantic_version" in model.model_dump()["features"][FEATURE]


def test_trusted_policy_source_drift_fails_without_consulting_spec(monkeypatch):
    monkeypatch.setattr(policy_release, "POLICY_CONTENT_HASH", "sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="reviewed release"):
        policy_release.approved_policy_payload()
