"""Bounded linked calibration inspection over one pinned, private snapshot."""

import hashlib
import os
import tarfile
import tempfile
import zlib
from dataclasses import dataclass
from pathlib import Path

from ..analytical.policy_release import canonical_payload_bytes, payload_hash
from ..models.analytical_response_v2 import AnalyticalResponseV2
from ..models.observation_v2 import ObservationWindowV2
from ..observability.json import decode_trace_json
from ..scenarios.bundle_io import read_members
from ..scenarios.inspect import _inspect_experiment_members
from .bundle_io import DatasetSnapshot
from .contracts import AGGREGATE_BYTES, ARCHIVE_BYTES, REASONS, RELEASE, ROLES
from .dataset import CalibrationDataset
from .lineage import validate_calibration_lineage
from .records import label_reasons, partition_id, semantic_identity, verify_bindings, windows
from .report import CalibrationReport, _counts


@dataclass(frozen=True, slots=True)
class ValidatedArtifact:
    artifact_id: str
    record: object


@dataclass(frozen=True, slots=True)
class InspectedCalibration:
    dataset: CalibrationDataset
    report: CalibrationReport
    artifacts: tuple[ValidatedArtifact, ...]


def inspect_calibration_dataset(
    directory: Path, *, expected_split_id=None, expected_dataset_content_hash=None
) -> InspectedCalibration:
    """Verify actual bounded artifact bytes, retaining all valid unsupported evidence."""
    return _inspect_calibration_snapshot(
        directory,
        expected_split_id=expected_split_id,
        expected_dataset_content_hash=expected_dataset_content_hash,
    )[0]


def _inspect_calibration_snapshot(
    directory: Path, *, expected_split_id=None, expected_dataset_content_hash=None
):
    """Same inspector, also retaining actual pinned root identity for safe callers."""
    snapshot = None
    try:
        snapshot = DatasetSnapshot(Path(directory))
        dataset = snapshot.dataset
        lineage = validate_calibration_lineage(
            dataset,
            expected_split_id=expected_split_id,
            expected_dataset_content_hash=expected_dataset_content_hash,
        )
        records = _records(snapshot)
        report = _report(dataset, lineage, records)
        metadata = os.fstat(snapshot.descriptor)
        return InspectedCalibration(
            dataset,
            report,
            tuple(ValidatedArtifact(identifier, record) for identifier, record in records.items()),
        ), (metadata.st_dev, metadata.st_ino)
    except (OSError, ValueError, TypeError, KeyError, EOFError, tarfile.TarError, zlib.error):
        raise ValueError("invalid_calibration_dataset") from None
    finally:
        if snapshot is not None:
            try:
                snapshot.close()
            except (OSError, ValueError):
                raise ValueError("invalid_calibration_dataset") from None


def _records(snapshot):
    records = {}
    for artifact in snapshot.dataset.artifacts:
        raw = snapshot.read(artifact)
        if (
            len(raw) != artifact.bytes
            or "sha256:" + hashlib.sha256(raw).hexdigest() != artifact.sha256
        ):
            raise ValueError("calibration artifact bytes/hash mismatch")
        remaining = AGGREGATE_BYTES - snapshot.decoded_bytes
        if artifact.kind == "experiment_bundle":
            # Existing USTAR reader/validator, on the exact pinned bytes just hashed.
            with tempfile.TemporaryDirectory(prefix="n6-") as temporary:
                staged = Path(temporary).resolve() / "experiment.tar.gz"
                descriptor = os.open(
                    staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
                )
                try:
                    with os.fdopen(descriptor, "wb", closefd=False) as target:
                        target.write(raw)
                finally:
                    os.close(descriptor)
                files = read_members(staged, max_expanded_bytes=min(ARCHIVE_BYTES, remaining))
            snapshot.decoded_bytes += sum(map(len, files.values()))
            record = _inspect_experiment_members(files)
        else:
            if len(raw) > remaining:
                raise ValueError("calibration decoded JSON aggregate exceeds bound")
            snapshot.decoded_bytes += len(raw)
            cls = (
                AnalyticalResponseV2
                if artifact.kind == "analytical_response"
                else ObservationWindowV2
            )
            record = cls.model_validate(decode_trace_json(raw))
        records[artifact.artifact_id] = record
    return records


