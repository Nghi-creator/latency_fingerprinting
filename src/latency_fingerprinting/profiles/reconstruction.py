"""Reconstruct every profile and denominator from selected immutable input values."""

from ..analytical.policy_release import payload_hash
from .arithmetic import candidate_support, feature_statistics, median
from .policy_release import FEATURE_NAMES
from .selection import selection_reasons


def reconstruct(report, inputs, policy_hash):
    entries = report.entries
    reasons, mixed = selection_reasons(entries)
    if tuple(item.entry_id for item in inputs) != tuple(entry.entry_id for entry in entries):
        raise ValueError("profile input inventory disagrees with N6 report")
    vectors, selected = {}, []
    for entry, item in zip(entries, inputs, strict=True):
        if list(item.reason_codes) != reasons[entry.entry_id]:
            raise ValueError("profile selection does not reconstruct")
        if item.selected:
            if (
                sum(value is not None for value in item.feature_values.values())
                != entry.eligible_feature_count
            ):
                raise ValueError("selected feature count disagrees with N6")
            vectors[entry.entry_id] = item.feature_values
            selected.append(entry)
    profiles = []
    keys = sorted(
        {
            (entry.partition_id, entry.label)
            for entry in entries
            if entry.input_kind == "response"
            and entry.role == "training"
            and entry.label is not None
        }
    )
    for partition, label in keys:
        members = [
            entry for entry in selected if (entry.partition_id, entry.label) == (partition, label)
        ]
        group_ids = sorted({entry.group_id for entry in members})
        features = {}
        for name in FEATURE_NAMES:
            values = []
            for group in group_ids:
                observed = [
                    entry.entry_id
                    for entry in members
                    if entry.group_id == group and vectors[entry.entry_id][name] is not None
                ]
                if observed:
                    values.append(
                        dict(
                            group_id=group,
                            entry_ids=observed,
                            median=median([vectors[identifier][name] for identifier in observed]),
                        )
                    )
            features[name] = dict(
                group_values=values,
                **feature_statistics([row["median"] for row in values], len(group_ids)),
            )
        profile = dict(
            partition_id=partition,
            label=label,
            training_group_ids=group_ids,
            selected_entry_ids=[entry.entry_id for entry in members],
            features=features,
            **candidate_support(
                len(group_ids), sum(f["state"] == "supported" for f in features.values())
            ),
        )
        profile["profile_id"] = (
            "profile-"
            + payload_hash(
                dict(
                    policy_content_hash=policy_hash,
                    source_report_id=report.report_id,
                    profile=profile,
                )
            )[7:]
        )
        profiles.append(profile)
    counts = dict(
        retained_entries=len(entries),
        selected_entries=len(selected),
        excluded_entries=len(entries) - len(selected),
        selected_groups=len({entry.group_id for entry in selected}),
        baseline_entries=sum(e.input_kind == "healthy_window" for e in entries),
        missing_entries=sum(e.input_kind == "missing" for e in entries),
        heldout_response_entries=sum(
            e.input_kind == "response" and e.role in ("validation", "final_test") for e in entries
        ),
        mixed_label_groups=len(mixed),
    )
    return profiles, counts
