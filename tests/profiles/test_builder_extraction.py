"""Artificial inspection boundary: distinct feature bindings, missing data and metadata gates."""

from types import SimpleNamespace

import pytest

from latency_fingerprinting.calibration.report import CalibrationReport
from latency_fingerprinting.profiles import build_profile_snapshot, operations
from tests.calibration.cases import seal_report

from .cases import NAMES, candidate_id, policy, seal, supported
from .test_operations import UnreadableArtifact


class ExcludedFeature:
    state = "excluded"

    @property
    def normalized_value(self):
        raise AssertionError("excluded N3 feature value was accessed")


def distinct_features():
    """Literal affine offsets preserve the hand-authored center=2, MAD=1 expectations."""
    p = supported()
    candidate = p["profiles"][0]
    for number, name in enumerate(NAMES):
        offset = float(16 * (number - 11))
        for row in p["inputs"]:
            if row["selected"]:
                row["feature_values"][name] += offset
        feature = candidate["features"][name]
        feature["center"] += offset
        for row in feature["group_values"]:
            row["median"] += offset
    # A missing value changes only this feature's support; it must never become zero.
    p["inputs"][4]["feature_values"][NAMES[-1]] = None
    report = p["source_report"]
    report["entries"][4]["eligible_feature_count"] = 21
    seal_report(report)
    feature = candidate["features"][NAMES[-1]]
    feature.update(
        state="excluded",
        reason_codes=["insufficient_group_support"],
        weight=0.0,
        group_values=[r for r in feature["group_values"] if r["entry_ids"] != ["entry-004"]],
        contributing_groups=4,
        availability=dict(numerator=4, denominator=5, value=0.8),
        center=161.5,
    )
    candidate.update(
        active_feature_count=21,
        active_feature_coverage=dict(numerator=21, denominator=22, value=21 / 22),
    )
    candidate_id(candidate, p["policy"], report)
    return seal(p)


def boundary(payload, monkeypatch):
    report = CalibrationReport.model_validate(payload["source_report"])
    records = []
    for entry, row in zip(report.entries, payload["inputs"], strict=True):
        record = UnreadableArtifact()
        if row["selected"]:
            record = SimpleNamespace(
                policy=SimpleNamespace(content_hash=policy()["response_policy_hash"]),
                observation=SimpleNamespace(
                    degraded_window=SimpleNamespace(
                        registry=SimpleNamespace(model_dump=lambda **kw: policy()["registry"])
                    )
                ),
                features={
                    name: ExcludedFeature()
                    if value is None
                    else SimpleNamespace(state="eligible", normalized_value=value)
                    for name, value in row["feature_values"].items()
                },
            )
        records.append(SimpleNamespace(artifact_id=entry.entry_id, record=record))
    inspected = SimpleNamespace(
        report=report,
        dataset=SimpleNamespace(
            entries=[
                SimpleNamespace(entry_id=e.entry_id, artifact_id=e.entry_id)
                for e in reversed(report.entries)
            ]
        ),
        artifacts=list(reversed(records)),
    )
    monkeypatch.setattr(operations, "_inspect_dataset", lambda *a, **kw: (inspected, (0, 0)))
    return records


def test_distinct_feature_bindings_and_excluded_values_survive_unordered_artifacts(monkeypatch):
    expected = distinct_features()
    boundary(expected, monkeypatch)
    actual = build_profile_snapshot("artificial-inspection-only", policy())
    assert actual.model_dump(mode="json") == expected
    assert actual.inputs[4].feature_values[NAMES[-1]] is None
    assert actual.profiles[0].features[NAMES[-1]].center == 161.5
    assert actual.profiles[0].features[NAMES[-1]].dispersion == 1.0
    assert actual.profiles[0].features[NAMES[-1]].weight == 0.0


@pytest.mark.parametrize("change", ["registry", "policy", "missing_feature", "nonfinite", "count"])
def test_selected_source_contradictions_fail_the_entire_build(change, monkeypatch):
    records = boundary(distinct_features(), monkeypatch)
    record = records[0].record
    if change == "registry":
        record.observation.degraded_window.registry.model_dump = lambda **kw: {
            **policy()["registry"],
            "content_hash": "sha256:" + "0" * 64,
        }
    elif change == "policy":
        record.policy.content_hash = "sha256:" + "0" * 64
    elif change == "missing_feature":
        del record.features[NAMES[0]]
    elif change == "nonfinite":
        record.features[NAMES[0]].normalized_value = float("inf")
    else:
        record.features[NAMES[0]] = ExcludedFeature()
    with pytest.raises(ValueError, match="^invalid_profile_build$"):
        build_profile_snapshot("artificial-inspection-only", policy())


@pytest.mark.parametrize("excluded_conflict", [False, True])
def test_mixed_labels_are_resolved_before_feature_access(excluded_conflict, monkeypatch):
    from .cases import grouped

    payload = grouped([[0, 2], [1], [2], [3], [4]])
    report = payload["source_report"]
    report["entries"][1]["label"] = "render_capture_slowdown"
    excluded = [1] if excluded_conflict else [0, 1]
    if excluded_conflict:
        report["entries"][1].update(eligible=False, reason_codes=["label_unverified"])
        for counts in (report["counts"], report["counts"]["by_role"]["training"]):
            counts.update(eligible_entries=5, excluded_entries=1)
        report["partitions"][0]["eligible_entries"] = 5
    seal_report(report)
    for index in excluded:
        payload["inputs"][index].update(
            selected=False,
            reason_codes=["n6_excluded" if excluded_conflict else "mixed_group_labels"],
            feature_values=None,
        )
    boundary(payload, monkeypatch)
    result = build_profile_snapshot("artificial-inspection-only", policy())
    assert result.counts.selected_entries == (5 if excluded_conflict else 4)
    assert result.counts.mixed_label_groups == (0 if excluded_conflict else 1)
    assert all(result.inputs[i].feature_values is None for i in excluded)
    profiles = {p.label: p for p in result.profiles}
    host = profiles["host_contention"]
    assert host.features[NAMES[0]].center == (2.0 if excluded_conflict else 2.5)
    assert host.features[NAMES[0]].dispersion == 1.0
    assert host.state == ("provisional" if excluded_conflict else "rejected")
    assert not profiles["render_capture_slowdown"].training_group_ids
