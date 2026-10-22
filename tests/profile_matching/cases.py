"""Independent model-only evidence and hand/Decimal results; no inspected real acquisitions."""

import copy
import hashlib
import json
from pathlib import Path

from tests.calibration.cases import HASH, seal_dataset, seal_report
from tests.profiles.cases import NAMES, candidate_id, draft, seal, source_report
from tests.profiles.test_design import feature

ROOT = Path(__file__).resolve().parents[2]


def policy():
    return json.loads((ROOT / "docs/profile_matching/N8_MATCH_POLICY_SPEC.json").read_bytes())


def canonical(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode()


def digest(value):
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def root_seal(payload):
    prefix = (
        "profile-evaluation-"
        if payload["schema_version"] == "profile-evaluation-result-v1"
        else "profile-match-"
    )
    h = digest({k: v for k, v in payload.items() if k not in ("result_id", "content_hash")})
    payload.update(content_hash=h, result_id=prefix + h[7:])
    return payload


def evidence(n=5):
    report = source_report(n * 2)
    sources, artifacts, entries, reviews = [], [], [], []
    for i, entry in enumerate(report["entries"]):
        group = next(g for g in report["groups"] if g["group_id"] == entry["group_id"])
        label = "healthy" if i < n else "host_contention"
        entry["label"] = label
        artifact = f"artifact-{i:03d}"
        artifacts.append(
            dict(
                artifact_id=artifact,
                kind="analytical_response",
                file_name=artifact + ".json",
                sha256=digest(artifact),
                bytes=1,
            )
        )
        review_id = f"independence-{i:03d}"
        reviews.append(
            dict(
                review_id=review_id,
                reviewer_id="operator",
                kind="independence",
                subject_ids=group["source_ids"],
                outcome="confirmed",
                evidence_sha256=HASH,
            )
        )
        label_id = f"label-{i:03d}"
        reviews.append(
            dict(
                review_id=label_id,
                reviewer_id="operator",
                kind="label_binding",
                subject_ids=[entry["entry_id"]],
                outcome="confirmed",
                evidence_sha256=HASH,
            )
        )
        for name in group["source_ids"]:
            sources.append(
                dict(
                    source_id=name,
                    acquisition_namespace="model-only",
                    run_id="run-" + name,
                    session_id=f"session-{i:03d}",
                    independence_group=f"component-{i:03d}",
                    source_type="pixelated_bundle",
                    source_content_hash=digest(name),
                    bundle_schema_version="2",
                    review_id=review_id,
                )
            )
        entries.append(
            dict(
                entry_id=entry["entry_id"],
                input_kind="response",
                artifact_id=artifact,
                source_bindings=[
                    dict(window_role=role, source_id=name, window_id="window-" + name)
                    for role, name in zip(("degraded", "relief"), group["source_ids"], strict=True)
                ],
                label=label,
                label_basis="external_confirmation",
                label_review_id=label_id,
                experiment_artifact_id=None,
                experiment_phase=None,
            )
        )
    dataset = dict(
        schema_version="calibration-dataset-v1",
        method_release="n6-calibration-evidence-v1",
        artifacts=artifacts,
        sources=sorted(sources, key=lambda s: s["source_id"]),
        derivations=[],
        reviews=[],
        split=dict(
            mode="prospective",
            protocol_sha256=HASH,
            assignments=[dict(group_id=g["group_id"], role=g["role"]) for g in report["groups"]],
            freeze_review_id="freeze",
        ),
        entries=entries,
    )
    seal_dataset(dataset)
    reviews.append(
        dict(
            review_id="freeze",
            reviewer_id="operator",
            kind="split_freeze",
            subject_ids=[dataset["split"]["split_id"]],
            outcome="confirmed",
            evidence_sha256=HASH,
        )
    )
    dataset["reviews"] = sorted(reviews, key=lambda r: r["review_id"])
    seal_dataset(dataset)
    report.update(
        dataset_id=dataset["dataset_id"],
        dataset_content_hash=dataset["content_hash"],
        split_id=dataset["split"]["split_id"],
        artifact_receipts=copy.deepcopy(artifacts),
    )
    seal_report(report)
    snapshot = draft()
    snapshot["source_report"] = copy.deepcopy(report)
    snapshot["inputs"] = [
        dict(
            entry_id=e["entry_id"],
            selected=e["role"] == "training",
            reason_codes=[] if e["role"] == "training" else ["not_training"],
            feature_values={name: float(i if i < n else i - n + 4) for name in NAMES}
            if e["role"] == "training"
            else None,
        )
        for i, e in enumerate(report["entries"])
    ]
    profiles = []
    for label in ("healthy", "host_contention"):
        selected = [
            (e, item)
            for e, item in zip(report["entries"], snapshot["inputs"], strict=True)
            if item["selected"] and e["label"] == label
        ]
        values = [[item["feature_values"][NAMES[0]]] for e, item in selected]
        stats = feature(values)
        medians = stats.pop("group_medians")
        rows = sorted(
            [
                dict(group_id=e["group_id"], entry_ids=[e["entry_id"]], median=m)
                for (e, item), m in zip(selected, medians, strict=True)
            ],
            key=lambda r: r["group_id"],
        )
        profile = dict(
            partition_id=selected[0][0]["partition_id"],
            label=label,
            state="provisional",
            reason_codes=[],
            training_group_ids=sorted(e["group_id"] for e, item in selected),
            selected_entry_ids=[e["entry_id"] for e, item in selected],
            features={
                name: dict(group_values=copy.deepcopy(rows), **copy.deepcopy(stats))
                for name in NAMES
            },
            active_feature_count=22,
            active_feature_coverage=dict(numerator=22, denominator=22, value=1.0),
        )
        candidate_id(profile, snapshot["policy"], report)
        profiles.append(profile)
    snapshot["profiles"] = profiles
    snapshot["counts"].update(
        retained_entries=2 * n + 2,
        selected_entries=2 * n,
        excluded_entries=2,
        selected_groups=2 * n,
        heldout_response_entries=2,
    )
    snapshot["lifecycle"].update(
        state="provisional", operation="build", reason_code="supported_profiles"
    )
    seal(snapshot)
    return dict(dataset=dataset, report=report, snapshot=snapshot)


def match(n=5):
    ev = evidence(n)
    query = ev["report"]["entries"][-2]
    declaration = ev["dataset"]["entries"][-2]
    rows = []
    query_value = 2.0 if n == 5 else 2.5
    for profile in ev["snapshot"]["profiles"]:
        center = profile["features"][NAMES[0]]["center"]
        scale = profile["features"][NAMES[0]]["dispersion"]
        standardized = 0.0 if profile["label"] == "healthy" else 4.0 / scale
        absolute = 0.0 if profile["label"] == "healthy" else 4.0
        features = {
            name: dict(
                state="included",
                reason_codes=[],
                query_value=query_value,
                center=center,
                dispersion=scale,
                profile_weight=1.0,
                applied_weight=1.0,
                absolute_deviation=absolute,
                standardized_deviation=standardized,
                weighted_contribution=standardized,
            )
            for name in NAMES
        }
        rows.append(
            dict(
                profile_id=profile["profile_id"],
                partition_id=profile["partition_id"],
                label=profile["label"],
                state="scored",
                reason_codes=[],
                features=features,
                weight_sum=22.0,
                distance=standardized,
            )
        )
    decision = dict(
        query_entry_id=query["entry_id"],
        query_artifact_id=declaration["artifact_id"],
        query_record_id="response-v2-" + "e" * 64,
        query_mode="held_out",
        excluded_group_id=None,
        refit_id=None,
        query_feature_values=dict.fromkeys(NAMES, query_value),
        candidates=rows,
        common_feature_names=list(NAMES),
        common_coverage=dict(numerator=22, denominator=22, value=1.0),
        ranked_profile_ids=[r["profile_id"] for r in rows],
        best_label="healthy",
        runner_up_label="host_contention",
        best_distance=0.0,
        runner_up_distance=rows[1]["distance"],
        margin=rows[1]["distance"],
        state="provisional_match",
        chosen_label="healthy",
        reason_codes=[],
    )
    return root_seal(
        dict(
            schema_version="profile-match-result-v1",
            method_release="n8-profile-matching-v1",
            policy=policy(),
            evidence=ev,
            decision=decision,
            assurance=ev["snapshot"]["assurance"],
        )
    )


def oracle_decision(ev, entry, profiles, *, mode="held_out", refit=None):
    """Expected rows use the preimplementation Decimal oracle, never the scorer."""
    from .test_design import decide, deviation, margin, mean, standardize

    original = next(e for e in ev["dataset"]["entries"] if e["entry_id"] == entry["entry_id"])
    n = ev["snapshot"]["counts"]["selected_entries"] // 2
    if mode == "held_out":
        value = 2.0 if n == 5 else 2.5
    else:
        value = next(
            i["feature_values"][NAMES[0]]
            for i in ev["snapshot"]["inputs"]
            if i["entry_id"] == entry["entry_id"]
        )
    rows = []
    for profile in profiles:
        active = profile["state"] == "provisional"
        features = None
        if active:
            features = {}
            for name in NAMES:
                f = profile["features"][name]
                absolute = deviation(value, f["center"])
                std = standardize(absolute, f["dispersion"])
                features[name] = dict(
                    state="included",
                    reason_codes=[],
                    query_value=value,
                    center=f["center"],
                    dispersion=f["dispersion"],
                    profile_weight=1.0,
                    applied_weight=1.0,
                    absolute_deviation=absolute,
                    standardized_deviation=std,
                    weighted_contribution=std,
                )
        rows.append(
            dict(
                profile_id=profile["profile_id"],
                partition_id=profile["partition_id"],
                label=profile["label"],
                state="scored" if active else "excluded",
                reason_codes=[] if active else ["profile_rejected"],
                features=features,
                weight_sum=22.0 if active else None,
                distance=mean([f["weighted_contribution"] for f in features.values()])
                if active
                else None,
            )
        )
    ranked = sorted(
        [r for r in rows if r["state"] == "scored"],
        key=lambda r: (r["distance"], r["label"], r["profile_id"]),
    )
    common = list(NAMES) if ranked else []
    state, chosen, reasons = decide([[r["label"], r["distance"]] for r in ranked], len(common))
    best = ranked[0] if ranked else None
    runner = ranked[1] if len(ranked) > 1 else None
    return dict(
        query_entry_id=entry["entry_id"],
        query_artifact_id=original["artifact_id"],
        query_record_id="response-v2-" + "e" * 64,
        query_mode=mode,
        excluded_group_id=entry["group_id"] if mode != "held_out" else None,
        refit_id=refit["refit_id"] if refit else None,
        query_feature_values=dict.fromkeys(NAMES, value),
        candidates=rows,
        common_feature_names=common,
        common_coverage=dict(numerator=len(common), denominator=22, value=len(common) / 22),
        ranked_profile_ids=[r["profile_id"] for r in ranked],
        best_label=best["label"] if best else None,
        runner_up_label=runner["label"] if runner else None,
        best_distance=best["distance"] if best else None,
        runner_up_distance=runner["distance"] if runner else None,
        margin=margin(runner["distance"], best["distance"]) if runner else None,
        state=state,
        chosen_label=chosen,
        reason_codes=reasons,
    )


def oracle_refit(ev, group):
    snapshot = ev["snapshot"]
    report = ev["report"]
    inputs = copy.deepcopy(snapshot["inputs"])
    for entry, item in zip(report["entries"], inputs, strict=True):
        if entry["group_id"] == group:
            item.update(
                selected=False,
                reason_codes=[*item["reason_codes"], "leave_source_group_out"],
                feature_values=None,
            )
    profiles = []
    for base in snapshot["profiles"]:
        members = [
            (e, i)
            for e, i in zip(report["entries"], inputs, strict=True)
            if i["selected"] and e["label"] == base["label"]
        ]
        expected = feature([[i["feature_values"][NAMES[0]]] for e, i in members])
        medians = expected.pop("group_medians")
        values = sorted(
            [
                dict(group_id=e["group_id"], entry_ids=[e["entry_id"]], median=m)
                for (e, i), m in zip(members, medians, strict=True)
            ],
            key=lambda r: r["group_id"],
        )
        supported = expected["state"] == "supported"
        profile = dict(
            partition_id=base["partition_id"],
            label=base["label"],
            state="provisional" if supported else "rejected",
            reason_codes=[]
            if supported
            else [
                "insufficient_training_groups",
                "insufficient_active_features",
                "insufficient_active_coverage",
            ],
            training_group_ids=sorted(e["group_id"] for e, i in members),
            selected_entry_ids=[e["entry_id"] for e, i in members],
            features={
                name: dict(group_values=copy.deepcopy(values), **copy.deepcopy(expected))
                for name in NAMES
            },
            active_feature_count=22 if supported else 0,
            active_feature_coverage=dict(
                numerator=22 if supported else 0, denominator=22, value=1.0 if supported else 0.0
            ),
        )
        h = digest(
            dict(
                policy_content_hash=policy()["content_hash"],
                profile_policy_content_hash=snapshot["policy"]["content_hash"],
                source_report_id=report["report_id"],
                snapshot_id=snapshot["snapshot_id"],
                excluded_group_id=group,
                profile=profile,
            )
        )
        profile["profile_id"] = "profile-fold-" + h[7:]
        profiles.append(profile)
    selected = sum(i["selected"] for i in inputs)
    row = dict(
        excluded_group_id=group,
        state="computed",
        reason_codes=[],
        inputs=inputs,
        profiles=profiles,
        counts=dict(
            retained_entries=len(inputs),
            base_selected_entries=snapshot["counts"]["selected_entries"],
            removed_entries=1,
            selected_entries=selected,
            excluded_entries=len(inputs) - selected,
            selected_groups=selected,
        ),
    )
    h = digest(
        dict(
            policy_content_hash=policy()["content_hash"],
            source_report_id=report["report_id"],
            snapshot_id=snapshot["snapshot_id"],
            refit=row,
        )
    )
    row["refit_id"] = "profile-refit-" + h[7:]
    return row


def evaluation(mode="validation", n=5):
    ev = evidence(n)
    fold = mode == "leave_training_group_out"
    entries = [e for e in ev["report"]["entries"] if e["role"] == ("training" if fold else mode)]
    refits = [oracle_refit(ev, g) for g in sorted({e["group_id"] for e in entries})] if fold else []
    decisions = []
    for entry in entries:
        refit = next((r for r in refits if r["excluded_group_id"] == entry["group_id"]), None)
        decisions.append(
            oracle_decision(
                ev,
                entry,
                refit["profiles"] if refit else ev["snapshot"]["profiles"],
                mode="leave_training_group_out" if fold else "held_out",
                refit=refit,
            )
        )
    groups = sorted(
        [
            dict(
                group_id=e["group_id"],
                entry_ids=[e["entry_id"]],
                representative_entry_ids=[e["entry_id"]],
                truth_label=e["label"],
                truth_reason_codes=[],
                predicted_label=d["chosen_label"],
                prediction_reason_codes=["entry_unknown"] if d["chosen_label"] is None else [],
            )
            for e, d in zip(entries, decisions, strict=True)
        ],
        key=lambda g: g["group_id"],
    )
    labels = ("healthy", "host_contention", "render_capture_slowdown")
    matrix = {
        label: dict.fromkeys((*labels, "unknown"), 0) for label in (*labels, "unverified_truth")
    }
    for group in groups:
        matrix[group["truth_label"]][group["predicted_label"] or "unknown"] += 1
    unknown = sum(g["predicted_label"] is None for g in groups)
    correct = sum(g["predicted_label"] == g["truth_label"] for g in groups)

    def ratio(a, b):
        return dict(numerator=a, denominator=b, value=a / b if b else None)

    counts = dict(
        retained_entries=len(ev["report"]["entries"]),
        global_missing_entries=0,
        evaluated_entries=len(entries),
        response_entries=len(entries),
        baseline_entries=0,
        n6_excluded_entries=0,
        duplicate_entries=0,
        classification_groups=len(groups),
        baseline_only_groups=0,
        known_truth_groups=len(groups),
        unverified_truth_groups=0,
        provisional_match_groups=len(groups) - unknown,
        unknown_groups=unknown,
        correct_groups=correct,
        incorrect_groups=len(groups) - unknown - correct,
        computed_refits=len(refits),
        skipped_refits=0,
    )
    return root_seal(
        dict(
            schema_version="profile-evaluation-result-v1",
            method_release="n8-profile-matching-v1",
            policy=policy(),
            evidence=ev,
            mode=mode,
            refits=refits,
            decisions=decisions,
            group_outcomes=groups,
            confusion_matrix=matrix,
            counts=counts,
            metrics=dict(
                accuracy=ratio(correct, len(groups)),
                unknown_rate=ratio(unknown, len(groups)),
                truth_coverage=ratio(len(groups), len(groups)),
            ),
            assurance=ev["snapshot"]["assurance"],
        )
    )


def rebind(payload):
    """Reseal independently authored source declarations and all dependent content IDs."""
    ev = payload["evidence"]
    dataset = ev["dataset"]
    report = ev["report"]
    snapshot = ev["snapshot"]
    seal_dataset(dataset)
    report.update(
        dataset_id=dataset["dataset_id"],
        dataset_content_hash=dataset["content_hash"],
        split_id=dataset["split"]["split_id"],
    )
    seal_report(report)
    snapshot["source_report"] = copy.deepcopy(report)
    old_ids = [p["profile_id"] for p in snapshot["profiles"]]
    for p in snapshot["profiles"]:
        candidate_id(p, snapshot["policy"], report)
    seal(snapshot)
    mapping = dict(zip(old_ids, [p["profile_id"] for p in snapshot["profiles"]], strict=True))
    if "decision" in payload:
        for row in payload["decision"]["candidates"]:
            row["profile_id"] = mapping[row["profile_id"]]
        payload["decision"]["ranked_profile_ids"] = [
            mapping[i] for i in payload["decision"]["ranked_profile_ids"]
        ]
    return root_seal(payload)


def query_changed(value):
    from .test_design import deviation, margin, mean, standardize

    payload = match()
    d = payload["decision"]
    d["query_feature_values"] = dict.fromkeys(NAMES, value)
    for row in d["candidates"]:
        for f in row["features"].values():
            f["query_value"] = value
            f["absolute_deviation"] = deviation(value, f["center"])
            f["standardized_deviation"] = standardize(f["absolute_deviation"], f["dispersion"])
            f["weighted_contribution"] = f["standardized_deviation"]
        row["distance"] = mean([f["weighted_contribution"] for f in row["features"].values()])
    ranked = sorted(d["candidates"], key=lambda r: (r["distance"], r["label"], r["profile_id"]))
    gap = margin(ranked[1]["distance"], ranked[0]["distance"])
    reasons = []
    if ranked[0]["distance"] > 3.0:
        reasons.append("distance_exceeded")
    if gap < 0.25:
        reasons.append("ambiguous_labels")
    d.update(
        ranked_profile_ids=[r["profile_id"] for r in ranked],
        best_label=ranked[0]["label"],
        runner_up_label=ranked[1]["label"],
        best_distance=ranked[0]["distance"],
        runner_up_distance=ranked[1]["distance"],
        margin=gap,
        state="unknown" if reasons else "provisional_match",
        chosen_label=None if reasons else ranked[0]["label"],
        reason_codes=reasons,
    )
    return root_seal(payload)
