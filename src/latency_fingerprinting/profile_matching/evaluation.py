"""Whole-component refits and total group-level outcomes from declared evidence."""

from ..analytical.policy_release import payload_hash
from ..profiles.arithmetic import ratio
from ..profiles.reconstruction import fit_profiles
from .contracts import LABELS


def refit_profiles(evidence, group_id, policy_hash):
    entries = evidence.report.entries
    queries = [e for e in entries if e.group_id == group_id and e.input_kind == "response"]
    reasons = []
    if evidence.snapshot.lifecycle.state != "provisional":
        reasons.append("snapshot_unavailable")
    if not any(e.eligible and e.representative_entry_id == e.entry_id for e in queries):
        reasons.append("no_eligible_queries")
    row = dict(
        excluded_group_id=group_id,
        state="skipped" if reasons else "computed",
        reason_codes=reasons,
        inputs=None,
        profiles=None,
        counts=None,
    )
    if not reasons:
        inputs, selected, vectors = [], [], {}
        for entry, base in zip(entries, evidence.snapshot.inputs, strict=True):
            codes = list(base.reason_codes)
            if entry.group_id == group_id:
                codes.append("leave_source_group_out")
            values = dict(base.feature_values) if not codes else None
            inputs.append(
                dict(
                    entry_id=entry.entry_id,
                    selected=not codes,
                    reason_codes=codes,
                    feature_values=values,
                )
            )
            if not codes:
                selected.append(entry)
                vectors[entry.entry_id] = values
        profiles = fit_profiles(
            evidence.report, selected, vectors, evidence.snapshot.policy.content_hash
        )
        for profile in profiles:
            del profile["profile_id"]
            digest = payload_hash(
                dict(
                    policy_content_hash=policy_hash,
                    profile_policy_content_hash=evidence.snapshot.policy.content_hash,
                    source_report_id=evidence.report.report_id,
                    snapshot_id=evidence.snapshot.snapshot_id,
                    excluded_group_id=group_id,
                    profile=profile,
                )
            )
            profile["profile_id"] = "profile-fold-" + digest[7:]
        row.update(
            inputs=inputs,
            profiles=profiles,
            counts=dict(
                retained_entries=len(entries),
                base_selected_entries=evidence.snapshot.counts.selected_entries,
                removed_entries=sum(e.group_id == group_id for e in entries),
                selected_entries=len(selected),
                excluded_entries=len(entries) - len(selected),
                selected_groups=len({e.group_id for e in selected}),
            ),
        )
    row["refit_id"] = (
        "profile-refit-"
        + payload_hash(
            dict(
                policy_content_hash=policy_hash,
                source_report_id=evidence.report.report_id,
                snapshot_id=evidence.snapshot.snapshot_id,
                refit=row,
            )
        )[7:]
    )
    return row


def evaluation_inventory(evidence, mode):
    role = "training" if mode == "leave_training_group_out" else mode
    return [e for e in evidence.report.entries if e.role == role]


def summarize(evidence, mode, decisions, refits):
    entries = evaluation_inventory(evidence, mode)
    responses = [e for e in entries if e.input_kind == "response"]
    by_id = {d.query_entry_id: d for d in decisions}
    groups = []
    for group_id in sorted({e.group_id for e in responses}):
        members = [e for e in responses if e.group_id == group_id]
        reps = [e for e in members if e.representative_entry_id == e.entry_id]
        truth_reasons, prediction_reasons = [], []
        if any(
            e.label is None
            or {"label_unverified", "effect_unverified", "binding_unverified"} & set(e.reason_codes)
            for e in reps
        ):
            truth_reasons.append("label_unverified")
        if len({e.label for e in reps if e.label is not None}) > 1:
            truth_reasons.append("mixed_labels")
        votes = [by_id[e.entry_id].chosen_label for e in reps]
        if None in votes:
            prediction_reasons.append("entry_unknown")
        if len({v for v in votes if v is not None}) > 1:
            prediction_reasons.append("entry_disagreement")
        groups.append(
            dict(
                group_id=group_id,
                entry_ids=[e.entry_id for e in members],
                representative_entry_ids=[e.entry_id for e in reps],
                truth_label=None if truth_reasons else reps[0].label,
                truth_reason_codes=truth_reasons,
                predicted_label=None if prediction_reasons else votes[0],
                prediction_reason_codes=prediction_reasons,
            )
        )
    matrix = {
        label: dict.fromkeys((*LABELS, "unknown"), 0) for label in (*LABELS, "unverified_truth")
    }
    for group in groups:
        matrix[group["truth_label"] or "unverified_truth"][
            group["predicted_label"] or "unknown"
        ] += 1
    known = sum(g["truth_label"] is not None for g in groups)
    unknown = sum(g["predicted_label"] is None for g in groups)
    correct = sum(
        g["truth_label"] is not None and g["predicted_label"] == g["truth_label"] for g in groups
    )
    incorrect = sum(
        g["truth_label"] is not None
        and g["predicted_label"] is not None
        and g["predicted_label"] != g["truth_label"]
        for g in groups
    )
    counts = dict(
        retained_entries=len(evidence.report.entries),
        global_missing_entries=sum(e.input_kind == "missing" for e in evidence.report.entries),
        evaluated_entries=len(entries),
        response_entries=len(responses),
        baseline_entries=sum(e.input_kind == "healthy_window" for e in entries),
        n6_excluded_entries=sum(not e.eligible for e in entries),
        duplicate_entries=sum(e.representative_entry_id != e.entry_id for e in entries),
        classification_groups=len(groups),
        baseline_only_groups=len({e.group_id for e in entries} - {e.group_id for e in responses}),
        known_truth_groups=known,
        unverified_truth_groups=len(groups) - known,
        provisional_match_groups=len(groups) - unknown,
        unknown_groups=unknown,
        correct_groups=correct,
        incorrect_groups=incorrect,
        computed_refits=sum(r.state == "computed" for r in refits),
        skipped_refits=sum(r.state == "skipped" for r in refits),
    )
    return dict(
        group_outcomes=groups,
        confusion_matrix=matrix,
        counts=counts,
        metrics=dict(
            accuracy=ratio(correct, known),
            unknown_rate=ratio(unknown, len(groups)),
            truth_coverage=ratio(known, len(groups)),
        ),
    )


def refit_work_budget(evidence, group_ids):
    """Bound actual refitting work independently of any attacker-supplied summaries."""
    if evidence.snapshot.lifecycle.state != "provisional":
        return
    selected = [
        (entry, value)
        for entry, value in zip(evidence.report.entries, evidence.snapshot.inputs, strict=True)
        if value.selected
    ]
    candidate_count = group_rows = references = 0
    for group_id in group_ids:
        if not any(
            e.group_id == group_id
            and e.input_kind == "response"
            and e.eligible
            and e.representative_entry_id == e.entry_id
            for e in evidence.report.entries
        ):
            continue
        candidate_count += len(evidence.snapshot.profiles)
        groups = set()
        for entry, value in selected:
            if entry.group_id == group_id:
                continue
            for name, number in value.feature_values.items():
                if number is not None:
                    references += 1
                    groups.add((entry.partition_id, entry.label, entry.group_id, name))
        group_rows += len(groups)
        if candidate_count > 256 or group_rows > 32768 or references > 32768:
            raise ValueError("N8 actual refit work exceeds global budget")
