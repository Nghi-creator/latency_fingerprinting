"""N1 raw extraction retains row evidence and reuses bounded bundle contracts."""

from __future__ import annotations

import csv
import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from latency_fingerprinting.adapters import pixelated_bundle_io as bundle_io
from latency_fingerprinting.adapters import pixelated_measurement_samples as extraction
from latency_fingerprinting.adapters.pixelated_bundle_common import PixelatedBundleError
from latency_fingerprinting.models import ContextKey, WindowPhase

from .support import VALID_BUNDLE, VALID_V2_BUNDLE, copy_v2_bundle, write_tar


def load(path: Path, context: ContextKey) -> extraction.PixelatedMeasurementSamples:
    return extraction.load_pixelated_measurement_samples(
        path, phase=WindowPhase.DEGRADED, comparison_case_id="controlled-case-001", context=context
    )


def edit_row(bundle: Path, filename: str, index: int, **changes: str) -> None:
    path = bundle / filename
    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        headers = reader.fieldnames
        rows = list(reader)
    rows[index].update(changes)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def edit_json(bundle: Path, filename: str, edit) -> None:
    path = bundle / filename
    payload = json.loads(path.read_text(encoding="utf-8"))
    edit(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_all_sources_extract_raw_samples_with_original_rows_and_no_aggregation(
    context_v2: ContextKey, monkeypatch: pytest.MonkeyPatch
) -> None:
    from latency_fingerprinting.adapters import pixelated_bundle_metrics

    def no_aggregation(*args: object, **kwargs: object) -> None:
        pytest.fail("raw extraction must not aggregate")

    for name in ("mapped_metrics", "counter_metrics", "engine_metrics", "_aggregate"):
        monkeypatch.setattr(pixelated_bundle_metrics, name, no_aggregation)
    result = load(VALID_V2_BUNDLE, context_v2)
    assert len(result.series) == 31
    expectations = {
        "client.received_fps": ([50, 54, 58], [2, 3, 4]),
        "client.frames_decoded_rate_fps": ([100, 400, 700], [2, 3, 4]),
        "host.node_cpu_percent": ([5, 6, 7], [2, 4, 6]),
        "encoder.frames_out_rate_fps": ([98, 395, 690], [3, 5, 7]),
    }
    for name, (values, indices) in expectations.items():
        series = result.series[name]
        assert [sample.value for sample in series.samples] == values
        assert [sample.source_row for sample in series.samples] == indices
        assert [sample.elapsed_ms for sample in series.samples] == [0, 5000, 10000]
        assert all(sample.available for sample in series.samples)
    assert result.clock_provenance == "wall_clock_derived_elapsed"
    assert result.warnings


def test_directory_and_tar_are_identical_and_source_files_unchanged(
    tmp_path: Path, context_v2: ContextKey
) -> None:
    bundle = copy_v2_bundle(tmp_path)
    before = {path.name: path.read_bytes() for path in bundle.iterdir()}
    archive = tmp_path / "bundle.tar"
    write_tar(bundle, archive)
    assert load(bundle, context_v2) == load(archive, context_v2)
    assert {path.name: path.read_bytes() for path in bundle.iterdir()} == before


def test_bundle_is_read_once_and_counter_pairs_share_immutable_samples(
    context_v2: ContextKey, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = extraction.read_bundle
    calls = []

    def recording_read(*args: object, **kwargs: object):
        calls.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(extraction, "read_bundle", recording_read)
    result = load(VALID_V2_BUNDLE, context_v2)
    assert len(calls) == 1
    rate = result.series["client.frames_decoded_rate_fps"]
    total = result.series["client.frames_decoded_window_total"]
    assert rate.samples is total.samples
    with pytest.raises(TypeError):
        result.series["new"] = rate  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        rate.metric_name = "changed"
    with pytest.raises(FrozenInstanceError):
        result.clock_provenance = "monotonic"


def test_v1_missing_engine_sources_and_optional_browser_fields_stay_explicit(
    context: ContextKey,
) -> None:
    result = load(VALID_BUNDLE, context)
    assert result.series["host.node_cpu_percent"].samples == ()
    assert result.series["host.node_cpu_percent"].missing_reason
    frames = result.series["client.frames_decoded_rate_fps"]
    assert len(frames.samples) == 3
    assert all(sample.value is None and sample.missing_reason for sample in frames.samples)


@pytest.mark.parametrize(
    "raw", ["", "private-host-or-token", "NaN", "Infinity", "1e10000", "-1", "9" * 1000]
)
def test_browser_bad_cells_remain_row_evidence_without_dropping_samples(
    tmp_path: Path, context_v2: ContextKey, raw: str
) -> None:
    bundle = copy_v2_bundle(tmp_path)
    edit_row(bundle, "stream-telemetry.csv", 1, frames_decoded=raw)
    series = load(bundle, context_v2).series["client.frames_decoded_rate_fps"]
    assert len(series.samples) == 3
    middle = series.samples[1]
    assert middle.source_row == 3
    assert middle.value is None
    reason = middle.missing_reason if raw == "" else middle.rejection_reason
    assert "stream-telemetry.csv row 3 frames_decoded" in reason
    if raw:
        assert raw not in reason
    assert series.samples[0].value == 100
    assert series.samples[2].value == 700


def test_zero_and_finite_extreme_values_are_retained_without_arithmetic(
    tmp_path: Path, context_v2: ContextKey
) -> None:
    bundle = copy_v2_bundle(tmp_path)
    edit_row(bundle, "stream-telemetry.csv", 0, frames_decoded="0")
    edit_row(bundle, "stream-telemetry.csv", 1, frames_decoded="1e308")
    samples = load(bundle, context_v2).series["client.frames_decoded_rate_fps"].samples
    assert samples[0].value == 0
    assert samples[1].value == 1e308


def test_engine_available_row_missing_numeric_cell_is_rejected(
    tmp_path: Path, context_v2: ContextKey
) -> None:
    bundle = copy_v2_bundle(tmp_path)
    edit_row(bundle, "engine-telemetry.csv", 2, node_cpu_percent="")
    samples = load(bundle, context_v2).series["host.node_cpu_percent"].samples
    assert samples[1].source_row == 4
    assert samples[1].available
    assert samples[1].value is None
    assert "missing a required numeric cell" in samples[1].rejection_reason


@pytest.mark.parametrize("support", ["unsupported", "unavailable"])
def test_declared_unsupported_metric_remains_missing_even_with_stale_numeric_cell(
    tmp_path: Path, context_v2: ContextKey, support: str
) -> None:
    bundle = copy_v2_bundle(tmp_path)
    edit_row(bundle, "engine-telemetry.csv", 1, pipeline_delay_proxy_ms="999")
    edit_json(
        bundle,
        "bundle-manifest.json",
        lambda payload: payload["measurementSupport"].update(
            {"encoder_pipeline.pipelineDelayProxyMs": support}
        ),
    )
    samples = load(bundle, context_v2).series["encoder.pipeline_delay_proxy_ms"].samples
    assert all(sample.value is None and sample.missing_reason for sample in samples)
    assert all(sample.rejection_reason is None for sample in samples)
    assert all(not sample.available for sample in samples)


def test_counter_resets_are_raw_evidence_without_adapter_delta_policy(
    tmp_path: Path, context_v2: ContextKey
) -> None:
    bundle = copy_v2_bundle(tmp_path)
    edit_row(bundle, "stream-telemetry.csv", 1, frames_decoded="5", packets_lost_delta="invalid")
    samples = load(bundle, context_v2).series["client.frames_decoded_rate_fps"].samples
    assert [sample.value for sample in samples] == [100, 5, 700]
    assert all(sample.rejection_reason is None for sample in samples)


def test_engine_unavailable_row_discards_stale_cell_and_preserves_gap(
    tmp_path: Path, context_v2: ContextKey
) -> None:
    bundle = copy_v2_bundle(tmp_path)
    edit_row(
        bundle,
        "engine-telemetry.csv",
        3,
        available="false",
        error="temporarily unavailable",
        frames_out_total="stale-malformed-number",
    )
    edit_json(
        bundle,
        "summary.json",
        lambda payload: payload["validity"]["sources"]["encoderPipeline"].update(
            availableSampleCount=2
        ),
    )
    samples = load(bundle, context_v2).series["encoder.frames_out_rate_fps"].samples
    assert len(samples) == 3
    assert not samples[1].available
    assert samples[1].value is None
    assert samples[1].missing_reason
    assert samples[1].rejection_reason is None
    assert samples[1].source_row == 5


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "paused"},
        {"connection_state": "disconnected"},
        {"ice_connection_state": "failed"},
        {"last_engine_error": "error"},
    ],
)
def test_inactive_browser_source_discards_stale_numeric_cells(
    tmp_path: Path, context_v2: ContextKey, changes: dict[str, str]
) -> None:
    bundle = copy_v2_bundle(tmp_path)
    edit_row(bundle, "stream-telemetry.csv", 1, frames_decoded="999", **changes)
    middle = load(bundle, context_v2).series["client.frames_decoded_rate_fps"].samples[1]
    assert not middle.available
    assert middle.value is None
    assert middle.missing_reason


