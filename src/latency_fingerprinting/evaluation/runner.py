"""Deterministic N6/N7/N8/N9/N10 replay; missing planned slots never disappear."""

import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from pydantic import BaseModel, TypeAdapter

from ..adapters.pixelated_observation_v2 import ingest_pixelated_v2
from ..adapters.pixelated_source_local import ingest_pixelated_source_local
from ..adapters.pixelated_windows import WindowBounds, ingest_pixelated_windows
from ..analytical.fingerprints import create_fingerprint_v2
from ..analytical.matching import match_response_v2
from ..analytical.policy_release import canonical_payload_bytes, payload_hash
from ..analytical.repository import FingerprintRepositoryV2
from ..calibration import inspect_calibration_dataset
from ..calibration.records import windows
from ..live_probes import (
    GameBrowserProbeEvidence,
    IntegratedGameRecord,
    inspect_game_browser_evidence,
    reconstruct_integrated_game_record,
)
from ..models import ContextKey, FeaturePolicyV1
from ..models.v2_common import ImmutableJSONMap, thaw_json
from ..passive_gating import PassiveBaseline, PassiveGatePolicy, PassiveReplay, replay_passive_gate
from ..profile_matching import ProfileMatchPolicy, evaluate_profile_snapshot
from ..profile_matching.evaluation import summarize
from ..profiles import ProfileSnapshot
from .contracts import (
    MAX_INPUT_BYTES,
    RELEASE,
    EvaluationManifest,
    EvaluationReport,
    ResultReference,
    SlotOutcome,
    count_outcomes,
)
from .inputs import Inputs
from .lineage import verify_study_groups


@dataclass(frozen=True)
class EvaluationExecution:
    report: EvaluationReport
    artifacts: tuple[BaseModel | Mapping, ...]


def _raw_proofs(manifest, inspected, inputs, temporary):
    links = {
        (link.dataset_key, link.entry_id, link.window_role): link.raw_receipt
        for link in manifest.raw_derivations
    }
    consumed, verified = set(), set()
    staged = {}
    for key, source in inspected.items():
        records = {a.artifact_id: a.record for a in source.artifacts}
        for entry in source.dataset.entries:
            if entry.input_kind == "missing":
                continue
            record = records[entry.artifact_id]
            matched = []
            for binding, window in zip(
                entry.source_bindings, windows(record, entry.input_kind), strict=True
            ):
                identity = key, entry.entry_id, binding.window_role
                raw_id = links.get(identity)
                if raw_id is None:
                    matched.append(False)
                    continue
                consumed.add(identity)
                if raw_id not in staged:
                    path = temporary / (raw_id + ".tar")
                    path.write_bytes(inputs.raw[raw_id])
                    staged[raw_id] = path
                arguments = dict(
                    context=ContextKey.model_validate(window.context.model_dump(mode="json")),
                    phase=window.phase,
                    comparison_case_id=window.comparison_case_id,
                    provenance=window.provenance,
                    confounder_codes=window.confounder_codes,
                )
                if window.capture_method.method_version == "1.2.0":
                    rebuilt = ingest_pixelated_source_local(staged[raw_id], **arguments)
                elif window.capture_method.method_version == "1.1.0":
                    start, end = window.clock.elapsed_start_ms, window.clock.elapsed_end_ms
                    if not start.is_integer() or not end.is_integer():
                        raise ValueError("windowed extraction requires integral bounds")
                    bounds = WindowBounds(start_ms=int(start), end_ms=int(end))
                    rebuilt = ingest_pixelated_windows(
                        staged[raw_id], windows=[bounds], **arguments
                    )[0]
                else:
                    rebuilt = ingest_pixelated_v2(staged[raw_id], **arguments)
                if rebuilt.model_dump(mode="json") != window.model_dump(mode="json"):
                    raise ValueError("raw derivation does not reproduce actual N6 window")
                matched.append(True)
            if all(matched):
                verified.add((key, entry.entry_id))
    if consumed != links.keys():
        raise ValueError("unrelated raw derivation")
    return verified


def _point_evaluation(result, inspection, snapshot, policy, retain, job_id):
    entries = {e.entry_id: e for e in inspection.report.entries}
    records = {a.artifact_id: a.record for a in inspection.artifacts}
    declarations = {e.entry_id: e for e in inspection.dataset.entries}
    selected = [entries[i.entry_id] for i in snapshot.inputs if i.selected]
    if len(selected) > 128:
        raise ValueError("point repository exceeds existing 128-reference bound")
    repository = []
    for entry in selected:
        response = records[declarations[entry.entry_id].artifact_id]
        if response.policy != policy:
            raise ValueError("point response policy mismatch")
        repository.append(create_fingerprint_v2(response, bottleneck_label=entry.label))
    decisions = []
    if (
        sum(e.role == result.mode and e.input_kind == "response" for e in entries.values())
        * len(repository)
        > 4096
    ):
        raise ValueError("point comparison work bound exceeded")
    for entry in inspection.report.entries:
        if entry.role != result.mode:
            continue
        chosen = None
        if (
            entry.input_kind == "response"
            and entry.eligible
            and entry.representative_entry_id == entry.entry_id
        ):
            response = records[declarations[entry.entry_id].artifact_id]
            scored = match_response_v2(response, policy, FingerprintRepositoryV2(tuple(repository)))
            retain(job_id, scored, scored.match_id)
            chosen = scored.accepted_label
        decisions.append(SimpleNamespace(query_entry_id=entry.entry_id, chosen_label=chosen))
    # Reuse N8's exact group voting, truth and denominator semantics.
    return summarize(result.evidence, result.mode, decisions, [])


