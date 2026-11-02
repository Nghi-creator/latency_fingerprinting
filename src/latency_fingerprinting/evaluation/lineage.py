"""Study-wide alias and role checks across actual N6 inspected snapshots."""


def verify_study_groups(manifest, inspections):
    bindings = {(b.dataset_key, b.group_id): b.study_group for b in manifest.groups}
    slots = {s.study_group: s for s in manifest.slots}
    actual = {
        (key, g.group_id) for key, inspected in inspections.items() for g in inspected.report.groups
    }
    if set(bindings) != actual:
        raise ValueError("every actual N6 group must be bound exactly once")
    identities, declarations = {}, {}
    for key, inspected in inspections.items():
        for group in inspected.report.groups:
            study = bindings[key, group.group_id]
            if slots[study].role != group.role:
                raise ValueError("study role contradicts actual N6 group role")
            sources = [s for s in inspected.dataset.sources if s.source_id in group.source_ids]
            for source in sources:
                original = (
                    source.acquisition_namespace,
                    source.run_id,
                    source.source_type,
                    source.source_content_hash,
                )
                declaration = (source.session_id, source.independence_group)
                if declarations.setdefault(original, declaration) != declaration:
                    raise ValueError("contradictory original source declarations")
                for identity in (
                    ("content", source.source_type, source.source_content_hash),
                    ("run", source.acquisition_namespace, source.run_id),
                    ("session", source.acquisition_namespace, source.session_id),
                    ("operator_group", source.acquisition_namespace, source.independence_group),
                ):
                    if identities.setdefault(identity, study) != study:
                        raise ValueError("source component divided across study groups")
    # Same declared study alias conservatively joins otherwise disconnected groups.
    # It never creates additional independent repetitions or authenticated review.
    return bindings
