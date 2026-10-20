"""Pure reconstruction of declared source components, splits and known byte aliases."""

from dataclasses import dataclass

from ..analytical.policy_release import payload_hash
from .contracts import ReviewState, Role, SplitMode
from .dataset import CalibrationDataset
from .report import GroupInspection


@dataclass(frozen=True, slots=True)
class EntryLineage:
    entry_id: str
    group_id: str | None
    role: Role | None
    representative_entry_id: str


@dataclass(frozen=True, slots=True)
class CalibrationLineage:
    dataset_id: str
    dataset_content_hash: str
    split_id: str
    split_mode: SplitMode
    split_review_state: ReviewState
    groups: tuple[GroupInspection, ...]
    entries: tuple[EntryLineage, ...]
    assurance: str = "external_review_declarations_not_authenticated"


def validate_calibration_lineage(
    dataset: CalibrationDataset,
    *,
    expected_split_id: str | None = None,
    expected_dataset_content_hash: str | None = None,
) -> CalibrationLineage:
    """Revalidate declarations and reject split leakage; never read artifact files.

    Group membership and receipt-level duplicates follow declared identities.
    Actual bytes, semantic response IDs and physical independence remain separate
    linked-inspection/external-review requirements.
    """
    try:
        dataset = CalibrationDataset.model_validate(dataset)
        for expected, actual in (
            (expected_split_id, dataset.split.split_id),
            (expected_dataset_content_hash, dataset.content_hash),
        ):
            if expected is not None and (type(expected) is not str or expected != actual):
                raise ValueError("frozen calibration identity changed")
        return _lineage(dataset)
    except ValueError:
        raise ValueError("invalid_calibration_lineage") from None


def _lineage(dataset):
    parents = {source.source_id: source.source_id for source in dataset.sources}

    def root(identifier):
        while parents[identifier] != identifier:
            parents[identifier] = parents[parents[identifier]]
            identifier = parents[identifier]
        return identifier

    def join(a, b):
        a, b = root(a), root(b)
        if a != b:
            parents[max(a, b)] = min(a, b)

    indexes = {}
    for source in dataset.sources:
        for kind, value in (
            ("run", (source.acquisition_namespace, source.run_id)),
            ("content", (source.source_type, source.source_content_hash)),
            ("session", (source.acquisition_namespace, source.session_id)),
            ("operator_group", (source.acquisition_namespace, source.independence_group)),
        ):
            previous = indexes.setdefault((kind, value), source.source_id)
            join(previous, source.source_id)
    for edge in dataset.derivations:
        join(edge.parent_source_id, edge.child_source_id)
    for entry in dataset.entries:
        if entry.input_kind == "response":
            join(*(binding.source_id for binding in entry.source_bindings))
    components = {}
    for source in dataset.sources:
        components.setdefault(root(source.source_id), []).append(source)
    assignments = {assignment.group_id: assignment.role for assignment in dataset.split.assignments}
    reviews = {review.review_id: review for review in dataset.reviews}
    groups, source_groups = [], {}
    for members in components.values():
        identifiers = tuple(member.source_id for member in members)
        identifier = "group-" + payload_hash({"source_ids": list(identifiers)})[7:]
        if identifier not in assignments:
            raise ValueError("split lost or divided a reconstructed component")
        groups.append(
            GroupInspection(
                group_id=identifier,
                source_ids=identifiers,
                role=assignments[identifier],
                independence_review_state=_review_state(members, reviews),
            )
        )
        source_groups.update((member, identifier) for member in identifiers)
    if set(assignments) != {group.group_id for group in groups}:
        raise ValueError("split contains stale or unrelated source groups")
    groups.sort(key=lambda group: group.group_id)
    representatives = _byte_aliases(dataset)
    entries = []
    for entry in dataset.entries:
        identifiers = {source_groups[binding.source_id] for binding in entry.source_bindings}
        if len(identifiers) > 1:
            raise ValueError("entry spans multiple source components")
        identifier = next(iter(identifiers), None)
        entries.append(
            EntryLineage(
                entry_id=entry.entry_id,
                group_id=identifier,
                role=assignments[identifier] if identifier is not None else None,
                representative_entry_id=representatives[entry.entry_id],
            )
        )
    freeze = reviews.get(dataset.split.freeze_review_id)
    return CalibrationLineage(
        dataset_id=dataset.dataset_id,
        dataset_content_hash=dataset.content_hash,
        split_id=dataset.split.split_id,
        split_mode=dataset.split.mode,
        split_review_state=freeze.outcome if freeze is not None else "missing",
        groups=tuple(groups),
        entries=tuple(entries),
    )


def _review_state(members, reviews):
    references = {member.review_id for member in members}
    if None not in references and len(references) == 1:
        review = reviews[next(iter(references))]
        if review.subject_ids == tuple(member.source_id for member in members):
            return review.outcome
    outcomes = {reviews[identifier].outcome for identifier in references if identifier is not None}
    return (
        "rejected"
        if "rejected" in outcomes
        else "uncertain"
        if "uncertain" in outcomes
        else "missing"
    )


def _byte_aliases(dataset):
    artifacts = {artifact.artifact_id: artifact for artifact in dataset.artifacts}
    sources = {source.source_id: source for source in dataset.sources}
    receipts, representatives = {}, {}
    for entry in dataset.entries:
        representatives[entry.entry_id] = entry.entry_id
        if entry.artifact_id is None:
            continue
        artifact = artifacts[entry.artifact_id]
        # Equal raw bytes cannot simultaneously have different input models,
        # lengths or embedded run/window/source claims. Dataset aliases are local.
        bindings = tuple(
            (
                binding.window_role,
                binding.window_id,
                sources[binding.source_id].run_id,
                sources[binding.source_id].source_type,
                sources[binding.source_id].source_content_hash,
                sources[binding.source_id].bundle_schema_version,
            )
            for binding in entry.source_bindings
        )
        signature = (entry.input_kind, artifact.bytes, bindings)
        existing = receipts.get(artifact.sha256)
        if existing is None:
            receipts[artifact.sha256] = (signature, entry.entry_id, entry.label)
        else:
            previous, representative, label = existing
            if signature != previous or (
                label is not None and entry.label is not None and label != entry.label
            ):
                raise ValueError("duplicate content has conflicting declarations")
            representatives[entry.entry_id] = representative
            # A preceding unknown alias cannot hide conflicting later labels.
            receipts[artifact.sha256] = (previous, representative, label or entry.label)
    return representatives
