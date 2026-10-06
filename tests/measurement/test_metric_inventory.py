"""Keep the reviewed N1 inventory aligned with frozen adapter source contracts."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from latency_fingerprinting.adapters.pixelated_bundle_metrics import (
    BROWSER_METRIC_COLUMNS,
    ENCODER_COUNTER_METRICS,
    ENGINE_METRIC_COLUMNS,
    STREAM_COUNTER_METRICS,
)
from latency_fingerprinting.measurement import P0_FEATURE_CONFIG

ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "docs/measurement/METRIC_SEMANTICS_V2.md"


def inventory_table(section: str) -> list[dict[str, str]]:
    text = INVENTORY.read_text(encoding="utf-8")
    body = text.split(f"## {section}\n", 1)[1].split("\n## ", 1)[0]
    lines = [line for line in body.splitlines() if line.startswith("| ")]
    cells = [[cell.strip() for cell in line.strip("|").split("|")] for line in lines]
    return [dict(zip(cells[0], row, strict=True)) for row in cells[2:]]


def test_every_p0_feature_has_exactly_one_semantic_decision() -> None:
    rows = inventory_table("P0 mapping")
    adapter_names = (
        set(BROWSER_METRIC_COLUMNS)
        | set(ENGINE_METRIC_COLUMNS)
        | set(STREAM_COUNTER_METRICS)
        | set(ENCODER_COUNTER_METRICS)
    )
    assert adapter_names == set(P0_FEATURE_CONFIG)
    assert Counter(row["P0 feature"] for row in rows) == Counter(dict.fromkeys(adapter_names, 1))
    assert all(all(row.values()) for row in rows)
    assert all(row["clock basis"] == "source_elapsed_ms" for row in rows)


def test_each_proposed_output_has_one_definition_and_one_mapping() -> None:
    mapping = inventory_table("P0 mapping")
    outputs = inventory_table("Proposed output inventory")
    proposed = [row["proposed v2 feature"] for row in outputs]
    mapped = [name for row in mapping for name in row["proposed v2 feature"].split(", ")]
    assert len(proposed) == len(set(proposed)) == 31
    assert Counter(proposed) == Counter(mapped)
    by_name = {row["proposed v2 feature"]: row for row in outputs}
    for row in mapping:
        for name in row["proposed v2 feature"].split(", "):
            assert by_name[name]["P0 feature"] == row["P0 feature"]
            assert by_name[name]["metric kind"] == row["metric kind"]


def test_gauge_mapping_preserves_raw_quantity_and_units() -> None:
    rows = {row["P0 feature"]: row for row in inventory_table("P0 mapping")}
    gauges = {
        name: ("browser_webrtc", column, unit)
        for name, (column, unit) in BROWSER_METRIC_COLUMNS.items()
        if name != "transport.packets_lost_delta"
    }
    gauges.update(ENGINE_METRIC_COLUMNS)
    assert len(gauges) == 15
    for name, (source, field, unit) in gauges.items():
        row = rows[name]
        assert row["raw source file/source kind"].endswith(f"/{source}")
        assert row["raw field(s)"] == field
        assert row["canonical unit"] == unit == P0_FEATURE_CONFIG[name].unit
        assert row["metric kind"] == "gauge"
        assert row["primary aggregation"] == "median"
        assert row["gap policy"] == "omit_missing_samples"
        assert row["reset policy"] == "none"
        assert row["proposed v2 feature"] == name.replace("_rss_mb", "_rss_mib")


def test_counters_use_raw_totals_and_distinct_rate_and_total_names() -> None:
    rows = {row["P0 feature"]: row for row in inventory_table("P0 mapping")}
    counters = {**STREAM_COUNTER_METRICS, **ENCODER_COUNTER_METRICS}
    counters["transport.packets_lost_delta"] = ("packets_lost_total", "packets")
    outputs = inventory_table("Proposed output inventory")
    assert len(counters) == 8
    for name, (field, unit) in counters.items():
        row = rows[name]
        assert row["raw field(s)"] == field
        assert row["metric kind"] == "cumulative_counter"
        assert row["gap policy"] == "break_counter_continuity"
        assert row["reset policy"] == "reject_segment"
        derived = [output for output in outputs if output["P0 feature"] == name]
        assert len(derived) == 2
        rate, total = sorted(derived, key=lambda output: output["primary aggregation"])
        assert rate["primary aggregation"] == "time_weighted_rate"
        assert rate["role"] == "analytical-shadow"
        assert "_rate_" in rate["proposed v2 feature"]
        assert total["primary aggregation"] == "window_total"
        assert total["role"] == "audit-only"
        assert "_window_total" in total["proposed v2 feature"]
        assert total["canonical unit"] == unit
        assert name not in {output["proposed v2 feature"] for output in derived}
    rate_units = {
        output["proposed v2 feature"]: output["canonical unit"]
        for output in outputs
        if output["primary aggregation"] == "time_weighted_rate"
    }
    assert rate_units == {
        "client.frames_decoded_rate_fps": "frames/s",
        "client.frames_dropped_rate_fps": "frames/s",
        "client.freeze_count_rate_per_min": "freezes/min",
        "client.freeze_duration_rate_ms_per_s": "ms/s",
        "encoder.frames_in_rate_fps": "frames/s",
        "encoder.frames_out_rate_fps": "frames/s",
        "encoder.frames_dropped_rate_fps": "frames/s",
        "transport.packets_lost_rate_per_s": "packets/s",
    }


def test_raw_fields_exist_in_sanitized_source_and_settings_stay_context() -> None:
    fixture = ROOT / "tests/data/pixelated_bundle/valid-v2"
    headers = {}
    for source, filename in (
        ("browser_webrtc", "stream-telemetry.csv"),
        ("engine_runtime", "engine-telemetry.csv"),
        ("encoder_pipeline", "engine-telemetry.csv"),
    ):
        with (fixture / filename).open(encoding="utf-8", newline="") as file:
            headers[source] = set(next(csv.reader(file)))
    outputs = inventory_table("Proposed output inventory")
    context = {row["raw field"] for row in inventory_table("Context-only fields")}
    assert {"target_fps", "target_bitrate_kbps", "cpu_used", "max_quantizer"} <= context
    for output in outputs:
        assert output["raw field"] in headers[output["source"]]
        assert output["raw field"] not in context
        assert {"captured_at", "elapsed_ms"} <= headers[output["source"]]