def test_header_only_optional_engine_source_is_explicit(
    tmp_path: Path, context_v2: ContextKey
) -> None:
    bundle = copy_v2_bundle(tmp_path)
    path = bundle / "engine-telemetry.csv"
    path.write_text(path.read_text().splitlines()[0] + "\n", encoding="utf-8")
    edit_json(
        bundle,
        "run-metadata.json",
        lambda payload: payload.update(scenario="browser_only_baseline"),
    )
    edit_json(
        bundle,
        "bundle-manifest.json",
        lambda payload: payload["telemetrySources"].update(
            engine_runtime="unavailable", encoder_pipeline="unsupported"
        ),
    )

    def clear_counts(payload):
        for source in ("engineRuntime", "encoderPipeline"):
            payload["validity"]["sources"][source] = {"sampleCount": 0, "availableSampleCount": 0}

    edit_json(bundle, "summary.json", clear_counts)
    series = load(bundle, context_v2).series["encoder.frames_out_rate_fps"]
    assert series.samples == ()
    assert series.missing_reason


@pytest.mark.parametrize(
    "filename,index,row", [("stream-telemetry.csv", 1, 3), ("engine-telemetry.csv", 2, 4)]
)
@pytest.mark.parametrize("raw", ["-1", "0", "bad", "NaN", "1e10000", "-100"])
def test_invalid_elapsed_times_reject_input_with_original_row(
    tmp_path: Path, context_v2: ContextKey, filename: str, index: int, row: int, raw: str
) -> None:
    bundle = copy_v2_bundle(tmp_path)
    edit_row(bundle, filename, index, elapsed_ms=raw)
    with pytest.raises(PixelatedBundleError, match=f"{filename} row {row} elapsed_ms"):
        load(bundle, context_v2)


