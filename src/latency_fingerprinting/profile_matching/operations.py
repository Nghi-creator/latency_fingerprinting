"""Offline linked N8 operations over one freshly inspected N6 source snapshot."""

from types import SimpleNamespace

from ..analytical.policy_release import payload_hash
from ..calibration.inspection import _inspect_calibration_snapshot
from ..profiles.operations import _fit_inspected_profile_snapshot
from ..profiles.snapshot import ProfileSnapshot
from .contracts import ASSURANCE, RELEASE
from .evaluation import evaluation_inventory, refit_profiles, refit_work_budget, summarize
from .evidence import Evidence
from .models import ProfileEvaluationResult, ProfileMatchResult, QueryDecision, Refit, same
from .policy import ProfileMatchPolicy
from .scoring import query_reasons, reconstruct_decision

_FAILURES = (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError)


def _inspect(directory, snapshot, policy, **anchors):
    policy = ProfileMatchPolicy.model_validate(policy)
    snapshot = ProfileSnapshot.model_validate(snapshot)
    inspected, origin = _inspect_calibration_snapshot(directory, **anchors)
    if snapshot.source_report is not None:
        fitted = _fit_inspected_profile_snapshot(inspected, snapshot.policy)
        # Lifecycle revisions may withdraw an exact fit, but cannot alter its evidence.
        supplied = snapshot.model_dump(mode="json")
        expected = fitted.model_dump(mode="json")
        for key in ("policy", "source_report", "inputs", "profiles", "counts", "assurance"):
            same(supplied[key], expected[key])
    evidence = Evidence.model_validate(
        dict(dataset=inspected.dataset, report=inspected.report, snapshot=snapshot)
    )
    records = {a.artifact_id: a.record for a in inspected.artifacts}
    return policy, evidence, records, origin, inspected.file_identities


def _query(evidence, records, identifier, mode):
    declaration, entry = evidence.entry(identifier)
    record_id, values = None, None
    if entry.input_kind != "missing":
        record = records[declaration.artifact_id]
        if entry.input_kind == "response":
            record_id = record.response_id
            policy = evidence.snapshot.policy
            if (
                record.policy.content_hash != policy.response_policy_hash
                or record.observation.degraded_window.registry.model_dump(mode="json")
                != policy.registry.model_dump(mode="json")
            ):
                raise ValueError("query source registry/policy mismatch")
            if evidence.snapshot.lifecycle.state == "provisional" and not query_reasons(
                entry, mode
            ):
                values = {
                    name: record.features[name].normalized_value
                    if record.features[name].state == "eligible"
                    else None
                    for name in policy.feature_names
                }
        else:
            record_id = record.window_id
    return SimpleNamespace(
        query_entry_id=identifier,
        query_artifact_id=declaration.artifact_id,
        query_record_id=record_id,
        query_feature_values=values,
    )


def _seal(policy, evidence, model, **fields):
    payload = dict(
        schema_version=(
            "profile-match-result-v1"
            if model is ProfileMatchResult
            else "profile-evaluation-result-v1"
        ),
        method_release=RELEASE,
        policy=policy.model_dump(mode="json"),
        evidence=evidence.model_dump(mode="json"),
        assurance=ASSURANCE,
        **fields,
    )
    digest = payload_hash(payload)
    prefix = "profile-match-" if model is ProfileMatchResult else "profile-evaluation-"
    return model.model_validate(
        {**payload, "content_hash": digest, "result_id": prefix + digest[7:]}
    )


def _match_profile_snapshot(directory, snapshot, policy, *, query_entry_id, **anchors):
    policy, evidence, records, origin, files = _inspect(directory, snapshot, policy, **anchors)
    query = _query(evidence, records, query_entry_id, "held_out")
    decision = reconstruct_decision(evidence, query)
    return _seal(policy, evidence, ProfileMatchResult, decision=decision), origin, files


def match_profile_snapshot(
    directory,
    snapshot,
    policy,
    *,
    query_entry_id,
    expected_split_id=None,
    expected_dataset_content_hash=None,
):
    """Inspect one N6 directory, verify the supplied fit, then score one held-out entry."""
    try:
        return _match_profile_snapshot(
            directory,
            snapshot,
            policy,
            query_entry_id=query_entry_id,
            expected_split_id=expected_split_id,
            expected_dataset_content_hash=expected_dataset_content_hash,
        )[0]
    except _FAILURES:
        raise ValueError("invalid_profile_match") from None


def _evaluate_profile_snapshot(directory, snapshot, policy, *, mode, **anchors):
    if type(mode) is not str or mode not in (
        "validation",
        "final_test",
        "leave_training_group_out",
    ):
        raise ValueError("invalid evaluation mode")
    policy, evidence, records, origin, files = _inspect(directory, snapshot, policy, **anchors)
    entries = evaluation_inventory(evidence, mode)
    if len(entries) * len(evidence.snapshot.profiles) > 4096:
        raise ValueError("N8 actual candidate work exceeds global budget")
    fold = mode == "leave_training_group_out"
    groups = sorted({e.group_id for e in entries if e.input_kind == "response"}) if fold else []
    if len(groups) > 64:
        raise ValueError("N8 refit inventory exceeds global budget")
    refit_work_budget(evidence, groups)
    refits = [
        Refit.model_validate(refit_profiles(evidence, group, policy.content_hash))
        for group in groups
    ]
    by_group = {r.excluded_group_id: r for r in refits}
    decisions, feature_rows = [], 0
    for entry in entries:
        query_mode = "leave_training_group_out" if fold else "held_out"
        query = _query(evidence, records, entry.entry_id, query_mode)
        refit = by_group.get(entry.group_id) if fold else None
        computed = refit is not None and refit.state == "computed"
        row = reconstruct_decision(
            evidence,
            query,
            refit.profiles if computed else None,
            mode=query_mode,
            excluded_group_id=entry.group_id if fold else None,
            refit_id=refit.refit_id if computed else None,
            maximum_feature_rows=5632 - feature_rows,
        )
        feature_rows += sum(
            len(r["features"]) for r in row["candidates"] if r["features"] is not None
        )
        decisions.append(QueryDecision.model_validate(row))
    summary = summarize(evidence, mode, decisions, refits)
    result = _seal(
        policy,
        evidence,
        ProfileEvaluationResult,
        mode=mode,
        refits=[r.model_dump(mode="json") for r in refits],
        decisions=[d.model_dump(mode="json") for d in decisions],
        **summary,
    )
    return result, origin, files


def evaluate_profile_snapshot(
    directory,
    snapshot,
    policy,
    *,
    mode,
    expected_split_id=None,
    expected_dataset_content_hash=None,
):
    """Evaluate every measured entry in one explicit role, retaining unknown outcomes."""
    try:
        return _evaluate_profile_snapshot(
            directory,
            snapshot,
            policy,
            mode=mode,
            expected_split_id=expected_split_id,
            expected_dataset_content_hash=expected_dataset_content_hash,
        )[0]
    except _FAILURES:
        raise ValueError("invalid_profile_evaluation") from None
