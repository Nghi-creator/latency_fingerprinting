"""Linked offline N9 operations over one freshly inspected N6 source snapshot."""

from ..calibration.inspection import _inspect_calibration_snapshot
from .contracts import tree_budget
from .evidence import Evidence, metadata_reasons
from .models import PassiveBaseline, PassiveReplay, same
from .policy import PassiveGatePolicy
from .pure import evaluate_passive_replay, fit_passive_baseline

_FAILURES = (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError)


def _fit_inspected_passive_baseline(inspected, policy):
    """Fit original eligible training records from this exact inspected object."""
    evidence = Evidence(dataset=inspected.dataset, report=inspected.report)
    records = {artifact.artifact_id: artifact.record for artifact in inspected.artifacts}
    windows = {
        entry.entry_id: records[declaration.artifact_id]
        for declaration, entry in zip(
            evidence.dataset.entries, evidence.report.entries, strict=True
        )
        if not metadata_reasons(evidence, declaration, entry)
    }
    return fit_passive_baseline(evidence, windows, policy)


def _build_passive_baseline(directory, policy, **anchors):
    policy = PassiveGatePolicy.model_validate(policy)
    inspected, origin = _inspect_calibration_snapshot(directory, **anchors)
    baseline = _fit_inspected_passive_baseline(inspected, policy)
    return baseline, origin, inspected.file_identities


def build_passive_baseline(
    directory,
    policy,
    *,
    expected_split_id=None,
    expected_dataset_content_hash=None,
):
    """Inspect N6 bytes once and fit only confirmed healthy training evidence."""
    try:
        return _build_passive_baseline(
            directory,
            policy,
            expected_split_id=expected_split_id,
            expected_dataset_content_hash=expected_dataset_content_hash,
        )[0]
    except _FAILURES:
        raise ValueError("invalid_passive_baseline") from None


def _replay_passive_gate(directory, baseline, replay, policy, **anchors):
    policy = PassiveGatePolicy.model_validate(policy)
    baseline = PassiveBaseline.model_validate(baseline)
    replay = PassiveReplay.model_validate(replay)
    inspected, origin = _inspect_calibration_snapshot(directory, **anchors)
    fitted = _fit_inspected_passive_baseline(inspected, policy)
    # Compare the whole retained fit, including the original N2 training windows,
    # full dataset/report and exclusions. A self-consistent stale fit is insufficient.
    same(baseline, fitted.model_dump(mode="json"))
    records = {artifact.artifact_id: artifact.record for artifact in inspected.artifacts}
    expected_windows = {}
    for event in replay.events:
        if event.kind == "window":
            declaration, entry = fitted.evidence.entry(event.entry_id)
            if entry.input_kind == "healthy_window":
                expected_windows[declaration.artifact_id] = records[declaration.artifact_id]
    original_pool = [
        dict(artifact_id=identifier, window=window)
        for identifier, window in sorted(expected_windows.items())
    ]
    tree_budget(original_pool)
    pool = [
        dict(artifact_id=row["artifact_id"], window=row["window"].model_dump(mode="json"))
        for row in original_pool
    ]
    same([row.model_dump(mode="json") for row in replay.windows], pool)
    # Evaluate source-extracted query records, never unverified caller measurements.
    payload = replay.model_dump(mode="json")
    payload["windows"] = pool
    fresh_replay = PassiveReplay.model_validate(payload)
    result = evaluate_passive_replay(fitted, fresh_replay, policy)
    return result, origin, inspected.file_identities


def replay_passive_gate(
    directory,
    baseline,
    replay,
    policy,
    *,
    expected_split_id=None,
    expected_dataset_content_hash=None,
):
    """Verify a fresh fit and all query windows through the same N6 inspection."""
    try:
        return _replay_passive_gate(
            directory,
            baseline,
            replay,
            policy,
            expected_split_id=expected_split_id,
            expected_dataset_content_hash=expected_dataset_content_hash,
        )[0]
    except _FAILURES:
        raise ValueError("invalid_passive_replay") from None
