"""Actual producer composer/archive boundary, with artificial telemetry only."""

from pathlib import Path

from latency_fingerprinting.adapters import ingest_pixelated_windows
from latency_fingerprinting.models import ContextKey

ROOT = Path(__file__).resolve().parents[2]


def check_producer_bundle(bundle, *, full_sample_export=False):
    context = ContextKey.model_validate_json(
        (ROOT / "tests/data/pixelated_bundle/context-v2.json").read_bytes()
    )
    windows = ingest_pixelated_windows(
        Path(bundle).resolve(),
        context=context,
        phase="degraded",
        comparison_case_id="controlled-case-001",
        windows=[dict(start_ms=0, end_ms=5000), dict(start_ms=5000, end_ms=10000)],
    )
    reference = ingest_pixelated_windows(
        ROOT / "tests/data/pixelated_bundle/valid-v2",
        context=context,
        phase="degraded",
        comparison_case_id="controlled-case-001",
        windows=[dict(start_ms=0, end_ms=5000), dict(start_ms=5000, end_ms=10000)],
    )
    for index, (actual, expected) in enumerate(zip(windows, reference, strict=True)):
        if actual.sources != expected.sources:
            raise ValueError("producer measurement/support drift")
        for name, measurement in actual.measurements.items():
            original = expected.measurements[name]
            if full_sample_export:
                # Full export derives explicit per-metric declarations instead
                # of the composer's sparse fixture declarations. Preserve both
                # their provenance and the unchanged measurement arithmetic.
                if measurement.summary != original.summary:
                    raise ValueError("producer sample aggregation drift")
                if measurement.support.state != original.support.state:
                    raise ValueError("producer sample availability drift")
                basis = (
                    "source_support"
                    if name
                    in ("transport.packets_lost_rate_per_s", "transport.packets_lost_window_total")
                    else "measurement_declaration"
                )
                if measurement.support.basis != basis:
                    raise ValueError("producer explicit support declaration missing")
            elif measurement != original:
                raise ValueError("producer measurement/support drift")
        fps = actual.measurements["client.received_fps"].summary.value
        decoded = actual.measurements["client.frames_decoded_rate_fps"].summary
        if fps != (52, 56)[index] or decoded.value != 60 or decoded.observed_duration_ms != 5000:
            raise ValueError("producer independent interval expectation failed")
        if decoded.counter_intervals[0].delta != 300:
            raise ValueError("producer counter delta drift")
    if windows[0].source_artifact != windows[1].source_artifact:
        raise ValueError("producer windows lost their shared source")
    if windows[0].clock.domain_id != windows[1].clock.domain_id:
        raise ValueError("producer windows lost their shared clock")
    return windows


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--full-sample-export", action="store_true")
    args = parser.parse_args()
    check_producer_bundle(args.bundle, full_sample_export=args.full_sample_export)
    print("Producer composer/TAR interoperability passed; artificial telemetry only.")