def _execute(manifest, inputs):
    artifacts, references = [], []
    artifact_bytes = 0

    def retain(job_id, result, root_id):
        nonlocal artifact_bytes
        if len(artifacts) >= 4096:
            raise ValueError("evaluation result inventory exceeds bound")
        payload = (
            result.model_dump(mode="json") if isinstance(result, BaseModel) else thaw_json(result)
        )
        artifact_bytes += len(canonical_payload_bytes(payload))
        if artifact_bytes > MAX_INPUT_BYTES:
            raise ValueError("evaluation aggregate result bytes exceeded")
        artifacts.append(
            result
            if isinstance(result, BaseModel)
            else TypeAdapter(ImmutableJSONMap).validate_python(payload)
        )
        references.append(
            ResultReference(
                job_id=job_id,
                root_id=root_id,
                content_hash=getattr(result, "content_hash", None) or payload_hash(payload),
            )
        )

    with tempfile.TemporaryDirectory(prefix="n11-") as temporary_name:
        temporary = Path(temporary_name).resolve()
        paths, inspected = {}, {}
        for dataset in manifest.datasets:
            directory = inputs.stage_dataset(dataset, temporary)
            paths[dataset.dataset_key] = directory
            inspected[dataset.dataset_key] = inspect_calibration_dataset(
                directory,
                expected_split_id=dataset.split_id,
                expected_dataset_content_hash=dataset.content_hash,
            )
        groups = verify_study_groups(manifest, inspected)
        proofs = _raw_proofs(manifest, inspected, inputs, temporary)
        anchors = {
            d.dataset_key: dict(
                expected_split_id=d.split_id, expected_dataset_content_hash=d.content_hash
            )
            for d in manifest.datasets
        }
        diagnoses, passive = {}, {}
        comparison_work = 0
        for job in manifest.diagnoses:
            snapshot = inputs.model(job.snapshot_receipt, ProfileSnapshot)
            policy = inputs.model(job.response_policy_receipt, FeaturePolicyV1)
            query_count = sum(e.role == job.mode for e in inspected[job.dataset_key].report.entries)
            comparison_work += query_count * (
                len(snapshot.profiles) + sum(i.selected for i in snapshot.inputs)
            )
            if comparison_work > 4096:
                raise ValueError("study comparison work exceeds aggregate bound")
            result = evaluate_profile_snapshot(
                paths[job.dataset_key],
                snapshot,
                inputs.model(job.match_policy_receipt, ProfileMatchPolicy),
                mode=job.mode,
                **anchors[job.dataset_key],
            )
            if policy.content_hash != snapshot.policy.response_policy_hash:
                raise ValueError("explicit response policy mismatch")
            retain(job.job_id, result, result.result_id)
            points = _point_evaluation(
                result, inspected[job.dataset_key], snapshot, policy, retain, job.job_id
            )
            diagnoses[job.job_id] = job, result, points, snapshot
        for job in manifest.passive:
            result = replay_passive_gate(
                paths[job.dataset_key],
                inputs.model(job.baseline_receipt, PassiveBaseline),
                inputs.model(job.replay_receipt, PassiveReplay),
                inputs.model(job.policy_receipt, PassiveGatePolicy),
                **anchors[job.dataset_key],
            )
            retain(job.job_id, result, result.result_id)
            passive[job.job_id] = job, result
        for job in manifest.live:
            receipt = inputs.receipts[job.evidence_receipt]
            if receipt.kind == "game_evidence":
                root = inputs.model(receipt.receipt_id, GameBrowserProbeEvidence)
                result = inspect_game_browser_evidence(root)
            else:
                root = inputs.model(receipt.receipt_id, IntegratedGameRecord)
                result = reconstruct_integrated_game_record(root)
            retain(
                job.job_id,
                result,
                root.evidence_id if hasattr(root, "evidence_id") else root.record_id,
            )
        rows = []
        consumed_groups = set()
        for slot in manifest.slots:
            row = dict(
                slot_id=slot.slot_id,
                truth_label=None,
                profile_label=None,
                point_label=None,
                diagnosis_state="not_requested",
                reason_codes=[],
                passive_state="not_requested",
                proposals=None,
                first_proposal_ms=None,
                live_state="engineering_only" if slot.live_job else "not_requested",
            )
            if slot.diagnosis_job:
                job, result, points, snapshot = diagnoses[slot.diagnosis_job]
                candidates = [
                    g
                    for g in result.group_outcomes
                    if groups[job.dataset_key, g.group_id] == slot.study_group
                ]
                if len(candidates) > 1:
                    raise ValueError(
                        "one diagnosis slot cannot split its acquisition into extra groups"
                    )
                row["diagnosis_state"] = "unavailable"
                if candidates:
                    outcome = candidates[0]
                    consumed_groups.add((job.job_id, outcome.group_id))
                    if (
                        slot.truth_label is not None
                        and outcome.truth_label is not None
                        and slot.truth_label != outcome.truth_label
                    ):
                        raise ValueError("slot truth contradicts reviewed N6 truth")
                    row["truth_label"] = (
                        outcome.truth_label if slot.truth_label is not None else None
                    )
                    query_ids = outcome.representative_entry_ids
                    training_ids = [i.entry_id for i in snapshot.inputs if i.selected]
                    verified = all(
                        (job.dataset_key, e) in proofs for e in (*query_ids, *training_ids)
                    )
                    if slot.state == "retained" and verified:
                        row["diagnosis_state"] = "computed"
                        row["profile_label"] = outcome.predicted_label
                        row["point_label"] = next(
                            g["predicted_label"]
                            for g in points["group_outcomes"]
                            if g["group_id"] == outcome.group_id
                        )
                    elif not verified:
                        row["reason_codes"].append("raw_sources_unverified")
                else:
                    row["reason_codes"].append("missing_response_group")
            if slot.passive_job:
                job, result = passive[slot.passive_job]
                if slot.role != result.replay.mode:
                    raise ValueError("passive replay mode contradicts planned slot role")
                queries = []
                for event in result.replay.events:
                    if event.kind == "window":
                        _, entry = result.baseline.evidence.entry(event.entry_id)
                        if entry.group_id is not None:
                            if groups[job.dataset_key, entry.group_id] != slot.study_group:
                                raise ValueError("passive stream belongs to another planned group")
                            queries.append(entry.entry_id)
                baseline_ids = [i.entry_id for i in result.baseline.inputs if i.selected]
                verified = bool(queries) and all(
                    (job.dataset_key, e) in proofs for e in (*queries, *baseline_ids)
                )
                usable = (
                    result.baseline.state == "provisional"
                    and result.counts.accepted_windows > 0
                    and result.counts.unavailable_windows == 0
                )
                if slot.state == "retained" and verified and usable:
                    row["passive_state"] = "computed"
                    row["proposals"] = result.counts.proposals
                    proposed = [
                        result.replay.events[r.event_index].at_ms
                        for r in result.rows
                        if r.recommendation == "probe"
                    ]
                    row["first_proposal_ms"] = proposed[0] if proposed else None
                else:
                    row["passive_state"] = "unavailable"
                    reason = (
                        "raw_sources_unverified" if not verified else "passive_evidence_unavailable"
                    )
                    if reason not in row["reason_codes"]:
                        row["reason_codes"].append(reason)
            if slot.state != "retained":
                row["reason_codes"].append("acquisition_" + slot.state)
            rows.append(SlotOutcome.model_validate(row))
        expected = {
            (job.job_id, g.group_id)
            for job, result, _, _ in diagnoses.values()
            for g in result.group_outcomes
        }
        if consumed_groups != expected:
            raise ValueError("diagnostic evaluation groups missing from planned ledger")
    references.sort(key=lambda r: (r.job_id, r.root_id))
    body = dict(
        schema_version="n11-evaluation-report-v1",
        method_release=RELEASE,
        manifest=manifest.model_dump(mode="json"),
        results=[r.model_dump(mode="json") for r in references],
        rows=[r.model_dump(mode="json") for r in rows],
        counts=count_outcomes(manifest, rows),
        empirical_acceptance="unavailable_not_a_frozen_real_study",
        assurance="offline_source_bindings_external_truth_not_authenticated_no_live_authority",
    )
    digest = payload_hash(body)
    report = EvaluationReport.model_validate(
        {**body, "report_id": "evaluation-report-" + digest[7:], "content_hash": digest}
    )
    return EvaluationExecution(report, tuple(artifacts))


def _run_evaluation(manifest, receipt_paths):
    manifest = EvaluationManifest.model_validate(manifest)
    inputs = Inputs(manifest, receipt_paths)
    return _execute(manifest, inputs), inputs


def run_evaluation(manifest, receipt_paths):
    """Reconstruct from explicit local receipts; return report and computed artifacts."""
    try:
        return _run_evaluation(manifest, receipt_paths)[0]
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError("invalid_evaluation") from None


def verify_evaluation_report(report, receipt_paths):
    """Verify a retained report by repeating all linked source reconstruction."""
    try:
        report = EvaluationReport.model_validate(report)
        fresh = run_evaluation(report.manifest, receipt_paths).report
        if report.model_dump(mode="json") != fresh.model_dump(mode="json"):
            raise ValueError("evaluation reconstruction mismatch")
        return fresh
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError("invalid_evaluation_report") from None
