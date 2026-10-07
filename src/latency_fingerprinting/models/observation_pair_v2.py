"""Strict recorded intervention and comparability of two additive N2 windows."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from .common import NonEmptyStr, PositiveFiniteFloat, ProvenanceKind, RestorationStatus, WindowPhase
from .measurement import SemanticVersion
from .observation_v2 import ObservationWindowV2
from .v2_common import ConfounderCode, ImmutableJSONMap, V2Model, json_equal


class InterventionV2(V2Model):
    probe_id: NonEmptyStr
    probe_type: Literal["stream_profile_relief"]
    probe_version: SemanticVersion
    requested_settings: ImmutableJSONMap
    observed_settings: ImmutableJSONMap | None
    intensity: PositiveFiniteFloat
    application_method: Literal["paired_run", "simulated_pair"]
    execution_status: Literal["not_executed", "executed", "failed"]
    restoration_status: RestorationStatus
    degraded_window_id: NonEmptyStr
    relief_window_id: NonEmptyStr
    paired_window_order: tuple[Literal["degraded"], Literal["relief"]]
    confounder_codes: tuple[ConfounderCode, ...] = ()

    @model_validator(mode="after")
    def validate_intervention(self):
        if (
            not self.requested_settings
            or self.observed_settings is not None
            and not self.observed_settings
        ):
            raise ValueError("intervention settings cannot be empty")
        if self.degraded_window_id == self.relief_window_id:
            raise ValueError("intervention requires distinct windows")
        if len(set(self.confounder_codes)) != len(self.confounder_codes):
            raise ValueError("confounder codes cannot contain duplicates")
        if self.application_method == "simulated_pair":
            if (
                self.execution_status != "not_executed"
                or self.observed_settings is not None
                or self.restoration_status is not RestorationStatus.NOT_EXECUTED
            ):
                raise ValueError("simulated intervention cannot claim runtime execution")
        elif (
            self.execution_status != "executed"
            or self.observed_settings is None
            or self.restoration_status
            in {RestorationStatus.NOT_APPLICABLE, RestorationStatus.NOT_EXECUTED}
        ):
            raise ValueError(
                "paired-run intervention requires execution, settings and restoration outcome"
            )
        return self


class ObservationRecordV2(V2Model):
    schema_version: Literal["observation-v2"]
    contract_version: Literal["2.0.0"]
    observation_id: NonEmptyStr
    comparison_case_id: NonEmptyStr
    degraded_window: ObservationWindowV2
    relief_window: ObservationWindowV2
    intervention: InterventionV2

    @model_validator(mode="after")
    def validate_pair(self):
        degraded, relief, probe = self.degraded_window, self.relief_window, self.intervention
        if (
            degraded.phase is not WindowPhase.DEGRADED
            or relief.phase is not WindowPhase.RELIEF
            or degraded.window_id == relief.window_id
            or degraded.comparison_case_id != self.comparison_case_id
            or relief.comparison_case_id != self.comparison_case_id
            or probe.degraded_window_id != degraded.window_id
            or probe.relief_window_id != relief.window_id
        ):
            raise ValueError("pair identities, phases and intervention references must agree")
        if not json_equal(
            degraded.context.model_dump(mode="json"), relief.context.model_dump(mode="json")
        ):
            raise ValueError("paired context identities must match")
        if (
            degraded.registry != relief.registry
            or degraded.capture_method != relief.capture_method
            or degraded.provenance != relief.provenance
            or degraded.clock.basis != relief.clock.basis
            or degraded.clock.provenance != relief.clock.provenance
        ):
            raise ValueError("pair registry, method and clock meanings must match")
        if not degraded.validity.is_valid or not relief.validity.is_valid:
            raise ValueError("pair requires valid windows")
        durations = (degraded.clock.duration_ms, relief.clock.duration_ms)
        if abs(durations[0] - durations[1]) / max(durations) > 0.10:
            raise ValueError("paired durations differ by more than 10 percent")
        synthetic = degraded.provenance is ProvenanceKind.SYNTHETIC
        if (probe.application_method == "simulated_pair") != synthetic:
            raise ValueError(
                "simulated pairs require synthetic windows; real pairs require paired_run"
            )
        for setting, requested in probe.requested_settings.items():
            if setting not in relief.effective_settings or not json_equal(
                relief.effective_settings[setting], requested
            ):
                raise ValueError("requested relief setting was not applied")
            if setting in degraded.effective_settings and json_equal(
                degraded.effective_settings[setting], requested
            ):
                raise ValueError("requested setting did not change")
        if probe.observed_settings is not None and any(
            setting not in relief.effective_settings
            or not json_equal(value, relief.effective_settings[setting])
            for setting, value in probe.observed_settings.items()
        ):
            raise ValueError("observed settings disagree with relief")
        settings = set(degraded.effective_settings) | set(relief.effective_settings)
        changed = {
            key
            for key in settings
            if key not in degraded.effective_settings
            or key not in relief.effective_settings
            or not json_equal(degraded.effective_settings[key], relief.effective_settings[key])
        }
        if changed - set(probe.requested_settings) and not (
            degraded.confounder_codes or relief.confounder_codes or probe.confounder_codes
        ):
            raise ValueError("undeclared setting changes require confounder codes")
        return self
