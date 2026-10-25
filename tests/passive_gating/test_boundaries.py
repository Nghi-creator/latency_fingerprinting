"""N9 source declarations, invalid input, global budgets and public dispatch checks."""

import copy
import hashlib
import json
import math
from pathlib import Path

import pytest

from latency_fingerprinting.cli import main
from latency_fingerprinting.models import ObservationWindowV2
from latency_fingerprinting.passive_gating import (
    PassiveBaseline,
    PassiveGatePolicy,
    PassiveGateResult,
    PassiveReplay,
    create_passive_replay,
    evaluate_passive_replay,
    fit_passive_baseline,
)
from latency_fingerprinting.passive_gating.contracts import tree_budget
from latency_fingerprinting.passive_gating.evidence import quality_reasons
from latency_fingerprinting.passive_gating.models import ReplayWindow
from latency_fingerprinting.schemas import SCHEMA_MODELS, render_schema

from .cases import (
    HASH,
    POLICY,
    canonical,
    evidence,
    rebuild_evidence,
    replay_payload,
    seal,
    window,
)

ROOT = Path(__file__).resolve().parents[2]


def fit(ev, windows):
    # All artificial training records here are metadata-eligible unless the test
    # explicitly removes them. Wrong-role query windows are never fitted.
    return fit_passive_baseline(
        ev, {k: v for k, v in windows.items() if k.startswith("train")}, POLICY
    )


@pytest.mark.parametrize("n", [4, 5])
def test_baseline_support_is_required_before_classification(n):
    ev, windows = evidence([window("q", query=True, fps=0.0)], training_values=(60.0,) * n)
    b = fit(ev, windows)
    r = replay_payload(b.model_dump(mode="json"), windows)
    result = evaluate_passive_replay(b, r, POLICY)
    row = result.rows[0]
    assert b.strata[0].raw_mad == 0.0
    assert b.state == ("provisional" if n == 5 else "rejected")
    assert row.classification == ("low" if n == 5 else "unavailable")
    assert row.reason_codes == (("entry_pending",) if n == 5 else ("baseline_unavailable",))


def test_zero_center_is_rejected_without_ratio_division():
    ev, windows = evidence([window("q", query=True, fps=0.0)], training_values=(0.0,) * 5)
    b = fit(ev, windows)
    assert b.strata[0].reason_codes == ("baseline_center_not_positive",)
    row = evaluate_passive_replay(
        b, replay_payload(b.model_dump(mode="json"), windows), POLICY
    ).rows[0]
    assert row.reason_codes == ("baseline_unavailable",)
    assert row.observed_fps is row.relative_fps is None


def test_empty_fit_retains_all_metadata_exclusions_and_no_windows():
    ev, windows = evidence()
    for review in ev["dataset"]["reviews"]:
        if review["kind"] == "label_binding":
            review["outcome"] = "uncertain"
    ev = rebuild_evidence(ev, windows)
    b = fit_passive_baseline(ev, {}, POLICY)
    assert b.state == "rejected" and not b.strata
    assert b.counts.retained_entries == 5 and b.counts.metadata_eligible_entries == 0
    assert all(
        i.reason_codes == ("not_confirmed_healthy", "n6_excluded") and i.window is None
        for i in b.inputs
    )


def test_training_window_cannot_be_reused_as_query():
    ev, windows = evidence()
    b = fit(ev, windows)
    w = windows["train-0"]
    source = next(s for s in ev["dataset"]["sources"] if s["run_id"] == w["run_id"])
    stream = dict(
        acquisition_namespace=source["acquisition_namespace"],
        run_id=w["run_id"],
        clock_domain_id=w["clock"]["domain_id"],
        generation_id="g1",
        stratum_id=b.strata[0].stratum_id,
    )
    r = create_passive_replay(
        b,
        mode="validation",
        stream=stream,
        start_ms=0,
        windows=[dict(artifact_id="artifact-train-0", window=w)],
        events=[dict(kind="window", entry_id="train-0", reset_reason=None, at_ms=2000)],
    )
    row = evaluate_passive_replay(b, r, POLICY).rows[0]
    assert row.reason_codes == ("not_requested_role", "source_overlap")
    assert row.observed_fps is None and row.recommendation == "no_action"


def test_declared_quality_failure_clears_latch_and_retains_ledger(roots):
    ev, windows, _, _ = roots
    fourth = window("q3", query=True, start=6000, end=8000, fps=40.0)
    fourth["validity"] = dict(is_valid=False, reason_codes=["producer_invalid"])
    ObservationWindowV2.model_validate(fourth)
    ev, windows = evidence([windows[f"query-{i:03d}"] for i in range(3)] + [fourth])
    ev = rebuild_evidence(ev, windows)
    b = fit(ev, windows)
    result = evaluate_passive_replay(b, replay_payload(b.model_dump(mode="json"), windows), POLICY)
    assert result.rows[2].recommendation == "probe"
    assert result.rows[3].reason_codes == ("n6_excluded",)
    assert result.final_state.status == "unknown" and result.final_state.proposals == 1
    assert result.final_state.bad_duration_ms == 0 and not result.final_state.degraded_latched


