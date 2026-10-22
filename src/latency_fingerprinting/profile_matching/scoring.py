"""Pure label-blind scoring and exact reconstruction from retained declared values."""

from ..profiles.arithmetic import ratio
from ..profiles.policy_release import FEATURE_NAMES
from .arithmetic import deviation, margin, mean, standardize


def query_reasons(entry, mode):
    if entry.input_kind == "missing":
        return ["missing_measurements"]
    reasons = []
    if entry.input_kind == "healthy_window":
        reasons.append("baseline_only")
    if entry.role not in (
        ("training",) if mode == "leave_training_group_out" else ("validation", "final_test")
    ):
        reasons.append("not_held_out")
    if not entry.eligible:
        reasons.append("n6_excluded")
    if entry.representative_entry_id != entry.entry_id:
        reasons.append("duplicate_evidence")
    return reasons


def reconstruct_decision(
    evidence,
    query,
    profiles=None,
    *,
    mode="held_out",
    excluded_group_id=None,
    refit_id=None,
    maximum_feature_rows=5632,
):
    declaration, entry = evidence.entry(query.query_entry_id)
    if mode == "leave_training_group_out" and (
        entry.role != "training" or excluded_group_id != entry.group_id
    ):
        raise ValueError("invalid fold query binding")
    if query.query_artifact_id != declaration.artifact_id:
        raise ValueError("query artifact mismatch")
    identifier = query.query_record_id
    if entry.input_kind == "missing":
        if identifier is not None:
            raise ValueError("missing query cannot invent record")
    elif identifier is None:
        raise ValueError("measured query requires record ID")
    elif entry.input_kind == "response":
        import re

        if re.fullmatch(r"response-v2-[a-f0-9]{64}", identifier) is None:
            raise ValueError("invalid response ID")
    elif identifier != declaration.source_bindings[0].window_id:
        raise ValueError("baseline record ID mismatch")
    reasons = [] if evidence.snapshot.lifecycle.state == "provisional" else ["snapshot_unavailable"]
    unavailable = query_reasons(entry, mode)
    reasons += unavailable
    values = query.query_feature_values
    if reasons:
        if values is not None:
            raise ValueError("unavailable query exported values")
    elif (
        values is None
        or sum(v is not None for v in values.values()) != entry.eligible_feature_count
    ):
        raise ValueError("query feature count mismatch")
    if mode == "leave_training_group_out" and refit_id is None and not reasons:
        raise ValueError("available fold query requires computed refit")
    profiles = evidence.snapshot.profiles if profiles is None else profiles
    rows, prequalified = [], []
    query_sources, query_receipts = (
        evidence.footprint({entry.group_id}) if entry.group_id is not None else (set(), set())
    )
    for profile in profiles:
        codes = []
        if evidence.snapshot.lifecycle.state != "provisional":
            codes.append("snapshot_unavailable")
        if unavailable:
            codes.append("query_unavailable")
        if profile.partition_id != entry.partition_id:
            codes.append("partition_mismatch")
        if profile.state != "provisional":
            codes.append("profile_rejected")
        groups = set(profile.training_group_ids)
        sources, receipts = evidence.footprint(groups)
        if entry.group_id in groups or query_sources & sources or query_receipts & receipts:
            codes.append("source_overlap")
        row = dict(
            profile_id=profile.profile_id,
            partition_id=profile.partition_id,
            label=profile.label,
            state="excluded",
            reason_codes=codes,
            features=None,
            weight_sum=None,
            distance=None,
        )
        rows.append(row)
        if not codes:
            prequalified.append((profile, row))
    common = []
    if not reasons and prequalified:
        common = [
            name
            for name in FEATURE_NAMES
            if values[name] is not None
            and all(
                p.features[name].state == "supported"
                and p.features[name].weight == 1.0
                and p.features[name].dispersion > 0
                for p, _ in prequalified
            )
        ]
    coverage = ratio(len(common), 22)
    if not reasons:
        if not prequalified:
            reasons = ["no_compatible_profiles"]
        else:
            if len(common) < 17:
                reasons.append("insufficient_common_features")
            if len(common) * 4 < 22 * 3:
                reasons.append("insufficient_common_coverage")
            if not reasons and len(prequalified) * 22 > maximum_feature_rows:
                raise ValueError("N8 actual feature work exceeds global budget")
            for profile, row in prequalified:
                if reasons:
                    row["reason_codes"] = list(reasons)
                    continue
                features, contributions = {}, []
                for name in FEATURE_NAMES:
                    feature = profile.features[name]
                    codes = []
                    if values[name] is None:
                        codes.append("query_feature_missing")
                    if feature.state != "supported":
                        codes.append("profile_feature_excluded")
                    if not codes and name not in common:
                        codes.append("not_common_feature")
                    absolute = standardized = None
                    if not codes:
                        absolute = deviation(values[name], feature.center)
                        standardized = standardize(absolute, feature.dispersion)
                        contributions.append(standardized)
                    features[name] = dict(
                        state="excluded" if codes else "included",
                        reason_codes=codes,
                        query_value=values[name],
                        center=feature.center,
                        dispersion=feature.dispersion,
                        profile_weight=feature.weight,
                        applied_weight=0.0 if codes else 1.0,
                        absolute_deviation=absolute,
                        standardized_deviation=standardized,
                        weighted_contribution=standardized,
                    )
                row.update(
                    state="scored",
                    features=features,
                    weight_sum=float(len(common)),
                    distance=mean(contributions),
                )
    ranked = sorted(
        (r for r in rows if r["state"] == "scored"),
        key=lambda r: (r["distance"], r["label"], r["profile_id"]),
    )
    best = ranked[0] if ranked else None
    runner = ranked[1] if len(ranked) > 1 else None
    gap = margin(runner["distance"], best["distance"]) if runner else None
    if ranked:
        if len(ranked) < 2:
            reasons.append("no_competing_label")
        if best["distance"] > 3.0:
            reasons.append("distance_exceeded")
        if runner and gap < 0.25:
            reasons.append("ambiguous_labels")
    return dict(
        query_entry_id=entry.entry_id,
        query_artifact_id=declaration.artifact_id,
        query_record_id=identifier,
        query_mode=mode,
        excluded_group_id=excluded_group_id,
        refit_id=refit_id,
        query_feature_values=dict(values) if values is not None else None,
        candidates=rows,
        common_feature_names=common,
        common_coverage=coverage,
        ranked_profile_ids=[r["profile_id"] for r in ranked],
        best_label=best["label"] if best else None,
        runner_up_label=runner["label"] if runner else None,
        best_distance=best["distance"] if best else None,
        runner_up_distance=runner["distance"] if runner else None,
        margin=gap,
        state="unknown" if reasons else "provisional_match",
        chosen_label=None if reasons else best["label"],
        reason_codes=reasons,
    )
