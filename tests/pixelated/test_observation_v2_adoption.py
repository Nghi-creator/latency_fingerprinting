"""Raw evidence adoption, declaration precedence and unchanged public legacy paths."""

import json

import pytest

from latency_fingerprinting.adapters import ingest_pixelated_v2
from latency_fingerprinting.adapters import pixelated_measurement_samples as extraction
from latency_fingerprinting.cli import main
from latency_fingerprinting.models import ObservationWindowV2, ProvenanceKind, WindowPhase
from latency_fingerprinting.pipeline import canonical_json

from .support import VALID_BUNDLE, VALID_V2_BUNDLE, copy_v2_bundle, write_tar
from .test_measurement_samples import edit_json, edit_row


def adopt(path, context, **changes):
    return ingest_pixelated_v2(
        path,
        context=context,
        phase=WindowPhase.DEGRADED,
        comparison_case_id="controlled-case-001",
        **changes,
    )


def bytes_in(directory):
    return {p.name: p.read_bytes() for p in directory.iterdir()}


@pytest.mark.parametrize("version", [1, 2])
def test_adoption_is_deterministic_read_only_and_packaging_independent(
    tmp_path, context, context_v2, version
):
    bundle, ctx = (VALID_BUNDLE, context) if version == 1 else (VALID_V2_BUNDLE, context_v2)
    before = bytes_in(bundle)
    archive = tmp_path / "bundle.tar"
    write_tar(bundle, archive)
    first = adopt(bundle, ctx)
    assert (
        canonical_json(first)
        == canonical_json(adopt(bundle, ctx))
        == canonical_json(adopt(archive, ctx))
    )
    assert bytes_in(bundle) == before
    assert ObservationWindowV2.model_validate_json(canonical_json(first)) == first
    assert first.window_id == f"pixelated-v2-{first.source_artifact.content_hash[7:]}-degraded"
    assert first.clock.domain_id == f"pixelated-{first.source_artifact.content_hash[7:]}"
    assert first.capture_method.producer_version is None
    assert len(first.stage_timings) == 4
    assert all(
        timing.state == "unavailable" and timing.value is None for timing in first.stage_timings
    )
    assert first.clock.provenance == "wall_clock_derived_elapsed"
    assert len(first.measurements) == 31
    if version == 1:
        assert tuple(t.reason_code for t in first.stage_timings) == (
            "source_unavailable",
            "source_unavailable",
            "not_instrumented",
            "not_instrumented",
        )
        assert first.measurements["encoder.frames_out_rate_fps"].summary.value is None
        assert first.sources["engine_runtime"].state == "unavailable"
    else:
        assert all(t.reason_code == "not_instrumented" for t in first.stage_timings)
        assert first.measurements["client.decode_time_mean_ms"].summary.value > 0
        assert first.measurements["client.frames_decoded_rate_fps"].summary.value == 60
        assert first.measurements["client.frames_decoded_window_total"].summary.value == 600
        assert first.measurements["encoder.pipeline_delay_proxy_ms"].support.state == "unsupported"


def test_one_read_and_no_p0_aggregation(context_v2, monkeypatch):
    original = extraction.read_bundle
    calls = []

    def read_once(*args, **kwargs):
        calls.append(args[0])
        return original(*args, **kwargs)

    monkeypatch.setattr(extraction, "read_bundle", read_once)
    from latency_fingerprinting.adapters import pixelated_bundle_metrics

    monkeypatch.setattr(
        pixelated_bundle_metrics,
        "mapped_metrics",
        lambda *args, **kw: pytest.fail("P0 aggregation invoked"),
    )
    assert adopt(VALID_V2_BUNDLE, context_v2).validity.is_valid
    assert len(calls) == 1


def test_mutable_caller_context_cannot_change_adoption_mid_read(context_v2, monkeypatch):
    original = extraction.read_bundle
    expected = context_v2.node_id

    def mutate(*args, **kwargs):
        context_v2.node_id = "changed caller"
        context_v2.versions["pixelatedBundleSchema"] = "1"
        return original(*args, **kwargs)

    monkeypatch.setattr(extraction, "read_bundle", mutate)
    model = adopt(VALID_V2_BUNDLE, context_v2)
    assert model.context.node_id == expected
    assert model.context.versions["pixelatedBundleSchema"] == "2"


@pytest.mark.parametrize("state", ["unsupported", "unavailable"])
@pytest.mark.parametrize("scope", ["source", "metric"])
def test_declarations_override_stale_browser_values(tmp_path, context_v2, state, scope):
    bundle = copy_v2_bundle(tmp_path)

    def declare(payload):
        key = "telemetrySources" if scope == "source" else "measurementSupport"
        name = "browser_webrtc" if scope == "source" else "browser_webrtc.framesDecoded"
        payload[key][name] = state

    edit_json(bundle, "bundle-manifest.json", declare)
    model = adopt(bundle, context_v2)
    rate = model.measurements["client.frames_decoded_rate_fps"]
    total = model.measurements["client.frames_decoded_window_total"]
    assert rate.support.state == state and total.support == rate.support
    assert rate.summary.value is None and rate.summary.status == "missing"
    assert not rate.summary.counter_intervals
    assert rate.summary.source_sample_count == 3 and rate.summary.usable_sample_count == 0
    assert model.validity.is_valid == (scope == "metric")
    # A metric declaration cannot change the source's direct-stage capability.
    expected_reason = (
        ("unsupported_source" if state == "unsupported" else "source_unavailable")
        if scope == "source"
        else "not_instrumented"
    )
    assert tuple(t.reason_code for t in model.stage_timings[2:]) == (expected_reason,) * 2