def test_query_label_is_not_a_trigger_or_a_training_vote(roots):
    ev, windows, b, r = roots
    before = evaluate_passive_replay(b, r, POLICY)
    for entry in ev["dataset"]["entries"]:
        if not entry["entry_id"].startswith("query"):
            continue
        review = "new-label-" + entry["entry_id"]
        entry.update(label="healthy", label_basis="external_confirmation", label_review_id=review)
        ev["dataset"]["reviews"].append(
            dict(
                review_id=review,
                reviewer_id="operator",
                kind="label_binding",
                subject_ids=[entry["entry_id"]],
                outcome="confirmed",
                evidence_sha256=HASH,
            )
        )
    ev["dataset"]["reviews"].sort(key=lambda r: r["review_id"])
    ev = rebuild_evidence(ev, windows)
    changed = fit(ev, windows)
    after = evaluate_passive_replay(
        changed, replay_payload(changed.model_dump(mode="json"), windows), POLICY
    )
    assert changed.counts.selected_entries == before.baseline.counts.selected_entries == 5
    assert after.rows == before.rows


def test_raw_fps_signed_zero_survives_but_ratio_is_positive():
    w = window("q", query=True, fps=0.0)
    for key in w["measurements"]["client.received_fps"]["summary"]["aggregates"]:
        w["measurements"]["client.received_fps"]["summary"]["aggregates"][key] = -0.0
    ev, windows = evidence([w])
    b = fit(ev, windows)
    result = evaluate_passive_replay(b, replay_payload(b.model_dump(mode="json"), windows), POLICY)
    assert math.copysign(1, result.rows[0].observed_fps) == -1
    assert math.copysign(1, result.rows[0].relative_fps) == 1
    p = result.model_dump(mode="json")
    p["rows"][0]["observed_fps"] = 0.0
    with pytest.raises(ValueError, match="does not reconstruct"):
        PassiveGateResult.model_validate(seal(p, "result_id", "passive-gate-"))


def test_fractional_clock_can_be_n2_valid_but_not_n9_admissible():
    w = window("fraction", query=True, end=2000.5)
    ObservationWindowV2.model_validate(w)
    with pytest.raises(ValueError, match="integral milliseconds"):
        ReplayWindow.model_validate(dict(artifact_id="fraction", window=w))


@pytest.mark.parametrize("field", ["inputs", "strata", "windows", "events", "rows"])
@pytest.mark.parametrize("value", [iter(()), [None] * 257])
def test_resources_fail_before_parsing_children(field, value):
    with pytest.raises(ValueError):
        PassiveGateResult.model_validate({field: value})


@pytest.mark.parametrize("which", ["groups", "entry_ids", "selected_entry_ids"])
def test_aggregate_resources_reject_individually_bounded_lists(which):
    if which == "groups":
        rows = [dict(groups=[{}] * 129), dict(groups=[{}] * 129)]
    else:
        group = dict(entry_ids=["a"], selected_entry_ids=["a"])
        group[which] = ["a"] * 129
        rows = [dict(groups=[group, group])]
    with pytest.raises(ValueError, match="global .* budget"):
        PassiveBaseline.model_validate(dict(strata=rows))


def test_python_tree_budget_checks_exact_canonical_bytes_and_cycles(monkeypatch):
    import latency_fingerprinting.passive_gating.contracts as contracts

    obj = {"a": [1, 2.0, True, None, {"nested": "text"}], "unicode": "é"}
    monkeypatch.setattr(contracts, "MAX_BYTES", len(canonical(obj)))
    assert tree_budget(obj) == obj
    monkeypatch.setattr(contracts, "MAX_BYTES", len(canonical(obj)) - 1)
    with pytest.raises(ValueError, match="byte limit"):
        tree_budget(obj)
    cyclic = {}
    cyclic["baseline"] = cyclic
    with pytest.raises(ValueError):
        PassiveBaseline.model_validate(cyclic)


@pytest.mark.parametrize(
    "cls", [PassiveGatePolicy, PassiveBaseline, PassiveReplay, PassiveGateResult]
)
@pytest.mark.parametrize(
    "raw",
    [
        b'{"schema_version":1,"schema_version":2}',
        b'{"v":NaN}',
        b"[" * 33 + b"0" + b"]" * 33,
        b" " * (10485760 + 1),
    ],
)
def test_all_root_json_decoders_are_bounded_and_duplicate_safe(cls, raw):
    with pytest.raises(ValueError):
        cls.model_validate_json(raw)


