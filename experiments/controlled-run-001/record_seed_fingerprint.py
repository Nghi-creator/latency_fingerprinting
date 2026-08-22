#!/usr/bin/env python3
"""Build or verify the unvalidated controlled-real seed fingerprint."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from latency_fingerprinting.json_io import load_model_file
from latency_fingerprinting.models import (
    CompatibilityKey,
    Fingerprint,
    ObservationRecord,
    ProvenanceKind,
    ValidationStatus,
)
from latency_fingerprinting.pipeline import canonical_json

EXPERIMENT_ROOT = Path(__file__).resolve().parent
OBSERVATION_PATH = EXPERIMENT_ROOT / "observation.json"
FINGERPRINT_PATH = EXPERIMENT_ROOT / "fingerprint.json"
FINGERPRINT_CREATED_AT = datetime(2026, 8, 12, 4, 34, 51, tzinfo=UTC)
SOFTWARE_VERSION = "0.1.0"


def build_fingerprint() -> Fingerprint:
    observation = load_model_file(OBSERVATION_PATH, ObservationRecord)
    if observation.provenance is not ProvenanceKind.CONTROLLED_REAL:
        raise ValueError("the seed fingerprint requires controlled_real provenance")

    degraded = observation.degraded_window
    relief = observation.relief_window
    case_id = degraded.comparison_case_id
    if case_id is None or relief.comparison_case_id != case_id:
        raise ValueError("the source windows require one shared comparison case")
    if degraded.run_id != relief.run_id:
        raise ValueError("the source windows require one shared run ID")

    return Fingerprint(
        fingerprint_id="fingerprint-host_encoder_pressure-controlled-run-001-seed-v1",
        bottleneck_label="host_encoder_pressure",
        context=observation.context,
        compatibility=CompatibilityKey(
            compatibility_group=observation.context.compatibility_group,
            probe_type=observation.probe.probe_type,
        ),
        raw_response_delta=observation.response_delta,
        normalized_response=observation.normalized_response,
        feature_weights={feature: 1.0 for feature in observation.normalized_response.features},
        provenance=ProvenanceKind.CONTROLLED_REAL,
        source_case_ids=[case_id],
        source_window_ids=[degraded.window_id, relief.window_id],
        source_run_ids=[degraded.run_id],
        created_at=FINGERPRINT_CREATED_AT,
        software_version=SOFTWARE_VERSION,
        validation_status=ValidationStatus.UNVALIDATED,
        notes=[
            "Unvalidated controlled-real seed derived from one paired run; use only "
            "with independent held-out repeat runs.",
            "The host_encoder_pressure label records the bounded injected condition, "
            "not a matcher-inferred diagnosis.",
            "All measured response features use equal provisional weights of 1.0; "
            "the weights are not calibrated.",
            "The stream-profile relief is composite, so its response cannot be "
            "attributed to one changed control.",
            "Controlled run 001 must not be reused as its own query when evaluating "
            "this fingerprint.",
        ],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="verify fingerprint.json")
    mode.add_argument("--write", action="store_true", help="write fingerprint.json")
    args = parser.parse_args()

    try:
        rendered = canonical_json(build_fingerprint())
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.check:
        if not FINGERPRINT_PATH.is_file():
            print(f"missing seed fingerprint: {FINGERPRINT_PATH}", file=sys.stderr)
            return 1
        if FINGERPRINT_PATH.read_text(encoding="utf-8") != rendered:
            print("fingerprint.json is stale or the source observation changed", file=sys.stderr)
            return 1
        print("controlled-run-001 seed fingerprint is current")
        return 0
    if args.write:
        FINGERPRINT_PATH.write_text(rendered, encoding="utf-8")
        print(f"wrote {FINGERPRINT_PATH}")
        return 0

    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
