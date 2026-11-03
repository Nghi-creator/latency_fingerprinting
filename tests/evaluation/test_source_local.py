"""Independent source-local vectors, old-method separation and hostile declarations."""

import csv
import hashlib
import json
from pathlib import Path

import pytest

from latency_fingerprinting.adapters import ingest_pixelated_source_local, ingest_pixelated_v2
from latency_fingerprinting.cli import main
from latency_fingerprinting.models import ContextKey, ObservationRecordV2, ObservationWindowV2
from latency_fingerprinting.passive_gating.models import ReplayWindow
from tests.pixelated.support import write_tar
from tests.pixelated.test_measurement_samples import edit_json, edit_row

from .support import canonical
from .test_source_boundaries import asynchronous_bundle
from .test_windows import context

EXPECTATIONS = json.loads(Path("fixtures/source-local-v1/expectations.json").read_bytes())


def local_context():
    data = context().model_dump(mode="json")
    data["versions"]["pixelatedTemporalContract"] = "source_local_stable_phase_v1"
    return ContextKey.model_validate(data)


def declare(directory, *, phase="degraded", **changes):
    declaration = dict(
        schemaVersion="source-local-stable-phase-v1",
        basis="operator_declared_not_authenticated",
        phase=phase,
        comparisonCaseId="controlled-case-001",
        elapsedStartMs=0,
        elapsedEndMs=10000,
        evidenceSha256="sha256:" + "a" * 64,
    )
    declaration.update(changes)
    edit_json(directory, "bundle-manifest.json", lambda d: d.update(sourceLocalPhase=declaration))


def adopt(path, **changes):
    return ingest_pixelated_source_local(
        path,
        context=changes.pop("context", local_context()),
        phase=changes.pop("phase", "degraded"),
        comparison_case_id="controlled-case-001",
        **changes,
    )


def source(tmp_path):
    directory = asynchronous_bundle(tmp_path)
    declare(directory)
    return directory


def test_hand_authored_async_arithmetic_and_same_source_bounds(tmp_path):
    directory = source(tmp_path)
    window = adopt(directory)
    expected = EXPECTATIONS["asynchronous"]
    assert window.capture_method.method_version == "1.2.0"
    assert window.clock.elapsed_start_ms == 0 and window.clock.elapsed_end_ms == 10000
    for metric in window.measurements.values():
        summary = metric.summary
        bounds = (
            expected["browser_bounds_ms"]
            if summary.source == "browser_webrtc"
            else expected["engine_bounds_ms"]
        )
        assert [summary.window_start_ms, summary.window_end_ms] == bounds
    assert (
        window.measurements["host.camera_cpu_percent"].summary.value
        == expected["camera_cpu_median"]
    )
    assert (
        window.measurements["encoder.frames_in_rate_fps"].summary.value
        == expected["encoder_frames_in_rate_fps"]
    )
    assert (
        window.measurements["encoder.frames_out_rate_fps"].summary.value
        == expected["encoder_frames_out_rate_fps"]
    )
    assert window.measurements["host.camera_cpu_percent"].summary.coverage == 1
    original = ingest_pixelated_v2(
        directory, context=context(), phase="degraded", comparison_case_id="controlled-case-001"
    )
    assert original.measurements["host.camera_cpu_percent"].summary.coverage == 0.5
    assert original.source_artifact == window.source_artifact
    assert window.validity == original.validity
    assert ObservationWindowV2.model_validate_json(window.model_dump_json()) == window


def test_metric_missingness_cannot_shrink_its_source_window(tmp_path):
    directory = source(tmp_path)
    edit_row(directory, "engine-telemetry.csv", 0, camera_cpu_percent="")
    window = adopt(directory)
    metric = window.measurements["host.camera_cpu_percent"].summary
    expected = EXPECTATIONS["missing_metric"]
    assert [metric.window_start_ms, metric.window_end_ms] == expected["source_bounds_ms"]
    assert metric.status == expected["status"] and metric.coverage == expected["coverage"]
    assert metric.usable_sample_count == expected["usable_samples"]
    assert window.measurements["host.node_cpu_percent"].summary.coverage == 1


