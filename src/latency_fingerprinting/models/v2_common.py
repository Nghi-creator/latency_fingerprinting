"""Immutable JSON, context and registry identity for additive N2 contracts."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BeforeValidator,
    ConfigDict,
    Field,
    JsonValue,
    PlainSerializer,
    field_validator,
    model_validator,
)

from .common import ContractModel, NonEmptyStr, json_values_equal
from .measurement import SemanticVersion

V2_CONTRACT_VERSION = "2.0.0"
OBSERVATION_WINDOW_V2_SCHEMA_VERSION = "observation-window-v2"
OBSERVATION_V2_SCHEMA_VERSION = "observation-v2"
REGISTRY_CONTENT_HASH = "sha256:50329d193303c271194b28e9164ae8627dd257d7620174c5ab136ba209864884"
ContentHash = Annotated[str, Field(strict=True, pattern=r"^sha256:[0-9a-f]{64}$")]
ConfounderCode = Literal["composite_profile_change", "other_setting_change", "operator_declared"]


def thaw_json(value):
    """Return JSON containers without retaining caller-owned mutable objects."""
    if isinstance(value, Mapping):
        return {key: thaw_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [thaw_json(item) for item in value]
    return value


def _freeze_json(value):
    if isinstance(value, Mapping):
        for key in value:
            normalized = "".join(char for char in key.lower() if char.isalnum())
            if normalized in {
                "absolutepath",
                "enginetoken",
                "hostname",
                "username",
                "peerid",
                "rawpeerid",
                "shareurl",
                "notes",
            }:
                raise ValueError("private metadata keys are not permitted")
        return MappingProxyType({key: _freeze_json(item) for key, item in sorted(value.items())})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            finite = math.isfinite(value)
        except OverflowError as error:
            raise ValueError("JSON number exceeds the finite numeric range") from error
        if not finite:
            raise ValueError("JSON numbers must be finite")
    return value


ImmutableJSONMap = Annotated[
    Mapping[NonEmptyStr, JsonValue],
    BeforeValidator(thaw_json),
    AfterValidator(_freeze_json),
    PlainSerializer(thaw_json, return_type=dict),
]
ImmutableStringMap = Annotated[
    Mapping[NonEmptyStr, NonEmptyStr],
    AfterValidator(_freeze_json),
    PlainSerializer(thaw_json, return_type=dict),
]


def json_equal(left, right):
    return json_values_equal(thaw_json(left), thaw_json(right))


class V2Model(ContractModel):
    model_config = ConfigDict(frozen=True, validate_default=True, revalidate_instances="always")

    @field_validator("*", mode="before")
    @classmethod
    def reject_unordered_values(cls, value):
        if isinstance(value, (set, frozenset)):
            raise ValueError("ordered contract collections cannot be sets")
        return value


class V2ContextSnapshot(V2Model):
    context_id: NonEmptyStr
    compatibility_group: NonEmptyStr
    edge_node_class: NonEmptyStr
    node_id: NonEmptyStr
    operating_system: NonEmptyStr
    runtime_class: NonEmptyStr
    workload_id: NonEmptyStr
    capture_implementation: NonEmptyStr
    encoder_family: NonEmptyStr
    encoder_profile: NonEmptyStr
    transport_implementation: NonEmptyStr
    connection_mode: NonEmptyStr
    client_class: NonEmptyStr
    nominal_stream_profile: ImmutableJSONMap
    network_scenario: NonEmptyStr | None
    versions: ImmutableStringMap

    @model_validator(mode="after")
    def validate_profile(self):
        if not self.nominal_stream_profile:
            raise ValueError("nominal stream profile cannot be empty")
        return self


def trusted_registry():
    # Lazy resolution avoids a model/schema/registry import cycle. Never resolve
    # a path or URL supplied by a record.
    from ..measurement.metric_registry import CANONICAL_METRIC_REGISTRY, render_metric_registry

    content_hash = "sha256:" + hashlib.sha256(render_metric_registry().encode("utf-8")).hexdigest()
    if content_hash != REGISTRY_CONTENT_HASH:
        raise ValueError("trusted registry content changed without a reviewed release")
    return CANONICAL_METRIC_REGISTRY


class RegistryReference(V2Model):
    registry_version: Literal["latency-metrics-v2.0.0"]
    content_hash: ContentHash

    @model_validator(mode="after")
    def validate_release(self):
        trusted_registry()
        if self.content_hash != REGISTRY_CONTENT_HASH:
            raise ValueError("unknown registry version/content hash pair")
        return self


class CaptureMethodReference(V2Model):
    method_id: Literal["pixelated_bundle_offline", "synthetic_series"]
    method_version: SemanticVersion
    producer_version: NonEmptyStr | None

    @model_validator(mode="after")
    def validate_method(self):
        if self.method_version != "1.0.0":
            raise ValueError("capture method/version is not approved")
        return self


class SourceArtifactV2(V2Model):
    source_type: Literal["pixelated_bundle", "synthetic_series"]
    content_hash: ContentHash
    bundle_schema_version: Literal["1", "2"] | None

    @model_validator(mode="after")
    def validate_source_type(self):
        if (self.source_type == "pixelated_bundle") != (self.bundle_schema_version is not None):
            raise ValueError("artifact type and bundle schema version disagree")
        return self