@pytest.mark.parametrize("cell", ["", "bad-secret", "-1", "NaN", "1e10000"])
def test_numeric_failures_are_structured_and_private(tmp_path, context_v2, cell):
    bundle = copy_v2_bundle(tmp_path)
    edit_row(bundle, "stream-telemetry.csv", 1, jitter_ms=cell)
    model = adopt(bundle, context_v2)
    summary = model.measurements["transport.jitter_ms"].summary
    assert summary.status == "incomplete" and summary.usable_sample_count == 2
    assert summary.coverage == 0
    assert summary.missing_reasons if cell == "" else summary.rejected_reasons
    assert "bad-secret" not in canonical_json(model)


def test_zero_is_numeric_and_resets_are_not_upgraded_from_p0(tmp_path, context_v2):
    bundle = copy_v2_bundle(tmp_path)
    for index in range(3):
        edit_row(bundle, "stream-telemetry.csv", index, frames_decoded="0", jitter_ms="0")
    model = adopt(bundle, context_v2)
    assert model.measurements["client.frames_decoded_rate_fps"].summary.value == 0
    assert model.measurements["transport.jitter_ms"].summary.value == 0
    for index, value in enumerate((100, 20, 80)):
        edit_row(bundle, "stream-telemetry.csv", index, frames_decoded=str(value))
    summary = adopt(bundle, context_v2).measurements["client.frames_decoded_rate_fps"].summary
    assert summary.reset_source_rows == (3,) and summary.value == 12 and summary.coverage == 0.5


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "paused"},
        {"connection_state": "disconnected"},
        {"ice_connection_state": "failed"},
        {"last_engine_error": "private error"},
    ],
)
def test_browser_source_gaps_reduce_coverage_and_validity(tmp_path, context_v2, changes):
    bundle = copy_v2_bundle(tmp_path)
    edit_row(bundle, "stream-telemetry.csv", 1, **changes)
    model = adopt(bundle, context_v2)
    rate = model.measurements["client.frames_decoded_rate_fps"].summary
    assert rate.value is None and rate.gap_source_rows == (3,)
    assert not model.validity.is_valid
    assert "source_samples_unavailable" in model.validity.reason_codes
    assert "private error" not in canonical_json(model)


def test_engine_gap_and_optional_header_only_sources(tmp_path, context_v2):
    bundle = copy_v2_bundle(tmp_path)
    edit_row(bundle, "engine-telemetry.csv", 2, available="false", error="private failure")
    edit_json(
        bundle,
        "summary.json",
        lambda p: p["validity"]["sources"]["engineRuntime"].update(availableSampleCount=2),
    )
    model = adopt(bundle, context_v2)
    assert model.sources["engine_runtime"].available_row_count == 2
    assert not model.validity.is_valid
    path = bundle / "engine-telemetry.csv"
    path.write_text(path.read_text().splitlines()[0] + "\n")
    edit_json(bundle, "run-metadata.json", lambda p: p.update(scenario="browser_only_baseline"))
    edit_json(
        bundle,
        "bundle-manifest.json",
        lambda p: p["telemetrySources"].update(
            engine_runtime="unavailable", encoder_pipeline="unsupported"
        ),
    )

    def counts(payload):
        for source in ("engineRuntime", "encoderPipeline"):
            payload["validity"]["sources"][source] = {"sampleCount": 0, "availableSampleCount": 0}

    edit_json(bundle, "summary.json", counts)
    model = adopt(bundle, context_v2)
    assert model.validity.is_valid
    assert model.measurements["encoder.frames_out_rate_fps"].support.state == "unsupported"
    assert tuple(t.reason_code for t in model.stage_timings) == (
        "source_unavailable",
        "unsupported_source",
        "not_instrumented",
        "not_instrumented",
    )


@pytest.mark.parametrize("producer", [None, "producer-1.0"])
def test_declared_producer_version_is_retained_only_when_supplied(tmp_path, context_v2, producer):
    bundle = copy_v2_bundle(tmp_path)
    edit_json(bundle, "bundle-manifest.json", lambda p: p.update(producerVersion=producer))
    assert adopt(bundle, context_v2).capture_method.producer_version == producer


@pytest.mark.parametrize("producer", ["", True, 1, {}])
def test_invalid_producer_version_rejects_adoption(tmp_path, context_v2, producer):
    bundle = copy_v2_bundle(tmp_path)
    edit_json(bundle, "bundle-manifest.json", lambda p: p.update(producerVersion=producer))
    with pytest.raises(ValueError, match="producerVersion"):
        adopt(bundle, context_v2)


