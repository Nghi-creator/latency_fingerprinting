"""Pinned N6-to-median readiness inspection, without classification or trust."""

import re
from collections import defaultdict
from copy import deepcopy

from ..analytical.policy_release import payload_hash
from ..calibration.inspection import inspect_calibration_dataset
from ..profiles.selection import selection_reasons
from .median_response import METHOD_CONTENT_HASH, _origins, summarize_engineering_responses

RELEASE = "n11-reviewed-median-readiness-v1"
ERROR = "invalid_reviewed_median_readiness"
READINESS_METHOD_CONTENT_HASH = (
    "sha256:548819229cbdb5b3d1d1115004cf2ec72ec93bfec028a15ea9250f0c3c7e2fd6"
)
LABELS = ("healthy", "host_contention", "render_capture_slowdown")
_METHOD = dict(
    method_release=RELEASE,
    median_method_content_hash=METHOD_CONTENT_HASH,
    source_selection="linked_pinned_n6_eligible_unique_training_responses_only",
    group_selection="reconstructed_n6_components_exclude_mixed_partition_labels",
    required_labels=list(LABELS),
    minimum_groups_per_label=5,
    maximum_candidates=16,
    heldout_feature_use="validation_and_final_test_excluded_from_summaries",
    classification_authority=False,
)


def inspect_reviewed_median_readiness(
    directory, *, expected_dataset_content_hash, expected_split_id
):
    """Inspect actual pinned N6 files; never accept a detached supplied report.

    External review declarations are not authenticated. Eligibility and numeric
    summaries cannot establish cause truth, class separation, decision thresholds
    or independent evaluation. No lifecycle/trust promotion is performed.
    """
    try:
        if payload_hash(_METHOD) != READINESS_METHOD_CONTENT_HASH:
            raise ValueError(ERROR)
        for value, prefix in (
            (expected_dataset_content_hash, "sha256:"),
            (expected_split_id, "split-"),
        ):
            if type(value) is not str or re.fullmatch(prefix + r"[a-f0-9]{64}", value) is None:
                raise ValueError(ERROR)
        inspected = inspect_calibration_dataset(
            directory,
            expected_dataset_content_hash=expected_dataset_content_hash,
            expected_split_id=expected_split_id,
        )
        return _readiness(inspected)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError(ERROR) from None


def _readiness(inspected):
    report, dataset = inspected.report, inspected.dataset
    reasons, _ = selection_reasons(report.entries)
    declarations = {e.entry_id: e for e in dataset.entries}
    records = {a.artifact_id: a.record for a in inspected.artifacts}
    candidates, origins, selected = defaultdict(dict), {}, []
    for entry in report.entries:
        if reasons[entry.entry_id]:
            continue
        record = records[declarations[entry.entry_id].artifact_id]
        for origin in _origins(record):
            if origin in origins and origins[origin] != entry.group_id:
                raise ValueError(ERROR)
            origins[origin] = entry.group_id
        key = entry.partition_id, entry.label
        candidates[key].setdefault(entry.group_id, []).append(record)
        selected.append(entry.entry_id)
    if len(candidates) > 16:
        raise ValueError(ERROR)
    summaries = [
        dict(
            partition_id=partition,
            reviewed_label=label,
            summary=summarize_engineering_responses(groups),
        )
        for (partition, label), groups in sorted(candidates.items())
    ]
    partitions = sorted({e.partition_id for e in report.entries if e.input_kind == "response"})
    coverage = []
    for partition in partitions:
        available = [
            s["reviewed_label"]
            for s in summaries
            if s["partition_id"] == partition and s["summary"]["state"] == "computable"
        ]
        coverage.append(
            dict(
                partition_id=partition,
                numeric_reviewed_labels=sorted(available),
                missing_numeric_labels=sorted(set(LABELS) - set(available)),
            )
        )
    payload = dict(
        method_release=RELEASE,
        method_spec=deepcopy(_METHOD),
        method_content_hash=READINESS_METHOD_CONTENT_HASH,
        state="reviewed_training_summaries_available"
        if any(not p["missing_numeric_labels"] for p in coverage)
        else "unavailable",
        source_dataset_id=dataset.dataset_id,
        source_dataset_content_hash=dataset.content_hash,
        source_split_id=dataset.split.split_id,
        source_report_id=report.report_id,
        assurance="external_review_declarations_not_authenticated",
        scope="training_readiness_only_not_separation_or_diagnostic_acceptance",
        selected_entry_ids=selected,
        selected_group_ids=sorted({e.group_id for e in report.entries if e.entry_id in selected}),
        exclusions=[
            dict(
                entry_id=e.entry_id,
                selection_reason_codes=reasons[e.entry_id],
                n6_reason_codes=list(e.reason_codes),
            )
            for e in report.entries
            if reasons[e.entry_id]
        ],
        candidates=summaries,
        label_coverage=coverage,
        decision_method="unavailable_requires_separately_frozen_contract",
        diagnostic_label=None,
        accepted_diagnostic_groups=0,
        acquisition_authority=False,
    )
    return {**payload, "readiness_id": "median-readiness-" + payload_hash(payload)[7:]}
