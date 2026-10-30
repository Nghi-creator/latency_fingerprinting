"""Fresh source-byte binding, exact fit/query verification and single-inspection N9 APIs."""

import copy

import pytest

from latency_fingerprinting.passive_gating import (
    PassiveBaseline,
    PassiveReplay,
    build_passive_baseline,
    evaluate_passive_replay,
    fit_passive_baseline,
    operations,
    replay_passive_gate,
)
from tests.calibration.check_reproduction import FIXTURES

from .cases import POLICY, canonical, seal
from .linked_cases import source_case, write_source


@pytest.fixture
def source(tmp_path):
    ev, windows = source_case()
    directory = tmp_path / "source"
    ev, b, r = write_source(directory, ev, windows)
    return directory, ev, windows, b, r


@pytest.mark.parametrize("operation", ["build", "replay"])
def test_actual_source_matches_independent_literals_with_one_inspection(
    source, monkeypatch, operation
):
    directory, ev, _, b, r = source
    original = operations._inspect_calibration_snapshot
    calls = []

    def inspect(path, **anchors):
        calls.append((path, anchors))
        return original(path, **anchors)

    monkeypatch.setattr(operations, "_inspect_calibration_snapshot", inspect)
    anchors = dict(
        expected_split_id=ev["dataset"]["split"]["split_id"],
        expected_dataset_content_hash=ev["dataset"]["content_hash"],
    )
    if operation == "build":
        result = build_passive_baseline(directory, POLICY, **anchors)
        assert canonical(result.model_dump(mode="json")) == canonical(b)
    else:

        def never(*args, **kwargs):
            raise AssertionError("replay must not call the public builder and inspect twice")

        monkeypatch.setattr(operations, "build_passive_baseline", never)
        result = replay_passive_gate(directory, b, r, POLICY, **anchors)
        assert result == evaluate_passive_replay(b, r, POLICY)
        assert [row.recommendation for row in result.rows] == ["observe", "observe", "probe"]
        assert result.final_state.bad_duration_ms == 6000
    assert calls == [(directory, anchors)]


@pytest.mark.parametrize("wire_aliases", [False, True])
def test_raw_file_receipts_remain_distinct_from_normalized_n2_payload(tmp_path, wire_aliases):
    ev, windows = source_case()
    directory = tmp_path / "source"
    ev, b, r = write_source(directory, ev, windows, wire_aliases=wire_aliases)
    actual = build_passive_baseline(directory, POLICY)
    assert actual.model_dump(mode="json") == b
    assert replay_passive_gate(directory, b, r, POLICY) == evaluate_passive_replay(b, r, POLICY)
    assert actual.evidence.dataset.artifacts[0].sha256 == ev["dataset"]["artifacts"][0]["sha256"]


@pytest.mark.parametrize("which", ["query", "training"])
def test_self_consistent_forged_measurements_fail_fresh_source_comparison(source, which):
    directory, ev, windows, b, r = source
    if which == "query":
        p = r["windows"][0]["window"]["measurements"]["client.received_fps"]["summary"][
            "aggregates"
        ]
        for key in p:
            p[key] = 41.0
        r = seal(r, "replay_id", "passive-replay-")
        # Intrinsically valid declaration, but not the actual source's FPS.
        PassiveReplay.model_validate(r)
        evaluate_passive_replay(b, r, POLICY)
    else:
        changed = copy.deepcopy(windows)
        for identifier, w in changed.items():
            if identifier.startswith("train"):
                for key in w["measurements"]["client.received_fps"]["summary"]["aggregates"]:
                    w["measurements"]["client.received_fps"]["summary"]["aggregates"][key] = 61.0
        forged = fit_passive_baseline(
            ev, {k: v for k, v in changed.items() if k.startswith("train")}, POLICY
        )
        assert forged.strata[0].center == 61.0
        PassiveBaseline.model_validate(forged)
        with pytest.raises(ValueError, match="^invalid_passive_replay$"):
            replay_passive_gate(directory, forged, r, POLICY)
        return
    with pytest.raises(ValueError, match="^invalid_passive_replay$"):
        replay_passive_gate(directory, b, r, POLICY)


