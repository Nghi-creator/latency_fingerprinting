"""Independent abstract N10 lifecycle examples; no production adapter exists yet."""

import hashlib
import json
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[2] / "docs/live_probes/N10_DESIGN_VECTORS.json"
RAW = PATH.read_bytes()
VECTORS = json.loads(RAW)


def expectation(operands):
    # Test-only design oracle. It has no runtime, media, journal or core imports.
    dirty = operands["prior_dirty"]
    permitted = all(
        operands[key]
        for key in (
            "capability_qualified",
            "durable_intent",
            "exact_generation",
            "exclusive_owner",
            "limits_available",
        )
    )
    if dirty or not permitted or operands["cancelled_before_call"]:
        return dict(
            action="reject",
            restoration="unknown" if dirty else "not_needed",
            dirty=dirty,
            budget_consumed=False,
        )
    if operands["observed_value"] in {"foreign", "unknown", "new_generation"}:
        return dict(action="block_restore", restoration="unknown", dirty=True, budget_consumed=True)
    # Exceptions/interruptions never refund an attempted setter or erase intent.
    assert operands["application"] in {"returned", "raised", "interrupted", "unknown"}
    verified = all(
        operands[key] for key in ("restore_setting", "restore_output", "restore_receiver")
    )
    return dict(
        action="observe_prior" if operands["observed_value"] == "prior" else "apply_restore",
        restoration="verified" if verified else "unknown",
        dirty=not verified,
        budget_consumed=True,
    )


@pytest.mark.parametrize("case", VECTORS["cases"], ids=lambda case: case["case_id"])
def test_literal_lifecycle_expectations(case):
    assert expectation(VECTORS["defaults"] | case["overrides"]) == case["expected"]


def test_design_inventory_and_canonical_bytes():
    assert VECTORS["design_revision"] == "n10-live-evidence-design-v1"
    assert VECTORS["scope"] == "abstract_software_expectations_not_live_authority"
    assert len({case["case_id"] for case in VECTORS["cases"]}) == 20
    assert (json.dumps(VECTORS, indent=2, sort_keys=True) + "\n").encode() == RAW
    assert (
        hashlib.sha256(RAW).hexdigest()
        == "17a1dad270e6854393a9bbec7e16c24dd78b6ce8938166061eba86bdf60f10b7"
    )
