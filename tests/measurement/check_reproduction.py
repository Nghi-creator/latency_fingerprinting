"""Read-only CI reproduction of pinned N1 registry and sanitized shadow report."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from latency_fingerprinting.json_io import load_model_file
from latency_fingerprinting.measurement.metric_registry import (
    METRIC_REGISTRY_VERSION,
    metric_registry_drift,
    render_metric_registry,
)
from latency_fingerprinting.measurement_inspection import (
    inspect_measurements,
    render_measurement_inspection,
)
from latency_fingerprinting.models import ContextKey, WindowPhase

EXPECTED_REGISTRY_SHA256 = "50329d193303c271194b28e9164ae8627dd257d7620174c5ab136ba209864884"
EXPECTED_REPORT_SHA256 = "295f57a6f0e0ab80f64c7323be3cd5fc4e278aac712825f0173955594513c423"
FIXTURES = Path(__file__).resolve().parents[1] / "data/pixelated_bundle"


def check_reproduction() -> dict[str, str]:
    if metric_registry_drift():
        raise ValueError("canonical N1 registry artifact drift")
    registry_hash = hashlib.sha256(render_metric_registry().encode("utf-8")).hexdigest()
    if registry_hash != EXPECTED_REGISTRY_SHA256:
        raise ValueError("canonical N1 registry release pin mismatch")
    report = inspect_measurements(
        FIXTURES / "valid-v2",
        context=load_model_file(FIXTURES / "context-v2.json", ContextKey),
        phase=WindowPhase.DEGRADED,
        comparison_case_id="controlled-case-001",
    )
    report_hash = hashlib.sha256(render_measurement_inspection(report).encode("utf-8")).hexdigest()
    if report_hash != EXPECTED_REPORT_SHA256:
        raise ValueError("sanitized N1 shadow report reproduction mismatch")
    return {
        "status": "current",
        "registryVersion": METRIC_REGISTRY_VERSION,
        "registrySha256": registry_hash,
        "reportSha256": report_hash,
    }


def main() -> int:
    try:
        result = check_reproduction()
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