@pytest.mark.parametrize(
    "member", ["artifact-query-000.json", "artifact-train-0.json", "calibration-dataset.json"]
)
@pytest.mark.parametrize("operation", ["build", "replay"])
def test_changed_source_bytes_fail_with_fixed_private_errors(source, member, operation):
    directory, _, _, b, r = source
    path = directory / member
    if member == "calibration-dataset.json":
        path.write_bytes(b"private malformed /secret/path")
    else:
        path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(
        ValueError,
        match="^invalid_passive_" + ("baseline" if operation == "build" else "replay") + "$",
    ):
        if operation == "build":
            build_passive_baseline(directory, POLICY)
        else:
            replay_passive_gate(directory, b, r, POLICY)


@pytest.mark.parametrize("member", ["query", "training"])
def test_source_changes_with_updated_receipts_cannot_reuse_old_baseline(source, member):
    directory, ev, windows, b, r = source
    key = "query-000" if member == "query" else "train-0"
    w = windows[key]
    for aggregate in w["measurements"]["client.received_fps"]["summary"]["aggregates"]:
        w["measurements"]["client.received_fps"]["summary"]["aggregates"][aggregate] = 50.0
    # A new valid N6 dataset is legitimate, but the old immutable baseline is stale.
    other = directory.parent / "changed"
    write_source(other, ev, windows)
    build_passive_baseline(other, POLICY)
    with pytest.raises(ValueError, match="^invalid_passive_replay$"):
        replay_passive_gate(other, b, r, POLICY)


@pytest.mark.parametrize(
    "anchor,value",
    [
        ("expected_split_id", "split-" + "0" * 64),
        ("expected_dataset_content_hash", "sha256:" + "0" * 64),
        ("expected_split_id", True),
    ],
)
@pytest.mark.parametrize("operation", ["build", "replay"])
def test_anchors_are_checked_by_n6(source, anchor, value, operation):
    directory, _, _, b, r = source
    with pytest.raises(
        ValueError,
        match="^invalid_passive_" + ("baseline" if operation == "build" else "replay") + "$",
    ):
        if operation == "build":
            build_passive_baseline(directory, POLICY, **{anchor: value})
        else:
            replay_passive_gate(directory, b, r, POLICY, **{anchor: value})


@pytest.mark.parametrize(
    "case", ["baseline", "declared", "reviewed-roles", "missing", "controlled-healthy"]
)
def test_existing_synthetic_or_missing_evidence_never_fabricates_a_healthy_baseline(case):
    result = build_passive_baseline(FIXTURES / case, POLICY)
    assert result.state == "rejected" and not result.strata
    assert all(not item.selected for item in result.inputs)


@pytest.mark.parametrize("problem", ["directory", "policy", "baseline", "replay"])
def test_invalid_public_operands_have_fixed_errors(source, problem):
    directory, _, _, b, r = source
    if problem == "directory":
        directory = directory / "missing"
    elif problem == "policy":
        p = copy.deepcopy(POLICY)
        p["gates"]["minimum_bad_windows"] = 1
        POLICY_ARG = p
    elif problem == "baseline":
        b = PassiveBaseline.model_validate(b).model_copy(update={"state": "rejected"})
    else:
        r = PassiveReplay.model_validate(r).model_copy(update={"events": iter(())})
    with pytest.raises(ValueError, match="^invalid_passive_replay$"):
        replay_passive_gate(directory, b, r, POLICY_ARG if problem == "policy" else POLICY)


