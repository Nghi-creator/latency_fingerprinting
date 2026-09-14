"""Aggregation evidence keeps original source locations after filtering."""

from latency_fingerprinting.adapters.pixelated_bundle_metrics import engine_metrics


def test_engine_rejections_retain_original_csv_row_numbers() -> None:
    rows = [
        {"source": "engine_runtime", "available": "true", "node_cpu_percent": "10"},
        {"source": "encoder_pipeline", "available": "true", "frames_in_total": "0"},
        {"source": "engine_runtime", "available": "false", "node_cpu_percent": "stale"},
        {"source": "encoder_pipeline", "available": "false", "frames_in_total": "stale"},
        {"source": "engine_runtime", "available": "true", "node_cpu_percent": "bad"},
        {"source": "encoder_pipeline", "available": "true", "frames_in_total": "bad"},
    ]
    metrics, _, rejected = engine_metrics(rows)
    assert "host.node_cpu_percent" not in metrics
    assert "row 6 node_cpu_percent" in rejected["host.node_cpu_percent"]
    assert "row 7 frames_in_total" in rejected["encoder.frames_in_delta"]
    assert "row 4" not in rejected["host.node_cpu_percent"]


def test_unavailable_encoder_poll_still_breaks_counter_continuity() -> None:
    rows = [
        {"source": "encoder_pipeline", "available": "true", "frames_in_total": "10"},
        {"source": "encoder_pipeline", "available": "false", "frames_in_total": "50"},
        {"source": "encoder_pipeline", "available": "true", "frames_in_total": "100"},
        {"source": "encoder_pipeline", "available": "true", "frames_in_total": "120"},
    ]
    metrics, _, rejected = engine_metrics(rows)
    assert not rejected
    assert metrics["encoder.frames_in_delta"].value == 20
    assert metrics["encoder.frames_in_delta"].count == 1
