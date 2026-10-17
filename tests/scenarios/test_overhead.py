"""Raw five-pair arithmetic, inclusive thresholds and linked nominal coverage."""

import gzip
import hashlib
import json

import pytest

from latency_fingerprinting.cli import main
from latency_fingerprinting.scenarios.overhead import inspect_overhead
from latency_fingerprinting.scenarios.overhead_models import ORDER, OverheadEvidence
from tests.scenarios.test_bundle import TRACE, archive, encoded
from tests.scenarios.test_campaign import plan


def overhead(
    directory,
    *,
    cpu_extra=1_500_000_000,
    enabled_frames=855,
    capture_frames=None,
    reversed_pair=None,
):
    directory.mkdir()
    schedule = plan(
        [
            dict(
                run_id=f"run-{i + 1}",
                source_id=f"{i + 1:032x}",
                scenario="healthy",
                assignment="engineering",
                repeat_index=i + 1,
            )
            for i in range(10)
        ]
    )
    raw = encoded(schedule)
    (directory / "overhead-plan.json").write_bytes(raw)
    rows = []
    nominal = enabled_frames if capture_frames is None else capture_frames
    for pair, mode in ORDER:
        row = dict(
            pair=pair,
            mode=mode,
            warmup_ns=10_000_000_000,
            wall_ns=30_000_000_000,
            cpu_ns=6_000_000_000 + (cpu_extra if mode == "enabled" else 0),
            frames_start=0,
            frames_end=enabled_frames if mode == "enabled" else 900,
            trace_file_name=None,
            trace_bytes=0,
            trace_sha256=None,
            export_duration_ns=None,
        )
        if mode == "enabled":
            trace = json.loads(TRACE.read_bytes())
            stream = trace["streams"][0]
            stream["frames"] = [
                dict(frame_id=f"frame-{i + 1}", source_sequence=i + 1, correlation="exact")
                for i in range(nominal)
            ]
            stream["events"] = [
                dict(
                    frame_id=f"frame-{i + 1}",
                    boundary=b,
                    sequence=i * 5 + j + 1,
                    timestamp_ns=i * 33_333_333 + j * 1_000_000,
                )
                for i in range(nominal)
                for j, b in enumerate(
                    (
                        "capture_output",
                        "pre_encode_queue_enter",
                        "pre_encode_queue_exit",
                        "encode_input",
                        "encode_output",
                    )
                )
            ]
            stream["loss"].update(
                offered_frames=nominal,
                sampled_frames=nominal,
                attempted_events=nominal * 5,
                retained_events=nominal * 5,
            )
            if reversed_pair is not None:
                start, end = reversed_pair
                for event in stream["events"]:
                    if event["boundary"] == end:
                        offset = 1 if start == "pre_encode_queue_enter" else 3
                        event["timestamp_ns"] = (
                            (int(event["frame_id"].split("-")[1]) - 1) * 33_333_333
                            + offset * 1_000_000
                            - 1
                        )
            record = encoded(trace)
            # Use the independently pinned N4 manifest shape, replacing only its receipt.
            template = json.loads((TRACE.parent / "trace-manifest.json").read_bytes())
            for key in template:
                if key.endswith("sha256"):
                    template[key] = hashlib.sha256(record).hexdigest()
                if key in ("bytes", "record_bytes", "trace_bytes"):
                    template[key] = len(record)
            manifest = encoded(template)
            payload = gzip.compress(
                archive((("trace-record.json", record), ("trace-manifest.json", manifest))), mtime=0
            )
            name = f"pair-{pair}-enabled.tar.gz"
            (directory / name).write_bytes(payload)
            row.update(
                trace_file_name=name,
                trace_bytes=len(payload),
                trace_sha256=hashlib.sha256(payload).hexdigest(),
                export_duration_ns=1000,
            )
        rows.append(row)
    measure = dict(
        warmup_ns=10_000_000_000,
        wall_ns=30_000_000_000,
        cpu_ns=6_000_000_000,
        frames_start=0,
        frames_end=900,
    )
    evidence = dict(
        schema_version="n4-overhead-evidence-v1",
        provenance="synthetic",
        campaign_id="campaign-1",
        plan_sha256=hashlib.sha256(raw).hexdigest(),
        core_version="a" * 40,
        producer_version="a" * 40,
        runtime=dict(
            kind="synthetic",
            python_version="3.14.4",
            node_version="26.4.0",
            gst_version="1.28.2",
            cpu_allocation=2,
            width=1280,
            height=720,
            fps=30,
            codec="vp8",
            clock_source="python_monotonic_ns",
            clock_resolution_ns=1,
        ),
        state="completed",
        reason=None,
        trials=rows,
        diagnostic=dict(
            baseline=measure,
            measured=dict(measure, cpu_ns=6_300_000_000),
            probe_durations_ns=[100, 200] * 500,
            observed_probes=1000,
        ),
        cleanup_verified=True,
    )
    (directory / "overhead-evidence.json").write_bytes(encoded(evidence))
    return directory, evidence


