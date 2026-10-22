"""Immutable N8 roots reconstruct every decision, refit, identity and denominator."""

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from ..analytical.policy_release import canonical_payload_bytes
from ..calibration.contracts import (
    Alias,
    Count,
    GroupID,
    Hash,
    Label,
    OriginalID,
    PartitionID,
    check_identity,
    check_json_size,
    exact_string,
)
from ..profiles.contracts import SELECTION_REASONS, FeatureName, Finite
from ..profiles.evidence import Candidate, Ratio
from .contracts import (
    ASSURANCE,
    CANDIDATE_REASONS,
    DECISION_REASONS,
    FEATURE_REASONS,
    CandidateID,
    FoldID,
    MatchModel,
    Mode,
    Nonnegative,
    RefitID,
    result_budget,
)
from .evaluation import evaluation_inventory, refit_profiles, refit_work_budget, summarize
from .evidence import Evidence
from .policy import ProfileMatchPolicy
from .scoring import reconstruct_decision


def same(actual, expected):
    payload = actual.model_dump(mode="json") if hasattr(actual, "model_dump") else actual
    if canonical_payload_bytes(payload) != canonical_payload_bytes(expected):
        raise ValueError("N8 result does not reconstruct")


class FeatureScore(MatchModel):
    state: Literal["included", "excluded"]
    reason_codes: Annotated[tuple[Literal[*FEATURE_REASONS], ...], Field(max_length=3)]
    query_value: Finite | None
    center: Finite | None
    dispersion: Nonnegative | None
    profile_weight: Annotated[Finite, Field(ge=0, le=1)]
    applied_weight: Annotated[Finite, Field(ge=0, le=1)]
    absolute_deviation: Nonnegative | None
    standardized_deviation: Nonnegative | None
    weighted_contribution: Nonnegative | None


class CandidateScore(MatchModel):
    profile_id: CandidateID
    partition_id: PartitionID
    label: Label
    state: Literal["excluded", "scored"]
    reason_codes: Annotated[tuple[Literal[*CANDIDATE_REASONS], ...], Field(max_length=7)]
    features: (
        Annotated[Mapping[FeatureName, FeatureScore], Field(min_length=22, max_length=22)] | None
    )
    weight_sum: Annotated[Finite, Field(gt=0, le=22)] | None
    distance: Nonnegative | None


class QueryDecision(MatchModel):
    query_entry_id: Alias
    query_artifact_id: Alias | None
    query_record_id: OriginalID | None
    query_mode: Literal["held_out", "leave_training_group_out"]
    excluded_group_id: GroupID | None
    refit_id: RefitID | None
    query_feature_values: (
        Annotated[Mapping[FeatureName, Finite | None], Field(min_length=22, max_length=22)] | None
    )
    candidates: Annotated[tuple[CandidateScore, ...], Field(max_length=256)]
    common_feature_names: Annotated[tuple[FeatureName, ...], Field(max_length=22)]
    common_coverage: Ratio
    ranked_profile_ids: Annotated[tuple[CandidateID, ...], Field(max_length=256)]
    best_label: Label | None
    runner_up_label: Label | None
    best_distance: Nonnegative | None
    runner_up_distance: Nonnegative | None
    margin: Nonnegative | None
    state: Literal["provisional_match", "unknown"]
    chosen_label: Label | None
    reason_codes: Annotated[tuple[Literal[*DECISION_REASONS], ...], Field(max_length=12)]


class FoldInput(MatchModel):
    entry_id: Alias
    selected: Annotated[bool, Field(strict=True)]
    reason_codes: Annotated[
        tuple[Literal[*SELECTION_REASONS, "leave_source_group_out"], ...], Field(max_length=8)
    ]
    feature_values: (
        Annotated[Mapping[FeatureName, Finite | None], Field(min_length=22, max_length=22)] | None
    )


class FoldCandidate(Candidate):
    profile_id: FoldID


class RefitCounts(MatchModel):
    retained_entries: Count
    base_selected_entries: Count
    removed_entries: Count
    selected_entries: Count
    excluded_entries: Count
    selected_groups: Count


class Refit(MatchModel):
    @field_validator("*", mode="before")
    @classmethod
    def bound_containers(cls, value, info):
        if value is None and info.field_name in ("inputs", "profiles"):
            return value
        return super().bound_containers(value, info)

    refit_id: RefitID
    excluded_group_id: GroupID
    state: Literal["computed", "skipped"]
    reason_codes: Annotated[
        tuple[Literal["snapshot_unavailable", "no_eligible_queries"], ...], Field(max_length=2)
    ]
    inputs: Annotated[tuple[FoldInput, ...], Field(max_length=256)] | None
    profiles: Annotated[tuple[FoldCandidate, ...], Field(max_length=256)] | None
    counts: RefitCounts | None


class GroupOutcome(MatchModel):
    group_id: GroupID
    entry_ids: Annotated[tuple[Alias, ...], Field(min_length=1, max_length=256)]
    representative_entry_ids: Annotated[tuple[Alias, ...], Field(min_length=1, max_length=256)]
    truth_label: Label | None
    truth_reason_codes: Annotated[
        tuple[Literal["label_unverified", "mixed_labels"], ...], Field(max_length=2)
    ]
    predicted_label: Label | None
    prediction_reason_codes: Annotated[
        tuple[Literal["entry_unknown", "entry_disagreement"], ...], Field(max_length=2)
    ]


