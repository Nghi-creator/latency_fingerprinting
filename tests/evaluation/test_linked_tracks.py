"""Raw-fixture interoperability only; no independently acquired real calibration."""

import json
import shutil

import pytest

from latency_fingerprinting.adapters import ingest_pixelated_windows
from latency_fingerprinting.evaluation import (
    run_evaluation,
    seal_manifest,
    verify_evaluation_report,
)
from latency_fingerprinting.live_probes import (
    import_game_browser_acquisition,
    import_integrated_game_cohort,
)
from latency_fingerprinting.models import ContextKey
from latency_fingerprinting.passive_gating import build_passive_baseline, create_passive_replay
from tests.calibration.cases import group_id
from tests.live_probes.game_browser_cases import META, acquisition
from tests.live_probes.integrated_game_cases import cohort
from tests.passive_gating.cases import POLICY, evidence, rebuild_evidence, window
from tests.passive_gating.linked_cases import write_source
from tests.pixelated.support import FIXTURE_ROOT, VALID_V2_BUNDLE, write_tar

from .support import add_receipt, base, canonical, slot


def raw_passive_case(tmp_path, training_count=5):
    manifest, paths = base(tmp_path)
    ev, windows = evidence(
        [window("q0", query=True), window("q1", query=True, start=2000, end=4000)],
        training_values=(60.0,) * training_count,
    )
    raw_paths = {}
    ctx = ContextKey.model_validate_json((FIXTURE_ROOT / "context-v2.json").read_bytes())
    for name in [*(f"train-{i}" for i in range(training_count)), "query"]:
        directory = tmp_path / name
        shutil.copytree(VALID_V2_BUNDLE, directory)
        for p in directory.iterdir():
            p.write_text(
                p.read_text()
                .replace("pixelated-sanitized-run-v2-001", "raw-" + name)
                .replace("anonymous-session-v2-001", "session-" + name)
            )
        p = directory / "bundle-manifest.json"
        data = json.loads(p.read_bytes())
        data["phase"] = "healthy"
        p.write_bytes(canonical(data))
        target = tmp_path / (name + ".tar")
        write_tar(directory, target)
        raw_paths[name] = target
        slices = ingest_pixelated_windows(
            target,
            context=ctx,
            phase="baseline",
            comparison_case_id="controlled-case-001",
            windows=[dict(start_ms=0, end_ms=5000), dict(start_ms=5000, end_ms=10000)]
            if name == "query"
            else [dict(start_ms=0, end_ms=5000)],
        )
        if name == "query":
            windows["query-000"], windows["query-001"] = [w.model_dump(mode="json") for w in slices]
        else:
            windows[name] = slices[0].model_dump(mode="json")
    sources = {s["source_id"]: s for s in ev["dataset"]["sources"]}
    for entry in ev["dataset"]["entries"]:
        w = windows[entry["entry_id"]]
        binding = entry["source_bindings"][0]
        binding["window_id"] = w["window_id"]
        sources[binding["source_id"]].update(
            run_id=w["run_id"], source_content_hash=w["source_artifact"]["content_hash"]
        )
    ev = rebuild_evidence(ev, windows)
    directory = tmp_path / "passive-sources"
    # Write actual source bytes with the established N6 inventory helper.
    write_source(directory, ev, windows)
    d = ev["dataset"]
    baseline = build_passive_baseline(directory, POLICY)
    assert baseline.state == ("provisional" if training_count >= 5 else "rejected")
    query = windows["query-000"]
    replay = create_passive_replay(
        baseline,
        mode="validation",
        start_ms=0,
        stream=dict(
            acquisition_namespace="model-only",
            run_id=query["run_id"],
            clock_domain_id=query["clock"]["domain_id"],
            generation_id="generation-1",
            stratum_id=baseline.strata[0].stratum_id,
        ),
        windows=[
            dict(artifact_id="artifact-" + name, window=windows[name])
            for name in ("query-000", "query-001")
        ],
        events=[
            dict(kind="window", at_ms=end, entry_id=name, reset_reason=None)
            for name, end in (("query-000", 5000), ("query-001", 10000))
        ],
    )
    add_receipt(
        manifest, paths, "dataset", "dataset_manifest", directory / "calibration-dataset.json"
    )
    manifest["datasets"] = [
        dict(
            dataset_key="sources",
            manifest_receipt="dataset",
            content_hash=d["content_hash"],
            split_id=d["split"]["split_id"],
        )
    ]
    for name in [*(f"train-{i}" for i in range(training_count)), "query"]:
        source_id = "query-source" if name == "query" else "source-" + name
        manifest["groups"].append(
            dict(dataset_key="sources", group_id=group_id([source_id]), study_group="study-" + name)
        )
        row = slot(name, role="validation" if name == "query" else "training")
        row["truth_label"] = None if name == "query" else "healthy"
        row["passive_job"] = "passive" if name == "query" else None
        manifest["slots"].append(row)
        add_receipt(manifest, paths, "raw-" + name, "raw_bundle", raw_paths[name])
    manifest["groups"].sort(key=lambda g: (g["dataset_key"], g["group_id"]))
    manifest["slots"].sort(key=lambda s: s["slot_id"])
    for entry in d["entries"]:
        name = entry["entry_id"]
        manifest["raw_derivations"].append(
            dict(
                dataset_key="sources",
                entry_id=name,
                window_role="healthy",
                raw_receipt="raw-query" if name.startswith("query") else "raw-" + name,
            )
        )
    for name, kind, payload in (
        ("baseline", "passive_baseline", baseline.model_dump(mode="json")),
        ("replay", "passive_replay", replay.model_dump(mode="json")),
        ("policy", "passive_policy", POLICY),
    ):
        p = tmp_path / (name + ".json")
        p.write_bytes(canonical(payload))
        add_receipt(manifest, paths, name, kind, p)
    manifest["passive"] = [
        dict(
            job_id="passive",
            dataset_key="sources",
            baseline_receipt="baseline",
            replay_receipt="replay",
            policy_receipt="policy",
        )
    ]
    return seal_manifest(manifest), paths