@pytest.mark.parametrize(
    ("filename", "index", "changes", "message"),
    [
        ("stream-telemetry.csv", 1, {"session_id": "other"}, "session_id disagrees"),
        ("engine-telemetry.csv", 2, {"session_id": "other"}, "row 4 identity disagrees"),
        ("engine-telemetry.csv", 2, {"source": "unknown"}, "row 4 has unsupported source"),
        ("stream-telemetry.csv", 1, {"captured_at": "invalid"}, "row 3 captured_at"),
        (
            "stream-telemetry.csv",
            1,
            {"captured_at": "2026-08-10T02:03:04.000Z"},
            "row 3 captured_at must be strictly increasing",
        ),
        (
            "engine-telemetry.csv",
            2,
            {"captured_at": "2026-08-10T02:03:04.000Z"},
            "row 4 captured_at must be strictly increasing",
        ),
        ("stream-telemetry.csv", 1, {"elapsed_ms": "4000"}, "row 3 wall-clock and elapsed"),
        ("engine-telemetry.csv", 2, {"elapsed_ms": "4000"}, "row 4 wall-clock and elapsed"),
    ],
)
def test_identity_and_clock_contracts_are_not_bypassed(
    tmp_path: Path,
    context_v2: ContextKey,
    filename: str,
    index: int,
    changes: dict[str, str],
    message: str,
) -> None:
    bundle = copy_v2_bundle(tmp_path)
    edit_row(bundle, filename, index, **changes)
    with pytest.raises(PixelatedBundleError, match=message):
        load(bundle, context_v2)


def test_csv_row_limit_stays_in_force(
    context_v2: ContextKey, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bundle_io, "MAX_CSV_ROWS", 2)
    with pytest.raises(PixelatedBundleError, match="more than 2 data rows"):
        load(VALID_V2_BUNDLE, context_v2)