class EvaluationCounts(MatchModel):
    retained_entries: Count
    global_missing_entries: Count
    evaluated_entries: Count
    response_entries: Count
    baseline_entries: Count
    n6_excluded_entries: Count
    duplicate_entries: Count
    classification_groups: Count
    baseline_only_groups: Count
    known_truth_groups: Count
    unverified_truth_groups: Count
    provisional_match_groups: Count
    unknown_groups: Count
    correct_groups: Count
    incorrect_groups: Count
    computed_refits: Count
    skipped_refits: Count


class EvaluationMetrics(MatchModel):
    accuracy: Ratio
    unknown_rate: Ratio
    truth_coverage: Ratio


class ResultBase(MatchModel):
    method_release: Literal["n8-profile-matching-v1"]
    content_hash: Hash
    policy: ProfileMatchPolicy
    evidence: Evidence
    assurance: Literal[ASSURANCE]

    @model_validator(mode="before")
    @classmethod
    def budget(cls, value):
        return result_budget(value)

    def identity(self, prefix):
        digest = check_identity(self, "result_id", prefix, ("result_id", "content_hash"))
        if self.content_hash != digest:
            raise ValueError("N8 content hash mismatch")
        check_json_size(self)


class ProfileMatchResult(ResultBase):
    schema_version: Literal["profile-match-result-v1"]
    result_id: exact_string(r"profile-match-[a-f0-9]{64}")
    decision: QueryDecision

    @model_validator(mode="after")
    def reconstruct(self):
        decision = self.decision
        if (
            decision.query_mode != "held_out"
            or decision.excluded_group_id is not None
            or decision.refit_id is not None
        ):
            raise ValueError("ordinary match cannot borrow a refit")
        same(decision, reconstruct_decision(self.evidence, decision))
        self.identity("profile-match-")
        return self


class ProfileEvaluationResult(ResultBase):
    schema_version: Literal["profile-evaluation-result-v1"]
    result_id: exact_string(r"profile-evaluation-[a-f0-9]{64}")
    mode: Mode
    refits: Annotated[tuple[Refit, ...], Field(max_length=64)]
    decisions: Annotated[tuple[QueryDecision, ...], Field(max_length=256)]
    group_outcomes: Annotated[tuple[GroupOutcome, ...], Field(max_length=256)]
    confusion_matrix: Annotated[
        Mapping[
            Literal["healthy", "host_contention", "render_capture_slowdown", "unverified_truth"],
            Annotated[
                Mapping[
                    Literal["healthy", "host_contention", "render_capture_slowdown", "unknown"],
                    Count,
                ],
                Field(min_length=4, max_length=4),
            ],
        ],
        Field(min_length=4, max_length=4),
    ]
    counts: EvaluationCounts
    metrics: EvaluationMetrics

    @model_validator(mode="after")
    def reconstruct(self):
        entries = evaluation_inventory(self.evidence, self.mode)
        if tuple(d.query_entry_id for d in self.decisions) != tuple(e.entry_id for e in entries):
            raise ValueError("N8 evaluation query inventory mismatch")
        if len(entries) * len(self.evidence.snapshot.profiles) > 4096:
            raise ValueError("N8 actual candidate work exceeds global budget")
        fold = self.mode == "leave_training_group_out"
        groups = sorted({e.group_id for e in entries if e.input_kind == "response"}) if fold else []
        if tuple(r.excluded_group_id for r in self.refits) != tuple(groups):
            raise ValueError("N8 refit inventory mismatch")
        refit_work_budget(self.evidence, groups)
        for refit, group in zip(self.refits, groups, strict=True):
            same(refit, refit_profiles(self.evidence, group, self.policy.content_hash))
        by_group = {r.excluded_group_id: r for r in self.refits}
        feature_rows = 0
        for decision, entry in zip(self.decisions, entries, strict=True):
            if fold:
                refit = by_group.get(entry.group_id)
                computed = refit is not None and refit.state == "computed"
                profiles = refit.profiles if computed else self.evidence.snapshot.profiles
                identifier = refit.refit_id if computed else None
                expected = reconstruct_decision(
                    self.evidence,
                    decision,
                    profiles,
                    mode="leave_training_group_out",
                    excluded_group_id=entry.group_id,
                    refit_id=identifier,
                    maximum_feature_rows=5632 - feature_rows,
                )
            else:
                expected = reconstruct_decision(
                    self.evidence, decision, maximum_feature_rows=5632 - feature_rows
                )
            feature_rows += sum(
                len(row["features"])
                for row in expected["candidates"]
                if row["features"] is not None
            )
            same(decision, expected)
        expected = summarize(self.evidence, self.mode, self.decisions, self.refits)
        actual = self.model_dump(mode="json")
        for key, value in expected.items():
            same(actual[key], value)
        self.identity("profile-evaluation-")
        return self