def test_actual_raw_slices_reconstruct_through_n6_n9_and_study(tmp_path):
    manifest, paths = raw_passive_case(tmp_path)
    execution = run_evaluation(manifest, paths)
    query = execution.report.rows[0]
    assert query.slot_id == "query"
    assert query.passive_state == "computed"
    assert query.proposals == 0 and query.first_proposal_ms is None
    assert query.profile_label is query.point_label is query.truth_label is None
    assert execution.report.counts.held_out_slots == 1
    assert execution.report.counts.profile_unknown.value == 1
    assert verify_evaluation_report(execution.report, paths) == execution.report
    assert execution.artifacts[0].counts.accepted_windows == 2


def test_explicit_wrong_raw_binding_fails_even_when_all_sources_are_valid(tmp_path):
    manifest, paths = raw_passive_case(tmp_path)
    payload = manifest.model_dump(mode="json")
    payload["raw_derivations"][0]["raw_receipt"] = "raw-train-0"
    with pytest.raises(ValueError, match="^invalid_evaluation$"):
        run_evaluation(seal_manifest(payload), paths)


def test_absent_raw_binding_is_visible_instead_of_a_successful_stream(tmp_path):
    manifest, paths = raw_passive_case(tmp_path)
    payload = manifest.model_dump(mode="json")
    payload["raw_derivations"] = [
        r for r in payload["raw_derivations"] if r["raw_receipt"] != "raw-query"
    ]
    payload["receipts"] = [r for r in payload["receipts"] if r["receipt_id"] != "raw-query"]
    paths.pop("raw-query")
    result = run_evaluation(seal_manifest(payload), paths).report
    assert result.rows[0].passive_state == "unavailable"
    assert result.rows[0].proposals is None
    assert "raw_sources_unverified" in result.rows[0].reason_codes


@pytest.mark.parametrize("kind", ["game_evidence", "integrated_evidence"])
def test_live_forensics_stays_engineering_only(tmp_path, kind):
    manifest, paths = base(tmp_path)
    if kind == "game_evidence":
        root = import_game_browser_acquisition(acquisition(), **META)
    else:
        root = import_integrated_game_cohort(
            canonical(cohort()), acquisition_id="cohort", producer_revision="a" * 40
        )
    path = tmp_path / "engineering.json"
    path.write_bytes(canonical(root.model_dump(mode="json")))
    add_receipt(manifest, paths, "engineering", kind, path)
    manifest["live"] = [dict(job_id="engineering", evidence_receipt="engineering")]
    row = slot("case", role="engineering")
    row["live_job"] = "engineering"
    manifest["slots"] = [row]
    result = run_evaluation(seal_manifest(manifest), paths)
    assert result.report.rows[0].live_state == "engineering_only"
    assert result.report.rows[0].diagnosis_state == "not_requested"
    assert result.report.counts.held_out_slots == 0
    assert result.report.empirical_acceptance == "unavailable_not_a_frozen_real_study"


