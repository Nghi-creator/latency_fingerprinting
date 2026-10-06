"""Small synthetic inputs for N2 contract tests; not production adopted records."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from latency_fingerprinting.measurement.aggregation import aggregate_counter, aggregate_gauge
from latency_fingerprinting.measurement.metric_registry import CANONICAL_METRIC_REGISTRY
from latency_fingerprinting.models import MeasurementSample, MetricKind, MetricSource
from latency_fingerprinting.models.v2_common import REGISTRY_CONTENT_HASH


def window_payload(*, phase="degraded", real=False, duration=2000, values=(0, 60, 120)):
    context = json.loads(
        (Path(__file__).parents[1] / "data/pixelated_bundle/context-v2.json").read_text()
    )
    rows = tuple(
        MeasurementSample(
            elapsed_ms=i * duration / 2,
            captured_at=datetime(2026, 10, 6, tzinfo=UTC) + timedelta(seconds=i),
            value=value,
            available=True,
            source_row=i + 2,
            missing_reason="missing" if value is None else None,
        )
        for i, value in enumerate(values)
    )
    measurements = {}
    for definition in CANONICAL_METRIC_REGISTRY.definitions:
        aggregate = aggregate_gauge if definition.kind is MetricKind.GAUGE else aggregate_counter
        summary = aggregate(
            definition,
            rows,
            window_start_ms=0,
            window_end_ms=duration,
            registry_version=CANONICAL_METRIC_REGISTRY.registry_version,
        ).model_dump()
        for field, safe in [
            ("missing_reasons", "Missing source evidence."),
            ("rejected_reasons", "Rejected source evidence."),
            ("warnings", "Measurement provenance requires review."),
        ]:
            summary[field] = (safe,) if summary[field] else ()
        measurements[definition.name] = {
            "role": "audit_only"
            if definition.primary_aggregation == "window_total"
            else "analytical_candidate",
            "support": {"state": "supported", "declared_state": None, "basis": "source_rows"},
            "summary": summary,
        }
    return {
        "schema_version": "observation-window-v2",
        "contract_version": "2.0.0",
        "run_id": f"run-{phase}",
        "window_id": f"window-{phase}",
        "comparison_case_id": "case-001",
        "context": context,
        "phase": phase,
        "provenance": "controlled_real" if real else "synthetic",
        "registry": {
            "registry_version": "latency-metrics-v2.0.0",
            "content_hash": REGISTRY_CONTENT_HASH,
        },
        "capture_method": {
            "method_id": "pixelated_bundle_offline" if real else "synthetic_series",
            "method_version": "1.0.0",
            "producer_version": None,
        },
        "clock": {
            "basis": "source_elapsed_ms",
            "provenance": "wall_clock_derived_elapsed" if real else "synthetic_elapsed",
            "domain_id": f"domain-{phase}",
            "elapsed_start_ms": 0,
            "elapsed_end_ms": duration,
            "duration_ms": duration,
            "started_at": "2026-10-06T00:00:00Z" if real else None,
            "ended_at": (
                datetime(2026, 10, 6, tzinfo=UTC) + timedelta(milliseconds=duration)
            ).isoformat()
            if real
            else None,
        },
        "source_artifact": {
            "source_type": "pixelated_bundle" if real else "synthetic_series",
            "content_hash": "sha256:" + "0" * 64,
            "bundle_schema_version": "2" if real else None,
        },
        "sources": {
            source.value: {
                "state": "supported",
                "declared_state": None,
                "basis": "source_rows",
                "source_file": (
                    "stream-telemetry.csv"
                    if source is MetricSource.BROWSER_WEBRTC
                    else "engine-telemetry.csv"
                )
                if real
                else None,
                "row_count": 3,
                "available_row_count": 3,
            }
            for source in MetricSource
        },
        "effective_settings": {"targetFps": 30 if phase == "relief" else 60},
        "measurements": measurements,
        "validity": {"is_valid": True, "reason_codes": []},
    }


def pair_payload(*, real=False):
    return {
        "schema_version": "observation-v2",
        "contract_version": "2.0.0",
        "observation_id": "observation-001",
        "comparison_case_id": "case-001",
        "degraded_window": window_payload(real=real),
        "relief_window": window_payload(phase="relief", real=real),
        "intervention": {
            "probe_id": "probe-001",
            "probe_type": "stream_profile_relief",
            "probe_version": "1.0.0",
            "requested_settings": {"targetFps": 30},
            "observed_settings": {"targetFps": 30} if real else None,
            "intensity": 1,
            "application_method": "paired_run" if real else "simulated_pair",
            "execution_status": "executed" if real else "not_executed",
            "restoration_status": "unknown" if real else "not_executed",
            "degraded_window_id": "window-degraded",
            "relief_window_id": "window-relief",
            "paired_window_order": ["degraded", "relief"],
        },
    }


def timing_payload(**changes):
    return {
        "stage": "encode",
        "state": "unavailable",
        "source": "encoder_pipeline",
        "method_id": None,
        "method_version": None,
        "clock_domain_id": None,
        "unit": "ms",
        "statistic": None,
        "value": None,
        "sample_count": 0,
        "reason_code": "not_instrumented",
        **changes,
    }
