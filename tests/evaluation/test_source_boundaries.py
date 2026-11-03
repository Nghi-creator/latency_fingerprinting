"""Asynchronous source evidence cannot acquire common-window coverage by relabelling."""

import csv
import json
from datetime import datetime, timedelta

import pytest

from latency_fingerprinting.models import MetricSeriesSummary, ObservationWindowV2
from tests.pixelated.support import copy_v2_bundle

from .test_windows import adopt


def asynchronous_bundle(tmp_path):
    directory = copy_v2_bundle(tmp_path)
    path = directory / "engine-telemetry.csv"
    with path.open(newline="") as file:
        reader = csv.DictReader(file)
        headers = reader.fieldnames
        rows = list(reader)[:4]
    # Actual observations on [500, 5500], inside the browser's [0, 10000].
    # Preserve the original row values; this is an explicitly artificial fixture.
    for row in rows:
        row["elapsed_ms"] = str(int(row["elapsed_ms"]) + 500)
        stamp = datetime.fromisoformat(row["captured_at"].replace("Z", "+00:00"))
        row["captured_at"] = (
            (stamp + timedelta(milliseconds=500))
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    path = directory / "summary.json"
    summary = json.loads(path.read_bytes())
    for name in ("engineRuntime", "encoderPipeline"):
        summary["validity"]["sources"][name] = dict(sampleCount=2, availableSampleCount=2)
    path.write_text(json.dumps(summary))
    return directory


def test_asynchronous_sources_keep_partial_coverage_on_the_real_declared_window(tmp_path):
    window = adopt(asynchronous_bundle(tmp_path), windows=[dict(start_ms=0, end_ms=10000)])[0]
    assert window.validity.is_valid
    assert window.measurements["client.frames_decoded_rate_fps"].summary.coverage == 1
    for name in ("host.camera_cpu_percent", "encoder.frames_in_rate_fps"):
        summary = window.measurements[name].summary
        assert summary.status == "incomplete"
        assert summary.observed_duration_ms == 5000
        assert summary.coverage == 0.5
        assert summary.window_start_ms == 0 and summary.window_end_ms == 10000


def test_source_local_summary_cannot_masquerade_as_an_old_common_window(tmp_path):
    window = adopt(asynchronous_bundle(tmp_path), windows=[dict(start_ms=0, end_ms=10000)])[0]
    payload = window.model_dump(mode="json")
    summary = payload["measurements"]["host.camera_cpu_percent"]["summary"]
    summary.update(
        window_start_ms=500,
        window_end_ms=5500,
        window_duration_ms=5000,
        coverage=1.0,
        status="complete",
    )
    # Internally consistent N1 evidence with different declared bounds remains
    # illegal inside a common-window N2 root. An alternate method needs review.
    MetricSeriesSummary.model_validate(summary)
    with pytest.raises(ValueError, match="summary bounds/clock must match its window"):
        ObservationWindowV2.model_validate(payload)
