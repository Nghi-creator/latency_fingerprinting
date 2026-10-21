"""Hand-calculated model-only inputs. These reports are not inspected real measurements."""

import copy
import hashlib
import json
from pathlib import Path

from tests.calibration.cases import HASH, counts, group_id, seal_report

ROOT = Path(__file__).resolve().parents[2]
NAMES = tuple(
    json.loads((ROOT / "docs/profiles/N7_PROFILE_POLICY_SPEC.json").read_bytes())["feature_names"]
)
PARTITION = "partition-" + "1" * 64


def policy():
    return json.loads((ROOT / "docs/profiles/N7_PROFILE_POLICY_SPEC.json").read_bytes())


def canonical(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def seal(payload):
    content = digest({k: v for k, v in payload.items() if k not in ("snapshot_id", "content_hash")})
    payload.update(snapshot_id="profile-snapshot-" + content, content_hash="sha256:" + content)
    return payload


def candidate_id(profile, p, report):
    profile["profile_id"] = "profile-" + digest(
        dict(
            policy_content_hash=p["content_hash"],
            source_report_id=report["report_id"],
            profile={k: v for k, v in profile.items() if k != "profile_id"},
        )
    )


def draft():
    return seal(
        dict(
            schema_version="profile-snapshot-v1",
            method_release="n7-profile-statistics-v1",
            policy=policy(),
            source_report=None,
            inputs=[],
            profiles=[],
            counts={
                name: 0
                for name in (
                    "retained_entries",
                    "selected_entries",
                    "excluded_entries",
                    "selected_groups",
                    "baseline_entries",
                    "missing_entries",
                    "heldout_response_entries",
                    "mixed_label_groups",
                )
            },
            lifecycle=dict(
                state="created",
                operation="create",
                parent_snapshot_id=None,
                replacement_snapshot_id=None,
                reason_code="draft",
                review=None,
            ),
            assurance="software_provisional_external_reviews_not_authenticated",
        )
    )


def source_report(n=5, *, heldout=True):
    groups, entries = [], []
    for index in range(n + (2 if heldout else 0)):
        name = f"entry-{index:03d}"
        sources = [f"source-{index:03d}-a", f"source-{index:03d}-b"]
        role = "training" if index < n else "validation" if index == n else "final_test"
        identifier = group_id(sources)
        groups.append(
            dict(
                group_id=identifier,
                source_ids=sources,
                role=role,
                independence_review_state="confirmed",
            )
        )
        entries.append(
            dict(
                entry_id=name,
                input_kind="response",
                group_id=identifier,
                role=role,
                partition_id=PARTITION,
                label="host_contention",
                eligible=True,
                reason_codes=[],
                representative_entry_id=name,
                eligible_feature_count=22,
            )
        )
    return seal_report(
        dict(
            schema_version="calibration-report-v1",
            method_release="n6-calibration-evidence-v1",
            dataset_id="dataset-" + "a" * 64,
            dataset_content_hash=HASH,
            split_id="split-" + "b" * 64,
            split_mode="prospective",
            artifact_receipts=[],
            groups=sorted(groups, key=lambda g: g["group_id"]),
            entries=entries,
            partitions=[
                dict(
                    partition_id=PARTITION,
                    input_kind="response",
                    retained_entries=len(entries),
                    eligible_entries=len(entries),
                    eligible_groups=len(entries),
                )
            ],
            counts={
                **counts(len(entries), len(entries), 0, len(groups), len(groups)),
                "by_role": dict(
                    engineering=counts(0, 0, 0, 0, 0),
                    training=counts(n, n, 0, n, n),
                    validation=counts(int(heldout), int(heldout), 0, int(heldout), int(heldout)),
                    final_test=counts(int(heldout), int(heldout), 0, int(heldout), int(heldout)),
                ),
            },
            assurance="external_review_declarations_not_authenticated",
        )
    )


def supported():
    p = draft()
    report = source_report()
    p["source_report"] = report
    selected = report["entries"][:5]
    p["inputs"] = [
        dict(
            entry_id=e["entry_id"],
            selected=e["role"] == "training",
            reason_codes=[] if e["role"] == "training" else ["not_training"],
            feature_values={name: float(i) for name in NAMES} if e["role"] == "training" else None,
        )
        for i, e in enumerate(report["entries"])
    ]
    rows = sorted(
        [
            dict(group_id=e["group_id"], entry_ids=[e["entry_id"]], median=float(i))
            for i, e in enumerate(selected)
        ],
        key=lambda row: row["group_id"],
    )
    features = {
        name: dict(
            state="supported",
            reason_codes=[],
            weight=1.0,
            group_values=copy.deepcopy(rows),
            contributing_groups=5,
            availability=dict(numerator=5, denominator=5, value=1.0),
            center=2.0,
            dispersion=1.0,
        )
        for name in NAMES
    }
    profile = dict(
        partition_id=PARTITION,
        label="host_contention",
        state="provisional",
        reason_codes=[],
        training_group_ids=sorted(e["group_id"] for e in selected),
        selected_entry_ids=[e["entry_id"] for e in selected],
        features=features,
        active_feature_count=22,
        active_feature_coverage=dict(numerator=22, denominator=22, value=1.0),
    )
    candidate_id(profile, p["policy"], report)
    p["profiles"] = [profile]
    p["counts"].update(
        retained_entries=7,
        selected_entries=5,
        excluded_entries=2,
        selected_groups=5,
        heldout_response_entries=2,
    )
    p["lifecycle"].update(state="provisional", operation="build", reason_code="supported_profiles")
    return seal(p)


def reviewed(p, operation="mark_stale", reason="external_review", replacement=None):
    parent = p["snapshot_id"]
    p = copy.deepcopy(p)
    state = dict(mark_stale="stale", reject="rejected", supersede="superseded")[operation]
    p["lifecycle"] = dict(
        state=state,
        operation=operation,
        parent_snapshot_id=parent,
        replacement_snapshot_id=replacement,
        reason_code=reason,
        review=dict(
            actor_id="operator",
            subject_snapshot_id=parent,
            replacement_snapshot_id=replacement,
            reason_code=reason,
            evidence_sha256=HASH,
        ),
    )
    return seal(p)


def grouped(groups, *, constants=0, missing_feature_groups=()):
    """Build expectations with the independent Decimal oracle frozen before N7 code."""
    from tests.profiles.test_design import feature

    p = draft()
    report = source_report(len(groups), heldout=False)
    templates = report["entries"]
    entries, inputs = [], []
    for index, values in enumerate(groups):
        for value in values:
            entry = {**templates[index], "entry_id": f"entry-{len(entries):03d}"}
            entry["representative_entry_id"] = entry["entry_id"]
            vector = {name: 2.0 if i < constants else float(value) for i, name in enumerate(NAMES)}
            if index in missing_feature_groups:
                vector[NAMES[-1]] = None
                entry["eligible_feature_count"] = 21
            entries.append(entry)
            inputs.append(
                dict(
                    entry_id=entry["entry_id"],
                    selected=True,
                    reason_codes=[],
                    feature_values=vector,
                )
            )
    n, g = len(entries), len(groups)
    report["entries"] = entries
    report["counts"] = {
        **counts(n, n, 0, g, g),
        "by_role": dict(
            engineering=counts(0, 0, 0, 0, 0),
            training=counts(n, n, 0, g, g),
            validation=counts(0, 0, 0, 0, 0),
            final_test=counts(0, 0, 0, 0, 0),
        ),
    }
    report["partitions"][0].update(retained_entries=n, eligible_entries=n, eligible_groups=g)
    seal_report(report)
    features = {}
    for name in NAMES:
        by_group = []
        ids_by_group = []
        for template in templates:
            records = [
                item
                for item, e in zip(inputs, entries, strict=True)
                if e["group_id"] == template["group_id"]
                and item["feature_values"][name] is not None
            ]
            by_group.append([r["feature_values"][name] for r in records])
            ids_by_group.append([r["entry_id"] for r in records])
        expected = feature(by_group)
        medians = expected.pop("group_medians")
        rows = [
            dict(group_id=template["group_id"], entry_ids=ids, median=median)
            for template, ids, median in zip(templates, ids_by_group, medians, strict=True)
            if median is not None
        ]
        features[name] = dict(
            group_values=sorted(rows, key=lambda row: row["group_id"]), **expected
        )
    active = sum(f["state"] == "supported" for f in features.values())
    reasons = []
    if g < 5:
        reasons.append("insufficient_training_groups")
    if active < 17:
        reasons.append("insufficient_active_features")
    if active * 4 < 22 * 3:
        reasons.append("insufficient_active_coverage")
    candidate = dict(
        partition_id=PARTITION,
        label="host_contention",
        state="rejected" if reasons else "provisional",
        reason_codes=reasons,
        training_group_ids=sorted(t["group_id"] for t in templates),
        selected_entry_ids=[e["entry_id"] for e in entries],
        features=features,
        active_feature_count=active,
        active_feature_coverage=dict(numerator=active, denominator=22, value=active / 22),
    )
    candidate_id(candidate, p["policy"], report)
    p.update(source_report=report, inputs=inputs, profiles=[candidate])
    p["counts"].update(
        retained_entries=n, selected_entries=n, excluded_entries=0, selected_groups=g
    )
    p["lifecycle"].update(
        state=candidate["state"],
        operation="build",
        reason_code="supported_profiles" if not reasons else "no_supported_profiles",
    )
    return seal(p)


def excluded(source):
    """Expected empty statistics for actual frozen synthetic N6 inspected reports."""
    from latency_fingerprinting.calibration import inspect_calibration_dataset
    from tests.calibration.check_reproduction import FIXTURES

    p = draft()
    report = inspect_calibration_dataset(FIXTURES / source).report.model_dump(mode="json")
    assert all(not e["eligible"] for e in report["entries"])
    inputs = []
    for entry in report["entries"]:
        if entry["input_kind"] == "missing":
            reasons = ["missing_measurements"]
        else:
            reasons = ["baseline_only"] if entry["input_kind"] == "healthy_window" else []
            if entry["role"] != "training":
                reasons.append("not_training")
            reasons.append("n6_excluded")
            if entry["representative_entry_id"] != entry["entry_id"]:
                reasons.append("duplicate_evidence")
            if entry["input_kind"] == "response" and entry["label"] is None:
                reasons.append("unknown_label")
        inputs.append(
            dict(
                entry_id=entry["entry_id"],
                selected=False,
                reason_codes=reasons,
                feature_values=None,
            )
        )
    features = {
        name: dict(
            state="excluded",
            reason_codes=[
                "missing_measurements",
                "insufficient_group_support",
                "insufficient_availability",
            ],
            weight=0.0,
            group_values=[],
            contributing_groups=0,
            availability=dict(numerator=0, denominator=0, value=None),
            center=None,
            dispersion=None,
        )
        for name in NAMES
    }
    profiles = []
    for partition, label in sorted(
        {
            (e["partition_id"], e["label"])
            for e in report["entries"]
            if e["input_kind"] == "response" and e["role"] == "training" and e["label"] is not None
        }
    ):
        candidate = dict(
            partition_id=partition,
            label=label,
            state="rejected",
            reason_codes=[
                "insufficient_training_groups",
                "insufficient_active_features",
                "insufficient_active_coverage",
            ],
            training_group_ids=[],
            selected_entry_ids=[],
            features=copy.deepcopy(features),
            active_feature_count=0,
            active_feature_coverage=dict(numerator=0, denominator=22, value=0.0),
        )
        candidate_id(candidate, p["policy"], report)
        profiles.append(candidate)
    p.update(source_report=report, inputs=inputs, profiles=profiles)
    p["counts"].update(
        retained_entries=len(inputs),
        excluded_entries=len(inputs),
        baseline_entries=sum(e["input_kind"] == "healthy_window" for e in report["entries"]),
        missing_entries=sum(e["input_kind"] == "missing" for e in report["entries"]),
        heldout_response_entries=sum(
            e["input_kind"] == "response" and e["role"] in ("validation", "final_test")
            for e in report["entries"]
        ),
    )
    p["lifecycle"].update(state="rejected", operation="build", reason_code="no_supported_profiles")
    return seal(p)
