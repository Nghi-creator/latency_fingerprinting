"""Both public ingestion paths reject contradictory engine source envelopes."""

import csv

import pytest

from latency_fingerprinting.adapters import load_pixelated_measurement_samples
from latency_fingerprinting.adapters.pixelated_bundle import (
    PixelatedBundleError,
    ingest_pixelated_bundle,
)
from latency_fingerprinting.models import WindowPhase

from .support import copy_v2_bundle


@pytest.mark.parametrize("loader", [ingest_pixelated_bundle, load_pixelated_measurement_samples])
@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"source": "other"}, "unsupported source"),
        ({"run_id": "other"}, "identity disagrees"),
        ({"session_id": "other"}, "identity disagrees"),
        ({"game_id": "other"}, "workload disagrees"),
        ({"schema_version": "2"}, "schema_version 1"),
        ({"available": "maybe"}, "must be true or false"),
        ({"available": "true", "error": "failed"}, "available with an error"),
        ({"available": "false", "error": ""}, "require an error"),
        ({"elapsed_ms": "-1"}, "negative"),
        ({"captured_at": "not a timestamp"}, "ISO"),
        ({"target_fps": "-1"}, "changed during"),
        ({"target_fps": "45"}, "changed during"),
    ],
)
def test_engine_contract_failures_reject_both_paths(tmp_path, context_v2, loader, changes, message):
    bundle = copy_v2_bundle(tmp_path)
    path = bundle / "engine-telemetry.csv"
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        rows = list(reader)
    rows[0].update(changes)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(PixelatedBundleError, match=message):
        loader(
            bundle,
            context=context_v2,
            phase=WindowPhase.DEGRADED,
            comparison_case_id="controlled-case-001",
        )