def raw_diagnosis_case(tmp_path):
    """Artificial reviews/raw fixtures exercise code, never scientific labels."""
    from latency_fingerprinting.adapters import ingest_pixelated_v2
    from latency_fingerprinting.analytical.responses import derive_analytical_response
    from latency_fingerprinting.calibration import inspect_calibration_dataset
    from latency_fingerprinting.models import FeaturePolicyV1, ObservationRecordV2
    from latency_fingerprinting.profiles import build_profile_snapshot
    from tests.calibration.cases import HASH, seal_dataset
    from tests.pixelated.test_measurement_samples import edit_json, edit_row
    from tests.profiles.cases import policy as profile_policy

    from .support import ROOT

    manifest, paths = base(tmp_path)
    d = dict(
        schema_version="calibration-dataset-v1",
        method_release="n6-calibration-evidence-v1",
        artifacts=[],
        sources=[],
        derivations=[],
        reviews=[],
        entries=[],
        split=dict(
            mode="prospective", protocol_sha256=HASH, assignments=[], freeze_review_id="freeze"
        ),
    )
    ctx = ContextKey.model_validate_json((FIXTURE_ROOT / "context-v2.json").read_bytes())
    policy = FeaturePolicyV1.model_validate_json(
        (ROOT / "docs/analysis/N3_FEATURE_POLICY_SPEC.json").read_bytes()
    )
    output = tmp_path / "paired"
    output.mkdir()
    for index in range(6):
        name = f"case-{index}"
        bound, original = [], {}
        source_ids = [name + "-degraded", name + "-relief"]
        role = "validation" if index == 5 else "training"
        gid = group_id(source_ids)
        d["split"]["assignments"].append(dict(group_id=gid, role=role))
        d["reviews"].append(
            dict(
                review_id="ind-" + name,
                reviewer_id="software-fixture-only",
                kind="independence",
                subject_ids=source_ids,
                outcome="confirmed",
                evidence_sha256=HASH,
            )
        )
        for phase in ("degraded", "relief"):
            sid = name + "-" + phase
            source = tmp_path / sid
            shutil.copytree(VALID_V2_BUNDLE, source)
            for path in source.iterdir():
                path.write_text(
                    path.read_text()
                    .replace("pixelated-sanitized-run-v2-001", "raw-" + sid)
                    .replace("anonymous-session-v2-001", "session-" + name)
                )
            edit_json(
                source,
                "bundle-manifest.json",
                lambda value, phase=phase, name=name: value.update(
                    phase=phase, comparisonCaseId=name
                ),
            )
            if phase == "relief":
                edit_json(
                    source, "run-metadata.json", lambda value: value["streamProfile"].update(fps=30)
                )
                for row in (1, 3, 5):
                    edit_row(source, "engine-telemetry.csv", row, target_fps="30")
            archive = tmp_path / (sid + ".tar")
            write_tar(source, archive)
            w = ingest_pixelated_v2(archive, context=ctx, phase=phase, comparison_case_id=name)
            original[phase] = w
            d["sources"].append(
                dict(
                    source_id=sid,
                    acquisition_namespace="software-fixture",
                    run_id=w.run_id,
                    session_id="session-" + name,
                    independence_group=name,
                    source_type="pixelated_bundle",
                    source_content_hash=w.source_artifact.content_hash,
                    bundle_schema_version="2",
                    review_id="ind-" + name,
                )
            )
            bound.append(dict(window_role=phase, source_id=sid, window_id=w.window_id))
            add_receipt(manifest, paths, "raw-" + sid, "raw_bundle", archive)
            manifest["raw_derivations"].append(
                dict(
                    dataset_key="paired", entry_id=name, window_role=phase, raw_receipt="raw-" + sid
                )
            )
        observation = ObservationRecordV2.model_validate(
            dict(
                schema_version="observation-v2",
                contract_version="2.0.0",
                observation_id="obs-" + name,
                comparison_case_id=name,
                degraded_window=original["degraded"],
                relief_window=original["relief"],
                intervention=dict(
                    probe_id="probe-" + name,
                    probe_type="stream_profile_relief",
                    probe_version="1.0.0",
                    requested_settings=dict(fps=30, targetFps=30),
                    observed_settings=dict(fps=30, targetFps=30),
                    intensity=0.5,
                    application_method="paired_run",
                    execution_status="executed",
                    restoration_status="restored",
                    degraded_window_id=original["degraded"].window_id,
                    relief_window_id=original["relief"].window_id,
                    paired_window_order=["degraded", "relief"],
                    confounder_codes=[],
                ),
            )
        )
        response = derive_analytical_response(observation, policy)
        artifact = output / (name + ".json")
        artifact.write_bytes(canonical(response.model_dump(mode="json")))
        import hashlib

        d["artifacts"].append(
            dict(
                artifact_id=name,
                kind="analytical_response",
                file_name=artifact.name,
                bytes=artifact.stat().st_size,
                sha256="sha256:" + hashlib.sha256(artifact.read_bytes()).hexdigest(),
            )
        )
        d["entries"].append(
            dict(
                entry_id=name,
                input_kind="response",
                artifact_id=name,
                source_bindings=bound,
                label="host_contention",
                label_basis="external_confirmation",
                label_review_id="label-" + name,
                experiment_artifact_id=None,
                experiment_phase=None,
            )
        )
        d["reviews"].append(
            dict(
                review_id="label-" + name,
                reviewer_id="software-fixture-only",
                kind="label_binding",
                subject_ids=[name],
                outcome="confirmed",
                evidence_sha256=HASH,
            )
        )
        manifest["groups"].append(
            dict(dataset_key="paired", group_id=gid, study_group="study-" + name)
        )
        row = slot(name, role=role)
        row["diagnosis_job"] = "diagnosis" if index == 5 else None
        manifest["slots"].append(row)
    d["artifacts"].sort(key=lambda x: x["artifact_id"])
    d["sources"].sort(key=lambda x: x["source_id"])
    d["split"]["assignments"].sort(key=lambda x: x["group_id"])
    seal_dataset(d)
    d["reviews"].append(
        dict(
            review_id="freeze",
            reviewer_id="software-fixture-only",
            kind="split_freeze",
            subject_ids=[d["split"]["split_id"]],
            outcome="confirmed",
            evidence_sha256=HASH,
        )
    )
    d["reviews"].sort(key=lambda x: x["review_id"])
    seal_dataset(d)
    path = output / "calibration-dataset.json"
    path.write_bytes(canonical(d))
    assert all(e.eligible for e in inspect_calibration_dataset(output).report.entries)
    add_receipt(manifest, paths, "dataset", "dataset_manifest", path)
    manifest["datasets"] = [
        dict(
            dataset_key="paired",
            manifest_receipt="dataset",
            content_hash=d["content_hash"],
            split_id=d["split"]["split_id"],
        )
    ]
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_bytes(
        canonical(build_profile_snapshot(output, profile_policy()).model_dump(mode="json"))
    )
    add_receipt(manifest, paths, "snapshot", "profile_snapshot", snapshot)
    add_receipt(
        manifest,
        paths,
        "response-policy",
        "response_policy",
        ROOT / "docs/analysis/N3_FEATURE_POLICY_SPEC.json",
    )
    add_receipt(
        manifest,
        paths,
        "match-policy",
        "match_policy",
        ROOT / "docs/profile_matching/N8_MATCH_POLICY_SPEC.json",
    )
    manifest["diagnoses"] = [
        dict(
            job_id="diagnosis",
            dataset_key="paired",
            snapshot_receipt="snapshot",
            response_policy_receipt="response-policy",
            match_policy_receipt="match-policy",
            mode="validation",
        )
    ]
    manifest["groups"].sort(key=lambda x: (x["dataset_key"], x["group_id"]))
    return seal_manifest(manifest), paths


