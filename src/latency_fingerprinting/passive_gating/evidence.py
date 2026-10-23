"""Immutable N6 declarations and exact N2 bindings, without filesystem authority."""

from pydantic import model_validator

from ..calibration import CalibrationDataset, CalibrationReport
from ..calibration.lineage import validate_calibration_lineage
from ..calibration.records import partition_id, verify_bindings
from ..models.v2_common import V2ContextSnapshot, thaw_json
from .contracts import MAX_TIME, METRIC, GateModel


def bounds(window):
    clock = window.clock
    values = (clock.elapsed_start_ms, clock.elapsed_end_ms, clock.duration_ms)
    if any(not value.is_integer() or not 0 <= value <= MAX_TIME for value in values):
        raise ValueError("N9 clock requires bounded integral milliseconds")
    return tuple(int(value) for value in values)


def scope(window):
    context = window.context.model_dump(mode="json")
    for key in ("context_id", "node_id", "network_scenario"):
        del context[key]
    return dict(
        registry=window.registry.model_dump(mode="json"),
        provenance=window.provenance.value,
        capture_method=window.capture_method.model_dump(mode="json"),
        clock=dict(basis=window.clock.basis.value, provenance=window.clock.provenance),
        source_format=dict(
            source_type=window.source_artifact.source_type,
            bundle_schema_version=window.source_artifact.bundle_schema_version,
        ),
        context=context,
        effective_settings=thaw_json(window.effective_settings),
    )


def quality_reasons(window):
    metric = window.measurements[METRIC]
    summary = metric.summary
    reasons = []
    if metric.support.state != "supported" or metric.role != "analytical_candidate":
        reasons.append("unsupported_metric")
    if summary.status.value != "complete" or summary.value is None:
        reasons.append("incomplete_metric")
    if summary.rejected_reasons:
        reasons.append("rejected_samples")
    if summary.usable_sample_count < 2:
        reasons.append("insufficient_samples")
    if not 1000 <= window.clock.duration_ms <= 10000:
        reasons.append("unsupported_window_duration")
    return reasons


class Evidence(GateModel):
    dataset: CalibrationDataset
    report: CalibrationReport

    @model_validator(mode="after")
    def bindings(self):
        d, r = self.dataset, self.report
        lineage = validate_calibration_lineage(d)
        if (
            (r.dataset_id, r.dataset_content_hash, r.split_id, r.split_mode)
            != (d.dataset_id, d.content_hash, d.split.split_id, d.split.mode)
            or r.artifact_receipts != d.artifacts
            or r.groups != lineage.groups
            or len(d.entries) != len(r.entries)
        ):
            raise ValueError("N9 dataset/report binding mismatch")
        reports = {e.entry_id: e for e in r.entries}
        reviews = {review.review_id: review for review in d.reviews}
        for declared, actual, link in zip(d.entries, r.entries, lineage.entries, strict=True):
            if (actual.entry_id, actual.input_kind, actual.label, actual.group_id, actual.role) != (
                declared.entry_id,
                declared.input_kind,
                declared.label,
                link.group_id,
                link.role,
            ) or (
                link.representative_entry_id != link.entry_id
                and actual.representative_entry_id
                != reports[link.representative_entry_id].representative_entry_id
            ):
                raise ValueError("N9 entry/lineage binding mismatch")
            if actual.input_kind != "missing":
                review = reviews.get(declared.label_review_id)
                unverified = (
                    declared.label_basis in ("unknown", "declared_only")
                    or review is None
                    or review.outcome != "confirmed"
                )
                split_unverified = (
                    lineage.split_mode == "prospective"
                    and lineage.split_review_state != "confirmed"
                )
                if ("label_unverified" in actual.reason_codes) != unverified or (
                    "split_unverified" in actual.reason_codes
                ) != split_unverified:
                    raise ValueError("N9 review declarations disagree")
        return self

    def entry(self, identifier):
        for declaration, entry in zip(self.dataset.entries, self.report.entries, strict=True):
            if entry.entry_id == identifier:
                return declaration, entry
        raise ValueError("unknown N9 entry")

    def footprint(self, group_ids):
        sources = {s for g in self.report.groups if g.group_id in group_ids for s in g.source_ids}
        receipts = {
            ("source", s.source_content_hash)
            for s in self.dataset.sources
            if s.source_id in sources
        }
        artifacts = {
            d.artifact_id
            for d, r in zip(self.dataset.entries, self.report.entries, strict=True)
            if r.group_id in group_ids and d.artifact_id is not None
        }
        receipts.update(
            ("artifact", a.sha256) for a in self.dataset.artifacts if a.artifact_id in artifacts
        )
        return sources, receipts

    def bind_window(self, declaration, entry, window):
        """Check all N6 facts derivable from this retained original passive window."""
        bounds(window)
        if any(
            not s.strip() or len(s.encode("utf-8")) > 256
            for s in (window.run_id, window.window_id, window.clock.domain_id)
        ):
            raise ValueError("N9 original identifier exceeds bound")
        sources = {s.source_id: s for s in self.dataset.sources}
        verify_bindings(declaration, window, sources)
        if entry.partition_id != partition_id(window, "healthy_window"):
            raise ValueError("N9 passive partition binding mismatch")
        invalid = (
            not window.validity.is_valid
            or bool(window.confounder_codes)
            or not any(
                m.support.state == "supported"
                and m.summary.status.value == "complete"
                and m.summary.value is not None
                for m in window.measurements.values()
            )
        )
        if ("synthetic_only" in entry.reason_codes) != (window.provenance.value == "synthetic") or (
            "baseline_invalid" in entry.reason_codes
        ) != invalid:
            raise ValueError("N9 original window contradicts N6 quality declarations")


def metadata_reasons(evidence, declaration, entry):
    reasons = []
    reviews = {r.review_id: r for r in evidence.dataset.reviews}
    review = reviews.get(declaration.label_review_id)
    if entry.input_kind == "missing":
        reasons.append("missing_measurements")
    if entry.input_kind != "healthy_window":
        reasons.append("not_baseline_window")
    if entry.role != "training":
        reasons.append("not_training")
    if (
        entry.label != "healthy"
        or declaration.label_basis in ("unknown", "declared_only")
        or review is None
        or review.outcome != "confirmed"
    ):
        reasons.append("not_confirmed_healthy")
    if set(entry.reason_codes) - {"duplicate_evidence"}:
        reasons.append("n6_excluded")
    if entry.representative_entry_id != entry.entry_id:
        reasons.append("duplicate_evidence")
    if any(
        e.input_kind != "missing" and e.group_id == entry.group_id and e.label != "healthy"
        for e in evidence.report.entries
    ):
        reasons.append("group_not_explicitly_healthy")
    return reasons


def validate_context(value):
    if set(value) != set(V2ContextSnapshot.model_fields) - {
        "context_id",
        "node_id",
        "network_scenario",
    }:
        raise ValueError("N9 scope context inventory mismatch")
    V2ContextSnapshot.model_validate(
        dict(thaw_json(value), context_id="scope", node_id="scope", network_scenario=None)
    )
    return value
