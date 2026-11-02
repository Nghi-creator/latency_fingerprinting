"""Bounded offline N11 declarations; no scientific acceptance or live authority."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from ..analytical.policy_release import payload_hash
from ..calibration.contracts import Alias, GroupID, Hash, Label, Role, SplitID, unique_order
from ..json_io import MAX_CONTRACT_JSON_BYTES
from ..observability.contracts import TraceModel
from ..profiles.evidence import Ratio

RELEASE = "n11-offline-evaluation-v1"
MAX_INPUT_BYTES = 1024 * 1024 * 1024
MAX_RECEIPTS = 4096


class EvaluationModel(TraceModel):
    collection_limits = {
        "receipts": 4096,
        "datasets": 160,
        "groups": 4096,
        "slots": 256,
        "diagnoses": 160,
        "passive": 128,
        "live": 128,
        "raw_derivations": 4096,
        "rows": 256,
        "results": 4096,
        "reason_codes": 8,
    }


def identity(model, field, prefix):
    digest = payload_hash(model.model_dump(mode="json", exclude={field, "content_hash"}))
    if model.content_hash != digest or getattr(model, field) != prefix + digest[7:]:
        raise ValueError("evaluation identity mismatch")
    from ..analytical.policy_release import canonical_payload_bytes

    if len(canonical_payload_bytes(model.model_dump(mode="json"))) > MAX_CONTRACT_JSON_BYTES:
        raise ValueError("evaluation root exceeds byte limit")


class Receipt(EvaluationModel):
    receipt_id: Alias
    kind: Literal[
        "protocol",
        "raw_bundle",
        "dataset_manifest",
        "profile_snapshot",
        "response_policy",
        "match_policy",
        "passive_baseline",
        "passive_replay",
        "passive_policy",
        "game_evidence",
        "integrated_evidence",
    ]
    sha256: Hash
    bytes: Annotated[int, Field(strict=True, ge=1, le=64 * 1024 * 1024)]

    @model_validator(mode="after")
    def limit(self):
        if self.kind != "raw_bundle" and self.bytes > MAX_CONTRACT_JSON_BYTES:
            raise ValueError("JSON/protocol receipt exceeds byte limit")
        return self


class Dataset(EvaluationModel):
    dataset_key: Alias
    manifest_receipt: Alias
    content_hash: Hash
    split_id: SplitID


class GroupBinding(EvaluationModel):
    dataset_key: Alias
    group_id: GroupID
    study_group: Alias


class RawDerivation(EvaluationModel):
    dataset_key: Alias
    entry_id: Alias
    window_role: Literal["healthy", "degraded", "relief"]
    raw_receipt: Alias


class Diagnosis(EvaluationModel):
    job_id: Alias
    dataset_key: Alias
    snapshot_receipt: Alias
    response_policy_receipt: Alias
    match_policy_receipt: Alias
    mode: Literal["validation", "final_test"]


class Passive(EvaluationModel):
    job_id: Alias
    dataset_key: Alias
    baseline_receipt: Alias
    replay_receipt: Alias
    policy_receipt: Alias


class Live(EvaluationModel):
    job_id: Alias
    evidence_receipt: Alias


class Slot(EvaluationModel):
    slot_id: Alias
    study_group: Alias
    role: Role
    truth_label: Label | None
    state: Literal["retained", "failed", "not_started"]
    failure_code: Alias | None
    diagnosis_job: Alias | None
    passive_job: Alias | None
    live_job: Alias | None

    @model_validator(mode="after")
    def failure(self):
        if (self.failure_code is not None) != (self.state == "failed"):
            raise ValueError("failed slots require a failure code")
        return self


class EvaluationManifest(EvaluationModel):
    schema_version: Literal["n11-evaluation-manifest-v1"]
    method_release: Literal[RELEASE]
    manifest_id: Annotated[str, Field(pattern=r"^evaluation-manifest-[a-f0-9]{64}$")]
    content_hash: Hash
    study_mode: Literal["software_only", "exploratory_historical"]
    scope: Literal["offline_separate_tracks_no_live_response_bridge"]
    protocol_receipt: Alias
    receipts: Annotated[tuple[Receipt, ...], Field(min_length=1, max_length=4096)]
    datasets: Annotated[tuple[Dataset, ...], Field(max_length=160)]
    groups: Annotated[tuple[GroupBinding, ...], Field(max_length=4096)]
    raw_derivations: Annotated[tuple[RawDerivation, ...], Field(max_length=4096)]
    diagnoses: Annotated[tuple[Diagnosis, ...], Field(max_length=160)]
    passive: Annotated[tuple[Passive, ...], Field(max_length=128)]
    live: Annotated[tuple[Live, ...], Field(max_length=128)]
    slots: Annotated[tuple[Slot, ...], Field(min_length=1, max_length=256)]

    @model_validator(mode="after")
    def bindings(self):
        for items, key in (
            (self.receipts, lambda x: x.receipt_id),
            (self.datasets, lambda x: x.dataset_key),
            (self.groups, lambda x: (x.dataset_key, x.group_id)),
            (self.raw_derivations, lambda x: (x.dataset_key, x.entry_id, x.window_role)),
            (self.slots, lambda x: x.slot_id),
            *((items, lambda x: x.job_id) for items in (self.diagnoses, self.passive, self.live)),
        ):
            unique_order(items, key)
        receipts = {r.receipt_id: r for r in self.receipts}
        used = set()

        def require(key, kind):
            if key not in receipts or receipts[key].kind not in kind:
                raise ValueError("missing/wrong receipt kind")
            used.add(key)

        require(self.protocol_receipt, ("protocol",))
        datasets = {d.dataset_key for d in self.datasets}
        for dataset in self.datasets:
            require(dataset.manifest_receipt, ("dataset_manifest",))
        for group in (*self.groups, *self.raw_derivations):
            if group.dataset_key not in datasets:
                raise ValueError("unknown dataset")
        for row in self.raw_derivations:
            require(row.raw_receipt, ("raw_bundle",))
        jobs = [j.job_id for j in (*self.diagnoses, *self.passive, *self.live)]
        if len(jobs) != len(set(jobs)):
            raise ValueError("job identifiers must be globally unique")
        for job in (*self.diagnoses, *self.passive):
            if job.dataset_key not in datasets:
                raise ValueError("unknown job dataset")
        for job in self.diagnoses:
            require(job.snapshot_receipt, ("profile_snapshot",))
            require(job.response_policy_receipt, ("response_policy",))
            require(job.match_policy_receipt, ("match_policy",))
        for job in self.passive:
            for key, kind in (
                (job.baseline_receipt, "passive_baseline"),
                (job.replay_receipt, "passive_replay"),
                (job.policy_receipt, "passive_policy"),
            ):
                require(key, (kind,))
        for job in self.live:
            require(job.evidence_receipt, ("game_evidence", "integrated_evidence"))
        if used != receipts.keys():
            raise ValueError("unreferenced receipts")
        if len({s.study_group for s in self.slots}) != len(self.slots):
            raise ValueError("one planned slot per study group; exports are not repetitions")
        slots = {s.study_group: s for s in self.slots}
        if any(g.study_group not in slots for g in self.groups):
            raise ValueError("group has no planned slot")
        for slot in self.slots:
            for key, items in (
                (slot.diagnosis_job, self.diagnoses),
                (slot.passive_job, self.passive),
                (slot.live_job, self.live),
            ):
                if key is not None and key not in {j.job_id for j in items}:
                    raise ValueError("slot job does not exist")
            if slot.diagnosis_job is not None:
                job = next(j for j in self.diagnoses if j.job_id == slot.diagnosis_job)
                if slot.role != job.mode:
                    raise ValueError("diagnosis mode and slot role disagree")
        if any(j.job_id not in {s.passive_job for s in self.slots} for j in self.passive):
            raise ValueError("unassigned passive job")
        if any(j.job_id not in {s.live_job for s in self.slots} for j in self.live):
            raise ValueError("unassigned live job")
        if len({s.passive_job for s in self.slots if s.passive_job}) != len(self.passive):
            raise ValueError("one stream job cannot count as multiple acquisition groups")
        identity(self, "manifest_id", "evaluation-manifest-")
        return self


class ResultReference(EvaluationModel):
    job_id: Alias
    root_id: Annotated[str, Field(strict=True, min_length=1, max_length=128)]
    content_hash: Hash


class SlotOutcome(EvaluationModel):
    slot_id: Alias
    truth_label: Label | None
    profile_label: Label | None
    point_label: Label | None
    diagnosis_state: Literal["computed", "unavailable", "not_requested"]
    reason_codes: Annotated[tuple[Alias, ...], Field(max_length=8)]
    passive_state: Literal["computed", "unavailable", "not_requested"]
    proposals: Annotated[int, Field(strict=True, ge=0, le=3)] | None
    first_proposal_ms: Annotated[int, Field(strict=True, ge=0, le=2**53 - 1)] | None
    live_state: Literal["not_requested", "engineering_only"]

    @model_validator(mode="after")
    def consistency(self):
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("duplicate outcome reasons")
        if self.passive_state == "computed":
            if self.proposals is None or (self.first_proposal_ms is not None) != bool(
                self.proposals
            ):
                raise ValueError("computed proposal count/time disagree")
        elif self.proposals is not None or self.first_proposal_ms is not None:
            raise ValueError("unavailable passive evidence cannot claim a proposal count")
        return self


class EvaluationCounts(EvaluationModel):
    planned_slots: Annotated[int, Field(strict=True, ge=0, le=256)]
    held_out_slots: Annotated[int, Field(strict=True, ge=0, le=256)]
    failed_slots: Annotated[int, Field(strict=True, ge=0, le=256)]
    not_started_slots: Annotated[int, Field(strict=True, ge=0, le=256)]
    profile_correct: Ratio
    profile_wrong: Ratio
    profile_unknown: Ratio
    point_correct: Ratio
    point_wrong: Ratio
    point_unknown: Ratio


def count_outcomes(manifest, rows):
    from ..profiles.arithmetic import ratio

    held = {s.slot_id for s in manifest.slots if s.role in ("validation", "final_test")}
    values = [r for r in rows if r.slot_id in held]
    result = dict(
        planned_slots=len(manifest.slots),
        held_out_slots=len(held),
        failed_slots=sum(s.state == "failed" for s in manifest.slots),
        not_started_slots=sum(s.state == "not_started" for s in manifest.slots),
    )
    for method in ("profile", "point"):
        predictions = [(r.truth_label, getattr(r, method + "_label")) for r in values]
        result[method + "_correct"] = ratio(
            sum(t is not None and p == t for t, p in predictions), len(held)
        )
        result[method + "_wrong"] = ratio(
            sum(t is not None and p is not None and p != t for t, p in predictions), len(held)
        )
        result[method + "_unknown"] = ratio(sum(p is None for _, p in predictions), len(held))
    return result


class EvaluationReport(EvaluationModel):
    schema_version: Literal["n11-evaluation-report-v1"]
    method_release: Literal[RELEASE]
    report_id: Annotated[str, Field(pattern=r"^evaluation-report-[a-f0-9]{64}$")]
    content_hash: Hash
    manifest: EvaluationManifest
    results: Annotated[tuple[ResultReference, ...], Field(max_length=4096)]
    rows: Annotated[tuple[SlotOutcome, ...], Field(max_length=256)]
    counts: EvaluationCounts
    empirical_acceptance: Literal["unavailable_not_a_frozen_real_study"]
    assurance: Literal["offline_source_bindings_external_truth_not_authenticated_no_live_authority"]

    @model_validator(mode="after")
    def reconstruct(self):
        unique_order(self.results, lambda x: (x.job_id, x.root_id))
        jobs = {
            j.job_id
            for j in (*self.manifest.diagnoses, *self.manifest.passive, *self.manifest.live)
        }
        if {r.job_id for r in self.results} != jobs:
            raise ValueError("result links must cover every declared job and no unrelated job")
        if tuple(r.slot_id for r in self.rows) != tuple(s.slot_id for s in self.manifest.slots):
            raise ValueError("every planned slot must remain in order")
        for slot, row in zip(self.manifest.slots, self.rows, strict=True):
            for key in ("diagnosis", "passive"):
                job = getattr(slot, key + "_job")
                state = getattr(row, key + "_state")
                if (state == "not_requested") != (job is None):
                    raise ValueError("outcome availability contradicts requested method")
                if state == "computed" and slot.state != "retained":
                    raise ValueError("failed/unstarted slot cannot claim computed observations")
            if (row.live_state == "not_requested") != (slot.live_job is None):
                raise ValueError("live engineering link mismatch")
            if slot.state != "retained" and (
                row.profile_label is not None or row.point_label is not None
            ):
                raise ValueError("failed/unstarted slot cannot claim a diagnosis")
            if row.truth_label is not None and row.truth_label != slot.truth_label:
                raise ValueError("truth cannot be substituted")
            if row.diagnosis_state != "computed" and (
                row.profile_label is not None or row.point_label is not None
            ):
                raise ValueError("unavailable diagnosis cannot carry labels")
        if self.counts.model_dump(mode="json") != count_outcomes(self.manifest, self.rows):
            raise ValueError("planned denominators do not reconstruct")
        identity(self, "report_id", "evaluation-report-")
        return self


def seal_manifest(payload):
    """Seal an explicit complete declaration; this never approves a protocol."""
    payload = {k: v for k, v in payload.items() if k not in ("manifest_id", "content_hash")}
    digest = payload_hash(payload)
    return EvaluationManifest.model_validate(
        {**payload, "content_hash": digest, "manifest_id": "evaluation-manifest-" + digest[7:]}
    )
