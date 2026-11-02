"""Raw fixture arithmetic, original rows/clocks and hostile window requests."""

import hashlib

import pytest

from latency_fingerprinting.adapters import (
    WindowBounds,
    ingest_pixelated_v2,
    ingest_pixelated_windows,
)
from latency_fingerprinting.adapters import pixelated_measurement_samples as extraction
from latency_fingerprinting.cli import main
from latency_fingerprinting.json_io import canonical_json, load_model_file
from latency_fingerprinting.models import ContextKey, ObservationWindowV2
from tests.pixelated.support import FIXTURE_ROOT, VALID_V2_BUNDLE, write_tar


def context():
    return load_model_file(FIXTURE_ROOT / "context-v2.json", ContextKey)


def adopt(path=VALID_V2_BUNDLE, **changes):
    return ingest_pixelated_windows(
        path,
        context=context(),
        phase="degraded",
        comparison_case_id="controlled-case-001",
        windows=changes.pop(
            "windows", [dict(start_ms=0, end_ms=5000), dict(start_ms=5000, end_ms=10000)]
        ),
        **changes,
    )


def test_two_exact_windows_have_independent_hand_calculated_intervals_and_one_source(monkeypatch):
    calls = []
    original = extraction.read_bundle

    def read(*args, **kwargs):
        calls.append(args[0])
        return original(*args, **kwargs)

    monkeypatch.setattr(extraction, "read_bundle", read)
    first, second = adopt()
    assert len(calls) == 1
    assert first.capture_method.method_version == second.capture_method.method_version == "1.1.0"
    assert first.clock.domain_id == second.clock.domain_id
    assert first.source_artifact == second.source_artifact
    assert first.run_id == second.run_id
    assert first.window_id != second.window_id
    assert first.clock.elapsed_end_ms == second.clock.elapsed_start_ms == 5000
    assert first.measurements["client.received_fps"].summary.value == 52
    assert second.measurements["client.received_fps"].summary.value == 56
    decoded = [w.measurements["client.frames_decoded_rate_fps"].summary for w in (first, second)]
    assert [s.value for s in decoded] == [60, 60]
    assert [s.observed_duration_ms for s in decoded] == [5000, 5000]
    assert [s.usable_source_rows for s in decoded] == [(2, 3), (3, 4)]
    assert [s.counter_intervals[0].delta for s in decoded] == [300, 300]
    assert all(s.accepted_interval_count == 1 and s.coverage == 1 for s in decoded)
    assert first.sources["browser_webrtc"].row_count == 2
    assert ObservationWindowV2.model_validate_json(canonical_json(first)) == first
    assert all(s.state == "unavailable" for s in first.stage_timings)


def test_old_method_keeps_original_identity_and_slice_reproduces_across_archives(tmp_path):
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in VALID_V2_BUNDLE.iterdir()}
    old = ingest_pixelated_v2(
        VALID_V2_BUNDLE,
        context=context(),
        phase="degraded",
        comparison_case_id="controlled-case-001",
    )
    assert old.capture_method.method_version == "1.0.0"
    assert old.window_id.startswith("pixelated-v2-")
    archive = tmp_path / "bundle.tar"
    write_tar(VALID_V2_BUNDLE, archive)
    assert adopt() == adopt(archive)
    assert before == {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in VALID_V2_BUNDLE.iterdir()
    }


@pytest.mark.parametrize(
    "windows",
    [
        [],
        [dict(start_ms=True, end_ms=5000)],
        [dict(start_ms=0, end_ms=500)],
        [dict(start_ms=0, end_ms=10001)],
        [dict(start_ms=1, end_ms=5000)],
        [dict(start_ms=5000, end_ms=10000), dict(start_ms=0, end_ms=5000)],
        [dict(start_ms=0, end_ms=10000), dict(start_ms=5000, end_ms=10000)],
        [dict(start_ms=10000, end_ms=15000)],
        [dict(start_ms=0.0, end_ms=5000)],
    ],
)
def test_bad_bounds_never_round_interpolate_or_reorder(windows):
    with pytest.raises(ValueError, match="^invalid_pixelated_windows$"):
        adopt(windows=windows)


def test_confounds_cannot_be_discarded_and_synthetic_claims_rejected():
    assert adopt(confounder_codes=("operator_declared",))[0].confounder_codes == (
        "operator_declared",
    )
    with pytest.raises(ValueError):
        adopt(provenance="synthetic")
    with pytest.raises(ValueError):
        WindowBounds(start_ms=0, end_ms=5000).start_ms = 12


def test_window_cli_protects_raw_context_hardlinks_and_old_output(tmp_path, capsys):
    archive = tmp_path / "bundle.tar"
    write_tar(VALID_V2_BUNDLE, archive)
    ctx = tmp_path / "context.json"
    ctx.write_text(canonical_json(context()))
    args = [
        "ingest-pixelated-window",
        "--bundle",
        str(archive),
        "--context",
        str(ctx),
        "--phase",
        "degraded",
        "--comparison-case-id",
        "controlled-case-001",
        "--start-ms",
        "0",
        "--end-ms",
        "5000",
    ]
    output = tmp_path / "result.json"
    assert main([*args, "--output", str(output)]) == 0
    assert capsys.readouterr() == ("", "")
    assert output.read_text() == canonical_json(adopt()[0])
    assert output.stat().st_mode & 0o777 == 0o600
    for protected in (archive, ctx):
        alias = tmp_path / "alias"
        alias.hardlink_to(protected)
        before = protected.read_bytes()
        assert main([*args, "--output", str(alias)]) == 1
        assert capsys.readouterr() == (
            "",
            "error: ingest-pixelated-window: invalid_input_or_output\n",
        )
        assert protected.read_bytes() == before
        alias.unlink()
    bad = list(args)
    bad[bad.index("--end-ms") + 1] = "10001"
    saved = output.read_bytes()
    assert main([*bad, "--output", str(output)]) == 1
    assert output.read_bytes() == saved
    assert capsys.readouterr() == ("", "error: ingest-pixelated-window: invalid_input_or_output\n")


def test_raw_source_and_metric_declarations_are_preserved(tmp_path):
    import shutil

    from tests.pixelated.test_measurement_samples import edit_json

    directory = tmp_path / "source"
    shutil.copytree(VALID_V2_BUNDLE, directory)
    edit_json(
        directory,
        "bundle-manifest.json",
        lambda d: d["measurementSupport"].update({"browser_webrtc.fps": "unsupported"}),
    )
    first = adopt(directory)[0]
    assert first.sources["browser_webrtc"].available_row_count == 2
    assert first.measurements["client.received_fps"].summary.value is None
    assert first.measurements["client.received_fps"].support.state == "unsupported"
