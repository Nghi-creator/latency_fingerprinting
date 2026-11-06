"""Invented source-shaped data; never empirical fitting or independent support."""

import hashlib
import json
from copy import deepcopy

import pytest

from latency_fingerprinting.evaluation import combined_interval_candidate as method
from latency_fingerprinting.evaluation import combined_resource_projection as projection
from latency_fingerprinting.evaluation.contrast_bounds import native_worker_clock_id
from latency_fingerprinting.evaluation.cpu_resource_response import CONSTANTS, PHASES
from latency_fingerprinting.evaluation.fixture_conditions import CONDITIONS

CONTEXT = "sha256:" + "c" * 64


def source(identifier, arm=0, identical=False):
    generation = dict(owner=identifier, pipeline="pipe", peer="peer")
    worker_clock = native_worker_clock_id(generation)
    context = dict(
        method=projection.SOURCE_METHOD, generation=generation, controller_origin_ns="12345"
    )
    clock = (
        "controller-monotonic-"
        + hashlib.sha256(
            json.dumps(context, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )
    if identical:
        arm = 0
    events = [
        dict(
            kind="n11_resource_context",
            method=projection.SOURCE_METHOD,
            context=context,
            clock_id=clock,
            live_authority=False,
        ),
        dict(kind="n11_pair_dispatched", request=dict(generation=generation, target_fps=24)),
        dict(kind="n11_pacing_started", at_ns=3_500_000_000),
        dict(kind="n11_condition_cleanup", at_ns=15_500_000_000),
    ]
    samples, summaries = {}, []
    encoded, usage, throttled, sequence = 0, 0, 0, 0
    for i, phase in enumerate(PHASES):
        rate = 24 if phase == "relief" else 30
        if arm == 1 and phase in ("degraded", "relief", "recovery"):
            rate = 4 if phase == "relief" else 6
        cpu_step = 900000 if arm == 2 and phase in ("degraded", "relief", "recovery") else 100000
        throttle_step = 200000 if arm == 2 and phase in ("degraded", "relief", "recovery") else 0
        rows, samples[phase] = [], []
        for j in range(7):
            start = i * 4_000_000_000 + j * 500_000_000
            cpu = dict(
                **CONSTANTS,
                phase=phase,
                clock_id=clock,
                sequence=sequence,
                read_start_ns=start + 1000,
                read_end_ns=start + 2000,
                quota=dict(quota_usec=200000, period_usec=100000),
                source_identity={
                    n: dict(device=1, inode=k + 1)
                    for k, n in enumerate(("cgroup", "cpu.stat", "cpu.max"))
                },
                counters=dict(
                    usage_usec=usage + j * cpu_step,
                    user_usec=usage + j * cpu_step,
                    system_usec=0,
                    nr_periods=sequence,
                    nr_throttled=sequence,
                    throttled_usec=throttled + j * throttle_step,
                ),
                live_authority=False,
            )
            target = 24 if phase == "relief" else 30
            row = dict(
                at_ns=start,
                sequence=sequence + 1,
                encoded_buffers=encoded + j * rate // 2,
                configured_fps=target,
                negotiated_fps=target,
                native_read=dict(
                    method="native-counter-read-brackets-v1",
                    basis="worker_elapsed_monotonic_ns",
                    clock_id=worker_clock,
                    read_start_ns=start,
                    read_end_ns=start + 100,
                ),
                container_cpu_read=cpu,
                condition_witness=dict(condition=CONDITIONS[arm], dose=arm),
            )
            rows.append(row)
            samples[phase].append(cpu)
            sequence += 1
        encoded = rows[-1]["encoded_buffers"] + 10
        usage += 6 * cpu_step
        throttled += 6 * throttle_step
        if phase in ("healthy", "post"):
            events.append(dict(kind="n11_pacing_reference", phase=phase, samples=rows))
        else:
            events.append(dict(kind="n11_pair_phase_started", phase=phase, at_ns=i * 4_000_000_000))
            events.extend(dict(kind="n11_pair_native", phase=phase, **row) for row in rows)
            events.append(
                dict(
                    kind="n11_pair_phase_completed",
                    phase=phase,
                    at_ns=i * 4_000_000_000 + 3_000_100_000,
                )
            )
        summaries.append(
            dict(
                phase=phase,
                sample_count=7,
                read_start_ns=samples[phase][0]["read_start_ns"],
                read_end_ns=samples[phase][-1]["read_end_ns"],
                inner_duration_ns=2_999_999_000,
                outer_duration_ns=3_000_001_000,
            )
        )
    raw = dict(
        status="passed",
        method=projection.SOURCE_METHOD,
        live_authority=False,
        events=events,
        mode="engineering-n11-resource-condition-" + CONDITIONS[arm],
        role="engineering_resource_condition_witness_label_unavailable",
        context=dict(
            image="sha256:" + "a" * 64,
            software_hash="b" * 64,
            host_platform="test",
            host_arch="test",
        ),
    )
    text = json.dumps(raw, indent=2) + "\n"
    artifact = dict(
        method=projection.SOURCE_METHOD,
        source_payload_sha256="sha256:" + hashlib.sha256(text.encode()).hexdigest(),
        context=context,
        clock_id=clock,
        source_identity=samples["healthy"][0]["source_identity"],
        windows=summaries,
        samples=samples,
        empirical_acceptance=False,
        acquisition_authority=False,
    )
    return dict(acquisition_json=text, resource_artifact=artifact)


def slot(identifier, condition, arm, identical=False):
    value = source(identifier, arm, identical)
    binding = method.declare_combined_condition_binding(
        value,
        condition=condition,
        context_hash=CONTEXT,
        inspection_sha256="sha256:" + hashlib.sha256(identifier.encode()).hexdigest(),
    )
    return dict(source=value, binding=binding)


def blocks(count=6, identical=False):
    return {
        f"block-{i}": {c: slot(f"case-{i}-{j}", c, j, identical) for j, c in enumerate(CONDITIONS)}
        for i in range(count)
    }


def rebind_raw(value, mutate):
    raw = json.loads(value["acquisition_json"])
    mutate(raw)
    value["acquisition_json"] = json.dumps(raw, indent=2) + "\n"
    value["resource_artifact"]["source_payload_sha256"] = (
        "sha256:" + hashlib.sha256(value["acquisition_json"].encode()).hexdigest()
    )


def test_projection_nine_fixed_intervals_and_raw_byte_identity_are_deterministic():
    value = source("case")
    before = deepcopy(value)
    result = projection.project_combined_resource(value)
    assert (
        len(result["features"]) == 9 and result["state"] == "candidate_combined_response_available"
    )
    assert set(result["features"]) == set(method.FEATURES)
    assert result == projection.project_combined_resource(value) and value == before
    assert result["source_worker_clock"] != result["source_controller_clock"]
    assert not result["empirical_acceptance"] and not result["acquisition_authority"]


@pytest.mark.parametrize(
    "kind",
    [
        "raw_bytes",
        "aux_sample",
        "aux_window",
        "quota",
        "context",
        "mixed_source",
        "bounds",
        "label_leak",
        "duplicate_json",
    ],
)
def test_projection_rejects_tampered_or_mixed_sources(kind):
    value = source("case")
    if kind == "raw_bytes":
        value["acquisition_json"] += " "
    elif kind == "aux_sample":
        value["resource_artifact"]["samples"]["healthy"][0]["counters"]["usage_usec"] += 1
    elif kind == "aux_window":
        value["resource_artifact"]["windows"][0]["read_start_ns"] += 1
    elif kind == "quota":
        value["resource_artifact"]["samples"]["healthy"][0]["quota"]["quota_usec"] = 1
    elif kind == "context":
        value["resource_artifact"]["context"]["controller_origin_ns"] = "12346"
    elif kind == "mixed_source":
        value["resource_artifact"] = source("other")["resource_artifact"]
    elif kind == "bounds":
        rebind_raw(
            value,
            lambda raw: next(
                e for e in raw["events"] if e.get("kind") == "n11_pair_phase_completed"
            ).update(at_ns=4_000_000_001),
        )
    elif kind == "label_leak":
        value["resource_artifact"]["samples"]["healthy"][0]["condition"] = "label"
    else:
        value["acquisition_json"] = '{"method":1,"method":2}'
    with pytest.raises(ValueError, match=projection.ERROR):
        projection.project_combined_resource(value)


def test_witness_label_changes_do_not_change_nine_measured_intervals():
    value = source("case")
    before = projection.project_combined_resource(value)

    def change(raw):
        for event in raw["events"]:
            if event.get("kind") not in ("n11_pacing_reference", "n11_pair_native"):
                continue
            for row in event.get("samples", [event]):
                row["condition_witness"] = dict(condition="arbitrary", dose=999)

    rebind_raw(value, change)
    after = projection.project_combined_resource(value)
    assert (
        after["features"] == before["features"]
        and after["component_response_ids"] == before["component_response_ids"]
    )
    assert after["source_bytes_sha256"] != before["source_bytes_sha256"]


def test_complete_synthetic_fold_fit_requires_both_clocks_and_all_nine_coordinates():
    result = method.fit_combined_interval_candidate(blocks(), session_id="session")
    assert result["state"] == "candidate_calibration_available"
    assert len(result["folds"]) == 6 and result["calibration_query_count"] == 18
    assert len(result["source_clock_ids"]) == 36 and result["thresholds"] is not None
    assert all(f["complete_and_correct"] for f in result["folds"])
    assert result["accepted_diagnostic_groups"] == result["independent_support_groups"] == 0
    assert not result["empirical_acceptance"] and result["diagnostic_label"] is None


@pytest.mark.parametrize("arm", [0, 1, 2])
def test_fresh_query_has_no_truth_and_passes_only_after_full_rebuild(arm):
    data = blocks()
    before = method.fit_combined_interval_candidate(data, session_id="s")
    result = method.score_combined_interval_candidate(
        source("query", arm),
        data,
        session_id="s",
        query_session_id="s",
        query_block_id="new",
        context_hash=CONTEXT,
    )
    assert (
        result["predicted_condition"] == CONDITIONS[arm]
        and result["state"] == "candidate_condition_prediction"
    )
    assert method.fit_combined_interval_candidate(data, session_id="s") == before


@pytest.mark.parametrize("kind", ["partial", "missing", "ambiguous"])
def test_failed_calibration_retains_slots_folds_and_null_thresholds(kind):
    data = blocks(5) if kind == "partial" else blocks(identical=kind == "ambiguous")
    if kind == "missing":
        data["block-0"][CONDITIONS[0]] = None
    result = method.fit_combined_interval_candidate(data, session_id="s")
    assert (
        result["state"] == "unavailable"
        and result["thresholds"] is None
        and result["centers"] == {}
    )
    if kind == "ambiguous":
        assert len(result["folds"]) == 6 and all(
            not f["complete_and_correct"] for f in result["folds"]
        )


@pytest.mark.parametrize(
    "kind,reason",
    [
        ("session", "different_query_session"),
        ("context", "incompatible_query_context"),
        ("block", "query_block_overlap"),
        ("source", "query_source_or_clock_overlap"),
        ("worker", "query_source_or_clock_overlap"),
        ("calibration", "calibration_unavailable"),
    ],
)
def test_query_guards_never_grant_authority(kind, reason):
    data = blocks(5) if kind == "calibration" else blocks()
    value = source("query")
    session, context, block = "s", CONTEXT, "new"
    if kind == "session":
        session = "different"
    elif kind == "context":
        context = "sha256:" + "d" * 64
    elif kind == "block":
        block = "block-0"
    elif kind in ("source", "worker"):
        value = deepcopy(data["block-0"][CONDITIONS[0]]["source"])
        if kind == "worker":
            rebind_raw(value, lambda raw: raw.update(ignored_metadata="changed bytes"))
    result = method.score_combined_interval_candidate(
        value,
        data,
        session_id="s",
        query_session_id=session,
        query_block_id=block,
        context_hash=context,
    )
    assert (
        result["state"] == "abstain"
        and result["predicted_condition"] is None
        and reason in result["reason_codes"]
    )
    assert not result["empirical_acceptance"] and not result["acquisition_authority"]


def test_binding_tamper_inspection_reuse_and_extra_block_rejected():
    for kind in ("binding", "inspection", "extra"):
        data = blocks(6)
        if kind == "binding":
            data["block-0"][CONDITIONS[0]]["binding"]["source_bytes_sha256"] = "sha256:" + "f" * 64
        elif kind == "inspection":
            data["block-1"][CONDITIONS[0]]["binding"]["inspection_sha256"] = data["block-0"][
                CONDITIONS[0]
            ]["binding"]["inspection_sha256"]
        else:
            data["extra"] = deepcopy(data["block-0"])
        with pytest.raises(ValueError):
            method.fit_combined_interval_candidate(data, session_id="s")


def test_method_specs_are_distinct_detached_and_no_truth_or_cached_fit_api():
    spec = method.combined_interval_candidate_spec()
    spec["features"].clear()
    assert len(method.combined_interval_candidate_spec()["features"]) == 9
    assert (
        spec["projection_contract_hash"]
        == projection.combined_resource_projection_spec()["content_hash"]
    )
    with pytest.raises(TypeError):
        method.fit_combined_interval_candidate({}, session_id="s", cached_fit={})
    with pytest.raises(TypeError):
        method.score_combined_interval_candidate(
            {},
            {},
            session_id="s",
            query_session_id="s",
            query_block_id="new",
            context_hash=CONTEXT,
            truth="label",
        )


def test_runtime_source_context_change_rejects_training_and_abstains_query():
    data = blocks()
    changed = source("changed")
    rebind_raw(changed, lambda raw: raw["context"].update(software_hash="f" * 64))
    result = method.score_combined_interval_candidate(
        changed,
        data,
        session_id="s",
        query_session_id="s",
        query_block_id="new",
        context_hash=CONTEXT,
    )
    assert (
        "incompatible_query_context" in result["reason_codes"]
        and result["predicted_condition"] is None
    )
    data["block-0"][CONDITIONS[0]]["source"] = changed
    data["block-0"][CONDITIONS[0]]["binding"] = method.declare_combined_condition_binding(
        changed,
        condition=CONDITIONS[0],
        context_hash=CONTEXT,
        inspection_sha256="sha256:" + "e" * 64,
    )
    with pytest.raises(ValueError):
        method.fit_combined_interval_candidate(data, session_id="s")


def test_auxiliary_bool_or_float_alias_cannot_match_integer_raw_samples():
    for value in (True, 1.0):
        data = source("case")
        data["resource_artifact"]["samples"]["healthy"][0]["source_identity"]["cgroup"]["inode"] = (
            value
        )
        with pytest.raises(ValueError):
            projection.project_combined_resource(data)


def test_fold_centers_exclude_held_block_and_do_not_mutate_source(monkeypatch):
    data = blocks()
    before = deepcopy(data)
    seen = []
    original = method._centers

    def capture(prepared):
        seen.append(set(prepared))
        return original(prepared)

    monkeypatch.setattr(method, "_centers", capture)
    result = method.fit_combined_interval_candidate(data, session_id="s")
    for fold, used in zip(result["folds"], seen[:6], strict=True):
        assert used == set(fold["training_block_ids"]) and fold["held_out_block_id"] not in used
    assert data == before and len(seen[-1]) == 6


def test_combined_distance_enclosures_and_ambiguity_use_all_nine_coordinates():
    from fractions import Fraction

    def vector(lower, upper):
        return {name: (Fraction(lower), Fraction(upper)) for name in method.FEATURES}

    assert method._distance(vector(0, 2), vector(3, 4)) == (1, 4)
    centers = dict(zip(CONDITIONS, (vector(0, 1), vector(1, 2), vector(10, 11)), strict=True))
    _, winner, gap = method._score(vector(0, 1), centers)
    assert winner is None and gap is None


def test_unavailable_component_is_retained_and_never_uses_other_component_subset():
    value = source("case")
    raw = json.loads(value["acquisition_json"])
    # One validly structured 100ms CPU read exceeds its50ms source bound while
    # leaving the independent encoded counters and phase containment intact.
    ref = next(e for e in raw["events"] if e.get("phase") == "healthy")
    ref["samples"][0]["container_cpu_read"]["read_end_ns"] += 100_000_000
    value["resource_artifact"]["samples"]["healthy"][0]["read_end_ns"] += 100_000_000
    value["resource_artifact"]["windows"][0]["inner_duration_ns"] -= 100_000_000
    value["acquisition_json"] = json.dumps(raw, indent=2) + "\n"
    value["resource_artifact"]["source_payload_sha256"] = (
        "sha256:" + hashlib.sha256(value["acquisition_json"].encode()).hexdigest()
    )
    result = projection.project_combined_resource(value)
    assert result["state"] == "unavailable" and result["features"] == {}
    assert result["unavailable_components"] == ["cpu"]