def test_duplicate_json_and_directory_links_remain_rejected(
    tmp_path: Path, context_v2: ContextKey
) -> None:
    bundle = copy_v2_bundle(tmp_path)
    path = bundle / "run-metadata.json"
    path.write_text(
        path.read_text().replace('"schemaVersion":', '"schemaVersion": 1, "schemaVersion":'),
        encoding="utf-8",
    )
    with pytest.raises(PixelatedBundleError, match="duplicate JSON object key"):
        load(bundle, context_v2)
    path.unlink()
    path.symlink_to(VALID_V2_BUNDLE / "run-metadata.json")
    with pytest.raises(PixelatedBundleError, match="bundle links are not allowed"):
        load(bundle, context_v2)


def test_context_and_request_validation_guards(context_v2: ContextKey, context: ContextKey) -> None:
    with pytest.raises(PixelatedBundleError, match="comparison_case_id cannot be empty"):
        extraction.load_pixelated_measurement_samples(
            VALID_V2_BUNDLE, phase=WindowPhase.DEGRADED, comparison_case_id=" ", context=context_v2
        )
    with pytest.raises(PixelatedBundleError, match="pixelatedBundleSchema disagrees"):
        load(VALID_V2_BUNDLE, context)
    with pytest.raises(PixelatedBundleError, match="requires pixelatedBundleSchema"):
        load(VALID_V2_BUNDLE, context_v2.model_copy(update={"versions": {}}))
    with pytest.raises(PixelatedBundleError, match="workload identity disagrees"):
        load(VALID_V2_BUNDLE, context_v2.model_copy(update={"workload_id": "different"}))


@pytest.mark.parametrize("count", [0, 1])
def test_empty_or_zero_duration_browser_capture_cannot_form_a_window(
    tmp_path: Path, context_v2: ContextKey, count: int
) -> None:
    bundle = copy_v2_bundle(tmp_path)
    path = bundle / "stream-telemetry.csv"
    path.write_text("\n".join(path.read_text().splitlines()[: count + 1]) + "\n", encoding="utf-8")
    edit_json(
        bundle, "summary.json", lambda payload: payload["recording"].update(sampleCount=count)
    )
    with pytest.raises(
        PixelatedBundleError, match="at least one data row|duration must be greater"
    ):
        load(bundle, context_v2)


@pytest.mark.parametrize("raw", ["bad-number", "NaN", "Infinity", "1e10000", "-1"])
def test_engine_malformed_numeric_cells_retain_their_global_csv_row(
    tmp_path: Path, context_v2: ContextKey, raw: str
) -> None:
    bundle = copy_v2_bundle(tmp_path)
    edit_row(bundle, "engine-telemetry.csv", 3, frames_out_total=raw)
    middle = load(bundle, context_v2).series["encoder.frames_out_rate_fps"].samples[1]
    assert middle.value is None
    assert "engine-telemetry.csv row 5 frames_out_total" in middle.rejection_reason


@pytest.mark.parametrize(
    "kind", ["utf8", "duplicate_column", "file_size", "json_depth", "tar_link"]
)
def test_extraction_reuses_text_archive_and_json_security_bounds(
    tmp_path: Path, context_v2: ContextKey, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    import tarfile

    from latency_fingerprinting.json_io import MAX_JSON_NESTING_DEPTH

    bundle = copy_v2_bundle(tmp_path)
    path = bundle / "stream-telemetry.csv"
    if kind == "utf8":
        path.write_bytes(b"\xff")
        message = "not valid UTF-8"
    elif kind == "duplicate_column":
        path.write_text(
            path.read_text().replace("captured_at,", "elapsed_ms,", 1), encoding="utf-8"
        )
        message = "duplicate columns"
    elif kind == "file_size":
        monkeypatch.setattr(bundle_io, "MAX_TEXT_FILE_BYTES", 10)
        message = "file is too large"
    elif kind == "json_depth":
        depth = MAX_JSON_NESTING_DEPTH + 1
        (bundle / "run-metadata.json").write_text("[" * depth + "0" + "]" * depth, encoding="utf-8")
        message = "nesting exceeds"
    else:
        archive = tmp_path / "link.tar"
        with tarfile.open(archive, "w") as file:
            member = tarfile.TarInfo("stream-telemetry.csv")
            member.type = tarfile.SYMTYPE
            member.linkname = "other"
            file.addfile(member)
        bundle = archive
        message = "TAR links are not allowed"
    with pytest.raises(PixelatedBundleError, match=message):
        load(bundle, context_v2)
