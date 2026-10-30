"""Standalone declaration linking, without opening or authenticating source artifacts."""

from pydantic import model_validator

from ..calibration import CalibrationDataset, CalibrationReport
from ..calibration.lineage import validate_calibration_lineage
from ..profiles import ProfileSnapshot
from .contracts import MatchModel
from .policy_release import approved_policy_payload


class Evidence(MatchModel):
    dataset: CalibrationDataset
    report: CalibrationReport
    snapshot: ProfileSnapshot

    @model_validator(mode="after")
    def bindings(self):
        dataset, report = self.dataset, self.report
        lineage = validate_calibration_lineage(dataset)
        if (
            (report.dataset_id, report.dataset_content_hash, report.split_id, report.split_mode)
            != (
                dataset.dataset_id,
                dataset.content_hash,
                dataset.split.split_id,
                dataset.split.mode,
            )
            or report.artifact_receipts != dataset.artifacts
            or report.groups != lineage.groups
        ):
            raise ValueError("N8 dataset/report binding mismatch")
        if len(dataset.entries) != len(report.entries):
            raise ValueError("N8 entry inventory mismatch")
        report_entries = {entry.entry_id: entry for entry in report.entries}
        reviews = {review.review_id: review for review in dataset.reviews}
        for declared, actual, link in zip(
            dataset.entries, report.entries, lineage.entries, strict=True
        ):
            if (actual.entry_id, actual.input_kind, actual.label, actual.group_id, actual.role) != (
                declared.entry_id,
                declared.input_kind,
                declared.label,
                link.group_id,
                link.role,
            ) or (
                link.representative_entry_id != link.entry_id
                and actual.representative_entry_id
                != report_entries[link.representative_entry_id].representative_entry_id
            ):
                raise ValueError("N8 entry/lineage binding mismatch")
            if actual.input_kind != "missing":
                review = reviews.get(declared.label_review_id)
                label_unverified = (
                    declared.label_basis in ("unknown", "declared_only")
                    or review is None
                    or review.outcome != "confirmed"
                )
                split_unverified = (
                    lineage.split_mode == "prospective"
                    and lineage.split_review_state != "confirmed"
                )
                if ("label_unverified" in actual.reason_codes) != label_unverified or (
                    "split_unverified" in actual.reason_codes
                ) != split_unverified:
                    raise ValueError("N8 declared review reasons disagree")
        if self.snapshot.source_report is not None and self.snapshot.source_report != report:
            raise ValueError("N8 snapshot/report mismatch")
        if self.snapshot.policy.content_hash != approved_policy_payload()["profile_policy_hash"]:
            raise ValueError("N8 profile policy mismatch")
        return self

    def entry(self, identifier):
        for declaration, entry in zip(self.dataset.entries, self.report.entries, strict=True):
            if entry.entry_id == identifier:
                return declaration, entry
        raise ValueError("unknown N8 query entry")

    def footprint(self, group_ids):
        sources = {s for g in self.report.groups if g.group_id in group_ids for s in g.source_ids}
        receipts = {
            ("source", s.source_content_hash)
            for s in self.dataset.sources
            if s.source_id in sources
        }
        artifacts = {
            e.artifact_id
            for e, r in zip(self.dataset.entries, self.report.entries, strict=True)
            if r.group_id in group_ids and e.artifact_id is not None
        }
        receipts.update(
            ("artifact", a.sha256) for a in self.dataset.artifacts if a.artifact_id in artifacts
        )
        return sources, receipts