@pytest.mark.parametrize("case,kind", [("missing", "missing"), ("reviewed-roles", "response")])
def test_linked_nonpassive_inputs_keep_unknown_without_extracting_relief(case, kind):
    from latency_fingerprinting.passive_gating import create_passive_replay

    b = build_passive_baseline(FIXTURES / case, POLICY)
    entry = next(e for e in b.evidence.report.entries if e.input_kind == kind)
    r = create_passive_replay(
        b,
        mode="validation",
        start_ms=0,
        windows=[],
        stream=dict(
            acquisition_namespace="declared",
            run_id="declared",
            clock_domain_id="declared",
            generation_id="g1",
            stratum_id="passive-stratum-" + "0" * 64,
        ),
        events=[dict(kind="window", entry_id=entry.entry_id, at_ms=2000, reset_reason=None)],
    )
    result = replay_passive_gate(FIXTURES / case, b, r, POLICY)
    row = result.rows[0]
    assert row.reason_codes == (
        ("missing_measurements",) if kind == "missing" else ("not_passive_window",)
    )
    assert row.observed_fps is row.window_artifact_id is row.novelty_key is None
    assert row.recommendation == "no_action" and not row.state.degraded_latched


@pytest.mark.parametrize("wire_aliases", [False, True])
def test_actual_duplicate_export_before_canonical_does_not_credit_time_twice(
    tmp_path, wire_aliases
):
    from .cases import evidence

    _, windows = source_case()
    ev, windows = evidence(
        [
            windows["query-000"],
            windows["query-001"],
            windows["query-002"],
            copy.deepcopy(windows["query-000"]),
        ]
    )
    directory = tmp_path / "duplicates"
    _, b, r = write_source(directory, ev, windows, wire_aliases=wire_aliases)
    # Alias is last in the N6 inventory but arrives first in this replay.
    r["events"] = [r["events"][3], *r["events"][:3]]
    r = seal(r, "replay_id", "passive-replay-")
    result = replay_passive_gate(directory, b, r, POLICY)
    assert result.rows[0].reason_codes == ("duplicate_window",)
    assert [row.state.bad_windows for row in result.rows] == [0, 1, 2, 3]
    assert result.counts.ignored_duplicate_windows == 1
    assert result.final_state.bad_duration_ms == 6000
    assert result.final_state.proposals == 1


def test_fresh_query_pool_is_bounded_before_n9_serializes_it(tmp_path, monkeypatch):
    from latency_fingerprinting.models import ObservationWindowV2
    from latency_fingerprinting.passive_gating import create_passive_replay

    ev, windows = source_case()
    small = copy.deepcopy(windows)
    for key, w in windows.items():
        if key.startswith("query"):
            w["effective_settings"]["padding"] = "x" * (3600 * 1024)
    directory = tmp_path / "large-query-pool"
    write_source(directory, ev, windows)
    b = build_passive_baseline(directory, POLICY)
    inspected, origin = operations._inspect_calibration_snapshot(directory)
    declaration = b.evidence.dataset.entries[0]
    assert declaration.entry_id.startswith("query")
    stream = dict(
        acquisition_namespace="model-only",
        run_id="query-run",
        clock_domain_id="query-domain",
        generation_id="g1",
        stratum_id=b.strata[0].stratum_id,
    )
    query_entries = [e for e in b.evidence.dataset.entries if e.entry_id.startswith("query")]
    r = create_passive_replay(
        b,
        mode="validation",
        stream=stream,
        start_ms=0,
        windows=[dict(artifact_id=e.artifact_id, window=small[e.entry_id]) for e in query_entries],
        events=[
            dict(
                kind="window",
                entry_id=e.entry_id,
                at_ms=int(small[e.entry_id]["clock"]["elapsed_end_ms"]),
                reset_reason=None,
            )
            for e in query_entries
        ],
    )
    original_dump = ObservationWindowV2.model_dump

    def guard_dump(self, *args, **kwargs):
        if "padding" in self.effective_settings:
            raise AssertionError("N9 attempted to copy an over-budget fresh query pool")
        return original_dump(self, *args, **kwargs)

    monkeypatch.setattr(
        operations, "_inspect_calibration_snapshot", lambda *a, **kw: (inspected, origin)
    )
    monkeypatch.setattr(ObservationWindowV2, "model_dump", guard_dump)
    with pytest.raises(ValueError, match="^invalid_passive_replay$"):
        replay_passive_gate(directory, b, r, POLICY)
