"""Explicit synthetic N3 software snapshots; never experiment/calibration evidence."""

from pathlib import Path

from latency_fingerprinting.analytical.fingerprints import create_fingerprint_v2
from latency_fingerprinting.analytical.matching import match_response_v2
from latency_fingerprinting.analytical.repository import FingerprintRepositoryV2
from latency_fingerprinting.pipeline import canonical_json
from tests.models.v2_cases import window_payload

from .cases import policy_payload
from .matching_cases import fingerprint, response

DEFAULT_FIXTURE_DIRECTORY = Path(__file__).parents[2] / "fixtures/analytical-v2"


def fixture_records():
    """Build fixed software records with no ambient timestamps or file writes."""
    query = response()
    names = sorted(policy_payload()["features"])
    partial = response(excluded=names[16:])
    invalid = response(confounded=True)
    references = {
        "matched": (fingerprint(label="synthetic_reference", normalized=-0.25),),
        "weak": (fingerprint(label="synthetic_weak", normalized=-0.3),),
        "ambiguous": (
            fingerprint(label="synthetic_a", normalized=-0.1),
            fingerprint(label="synthetic_b", normalized=-0.12),
        ),
        "unreviewed": (fingerprint(label="synthetic_audit", status="unreviewed"),),
    }

    def conflicting(pair):
        pair["relief_window"]["measurements"]["transport.jitter_ms"] = window_payload(
            phase="relief", values=(0, 24, 48)
        )["measurements"]["transport.jitter_ms"]

    references["conflicting"] = (fingerprint(label="synthetic_conflict", changes=conflicting),)
    records = {
        Path("policy.json"): query.policy,
        Path("inputs/observation.json"): query.observation,
        Path("responses/complete.json"): query,
        Path("responses/insufficient.json"): partial,
        Path("responses/confounded.json"): invalid,
    }
    for group, members in references.items():
        for index, reference in enumerate(members):
            name = "fingerprint.json" if len(members) == 1 else f"fingerprint-{index + 1}.json"
            records[Path("references") / group / name] = reference
    cases = {
        "matched": (query, references["matched"]),
        "invalid_response": (invalid, references["matched"]),
        "no_fingerprints": (query, ()),
        "no_compatible_fingerprints": (query, references["unreviewed"]),
        "insufficient_features": (partial, references["matched"]),
        "weak_match": (query, references["weak"]),
        "ambiguous_margin": (query, references["ambiguous"]),
        "conflicting_evidence": (query, references["conflicting"]),
    }
    for name, (query_response, members) in cases.items():
        records[Path("matches") / f"{name}.json"] = match_response_v2(
            query_response, query_response.policy, FingerprintRepositoryV2(members)
        )
    # A complete negative-response input can also reproduce the declared reference
    # through the public creation API; stored labels are never inferred by matching.
    reference = references["matched"][0]
    if (
        create_fingerprint_v2(reference.response, bottleneck_label="synthetic_reference")
        != reference
    ):
        raise ValueError("synthetic fingerprint creation drift")
    return records


def rendered_fixture_files():
    return {
        path: canonical_json(record).encode("utf-8")
        for path, record in sorted(fixture_records().items())
    }


def fixture_drift(directory=DEFAULT_FIXTURE_DIRECTORY):
    """Read-only exact-byte checks, including unexpected nested JSON files."""
    expected = rendered_fixture_files()
    result = {}
    for relative, content in expected.items():
        path = directory / relative
        if path.is_symlink():
            result[relative] = "unsafe_link"
        elif not path.is_file():
            result[relative] = "missing"
        elif path.read_bytes() != content:
            result[relative] = "changed"
    if directory.is_dir():
        for path in directory.rglob("*.json"):
            relative = path.relative_to(directory)
            if relative not in expected:
                result[relative] = "unexpected"
    return result