def test_one_point_source_stays_missing_without_fake_span(tmp_path):
    directory = source(tmp_path)
    path = directory / "engine-telemetry.csv"
    with path.open(newline="") as file:
        reader = csv.DictReader(file)
        headers = reader.fieldnames
        rows = list(reader)[:2]
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    edit_json(
        directory,
        "summary.json",
        lambda d: [
            d["validity"]["sources"].update({name: dict(sampleCount=1, availableSampleCount=1)})
            for name in ("engineRuntime", "encoderPipeline")
        ],
    )
    window = adopt(directory)
    for measurement in window.measurements.values():
        if measurement.summary.source != "browser_webrtc":
            assert measurement.summary.status == "missing"
            assert measurement.summary.usable_sample_count == 0
            assert (
                measurement.summary.window_start_ms == 0
                and measurement.summary.window_end_ms == 10000
            )
    assert window.sources["engine_runtime"].available_row_count == 1


@pytest.mark.parametrize(
    "change",
    ["absent", "wrong_phase", "wrong_case", "wrong_bounds", "extra", "bad_hash", "false_basis"],
)
def test_stable_phase_declaration_is_strict_and_cannot_rebind_the_capture(tmp_path, change):
    directory = source(tmp_path)
    changes = {
        "wrong_phase": dict(phase="relief"),
        "wrong_case": dict(comparisonCaseId="another"),
        "wrong_bounds": dict(elapsedStartMs=500),
        "extra": dict(unknown=True),
        "bad_hash": dict(evidenceSha256="not-a-hash"),
        "false_basis": dict(basis="authenticated"),
    }
    if change == "absent":
        edit_json(directory, "bundle-manifest.json", lambda d: d.pop("sourceLocalPhase"))
    else:
        declare(directory, **changes[change])
    with pytest.raises(ValueError, match="^invalid_pixelated_source_local$"):
        adopt(directory)


def test_method_marker_and_common_window_contract_cannot_be_swapped(tmp_path):
    directory = source(tmp_path)
    window = adopt(directory)
    with pytest.raises(ValueError):
        adopt(directory, context=context())
    payload = window.model_dump(mode="json")
    payload["capture_method"]["method_version"] = "1.0.0"
    with pytest.raises(ValueError):
        ObservationWindowV2.model_validate(payload)
    payload = window.model_dump(mode="json")
    summary = payload["measurements"]["host.camera_cpu_percent"]["summary"]
    summary.update(
        window_start_ms=0,
        window_end_ms=10000,
        window_duration_ms=10000,
        coverage=0.5,
        status="incomplete",
    )
    with pytest.raises(ValueError, match="identical local bounds"):
        ObservationWindowV2.model_validate(payload)
    with pytest.raises(ValueError, match="N9 does not accept"):
        ReplayWindow(artifact_id="phase-only", window=window)


def test_full_raw_invalidity_and_counter_resets_are_not_trimmed(tmp_path):
    directory = source(tmp_path)
    edit_row(directory, "engine-telemetry.csv", 3, frames_in_total="50")
    window = adopt(directory)
    summary = window.measurements["encoder.frames_in_rate_fps"].summary
    assert summary.status == "rejected" and summary.reset_source_rows
    edit_json(
        directory,
        "summary.json",
        lambda d: d["validity"].update(isValid=False, reasons=["operator invalidated"]),
    )
    assert not adopt(directory).validity.is_valid


def test_source_duration_limit_rejects_short_spans_instead_of_masking_rows(tmp_path):
    directory = source(tmp_path)
    for index in (2, 3):
        edit_row(
            directory,
            "engine-telemetry.csv",
            index,
            elapsed_ms="1000",
            captured_at="2026-08-10T02:03:05.000Z",
        )
    with pytest.raises(ValueError, match="^invalid_pixelated_source_local$"):
        adopt(directory)


