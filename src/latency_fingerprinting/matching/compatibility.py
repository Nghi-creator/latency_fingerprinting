"""Fingerprint compatibility filtering for the P0 matcher."""

from __future__ import annotations

from ..fingerprints import FingerprintRepository
from ..models import CompatibilityResult, Fingerprint, ObservationRecord, ValidationStatus


def _add_rejection(rejected: dict[str, str], identifier: str, reason: str) -> None:
    if identifier in rejected:
        rejected[identifier] = f"{rejected[identifier]}; {reason}"
    else:
        rejected[identifier] = reason


def filter_compatible_fingerprints(
    query: ObservationRecord,
    repository: FingerprintRepository,
) -> tuple[tuple[Fingerprint, ...], CompatibilityResult, list[str]]:
    """Return compatible records, structured rejections, and repository warnings."""

    compatible: list[Fingerprint] = []
    rejected: dict[str, str] = {}
    warnings: list[str] = []
    for entry in sorted(repository.entries, key=lambda item: item.fingerprint.fingerprint_id):
        fingerprint = entry.fingerprint
        reasons: list[str] = []
        if fingerprint.contract_version != query.contract_version:
            reasons.append("contract version mismatch")
        if fingerprint.compatibility.compatibility_group != query.context.compatibility_group:
            reasons.append("compatibility group mismatch")
        if fingerprint.compatibility.probe_type != query.probe.probe_type:
            reasons.append("probe type mismatch")
        if fingerprint.validation_status is ValidationStatus.REJECTED:
            reasons.append("fingerprint validation status is rejected")
        if reasons:
            _add_rejection(
                rejected,
                fingerprint.fingerprint_id,
                ", ".join(reasons),
            )
        else:
            compatible.append(fingerprint)

    for rejection in repository.rejections:
        identifier = rejection.fingerprint_id or f"file:{rejection.path.name}"
        reason = f"repository {rejection.reason.value}: {rejection.message}"
        _add_rejection(rejected, identifier, reason)
        warnings.append(f"Rejected fingerprint source {rejection.path}: {reason}")

    compatible.sort(key=lambda fingerprint: fingerprint.fingerprint_id)
    return (
        tuple(compatible),
        CompatibilityResult(
            is_compatible=bool(compatible),
            compatibility_group=query.context.compatibility_group,
            compatible_fingerprint_ids=[fingerprint.fingerprint_id for fingerprint in compatible],
            rejected_fingerprints=rejected,
        ),
        warnings,
    )


__all__ = ["filter_compatible_fingerprints"]