@pytest.mark.parametrize(
    "cpu_extra,frames,passed",
    [(1_500_000_000, 855, True), (1_500_000_001, 855, False), (1_500_000_000, 854, False)],
)
def test_frozen_overhead_boundaries_from_raw_counters(tmp_path, cpu_extra, frames, passed):
    path, _ = overhead(tmp_path / "overhead", cpu_extra=cpu_extra, enabled_frames=frames)
    report = inspect_overhead(path)
    assert report["measured_thresholds_passed"] is passed
    assert report["real_overhead_acceptance"] is False
    assert len(report["pairs"]) == 5
    assert report["diagnostic"]["retained_samples"] == 1000
    assert report["diagnostic"]["mean_ns"] == 150
    assert report["phase_1_acceptance"] == "pending"


def test_missing_source_pairs_cannot_hide_behind_a_smaller_trace_denominator(tmp_path):
    path, _ = overhead(tmp_path / "overhead", capture_frames=500)
    report = inspect_overhead(path)
    assert report["measured_thresholds_passed"] is False
    assert all(t["nominal_capture_passed"] is False for t in report["nominal_traces"])


@pytest.mark.parametrize(
    "pair", [("pre_encode_queue_enter", "pre_encode_queue_exit"), ("encode_input", "encode_output")]
)
def test_negative_trace_durations_cannot_pass_nominal_capture(tmp_path, pair):
    path, _ = overhead(tmp_path / "overhead", reversed_pair=pair)
    report = inspect_overhead(path)
    assert report["measured_thresholds_passed"] is False
    assert all(t["nominal_capture_passed"] is False for t in report["nominal_traces"])


def test_order_cleanup_and_diagnostics_cannot_be_omitted(tmp_path):
    _, evidence = overhead(tmp_path / "overhead")
    for drift in ("order", "cleanup", "diagnostic", "missing"):
        value = json.loads(encoded(evidence))
        if drift == "order":
            value["trials"] = list(reversed(value["trials"]))
        elif drift == "cleanup":
            value["cleanup_verified"] = False
        elif drift == "diagnostic":
            value["diagnostic"]["probe_durations_ns"] = [100] * 999
        else:
            value["trials"].pop()
        with pytest.raises(ValueError):
            OverheadEvidence.model_validate(value)


def test_cli_canonical_report_and_fixed_preserved_output(tmp_path, capsys):
    path, _ = overhead(tmp_path / "overhead")
    output = tmp_path / "report.json"
    assert main(["inspect-overhead", "--directory", str(path), "--output", str(output)]) == 0
    assert main(["validate", str(output)]) == 0
    assert json.loads(capsys.readouterr().out) == json.loads(output.read_bytes())
    before = output.read_bytes()
    (path / "pair-1-enabled.tar.gz").write_bytes(b"changed")
    assert main(["inspect-overhead", "--directory", str(path), "--output", str(output)]) == 1
    assert output.read_bytes() == before
    assert capsys.readouterr() == ("", "error: inspect-overhead: invalid_input_or_output\n")
