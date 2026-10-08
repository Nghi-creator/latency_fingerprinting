"""Pure deterministic creation of declared v2 reference fingerprints."""

from ..models.analytical_response_v2 import AnalyticalResponseV2
from ..models.fingerprint_v2 import FingerprintV2, FingerprintValidationStatusV2
from .policy_release import payload_hash


def create_fingerprint_v2(
    response: AnalyticalResponseV2,
    *,
    bottleneck_label: str,
    validation_status: FingerprintValidationStatusV2 = "software_checked",
) -> FingerprintV2:
    """Retain valid response evidence with a caller-declared label and audit status."""
    response = AnalyticalResponseV2.model_validate(response)
    digest = payload_hash(
        {
            "response": response.model_dump(mode="json", by_alias=True),
            "bottleneckLabel": bottleneck_label,
            "validationStatus": validation_status,
        }
    )
    return FingerprintV2(
        schema_version="fingerprint-v2",
        contract_version="2.0.0",
        fingerprint_id="fingerprint-v2-" + digest[7:],
        bottleneck_label=bottleneck_label,
        provenance=response.observation.degraded_window.provenance,
        validation_status=validation_status,
        response=response,
        feature_vector={
            name: feature.normalized_value
            for name, feature in response.features.items()
            if feature.state == "eligible"
        },
    )
