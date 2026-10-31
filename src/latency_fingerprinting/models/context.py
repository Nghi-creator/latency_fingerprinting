"""Shared context identity used by P0 and current measurement ingestion."""

from __future__ import annotations

from pydantic import Field, JsonValue, model_validator

from .common import (
    ContractModel,
    NonEmptyStr,
    json_values_equal,
)


class ContextKey(ContractModel):
    """The explicit boundary within which P0 records may be compared."""

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
    nominal_stream_profile: dict[str, JsonValue]
    network_scenario: str | None = None
    versions: dict[str, str] = Field(default_factory=dict)

    def has_same_identity(self, other: ContextKey) -> bool:
        """Compare context fields without equating JSON booleans and numbers."""

        return json_values_equal(self.model_dump(), other.model_dump())

    @model_validator(mode="after")
    def validate_context_maps(self) -> ContextKey:
        if not self.nominal_stream_profile:
            raise ValueError("nominal_stream_profile cannot be empty")
        for field_name, values in (
            ("nominal_stream_profile", self.nominal_stream_profile),
            ("versions", self.versions),
        ):
            if any(not key.strip() for key in values):
                raise ValueError(f"{field_name} keys cannot be empty")
        if any(not value.strip() for value in self.versions.values()):
            raise ValueError("versions values cannot be empty")
        return self
