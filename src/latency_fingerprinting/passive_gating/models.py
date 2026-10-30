"""Immutable N9 roots reconstruct every retained statistic and replay transition."""

from typing import Annotated, Literal

from pydantic import Field, StrictBool, field_validator, model_validator

from ..analytical.policy_release import canonical_payload_bytes, payload_hash
from ..calibration.contracts import (
    Alias,
    Count,
    DatasetID,
    GroupID,
    Hash,
    OriginalID,
    check_identity,
    check_json_size,
    exact_string,
    unique_order,
)
from ..models.common import ProvenanceKind
from ..models.observation_v2 import ObservationWindowV2
from ..models.v2_common import CaptureMethodReference, ImmutableJSONMap, RegistryReference
from .contracts import (
    ASSURANCE,
    METADATA_REASONS,
    QUALITY_REASONS,
    RELEASE,
    ROW_REASONS,
    STRATUM_REASONS,
    BaselineID,
    Duration,
    EventID,
    GateModel,
    Mode,
    Nonnegative,
    NoveltyID,
    RootModel,
    StratumID,
    StreamID,
    Time,
)
from .evidence import Evidence, bounds, validate_context
from .policy import PassiveGatePolicy


def same(actual, expected):
    if hasattr(actual, "model_dump"):
        actual = actual.model_dump(mode="json")
    if canonical_payload_bytes(actual) != canonical_payload_bytes(expected):
        raise ValueError("N9 retained evidence does not reconstruct")


def identity(model, name, prefix):
    digest = check_identity(model, name, prefix, (name, "content_hash"))
    if model.content_hash != digest:
        raise ValueError("N9 content hash mismatch")
    check_json_size(model)


class ScopeClock(GateModel):
    basis: Literal["source_elapsed_ms"]
    provenance: Literal["wall_clock_derived_elapsed", "synthetic_elapsed"]


class SourceFormat(GateModel):
    source_type: Literal["pixelated_bundle", "synthetic_series"]
    bundle_schema_version: Literal["1", "2"] | None

    @model_validator(mode="after")
    def source_type_binding(self):
        if (self.source_type == "pixelated_bundle") != (self.bundle_schema_version is not None):
            raise ValueError("N9 source format mismatch")
        return self


class PassiveScope(GateModel):
    registry: RegistryReference
    provenance: ProvenanceKind
    capture_method: CaptureMethodReference
    clock: ScopeClock
    source_format: SourceFormat
    context: ImmutableJSONMap
    effective_settings: ImmutableJSONMap

    @field_validator("context")
    @classmethod
    def context_binding(cls, value):
        return validate_context(value)


class BaselineInput(GateModel):
    entry_id: Alias
    group_id: GroupID | None
    stratum_id: StratumID | None
    window: ObservationWindowV2 | None
    selected: StrictBool
    reason_codes: Annotated[
        tuple[Literal[*METADATA_REASONS, *QUALITY_REASONS], ...], Field(max_length=12)
    ]


class BaselineGroup(GateModel):
    group_id: GroupID
    entry_ids: Annotated[tuple[Alias, ...], Field(min_length=1, max_length=256)]
    selected_entry_ids: Annotated[tuple[Alias, ...], Field(max_length=256)]
    value: Nonnegative | None


class BaselineStratum(GateModel):
    stratum_id: StratumID
    scope: PassiveScope
    groups: Annotated[tuple[BaselineGroup, ...], Field(min_length=1, max_length=256)]
    center: Nonnegative | None
    raw_mad: Nonnegative | None
    state: Literal["provisional", "rejected"]
    reason_codes: Annotated[tuple[Literal[*STRATUM_REASONS], ...], Field(max_length=4)]


class BaselineCounts(GateModel):
    retained_entries: Count
    metadata_eligible_entries: Count
    selected_entries: Count
    excluded_entries: Count
    retained_strata: Count
    provisional_strata: Count


class PassiveBaseline(RootModel):
    schema_version: Literal["passive-baseline-v1"]
    method_release: Literal[RELEASE]
    baseline_id: BaselineID
    content_hash: Hash
    policy: PassiveGatePolicy
    evidence: Evidence
    inputs: Annotated[tuple[BaselineInput, ...], Field(max_length=256)]
    strata: Annotated[tuple[BaselineStratum, ...], Field(max_length=256)]
    state: Literal["provisional", "rejected"]
    counts: BaselineCounts
    assurance: Literal[ASSURANCE]

    @model_validator(mode="after")
    def reconstruct(self):
        from .baseline import reconstruct_baseline

        strata, counts, state = reconstruct_baseline(self.evidence, self.inputs)
        same([s.model_dump(mode="json") for s in self.strata], strata)
        same(self.counts, counts)
        if self.state != state:
            raise ValueError("N9 baseline state does not reconstruct")
        identity(self, "baseline_id", "passive-baseline-")
        return self


class PassiveStream(GateModel):
    acquisition_namespace: Alias
    run_id: OriginalID
    clock_domain_id: OriginalID
    generation_id: Alias
    stratum_id: StratumID
    stream_id: StreamID


