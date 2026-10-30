"""Independent declared source graphs; expected components are supplied by each test."""

from .cases import HASH, RELEASE, digest, group_id, seal_dataset


def source(identifier):
    return dict(
        source_id=identifier,
        acquisition_namespace="system",
        run_id="run-" + identifier,
        session_id="session-" + identifier,
        independence_group="independent-" + identifier,
        source_type="synthetic_series",
        source_content_hash="sha256:" + digest({"source": identifier}),
        bundle_schema_version=None,
        review_id=None,
    )


def payload(bindings, groups, *, roles=None, sources=None, edges=()):
    names = sorted({name for members in bindings for name in members})
    sources = [source(name) for name in names] if sources is None else sources
    entries, artifacts = [], []
    for index, members in enumerate(bindings):
        name = f"entry-{index:03d}"
        paired = len(members) == 2
        entries.append(
            dict(
                entry_id=name,
                input_kind="response" if paired else "healthy_window",
                artifact_id=name,
                source_bindings=[
                    dict(
                        window_role=role,
                        source_id=member,
                        window_id="window-" + name + "-" + member,
                    )
                    for role, member in zip(
                        ("degraded", "relief") if paired else ("healthy",), members, strict=True
                    )
                ],
                label="host_contention" if paired else "healthy",
                label_basis="declared_only",
                label_review_id=None,
                experiment_artifact_id=None,
                experiment_phase=None,
            )
        )
        artifacts.append(
            dict(
                artifact_id=name,
                kind="analytical_response" if paired else "observation_window",
                file_name=name + ".json",
                sha256="sha256:" + digest({"artifact": name}),
                bytes=100,
            )
        )
    roles = roles or ["training"] * len(groups)
    return seal_dataset(
        dict(
            schema_version="calibration-dataset-v1",
            method_release=RELEASE,
            dataset_id="dataset-" + "0" * 64,
            content_hash=HASH,
            artifacts=artifacts,
            sources=sorted(sources, key=lambda s: s["source_id"]),
            derivations=sorted(
                [dict(parent_source_id=a, child_source_id=b) for a, b in edges],
                key=lambda e: (e["parent_source_id"], e["child_source_id"]),
            ),
            reviews=[],
            split=dict(
                split_id="split-" + "0" * 64,
                mode="retrospective",
                protocol_sha256=HASH,
                freeze_review_id=None,
                assignments=sorted(
                    [
                        dict(group_id=group_id(names), role=role)
                        for names, role in zip(groups, roles, strict=True)
                    ],
                    key=lambda a: a["group_id"],
                ),
            ),
            entries=entries,
        )
    )


def add_review(p, identifier, names, outcome="confirmed"):
    p["reviews"].append(
        dict(
            review_id=identifier,
            reviewer_id="reviewer",
            kind="independence",
            subject_ids=sorted(names),
            outcome=outcome,
            evidence_sha256=HASH,
        )
    )
    p["reviews"].sort(key=lambda r: r["review_id"])
    for s in p["sources"]:
        if s["source_id"] in names:
            s["review_id"] = identifier
    return seal_dataset(p)