def test_cli_protects_inputs_and_reconstructs_method(tmp_path, capsys):
    directory = source(tmp_path)
    archive = tmp_path / "raw.tar"
    write_tar(directory, archive)
    ctx = tmp_path / "context.json"
    ctx.write_bytes(canonical(local_context().model_dump(mode="json")))
    output = tmp_path / "local.json"
    args = [
        "ingest-pixelated-source-local",
        "--bundle",
        str(archive),
        "--context",
        str(ctx),
        "--phase",
        "degraded",
        "--comparison-case-id",
        "controlled-case-001",
        "--output",
    ]
    assert main([*args, str(output)]) == 0
    assert capsys.readouterr() == ("", "")
    assert ObservationWindowV2.model_validate_json(output.read_bytes()) == adopt(archive)
    original = archive.read_bytes()
    assert main([*args, str(archive)]) == 1
    assert archive.read_bytes() == original
    assert capsys.readouterr() == (
        "",
        "error: ingest-pixelated-source-local: invalid_input_or_output\n",
    )


def test_pair_checks_real_per_source_durations_even_with_equal_phase_duration(tmp_path):
    degraded = source(tmp_path / "degraded")
    relief = source(tmp_path / "relief")
    edit_json(relief, "bundle-manifest.json", lambda d: d.update(phase="relief"))
    declare(relief, phase="relief")
    edit_json(relief, "run-metadata.json", lambda d: d["streamProfile"].update(fps=30))
    for index in (1, 3):
        edit_row(relief, "engine-telemetry.csv", index, target_fps="30")
    for index in (2, 3):
        edit_row(
            relief,
            "engine-telemetry.csv",
            index,
            elapsed_ms="6500",
            captured_at="2026-08-10T02:03:10.500Z",
        )
    a, b = adopt(degraded), adopt(relief, phase="relief")
    payload = dict(
        schema_version="observation-v2",
        contract_version="2.0.0",
        observation_id="source-local-pair",
        comparison_case_id="controlled-case-001",
        degraded_window=a,
        relief_window=b,
        intervention=dict(
            probe_id="software-only",
            probe_type="stream_profile_relief",
            probe_version="1.0.0",
            requested_settings=dict(fps=30, targetFps=30),
            observed_settings=dict(fps=30, targetFps=30),
            intensity=0.5,
            application_method="paired_run",
            execution_status="executed",
            restoration_status="restored",
            degraded_window_id=a.window_id,
            relief_window_id=b.window_id,
            paired_window_order=["degraded", "relief"],
            confounder_codes=[],
        ),
    )
    with pytest.raises(ValueError, match="paired source-local durations"):
        ObservationRecordV2.model_validate(payload)


def test_full_n6_n7_n8_n3_n11_reconstructs_source_local_raw_proofs(tmp_path):
    from latency_fingerprinting.evaluation import run_evaluation, verify_evaluation_report

    from .test_linked_tracks import raw_diagnosis_case

    manifest, paths = raw_diagnosis_case(tmp_path, source_local=True)
    execution = run_evaluation(manifest, paths)
    row = execution.report.rows[-1]
    assert row.diagnosis_state == "computed"
    assert row.point_label is None
    assert execution.report.counts.held_out_slots == 1
    assert verify_evaluation_report(execution.report, paths) == execution.report
    # Same-label point competition is unchanged under the new capture partition.
    points = [
        a for a in execution.artifacts if getattr(a, "schema_version", None) == "match-result-v2"
    ]
    assert len(points) == 1 and points[0].unknown_reason == "ambiguous_margin"


def test_source_local_expectations_remain_the_preimplementation_bytes():
    assert hashlib.sha256(
        Path("fixtures/source-local-v1/expectations.json").read_bytes()
    ).hexdigest() == ("99003b460cb1dc51e9dfcf077a001c016a35088ba3dfaa6f8f51e167ce1c1cdd")