def test_point_baseline_runs_original_n3_on_verified_paired_bytes(tmp_path):
    manifest, paths = raw_diagnosis_case(tmp_path)
    result = run_evaluation(manifest, paths)
    query = result.report.rows[-1]
    assert query.diagnosis_state == "computed"
    # All five identical same-label references compete in the original N3
    # margin calculation; they must remain ambiguous, not collapse to one label.
    assert query.point_label is None
    point_results = [
        a for a in result.artifacts if getattr(a, "schema_version", None) == "match-result-v2"
    ]
    assert len(point_results) == 1
    assert point_results[0].unknown_reason == "ambiguous_margin"
    assert len(point_results[0].repository_references) == 5
    assert verify_evaluation_report(result.report, paths) == result.report


def test_verified_raw_bytes_with_rejected_baseline_do_not_claim_zero_probe_rate(tmp_path):
    manifest, paths = raw_passive_case(tmp_path, training_count=4)
    execution = run_evaluation(manifest, paths)
    row = execution.report.rows[0]
    assert row.passive_state == "unavailable"
    assert row.proposals is row.first_proposal_ms is None
    assert row.reason_codes == ("passive_evidence_unavailable",)
    assert execution.artifacts[0].baseline.state == "rejected"
    assert execution.artifacts[0].counts.unavailable_windows == 2