def test_cli_adoption_and_validate_exact_bytes(tmp_path, context_v2, capsys):
    args = [
        "ingest-pixelated-v2",
        str(VALID_V2_BUNDLE),
        "--context",
        "tests/data/pixelated_bundle/context-v2.json",
        "--phase",
        "degraded",
        "--comparison-case-id",
        "controlled-case-001",
    ]
    assert main(args) == 0
    output = capsys.readouterr()
    assert not output.err and output.out == canonical_json(adopt(VALID_V2_BUNDLE, context_v2))
    path = tmp_path / "window.json"
    path.write_text(output.out)
    assert main(["validate", str(path)]) == 0
    assert capsys.readouterr().out == output.out
    assert (
        main(args + ["--provenance", "organic_real", "--confounder-code", "operator_declared"]) == 0
    )
    emitted = json.loads(capsys.readouterr().out)
    assert emitted["provenance"] == "organic_real" and emitted["confounderCodes"] == [
        "operator_declared"
    ]


@pytest.mark.parametrize("fault", ["clock", "privacy", "duplicate", "context", "size"])
def test_cli_envelope_failures_are_repeatable_without_partial_output(
    tmp_path, context_v2, capsys, monkeypatch, fault
):
    bundle = copy_v2_bundle(tmp_path)
    context = tmp_path / "context.json"
    context.write_text(context_v2.model_dump_json(by_alias=True))
    if fault == "clock":
        edit_row(bundle, "stream-telemetry.csv", 1, elapsed_ms="0")
    elif fault == "privacy":
        edit_json(bundle, "run-metadata.json", lambda p: p.update(engineToken="private"))
    elif fault == "duplicate":
        path = bundle / "bundle-manifest.json"
        path.write_text(
            path.read_text().replace('"schemaVersion":', '"schemaVersion":2,"schemaVersion":')
        )
    elif fault == "context":
        context.write_text(
            context.read_text().replace(
                '"pixelatedBundleSchema":"2"', '"pixelatedBundleSchema":"1"'
            )
        )
    else:
        from latency_fingerprinting.adapters import pixelated_bundle_io

        monkeypatch.setattr(pixelated_bundle_io, "MAX_TEXT_FILE_BYTES", 10)
    args = [
        "ingest-pixelated-v2",
        str(bundle),
        "--context",
        str(context),
        "--phase",
        "degraded",
        "--comparison-case-id",
        "controlled-case-001",
    ]
    previous = None
    for _ in range(2):
        assert main(args) == 1
        output = capsys.readouterr()
        assert not output.out and "Traceback" not in output.err
        assert previous is None or previous == output.err
        previous = output.err


def test_provenance_and_confounders_are_not_implicitly_invented(context_v2):
    with pytest.raises(ValueError, match="real provenance"):
        adopt(VALID_V2_BUNDLE, context_v2, provenance=ProvenanceKind.SYNTHETIC)
    with pytest.raises(ValueError, match="ordered"):
        adopt(VALID_V2_BUNDLE, context_v2, confounder_codes={"operator_declared"})


def test_opt_in_metadata_is_frozen_and_does_not_change_n1_series(context_v2):
    from dataclasses import FrozenInstanceError

    legacy = extraction.load_pixelated_measurement_samples(
        VALID_V2_BUNDLE,
        context=context_v2,
        phase=WindowPhase.DEGRADED,
        comparison_case_id="controlled-case-001",
    )
    extended = extraction.load_pixelated_measurement_samples(
        VALID_V2_BUNDLE,
        context=context_v2,
        phase=WindowPhase.DEGRADED,
        comparison_case_id="controlled-case-001",
        include_adoption_metadata=True,
    )
    assert (
        legacy.adoption is None
        and extended.series == legacy.series
        and extended.checksum == legacy.checksum
    )
    with pytest.raises(TypeError):
        extended.adoption.effective_settings["fps"] = 0
    with pytest.raises(TypeError):
        extended.adoption.metric_declarations["transport.jitter_ms"] = "unsupported"
    with pytest.raises(FrozenInstanceError):
        extended.adoption.run_id = "changed"


def test_n1_does_not_adopt_new_producer_version_validation(tmp_path, context_v2):
    bundle = copy_v2_bundle(tmp_path)
    edit_json(bundle, "bundle-manifest.json", lambda p: p.update(producerVersion=True))
    legacy = extraction.load_pixelated_measurement_samples(
        bundle,
        context=context_v2,
        phase=WindowPhase.DEGRADED,
        comparison_case_id="controlled-case-001",
    )
    assert legacy.adoption is None
    with pytest.raises(ValueError, match="producerVersion"):
        adopt(bundle, context_v2)


def test_producer_invalidity_is_typed_without_copying_reason_text(tmp_path, context_v2):
    bundle = copy_v2_bundle(tmp_path)
    edit_json(
        bundle,
        "summary.json",
        lambda p: p["validity"].update(isValid=False, reasons=["private operator reason"]),
    )
    model = adopt(bundle, context_v2)
    assert model.validity.reason_codes == ("producer_invalid",)
    assert "private operator reason" not in canonical_json(model)
