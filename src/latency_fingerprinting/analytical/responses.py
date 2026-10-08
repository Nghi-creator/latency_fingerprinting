"""Pure response derivation from revalidated N2 evidence and an explicit N3 policy."""

import math

from ..models.analytical_response_v2 import (
    AnalyticalResponseV2,
    FeatureResponseV2,
    _window_evidence,
    _window_exclusion,
)
from ..models.feature_policy import FeaturePolicyV1
from ..models.observation_pair_v2 import ObservationRecordV2
from .policy_release import payload_hash


def derive_analytical_response(
    observation: ObservationRecordV2, policy: FeaturePolicyV1
) -> AnalyticalResponseV2:
    """Return an immutable auditable response; invalid evidence retains exclusions.

    Both arguments are revalidated, including copied model instances. Arithmetic
    outside the finite range fails explicitly. No input is mutated and no files,
    timestamps or ambient identifiers are read or written.
    """
    observation = ObservationRecordV2.model_validate(observation)
    policy = FeaturePolicyV1.model_validate(policy)
    confounded = bool(
        observation.degraded_window.confounder_codes
        or observation.relief_window.confounder_codes
        or observation.intervention.confounder_codes
    )
    features = {}
    for name, parameter in policy.features.items():
        degraded = _window_evidence(observation.degraded_window, name)
        relief = _window_evidence(observation.relief_window, name)
        exclusions = (
            ("confounded_pair",)
            if confounded
            else tuple(
                code
                for code in (
                    _window_exclusion(degraded, parameter, "degraded"),
                    _window_exclusion(relief, parameter, "relief"),
                )
                if code is not None
            )
        )
        delta = reference = denominator = normalized = None
        if not exclusions:
            reference = degraded.primary_value
            delta = relief.primary_value - reference
            denominator = max(abs(reference), parameter.epsilon)
            normalized = delta / denominator
            if not all(math.isfinite(value) for value in (delta, denominator, normalized)):
                raise ValueError("analytical response exceeds the finite numeric range")
        features[name] = FeatureResponseV2(
            unit=parameter.unit,
            aggregation=parameter.aggregation,
            state="excluded" if exclusions else "eligible",
            degraded=degraded,
            relief=relief,
            exclusion_codes=exclusions,
            raw_delta=delta,
            reference_value=reference,
            denominator=denominator,
            normalized_value=normalized,
            was_clipped=False,
            unclipped_value=None,
        )
    reasons = (
        ("confounded_pair",)
        if confounded
        else (
            ("no_eligible_features",)
            if all(feature.state == "excluded" for feature in features.values())
            else ()
        )
    )
    digest = payload_hash(
        {
            "observation": observation.model_dump(mode="json", by_alias=True),
            "policy": policy.model_dump(mode="json", by_alias=True),
        }
    )
    return AnalyticalResponseV2(
        schema_version="analytical-response-v2",
        contract_version="2.0.0",
        response_id="response-v2-" + digest[7:],
        observation=observation,
        policy=policy,
        features=features,
        is_valid=not reasons,
        invalid_reason_codes=reasons,
    )
