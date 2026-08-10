"""Auditable normalization of finite raw response deltas."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from .models import NormalizedFeature, NormalizedResponse, ResponseDelta


class NormalizationError(ValueError):
    """Raised when a valid response cannot use the declared feature configuration."""


@dataclass(frozen=True, slots=True)
class FeatureNormalizationConfig:
    """Unit, numerical floor, and optional clipping for one feature."""

    unit: str
    epsilon: float
    clip_min: float | None = None
    clip_max: float | None = None

    def __post_init__(self) -> None:
        if not self.unit.strip():
            raise ValueError("normalization feature unit cannot be empty")
        if not math.isfinite(self.epsilon) or self.epsilon <= 0:
            raise ValueError("normalization epsilon must be finite and greater than zero")
        if self.clip_min is not None and not math.isfinite(self.clip_min):
            raise ValueError("clip_min must be finite when provided")
        if self.clip_max is not None and not math.isfinite(self.clip_max):
            raise ValueError("clip_max must be finite when provided")
        if (
            self.clip_min is not None
            and self.clip_max is not None
            and self.clip_min > self.clip_max
        ):
            raise ValueError("clip_min must not exceed clip_max")


P0_FEATURE_CONFIG: Mapping[str, FeatureNormalizationConfig] = {
    "client.available_incoming_bitrate_kbps": FeatureNormalizationConfig(unit="kbps", epsilon=1.0),
    "client.decode_time_mean_ms": FeatureNormalizationConfig(unit="ms", epsilon=0.1),
    "client.frames_decoded_delta": FeatureNormalizationConfig(unit="frames", epsilon=1.0),
    "client.frames_dropped_delta": FeatureNormalizationConfig(unit="frames", epsilon=1.0),
    "client.freeze_count_delta": FeatureNormalizationConfig(unit="freezes", epsilon=1.0),
    "client.freeze_duration_ms_delta": FeatureNormalizationConfig(unit="ms", epsilon=1.0),
    "client.jitter_buffer_delay_mean_ms": FeatureNormalizationConfig(unit="ms", epsilon=0.1),
    "client.received_fps": FeatureNormalizationConfig(unit="fps", epsilon=1.0),
    "client.received_bitrate_kbps": FeatureNormalizationConfig(unit="kbps", epsilon=1.0),
    "encoder.frames_dropped_delta": FeatureNormalizationConfig(unit="frames", epsilon=1.0),
    "encoder.frames_in_delta": FeatureNormalizationConfig(unit="frames", epsilon=1.0),
    "encoder.frames_out_delta": FeatureNormalizationConfig(unit="frames", epsilon=1.0),
    "encoder.pipeline_delay_proxy_ms": FeatureNormalizationConfig(unit="ms", epsilon=0.1),
    "encoder.queue_level_buffers": FeatureNormalizationConfig(unit="buffers", epsilon=1.0),
    "host.camera_cpu_percent": FeatureNormalizationConfig(unit="percent", epsilon=0.1),
    "host.camera_rss_mb": FeatureNormalizationConfig(unit="MiB", epsilon=1.0),
    "host.game_cpu_percent": FeatureNormalizationConfig(unit="percent", epsilon=0.1),
    "host.game_rss_mb": FeatureNormalizationConfig(unit="MiB", epsilon=1.0),
    "host.node_cpu_percent": FeatureNormalizationConfig(unit="percent", epsilon=0.1),
    "host.node_rss_mb": FeatureNormalizationConfig(unit="MiB", epsilon=1.0),
    "transport.jitter_ms": FeatureNormalizationConfig(unit="ms", epsilon=0.1),
    "transport.packets_lost_delta": FeatureNormalizationConfig(unit="packets", epsilon=1.0),
    "transport.round_trip_time_ms": FeatureNormalizationConfig(unit="ms", epsilon=0.1),
}


def _clip(value: float, config: FeatureNormalizationConfig) -> tuple[float, bool]:
    clipped = value
    if config.clip_min is not None:
        clipped = max(clipped, config.clip_min)
    if config.clip_max is not None:
        clipped = min(clipped, config.clip_max)
    return clipped, clipped != value


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
        denominator = max(abs(reference_value), config.epsilon)
        unclipped_value = raw_feature.raw_delta / denominator
        value, was_clipped = _clip(unclipped_value, config)
        normalized_features[feature] = NormalizedFeature(
            value=value,
            epsilon=config.epsilon,
            reference_value=reference_value,
            was_clipped=was_clipped,
            unclipped_value=unclipped_value if was_clipped else None,
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
