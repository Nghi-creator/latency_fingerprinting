"""Read-only N2-to-N3 bridge; diagnostic labels and passive clocks stay unavailable."""

import hashlib
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from latency_fingerprinting.adapters.pixelated_source_local import ingest_pixelated_source_local
from latency_fingerprinting.analytical.policy_release import approved_policy_payload
from latency_fingerprinting.analytical.responses import derive_analytical_response
from latency_fingerprinting.json_io import MAX_CONTRACT_JSON_BYTES, strict_json_loads
from latency_fingerprinting.models import ContextKey, FeaturePolicyV1, ObservationRecordV2
from latency_fingerprinting.models.analytical_response_v2 import AnalyticalResponseV2

RELEASE = "n11-source-local-comparison-inputs-v1"
ROLES = ("degraded", "relief")
MAX_RAW_BYTES = 64 * 1024 * 1024
ERROR = "invalid_comparison_pair"


def _hash(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class ComparisonPairInspection:
    """Derived response plus byte custody, without a scientific acceptance claim."""

    observation_sha256: str
    raw_sha256: tuple[str, str]
    response: AnalyticalResponseV2

    def summary(self):
        features = self.response.features
        exclusions = {
            name: list(feature.exclusion_codes)
            for name, feature in features.items()
            if feature.state == "excluded"
        }
        return dict(
            method_release=RELEASE,
            observation_sha256=self.observation_sha256,
            raw_sha256=dict(zip(ROLES, self.raw_sha256, strict=True)),
            raw_windows_reproduced=2,
            response_id=self.response.response_id,
            response_policy_hash=self.response.policy.content_hash,
            feature_count=len(features),
            eligible_features=len(features) - len(exclusions),
            excluded_features=len(exclusions),
            feature_exclusions=exclusions,
            response_valid=self.response.is_valid,
            response_invalid_reasons=list(self.response.invalid_reason_codes),
            diagnostic_label=None,
            profile_prerequisites="unestablished_diagnostic_labels_and_independent_groups",
            passive_timing="unavailable_source_local_phase_windows",
            comparison_accuracy=None,
            empirical_acceptance=False,
            assurance="raw_reconstruction_not_label_context_or_execution_authentication",
        )


def inspect_comparison_pair(
    observation_bytes: bytes,
    raw_bundles: Mapping[str, bytes],
    *,
    expected_raw_sha256: Mapping[str, str],
):
    """Reproduce both source-local windows and derive the unchanged approved N3 response.

    Callers supply original observation JSON bytes and exactly two original TAR
    byte strings with separately pinned original TAR hashes. The N2 bundle
    content hash is distinct from a TAR file hash. Only capture method 1.2.0 is
    supported here. No paths, condition
    names, candidate coordinates, fitting values or predictions are accepted as
    replacements. Context and intervention declarations remain external evidence;
    matching their re-adoption does not authenticate those declarations.
    """
    try:
        if (
            type(observation_bytes) is not bytes
            or not 0 < len(observation_bytes) <= MAX_CONTRACT_JSON_BYTES
            or not isinstance(raw_bundles, Mapping)
            or set(raw_bundles) != set(ROLES)
            or not isinstance(expected_raw_sha256, Mapping)
            or set(expected_raw_sha256) != set(ROLES)
        ):
            raise ValueError(ERROR)
        bundles = tuple(raw_bundles[role] for role in ROLES)
        if any(type(raw) is not bytes or not 0 < len(raw) <= MAX_RAW_BYTES for raw in bundles):
            raise ValueError(ERROR)
        if any(
            _hash(raw) != expected_raw_sha256[role]
            for role, raw in zip(ROLES, bundles, strict=True)
        ):
            raise ValueError(ERROR)
        pair = ObservationRecordV2.model_validate(
            strict_json_loads(observation_bytes.decode("utf-8"))
        )
        with tempfile.TemporaryDirectory(prefix="n11-comparison-") as directory:
            for role, raw in zip(ROLES, bundles, strict=True):
                window = getattr(pair, role + "_window")
                if window.capture_method.method_version != "1.2.0":
                    raise ValueError(ERROR)
                path = Path(directory).resolve() / (role + ".tar")
                path.write_bytes(raw)
                rebuilt = ingest_pixelated_source_local(
                    path,
                    context=ContextKey.model_validate(window.context.model_dump(mode="json")),
                    phase=window.phase,
                    comparison_case_id=window.comparison_case_id,
                    provenance=window.provenance,
                    confounder_codes=window.confounder_codes,
                )
                if rebuilt != window:
                    raise ValueError(ERROR)
        policy = FeaturePolicyV1.model_validate(approved_policy_payload())
        response = derive_analytical_response(pair, policy)
        return ComparisonPairInspection(
            _hash(observation_bytes), tuple(map(_hash, bundles)), response
        )
    except (ValueError, TypeError, KeyError, OSError):
        raise ValueError(ERROR) from None