class ReplayWindow(GateModel):
    artifact_id: Alias
    window: ObservationWindowV2

    @model_validator(mode="after")
    def integral_time(self):
        bounds(self.window)
        return self


RESET_REASONS = (
    "disconnect",
    "context_changed",
    "clock_changed",
    "generation_changed",
    "operator_reset",
    "clock_unavailable",
)


class PassiveEvent(GateModel):
    event_id: EventID
    kind: Literal["window", "tick", "reset"]
    at_ms: Time
    entry_id: Alias | None
    reset_reason: Literal[*RESET_REASONS] | None

    @model_validator(mode="after")
    def binding(self):
        if (self.kind == "window") != (self.entry_id is not None) or (
            (self.kind == "reset") != (self.reset_reason is not None)
        ):
            raise ValueError("N9 event fields disagree")
        body = self.model_dump(mode="json", exclude={"event_id"})
        if (
            self.event_id
            != "passive-event-" + payload_hash(dict(method_release=RELEASE, event=body))[7:]
        ):
            raise ValueError("N9 event identity mismatch")
        return self


class PassiveReplay(RootModel):
    schema_version: Literal["passive-replay-v1"]
    method_release: Literal[RELEASE]
    replay_id: exact_string(r"passive-replay-[a-f0-9]{64}")
    content_hash: Hash
    policy_content_hash: Hash
    baseline_id: BaselineID
    dataset_id: DatasetID
    mode: Mode
    stream: PassiveStream
    start_ms: Time
    windows: Annotated[tuple[ReplayWindow, ...], Field(max_length=256)]
    events: Annotated[tuple[PassiveEvent, ...], Field(max_length=256)]
    assurance: Literal[ASSURANCE]

    @model_validator(mode="after")
    def reconstruct(self):
        from .policy_release import POLICY_HASH

        if self.policy_content_hash != POLICY_HASH:
            raise ValueError("N9 replay policy mismatch")
        unique_order(self.windows, lambda row: row.artifact_id)
        body = self.stream.model_dump(mode="json", exclude={"stream_id"})
        expected = payload_hash(
            dict(
                method_release=RELEASE,
                baseline_id=self.baseline_id,
                dataset_id=self.dataset_id,
                stream=body,
            )
        )
        if self.stream.stream_id != "passive-stream-" + expected[7:]:
            raise ValueError("N9 stream identity mismatch")
        identity(self, "replay_id", "passive-replay-")
        return self


class PassiveState(GateModel):
    status: Literal[
        "unknown", "pending_degradation", "pending_recovery", "healthy", "degraded", "recovering"
    ]
    degraded_latched: StrictBool
    watermark_ms: Time
    last_window_end_ms: Time | None
    last_valid_end_ms: Time | None
    barrier_ms: Time
    bad_windows: Count
    bad_duration_ms: Duration
    good_windows: Count
    good_duration_ms: Duration
    proposals: Annotated[int, Field(strict=True, ge=0, le=3)]
    last_proposal_ms: Time | None
    stream_invalidated: StrictBool


class PassiveRow(GateModel):
    event_index: Annotated[int, Field(strict=True, ge=0, le=255)]
    event_id: EventID
    entry_id: Alias | None
    window_artifact_id: Alias | None
    novelty_key: NoveltyID | None
    classification: Literal["low", "recovered", "band", "unavailable"]
    observed_fps: Nonnegative | None
    relative_fps: Nonnegative | None
    recommendation: Literal["observe", "probe", "cooldown", "no_action"]
    reason_codes: Annotated[tuple[Literal[*ROW_REASONS], ...], Field(min_length=1, max_length=10)]
    effect_hypothesis: Literal["received_fps_degradation"] | None
    cause_label: None
    profile_hypotheses: Literal["unavailable"]
    state: PassiveState


class ReplayCounts(GateModel):
    total_events: Count
    window_events: Count
    tick_events: Count
    reset_events: Count
    accepted_windows: Count
    ignored_duplicate_windows: Count
    ignored_out_of_order_windows: Count
    unavailable_windows: Count
    proposals: Annotated[int, Field(strict=True, ge=0, le=3)]


class PassiveGateResult(RootModel):
    schema_version: Literal["passive-gate-result-v1"]
    method_release: Literal[RELEASE]
    result_id: exact_string(r"passive-gate-[a-f0-9]{64}")
    content_hash: Hash
    policy: PassiveGatePolicy
    baseline: PassiveBaseline
    replay: PassiveReplay
    rows: Annotated[tuple[PassiveRow, ...], Field(max_length=256)]
    final_state: PassiveState
    counts: ReplayCounts
    assurance: Literal[ASSURANCE]

    @model_validator(mode="after")
    def reconstruct(self):
        from .replay import reconstruct_replay

        if self.policy != self.baseline.policy:
            raise ValueError("N9 result policy mismatch")
        rows, final, counts = reconstruct_replay(self.baseline, self.replay)
        same([r.model_dump(mode="json") for r in self.rows], rows)
        same(self.final_state, final)
        same(self.counts, counts)
        identity(self, "result_id", "passive-gate-")
        return self
