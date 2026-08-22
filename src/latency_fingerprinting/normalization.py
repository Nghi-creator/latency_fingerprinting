"""Auditable normalization of finite raw response deltas."""

from __future__ import annotations

from collections.abc import Mapping

from .feature_config import (
    P0_FEATURE_CONFIG,
    FeatureNormalizationConfig,
    normalize_feature_value,
)
from .models import NormalizedFeature, NormalizedResponse, ResponseDelta


class NormalizationError(ValueError):
    """Raised when a valid response cannot use the declared feature configuration."""


def normalize_response(
    response: ResponseDelta,
    *,
    feature_config: Mapping[str, FeatureNormalizationConfig] = P0_FEATURE_CONFIG,
) -> NormalizedResponse:
    """Normalize a response using its degraded aggregate as the reference.

    Invalid responses remain invalid and retain their evidence state. Missing
    configuration or unit disagreement is a configuration error rather than an
    analytical ``unknown`` outcome.
    """

    if not response.is_valid:
        return NormalizedResponse(
            features={},
            missing_features=list(response.missing_features),
            rejected_features=dict(response.rejected_features),
            is_valid=False,
            invalid_reasons=list(response.invalid_reasons),
            warnings=list(response.warnings),
        )

    normalized_features: dict[str, NormalizedFeature] = {}
    warnings = list(response.warnings)
    for feature in sorted(response.features):
        raw_feature = response.features[feature]
        config = feature_config.get(feature)
        if config is None:
            raise NormalizationError(
                f"feature {feature!r} has no declared normalization configuration"
            )
        if raw_feature.unit != config.unit:
            raise NormalizationError(
                f"feature {feature!r} uses unit {raw_feature.unit!r}; "
                f"normalization expects {config.unit!r}"
            )

        reference_value = raw_feature.degraded_value
        value, was_clipped, unclipped_value = normalize_feature_value(
            raw_feature.raw_delta,
            reference_value,
            config,
        )
        normalized_features[feature] = NormalizedFeature(
            value=value,
            epsilon=config.epsilon,
            reference_value=reference_value,
            was_clipped=was_clipped,
            unclipped_value=unclipped_value,
        )
        if was_clipped:
            warnings.append(
                f"normalized feature {feature!r} was clipped from "
                f"{unclipped_value:.12g} to {value:.12g}"
            )

    return NormalizedResponse(
        features=normalized_features,
        missing_features=list(response.missing_features),
        rejected_features=dict(response.rejected_features),
        is_valid=True,
        warnings=warnings,
    )


__all__ = [
    "P0_FEATURE_CONFIG",
    "FeatureNormalizationConfig",
    "NormalizationError",
    "normalize_response",
]