@pytest.mark.parametrize(
    "field,value", [("at_ms", True), ("at_ms", 1.5), ("at_ms", -1), ("at_ms", 9007199254740992)]
)
def test_event_clock_is_strict(roots, field, value):
    _, _, _, r = roots
    r["events"][0][field] = value
    with pytest.raises(ValueError):
        PassiveReplay.model_validate(seal(r, "replay_id", "passive-replay-"))


@pytest.mark.parametrize(
    "change",
    ["entry", "pool_missing", "pool_extra", "end", "stream", "generation", "event", "copy"],
)
def test_replay_references_and_identities_cannot_be_rehashed_away(roots, change):
    _, _, b, r = roots
    if change == "entry":
        r["events"][0]["entry_id"] = "unknown"
    elif change == "pool_missing":
        r["windows"].pop()
    elif change == "pool_extra":
        r["windows"].append(dict(artifact_id="zzz-unused", window=r["windows"][0]["window"]))
    elif change == "end":
        r["events"][0]["at_ms"] = 2001
    elif change == "stream":
        r["stream"]["stream_id"] = "passive-stream-" + "0" * 64
    elif change == "generation":
        r["stream"]["generation_id"] = "generation-2"
    elif change == "event":
        r["events"][0]["event_id"] = "passive-event-" + "0" * 64
    else:
        model = PassiveReplay.model_validate(r)
        invalid = model.model_copy(
            update={"events": (model.events[0].model_copy(update={"at_ms": True}),)}
        )
        with pytest.raises(ValueError):
            PassiveReplay.model_validate(invalid)
        return
    # Invalid references are checked even when every event follows a terminal reset.
    if change in {"entry", "end"}:
        event = r["events"][0]
        from .cases import digest

        event["event_id"] = "passive-event-" + digest(
            dict(
                method_release=r["method_release"],
                event={k: v for k, v in event.items() if k != "event_id"},
            )
        )
    with pytest.raises(ValueError, match="^invalid_passive_replay$"):
        evaluate_passive_replay(b, seal(r, "replay_id", "passive-replay-"), POLICY)


@pytest.mark.parametrize("kind", ["policy", "baseline", "replay", "result"])
def test_generic_validation_and_json_schema_roundtrip(roots, tmp_path, capsys, kind):
    import jsonschema

    from latency_fingerprinting import models

    _, _, b, r = roots
    payload, cls = {
        "policy": (POLICY, PassiveGatePolicy),
        "baseline": (b, PassiveBaseline),
        "replay": (r, PassiveReplay),
        "result": (
            evaluate_passive_replay(b, r, POLICY).model_dump(mode="json"),
            PassiveGateResult,
        ),
    }[kind]
    model = cls.model_validate(payload)
    assert getattr(models, cls.__name__) is cls
    jsonschema.validate(
        model.model_dump(mode="json", by_alias=True), json.loads(render_schema(cls))
    )
    file = tmp_path / "root.json"
    file.write_bytes(canonical(payload))
    assert main(["validate", str(file)]) == 0
    output = capsys.readouterr()
    assert not output.err
    assert cls.model_validate_json(output.out) == model


def test_additive_exports_keep_all_32_previous_schema_bytes():
    additions = {
        "passive-gate-policy-v1.schema.json",
        "passive-baseline-v1.schema.json",
        "passive-replay-v1.schema.json",
        "passive-gate-result-v1.schema.json",
    }
    assert len(SCHEMA_MODELS) == 38
    old = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (ROOT / "schemas").glob("*.schema.json")
        if p.name
        not in additions
        | {"live-probe-evidence-v1.schema.json", "cadence-probe-evidence-v1.schema.json"}
    }
    assert (
        hashlib.sha256(json.dumps(old, sort_keys=True).encode()).hexdigest()
        == "0ecfacf9a968e43cb6e70b2237855dc54cda2b8f138fbc47e68de1928f0204d9"
    )
    for name in additions:
        assert (ROOT / "schemas" / name).read_text() == render_schema(SCHEMA_MODELS[name])


