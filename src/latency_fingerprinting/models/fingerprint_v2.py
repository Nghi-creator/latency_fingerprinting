"""Immutable v2 fingerprints reconstructed from retained analytical evidence."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Literal

from pydantic import (
    Field,
    FieldSerializationInfo,
    field_serializer,
    field_validator,
    model_validator,
)

from ..analytical.policy_release import payload_hash
from .analytical_response_v2 import AnalyticalResponseV2
from .common import FiniteFloat, NonEmptyStr, ProvenanceKind
from .measurement import MetricName
from .v2_common import V2Model

FINGERPRINT_V2_SCHEMA_VERSION = "fingerprint-v2"
FingerprintValidationStatusV2 = Literal["unreviewed", "software_checked", "rejected"]
# Labels are declared identifiers, with no paths, URLs or free-form private notes.
BottleneckLabelV2 = Annotated[str, Field(strict=True, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")]


class FingerprintV2(V2Model):
    schema_version: Literal["fingerprint-v2"]
    contract_version: Literal["2.0.0"]
    fingerprint_id: NonEmptyStr
    bottleneck_label: BottleneckLabelV2
    provenance: ProvenanceKind
    validation_status: FingerprintValidationStatusV2
    response: AnalyticalResponseV2
    feature_vector: Mapping[MetricName, FiniteFloat]

    @field_validator("feature_vector", mode="after")
    @classmethod
    def freeze_vector(cls, value):
        return MappingProxyType(dict(sorted(value.items())))

    @field_serializer("feature_vector")
    def serialize_vector(self, value: Mapping, info: FieldSerializationInfo):
        return dict(value)

    @model_validator(mode="after")
    def validate_fingerprint(self):
        if not self.response.is_valid:
            raise ValueError("fingerprint requires a valid analytical response")
        if self.provenance != self.response.observation.degraded_window.provenance:
            raise ValueError("fingerprint provenance must equal its retained observation")
        expected = {
            name: feature.normalized_value
            for name, feature in self.response.features.items()
            if feature.state == "eligible"
        }
        if dict(self.feature_vector) != expected:
            raise ValueError(
                "fingerprint vector must reconstruct exactly from eligible response features"
            )
        decision = self.response.policy.decision
        if self.validation_status == "software_checked" and (
            len(expected) < decision.minimum_shared_features
            or len(expected) / len(self.response.policy.features)
            < decision.minimum_feature_coverage
        ):
            raise ValueError("software checking requires sufficient eligible features")
        digest = payload_hash(
            {
                "response": self.response.model_dump(mode="json", by_alias=True),
                "bottleneckLabel": self.bottleneck_label,
                "validationStatus": self.validation_status,
            }
        )
        if self.fingerprint_id != "fingerprint-v2-" + digest[7:]:
            raise ValueError("fingerprint identity must derive from its response, label and status")
        return self
