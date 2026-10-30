"""Independent model-only declarations, not inspected or recorded runtime evidence."""

import copy
import hashlib
import json
from datetime import UTC, datetime, timedelta

from latency_fingerprinting.models import ObservationWindowV2
from tests.calibration.cases import counts, group_id, seal_dataset, seal_report
from tests.models.v2_cases import window_payload

from .test_design import POLICY, fit

HASH = "sha256:" + "a" * 64
RELEASE = "n9-passive-gating-v1"
ASSURANCE = "software_provisional_declared_elapsed_not_live_authority"


def canonical(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def seal(payload, field, prefix):
    content = {k: v for k, v in payload.items() if k not in (field, "content_hash")}
    h = digest(content)
    payload.update({field: prefix + h, "content_hash": "sha256:" + h})
    return payload


def scope(window):
    context = copy.deepcopy(window["context"])
    for key in ("context_id", "node_id", "network_scenario"):
        del context[key]
    return dict(
        registry=window["registry"],
        provenance=window["provenance"],
        capture_method=window["capture_method"],
        clock={key: window["clock"][key] for key in ("basis", "provenance")},
        source_format={
            key: window["source_artifact"][key] for key in ("source_type", "bundle_schema_version")
        },
        context=context,
        effective_settings=window["effective_settings"],
    )


def scope_id(value):
    return "passive-stratum-" + digest(dict(method_release=RELEASE, scope=value))


def window(index, *, start=0, end=2000, fps=60.0, query=False):
    # All registered source evidence is derived by the established N1 test builder.
    p = ObservationWindowV2.model_validate(
        window_payload(phase="baseline", real=True, duration=end - start, values=(fps, fps, fps))
    ).model_dump(mode="json")
    p["run_id"] = "query-run" if query else f"training-{index}"
    p["window_id"] = f"window-{index}"
    p["source_artifact"]["content_hash"] = (
        "sha256:" + hashlib.sha256(p["run_id"].encode()).hexdigest()
    )
    c = p["clock"]
    c.update(
        domain_id="query-domain" if query else f"training-domain-{index}",
        elapsed_start_ms=float(start),
        elapsed_end_ms=float(end),
        duration_ms=float(end - start),
    )
    origin = datetime(2026, 10, 6, tzinfo=UTC)
    c["started_at"] = (origin + timedelta(milliseconds=start)).isoformat().replace("+00:00", "Z")
    c["ended_at"] = (origin + timedelta(milliseconds=end)).isoformat().replace("+00:00", "Z")
    for m in p["measurements"].values():
        summary = m["summary"]
        summary.update(window_start_ms=float(start), window_end_ms=float(end))
        for interval in summary["counter_intervals"]:
            interval["start_elapsed_ms"] += start
            interval["end_elapsed_ms"] += start
    # Any unusual FPS operand still has to satisfy the original N2 contract.
    return ObservationWindowV2.model_validate(p).model_dump(mode="json")


def evidence(query_windows=(), *, training_values=(60.0,) * 5):
    windows = {f"train-{i}": window(i, fps=v) for i, v in enumerate(training_values)}
    windows.update({f"query-{i:03d}": copy.deepcopy(w) for i, w in enumerate(query_windows)})
    entries, inspected, groups, sources, artifacts, reviews = [], [], {}, {}, [], []
    for name, w in sorted(windows.items()):
        query = name.startswith("query")
        sid = "query-source" if query else "source-" + name
        gid = group_id([sid])
        if sid not in sources:
            review = "review-" + sid
            sources[sid] = dict(
                source_id=sid,
                acquisition_namespace="model-only",
                run_id=w["run_id"],
                session_id="session-" + sid,
                independence_group="independent-" + sid,
                source_type="pixelated_bundle",
                source_content_hash=w["source_artifact"]["content_hash"],
                bundle_schema_version="2",
                review_id=review,
            )
            reviews.append(
                dict(
                    review_id=review,
                    reviewer_id="operator",
                    kind="independence",
                    subject_ids=[sid],
                    outcome="confirmed",
                    evidence_sha256=HASH,
                )
            )
            groups[gid] = dict(
                group_id=gid,
                source_ids=[sid],
                role="validation" if query else "training",
                independence_review_state="confirmed",
            )
        artifact = "artifact-" + name
        artifacts.append(
            dict(
                artifact_id=artifact,
                kind="observation_window",
                file_name=artifact + ".json",
                sha256="sha256:" + digest(w),
                bytes=len(canonical(w)),
            )
        )
        review = None if query else "label-" + name
        if review:
            reviews.append(
                dict(
                    review_id=review,
                    reviewer_id="operator",
                    kind="label_binding",
                    subject_ids=[name],
                    outcome="confirmed",
                    evidence_sha256=HASH,
                )
            )
        entries.append(
            dict(
                entry_id=name,
                input_kind="healthy_window",
                artifact_id=artifact,
                source_bindings=[
                    dict(window_role="healthy", source_id=sid, window_id=w["window_id"])
                ],
                label=None if query else "healthy",
                label_basis="unknown" if query else "external_confirmation",
                label_review_id=review,
                experiment_artifact_id=None,
                experiment_phase=None,
            )
        )
        # N6 partition projection is independently spelled out, including phase settings.
        s = scope(w)
        part = dict(
            input_kind="healthy_window",
            registry=s["registry"],
            policy_hash=None,
            provenance=s["provenance"],
            capture_method=s["capture_method"],
            clock=s["clock"],
            context=s["context"],
            probe=None,
            effective_settings={"baseline": s["effective_settings"]},
        )
        inspected.append(
            dict(
                entry_id=name,
                input_kind="healthy_window",
                group_id=gid,
                role="validation" if query else "training",
                partition_id="partition-" + digest(part),
                label=None if query else "healthy",
                eligible=not query,
                reason_codes=["label_unverified"] if query else [],
                representative_entry_id=name,
                eligible_feature_count=None,
            )
        )
    # N6 byte/semantic aliases retain one canonical representative, regardless
    # of event order. Do not count two exports as independent observations.
    representatives = {}
    for entry in inspected:
        original = windows[entry["entry_id"]]
        representative = representatives.setdefault(digest(original), entry["entry_id"])
        if representative != entry["entry_id"]:
            entry["representative_entry_id"] = representative
            entry["reason_codes"].append("duplicate_evidence")
            entry["eligible"] = False
    n, q = len(training_values), len(query_windows)
    dataset = dict(
        schema_version="calibration-dataset-v1",
        method_release="n6-calibration-evidence-v1",
        artifacts=artifacts,
        sources=sorted(sources.values(), key=lambda s: s["source_id"]),
        derivations=[],
        reviews=[],
        split=dict(
            mode="prospective",
            protocol_sha256=HASH,
            assignments=[dict(group_id=g, role=groups[g]["role"]) for g in sorted(groups)],
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
    partitions = []
    for pid in sorted({e["partition_id"] for e in inspected}):
        members = [e for e in inspected if e["partition_id"] == pid]
        selected = [e for e in members if e["eligible"]]
        partitions.append(
            dict(
                partition_id=pid,
                input_kind="healthy_window",
                retained_entries=len(members),
                eligible_entries=len(selected),
                eligible_groups=len({e["group_id"] for e in selected}),
            )
        )
    report = seal_report(
        dict(
            schema_version="calibration-report-v1",
            method_release="n6-calibration-evidence-v1",
            dataset_id=dataset["dataset_id"],
            dataset_content_hash=dataset["content_hash"],
            split_id=dataset["split"]["split_id"],
            split_mode="prospective",
            artifact_receipts=artifacts,
            groups=[groups[g] for g in sorted(groups)],
            entries=inspected,
            partitions=partitions,
            counts={
                **counts(n + q, n, q, len(groups), n),
                "by_role": dict(
                    engineering=counts(0, 0, 0, 0, 0),
                    training=counts(n, n, 0, n, n),
                    validation=counts(q, 0, q, int(bool(q)), 0),
                    final_test=counts(0, 0, 0, 0, 0),
                ),
            },
            assurance="external_review_declarations_not_authenticated",
        )
    )
    return dict(dataset=dataset, report=report), windows


def baseline(ev, windows):
    inputs = []
    projection = scope(next(w for key, w in windows.items() if key.startswith("train")))
    sid = scope_id(projection)
    groups = []
    for entry in ev["report"]["entries"]:
        w = windows[entry["entry_id"]]
        selected = entry["role"] == "training"
        inputs.append(
            dict(
                entry_id=entry["entry_id"],
                group_id=entry["group_id"],
                stratum_id=sid if selected else None,
                window=w if selected else None,
                selected=selected,
                reason_codes=[]
                if selected
                else [
                    "not_training",
                    "not_confirmed_healthy",
                    "n6_excluded",
                    *(
                        ["duplicate_evidence"]
                        if "duplicate_evidence" in entry["reason_codes"]
                        else []
                    ),
                    "group_not_explicitly_healthy",
                ],
            )
        )
        if selected:
            groups.append(
                dict(
                    group_id=entry["group_id"],
                    entry_ids=[entry["entry_id"]],
                    selected_entry_ids=[entry["entry_id"]],
                    value=w["measurements"]["client.received_fps"]["summary"]["aggregates"][
                        "median"
                    ],
                )
            )
    center, mad, reasons = fit([[g["value"]] for g in groups])
    state = "rejected" if reasons else "provisional"
    return seal(
        dict(
            schema_version="passive-baseline-v1",
            method_release=RELEASE,
            policy=copy.deepcopy(POLICY),
            evidence=copy.deepcopy(ev),
            inputs=inputs,
            strata=[
                dict(
                    stratum_id=sid,
                    scope=projection,
                    groups=sorted(groups, key=lambda g: g["group_id"]),
                    center=center,
                    raw_mad=mad,
                    state=state,
                    reason_codes=reasons,
                )
            ],
            state=state,
            assurance=ASSURANCE,
            counts=dict(
                retained_entries=len(inputs),
                metadata_eligible_entries=len(groups),
                selected_entries=len(groups),
                excluded_entries=len(inputs) - len(groups),
                retained_strata=1,
                provisional_strata=int(not reasons),
            ),
        ),
        "baseline_id",
        "passive-baseline-",
    )


def stream_and_queries(b):
    queries = [e for e in b["evidence"]["dataset"]["entries"] if e["entry_id"].startswith("query")]
    stream = dict(
        acquisition_namespace="model-only",
        run_id="query-run",
        clock_domain_id="query-domain",
        generation_id="generation-1",
        stratum_id=b["strata"][0]["stratum_id"],
    )
    stream["stream_id"] = "passive-stream-" + digest(
        dict(
            method_release=RELEASE,
            baseline_id=b["baseline_id"],
            dataset_id=b["evidence"]["dataset"]["dataset_id"],
            stream=stream,
        )
    )
    return stream, queries


def replay_payload(b, windows, events=None):
    stream, queries = stream_and_queries(b)
    if events is None:
        events = [
            dict(
                kind="window",
                at_ms=int(windows[e["entry_id"]]["clock"]["elapsed_end_ms"]),
                entry_id=e["entry_id"],
                reset_reason=None,
            )
            for e in queries
        ]
    events = copy.deepcopy(events)
    for event in events:
        event["event_id"] = "passive-event-" + digest(dict(method_release=RELEASE, event=event))
    ids = {e["entry_id"] for e in events if e["kind"] == "window"}
    pool = [
        dict(artifact_id=e["artifact_id"], window=windows[e["entry_id"]])
        for e in queries
        if e["entry_id"] in ids
    ]
    return seal(
        dict(
            schema_version="passive-replay-v1",
            method_release=RELEASE,
            policy_content_hash=POLICY["content_hash"],
            baseline_id=b["baseline_id"],
            dataset_id=b["evidence"]["dataset"]["dataset_id"],
            mode="validation",
            stream=stream,
            start_ms=0,
            windows=pool,
            events=events,
            assurance=ASSURANCE,
        ),
        "replay_id",
        "passive-replay-",
    )


def rebuild_evidence(ev, windows):
    """Derive existing N6 facts in memory; no N9 fitting or replay expectations."""
    from latency_fingerprinting.calibration import CalibrationDataset, validate_calibration_lineage
    from latency_fingerprinting.calibration.inspection import _report

    ev = copy.deepcopy(ev)
    d = ev["dataset"]
    artifacts = {artifact["artifact_id"]: artifact for artifact in d["artifacts"]}
    for entry in d["entries"]:
        if entry["input_kind"] == "healthy_window":
            raw = canonical(windows[entry["entry_id"]])
            artifacts[entry["artifact_id"]].update(
                sha256="sha256:" + hashlib.sha256(raw).hexdigest(), bytes=len(raw)
            )
    seal_dataset(d)
    for review in d["reviews"]:
        if review["kind"] == "split_freeze":
            review["subject_ids"] = [d["split"]["split_id"]]
    seal_dataset(d)
    dataset = CalibrationDataset.model_validate(d)
    records = {
        entry.artifact_id: ObservationWindowV2.model_validate(windows[entry.entry_id])
        for entry in dataset.entries
        if entry.input_kind == "healthy_window"
    }
    report = _report(dataset, validate_calibration_lineage(dataset), records)
    return dict(dataset=dataset.model_dump(mode="json"), report=report.model_dump(mode="json"))