def test_pure_factories_reject_bad_inventories_with_fixed_errors(roots):
    ev, windows, b, r = roots
    for supplied in ({}, windows, iter(windows), {None: None}):
        with pytest.raises(ValueError, match="^invalid_passive_baseline$"):
            fit_passive_baseline(ev, supplied, POLICY)
    with pytest.raises(ValueError, match="^invalid_passive_replay$"):
        create_passive_replay(b, mode="validation", stream={}, start_ms=0, windows=[], events=[])


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("missing", ("incomplete_metric", "insufficient_samples")),
        ("unsupported", ("unsupported_metric", "incomplete_metric", "insufficient_samples")),
        ("incomplete", ("incomplete_metric",)),
        ("rejected", ("incomplete_metric", "rejected_samples", "insufficient_samples")),
        ("one_sample", ("incomplete_metric", "insufficient_samples")),
        ("short", ("unsupported_window_duration",)),
    ],
)
def test_actual_n2_metric_exclusions_are_retained(kind, expected):
    from tests.models.v2_cases import window_payload

    w = window("quality", query=True, end=999 if kind == "short" else 2000)
    if kind != "short":
        values = {
            "incomplete": (60, None, 60),
            "one_sample": (60, None, None),
            "rejected": (-1, -1, -1),
        }.get(kind, (None, None, None))
        template = window_payload(real=True, values=values)
        w["measurements"]["client.received_fps"] = template["measurements"]["client.received_fps"]
        if kind == "unsupported":
            w["measurements"]["client.received_fps"]["support"] = dict(
                state="unsupported", declared_state="unsupported", basis="measurement_declaration"
            )
    typed = ObservationWindowV2.model_validate(w)
    assert tuple(quality_reasons(typed)) == expected
    ev, windows = evidence([w])
    ev = rebuild_evidence(ev, windows)
    b = fit(ev, windows)
    result = evaluate_passive_replay(b, replay_payload(b.model_dump(mode="json"), windows), POLICY)
    row = result.rows[0]
    assert row.reason_codes == expected
    assert row.observed_fps is row.relative_fps is None
    assert row.state.status == "unknown" and row.recommendation == "no_action"


@pytest.mark.parametrize("available,expected", [(8, ()), (7, ("insufficient_availability",))])
def test_selected_metric_missing_groups_remain_in_availability_denominator(available, expected):
    from tests.models.v2_cases import window_payload

    ev, windows = evidence(training_values=(60.0,) * 10)
    missing = window_payload(real=True, values=(None, None, None))["measurements"][
        "client.received_fps"
    ]
    for i in range(available, 10):
        windows[f"train-{i}"]["measurements"]["client.received_fps"] = copy.deepcopy(missing)
    ev = rebuild_evidence(ev, windows)
    b = fit(ev, windows)
    s = b.strata[0]
    assert s.reason_codes == expected
    assert len(s.groups) == 10
    assert sum(g.value is not None for g in s.groups) == available
    assert b.counts.metadata_eligible_entries == 10
    assert b.counts.selected_entries == available
    assert s.center == 60.0 and s.raw_mad == 0.0


def test_missing_event_breaks_degradation_without_inventing_a_window(roots):
    ev, windows, _, _ = roots
    ev["dataset"]["entries"].append(
        dict(
            entry_id="zzz-missing",
            input_kind="missing",
            artifact_id=None,
            source_bindings=[],
            label=None,
            label_basis="unknown",
            label_review_id=None,
            experiment_artifact_id=None,
            experiment_phase=None,
        )
    )
    ev = rebuild_evidence(ev, windows)
    b = fit(ev, windows)
    original = replay_payload(b.model_dump(mode="json"), windows)
    events = [{k: v for k, v in e.items() if k != "event_id"} for e in original["events"]]
    events.append(dict(kind="window", entry_id="zzz-missing", at_ms=8000, reset_reason=None))
    r = create_passive_replay(
        b,
        mode="validation",
        stream=original["stream"],
        start_ms=0,
        windows=original["windows"],
        events=events,
    )
    result = evaluate_passive_replay(b, r, POLICY)
    assert result.rows[-2].recommendation == "probe"
    last = result.rows[-1]
    assert last.reason_codes == ("missing_measurements",)
    assert last.window_artifact_id is last.novelty_key is last.observed_fps is None
    assert last.state.status == "unknown" and last.state.proposals == 1
    assert last.state.barrier_ms == 8000 and last.state.bad_duration_ms == 0


def test_response_is_never_a_passive_or_healthy_baseline_substitute():
    from tests.profile_matching.cases import evidence as paired_evidence

    paired = paired_evidence()
    ev = {key: paired[key] for key in ("dataset", "report")}
    b = fit_passive_baseline(ev, {}, POLICY)
    assert b.state == "rejected" and not b.strata
    query = next(e for e in b.evidence.report.entries if e.role == "validation")
    r = create_passive_replay(
        b,
        mode="validation",
        start_ms=0,
        windows=[],
        stream=dict(
            acquisition_namespace="model-only",
            run_id="unused",
            clock_domain_id="unused",
            generation_id="g1",
            stratum_id="passive-stratum-" + "0" * 64,
        ),
        events=[dict(kind="window", entry_id=query.entry_id, at_ms=2000, reset_reason=None)],
    )
    row = evaluate_passive_replay(b, r, POLICY).rows[0]
    assert row.reason_codes == ("not_passive_window",)
    assert row.window_artifact_id is row.novelty_key is row.observed_fps is None
    assert row.state.status == "unknown" and row.recommendation == "no_action"