def _report(dataset, lineage, records):
    sources = {s.source_id: s for s in dataset.sources}
    reviews = {r.review_id: r for r in dataset.reviews}
    groups = {g.group_id: g for g in lineage.groups}
    entry_lineage = {e.entry_id: e for e in lineage.entries}
    semantic, entries = {}, []
    for entry in dataset.entries:
        link = entry_lineage[entry.entry_id]
        item = dict(
            entry_id=entry.entry_id,
            input_kind=entry.input_kind,
            group_id=link.group_id,
            role=link.role,
            partition_id=None,
            label=entry.label,
            eligible=False,
            reason_codes=[],
            representative_entry_id=entry.entry_id,
            eligible_feature_count=None,
        )
        if entry.input_kind == "missing":
            item["reason_codes"] = ["missing_measurements"]
            entries.append(item)
            continue
        record = records[entry.artifact_id]
        verify_bindings(entry, record, sources)
        item["partition_id"] = partition_id(record, entry.input_kind)
        identity = semantic_identity(record, entry.input_kind)
        previous = semantic.get(identity)
        if previous is None:
            semantic[identity] = (entry.entry_id, entry.label)
        else:
            representative, label = previous
            if label is not None and entry.label is not None and label != entry.label:
                raise ValueError("semantic duplicate has conflicting labels")
            item["representative_entry_id"] = representative
            semantic[identity] = (representative, label or entry.label)
        reasons = _evidence_reasons(entry, record, lineage, groups[link.group_id], item)
        reasons += label_reasons(entry, record, records.get(entry.experiment_artifact_id), reviews)
        if item["representative_entry_id"] != entry.entry_id:
            reasons.append("duplicate_evidence")
        item["reason_codes"] = [code for code in REASONS if code in reasons]
        item["eligible"] = not item["reason_codes"]
        entries.append(item)
    return _build_report(dataset, lineage, entries)


def _evidence_reasons(entry, record, lineage, group, item):
    reasons = []
    if group.role == "engineering":
        reasons.append("engineering_only")
    if lineage.split_mode == "retrospective":
        reasons.append("retrospective_split")
    elif lineage.split_review_state != "confirmed":
        reasons.append("split_unverified")
    if group.independence_review_state != "confirmed":
        reasons.append("independence_unverified")
    window = windows(record, entry.input_kind)[0]
    if window.provenance.value == "synthetic":
        reasons.append("synthetic_only")
    if entry.input_kind == "response":
        count = sum(f.state == "eligible" for f in record.features.values())
        item["eligible_feature_count"] = count
        if "confounded_pair" in record.invalid_reason_codes:
            reasons.append("confounded_response")
        if (
            not record.is_valid
            or count < record.policy.decision.minimum_shared_features
            or count / len(record.policy.features) < record.policy.decision.minimum_feature_coverage
        ):
            reasons.append("insufficient_response_features")
    elif (
        not window.validity.is_valid
        or window.confounder_codes
        or not any(
            m.support.state == "supported"
            and m.summary.status.value == "complete"
            and m.summary.value is not None
            for m in window.measurements.values()
        )
    ):
        reasons.append("baseline_invalid")
    return reasons


def _build_report(dataset, lineage, entries):
    # Reuse the report's count reconstruction rather than maintaining another counter policy.
    from .report import EntryInspection

    entries = [EntryInspection.model_validate(item) for item in entries]
    partitions = []
    for identifier in sorted({e.partition_id for e in entries if e.partition_id is not None}):
        members = [e for e in entries if e.partition_id == identifier]
        eligible = [e for e in members if e.eligible]
        partitions.append(
            dict(
                partition_id=identifier,
                input_kind=members[0].input_kind,
                retained_entries=len(members),
                eligible_entries=len(eligible),
                eligible_groups=len({e.group_id for e in eligible}),
            )
        )
    payload = dict(
        schema_version="calibration-report-v1",
        method_release=RELEASE,
        dataset_id=dataset.dataset_id,
        dataset_content_hash=dataset.content_hash,
        split_id=dataset.split.split_id,
        split_mode=dataset.split.mode,
        artifact_receipts=[a.model_dump(mode="json") for a in dataset.artifacts],
        groups=[g.model_dump(mode="json") for g in lineage.groups],
        entries=[e.model_dump(mode="json") for e in entries],
        partitions=partitions,
        counts={
            **_counts(entries, lineage.groups),
            "by_role": {
                role: _counts(
                    [e for e in entries if e.role == role],
                    [g for g in lineage.groups if g.role == role],
                )
                for role in ROLES
            },
        },
        assurance=lineage.assurance,
    )
    payload["report_id"] = "calibration-report-" + payload_hash(payload)[7:]
    return CalibrationReport.model_validate(payload)


def register_calibration_command(subparsers):
    parser = subparsers.add_parser(
        "inspect-calibration", help="verify a calibration dataset and linked evidence"
    )
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-split-id")
    parser.add_argument("--expected-dataset-content-hash")

    def run(args):
        from ..observability.output import write_trace_output

        try:
            _reject_input_output(args.directory, args.output)
            result = inspect_calibration_dataset(
                args.directory,
                expected_split_id=args.expected_split_id,
                expected_dataset_content_hash=args.expected_dataset_content_hash,
            )
            write_trace_output(
                args.output, canonical_payload_bytes(result.report.model_dump(mode="json"))
            )
        except (OSError, ValueError):
            raise ValueError("inspect-calibration: invalid_input_or_output") from None

    parser.set_defaults(handler=run)


def _reject_input_output(directory, output):
    from ..adapters.pixelated_bundle_io import _open_bundle

    source = _open_bundle(directory)
    try:
        parent = _open_bundle(output.absolute().parent)
        try:
            a, b = os.fstat(source), os.fstat(parent)
            if (a.st_dev, a.st_ino) == (b.st_dev, b.st_ino):
                raise ValueError("calibration output must be outside the input directory")
        finally:
            os.close(parent)
    finally:
        os.close(source)
