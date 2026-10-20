"""Hand-authored evidence/count expectations; hashing uses only the standard library."""

import hashlib
import json

HASH = "sha256:" + "a" * 64
RELEASE = "n6-calibration-evidence-v1"


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def group_id(names):
    return "group-" + digest({"source_ids": sorted(names)})


def seal_dataset(payload):
    split = payload["split"]
    split["split_id"] = "split-" + digest(
        {key: split[key] for key in ("mode", "protocol_sha256", "assignments")}
    )
    content = digest({k: v for k, v in payload.items() if k not in ("dataset_id", "content_hash")})
    payload.update(dataset_id="dataset-" + content, content_hash="sha256:" + content)
    return payload


def dataset(missing=False):
    sources = [
        dict(
            source_id=name,
            acquisition_namespace="acquisition-system",
            run_id="run-" + name,
            session_id="session-" + name,
            independence_group="independent-" + name,
            source_type="synthetic_series",
            source_content_hash="sha256:" + letter * 64,
            bundle_schema_version=None,
            review_id=None,
        )
        for name, letter in (("source-a", "a"), ("source-b", "b"))
    ]
    entry = dict(
        entry_id="entry-a",
        input_kind="missing" if missing else "response",
        artifact_id=None if missing else "response-a",
        source_bindings=[]
        if missing
        else [
            dict(window_role=role, source_id=name, window_id="window-" + name)
            for role, name in (("degraded", "source-a"), ("relief", "source-b"))
        ],
        label=None if missing else "host_contention",
        label_basis="unknown" if missing else "declared_only",
        label_review_id=None,
        experiment_artifact_id=None,
        experiment_phase=None,
    )
    return seal_dataset(
        dict(
            schema_version="calibration-dataset-v1",
            method_release=RELEASE,
            dataset_id="dataset-" + "0" * 64,
            content_hash=HASH,
            artifacts=[]
            if missing
            else [
                dict(
                    artifact_id="response-a",
                    kind="analytical_response",
                    file_name="response-a.json",
                    sha256=HASH,
                    bytes=100,
                )
            ],
            sources=[] if missing else sources,
            derivations=[],
            reviews=[],
            split=dict(
                split_id="split-" + "0" * 64,
                mode="retrospective",
                protocol_sha256=HASH,
                assignments=[]
                if missing
                else [dict(group_id=group_id(["source-a", "source-b"]), role="training")],
                freeze_review_id=None,
            ),
            entries=[entry],
        )
    )


def seal_report(payload):
    payload["report_id"] = "calibration-report-" + digest(
        {key: value for key, value in payload.items() if key != "report_id"}
    )
    return payload


def counts(retained, eligible, excluded, groups, eligible_groups):
    return dict(
        retained_entries=retained,
        eligible_entries=eligible,
        excluded_entries=excluded,
        retained_groups=groups,
        eligible_groups=eligible_groups,
    )


def report():
    # Independent design example 1: 3 paired responses, one healthy baseline, one missing.
    groups, entries = [], []
    partition = "partition-" + "1" * 64
    baseline = "partition-" + "2" * 64
    for name, sources, role, kind, label in (
        ("e1", ["source-a", "source-b"], "training", "response", "host_contention"),
        ("e2", ["source-c", "source-d"], "validation", "response", "host_contention"),
        ("e3", ["source-e", "source-f"], "final_test", "response", "host_contention"),
        ("e4", ["source-g"], "training", "healthy_window", "healthy"),
    ):
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
                input_kind=kind,
                group_id=identifier,
                role=role,
                partition_id=partition if kind == "response" else baseline,
                label=label,
                eligible=True,
                reason_codes=[],
                representative_entry_id=name,
                eligible_feature_count=22 if kind == "response" else None,
            )
        )
    entries.append(
        dict(
            entry_id="e5",
            input_kind="missing",
            group_id=None,
            role=None,
            partition_id=None,
            label=None,
            eligible=False,
            reason_codes=["missing_measurements"],
            representative_entry_id="e5",
            eligible_feature_count=None,
        )
    )
    return seal_report(
        dict(
            schema_version="calibration-report-v1",
            method_release=RELEASE,
            report_id="calibration-report-" + "0" * 64,
            dataset_id="dataset-" + "a" * 64,
            dataset_content_hash=HASH,
            split_id="split-" + "b" * 64,
            split_mode="prospective",
            artifact_receipts=[],
            groups=sorted(groups, key=lambda g: g["group_id"]),
            entries=entries,
            partitions=[
                dict(
                    partition_id=partition,
                    input_kind="response",
                    retained_entries=3,
                    eligible_entries=3,
                    eligible_groups=3,
                ),
                dict(
                    partition_id=baseline,
                    input_kind="healthy_window",
                    retained_entries=1,
                    eligible_entries=1,
                    eligible_groups=1,
                ),
            ],
            counts={
                **counts(5, 4, 1, 4, 4),
                "by_role": dict(
                    engineering=counts(0, 0, 0, 0, 0),
                    training=counts(2, 2, 0, 2, 2),
                    validation=counts(1, 1, 0, 1, 1),
                    final_test=counts(1, 1, 0, 1, 1),
                ),
            },
            assurance="external_review_declarations_not_authenticated",
        )
    )
